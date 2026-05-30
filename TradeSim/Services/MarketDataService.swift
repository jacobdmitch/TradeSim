import Foundation

/// Errors surfaced by the market data layer.
enum MarketDataError: LocalizedError {
    case badURL
    case badResponse(Int)
    case decoding

    var errorDescription: String? {
        switch self {
        case .badURL: return "Could not build the request URL."
        case .badResponse(let code): return "Server returned status \(code)."
        case .decoding: return "Could not read the market data response."
        }
    }
}

/// Pulls live spot prices, the full product list, bulk 24h stats and
/// historical candles from Coinbase's public (no-auth) endpoints.
struct MarketDataService {
    /// Quote currencies we trade against (rotation routes through USD).
    static let quoteCurrency = "USD"

    /// Bases excluded as rotation targets because they don't move meaningfully.
    static let stablecoins: Set<String> = [
        "USDC", "USDT", "DAI", "PYUSD", "GUSD", "USDB", "PAX", "USDP",
        "EURC", "USD", "EUR", "GBP", "TUSD", "BUSD", "USTC", "RLUSD"
    ]

    private let session: URLSession = {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 20
        config.waitsForConnectivity = true
        return URLSession(configuration: config)
    }()

    init() {}

    // MARK: - Spot price

    private struct SpotResponse: Decodable {
        struct DataField: Decodable { let amount: String }
        let data: DataField
    }

    /// Current spot price (USD) for a product id like "DIMO-USD".
    func fetchSpotPrice(productID: String) async throws -> Quote {
        guard let url = URL(string: "https://api.coinbase.com/v2/prices/\(productID)/spot") else {
            throw MarketDataError.badURL
        }
        let (data, response) = try await session.data(from: url)
        try Self.validate(response)
        guard
            let decoded = try? JSONDecoder().decode(SpotResponse.self, from: data),
            let price = Double(decoded.data.amount)
        else { throw MarketDataError.decoding }
        return Quote(price: price, timestamp: Date())
    }

    // MARK: - Product universe

    private struct ProductDTO: Decodable {
        let id: String
        let base_currency: String
        let quote_currency: String
        let status: String
        let trading_disabled: Bool?
    }

    /// All online, tradable USD products (stablecoins filtered out).
    func fetchUSDProducts() async throws -> [Product] {
        guard let url = URL(string: "https://api.exchange.coinbase.com/products") else {
            throw MarketDataError.badURL
        }
        var request = URLRequest(url: url)
        request.setValue("TradeSim/1.0", forHTTPHeaderField: "User-Agent")
        let (data, response) = try await session.data(for: request)
        try Self.validate(response)
        guard let dtos = try? JSONDecoder().decode([ProductDTO].self, from: data) else {
            throw MarketDataError.decoding
        }
        return dtos.compactMap { dto in
            guard dto.quote_currency == Self.quoteCurrency,
                  dto.status == "online",
                  dto.trading_disabled != true,
                  !Self.stablecoins.contains(dto.base_currency)
            else { return nil }
            return Product(
                id: dto.id,
                base: dto.base_currency,
                quote: dto.quote_currency,
                status: dto.status,
                tradingDisabled: dto.trading_disabled ?? false
            )
        }
    }

    // MARK: - Bulk 24h stats

    private struct StatsDTO: Decodable {
        struct Window: Decodable {
            let open: String?
            let high: String?
            let low: String?
            let last: String?
            let volume: String?
        }
        let stats_24hour: Window?
    }

    /// 24h stats for every product, keyed by product id, in a single request.
    /// Returns only entries for the supplied `products`.
    func fetchStats(for products: [Product]) async throws -> [MarketStat] {
        guard let url = URL(string: "https://api.exchange.coinbase.com/products/stats") else {
            throw MarketDataError.badURL
        }
        var request = URLRequest(url: url)
        request.setValue("TradeSim/1.0", forHTTPHeaderField: "User-Agent")
        let (data, response) = try await session.data(for: request)
        try Self.validate(response)
        guard let raw = try? JSONDecoder().decode([String: StatsDTO].self, from: data) else {
            throw MarketDataError.decoding
        }
        let byBase = Dictionary(uniqueKeysWithValues: products.map { ($0.id, $0.base) })
        return raw.compactMap { (productID, dto) -> MarketStat? in
            guard let base = byBase[productID],
                  let w = dto.stats_24hour,
                  let last = w.last.flatMap(Double.init), last > 0
            else { return nil }
            return MarketStat(
                productID: productID,
                base: base,
                open: w.open.flatMap(Double.init) ?? last,
                high: w.high.flatMap(Double.init) ?? last,
                low: w.low.flatMap(Double.init) ?? last,
                last: last,
                volume: w.volume.flatMap(Double.init) ?? 0
            )
        }
    }

    // MARK: - Historical candles

    /// Recent candles for a product, returned oldest-first.
    func fetchCandles(productID: String, granularity: Granularity) async throws -> [Candle] {
        guard let url = URL(string: "https://api.exchange.coinbase.com/products/\(productID)/candles?granularity=\(granularity.rawValue)") else {
            throw MarketDataError.badURL
        }
        var request = URLRequest(url: url)
        request.setValue("TradeSim/1.0", forHTTPHeaderField: "User-Agent")
        let (data, response) = try await session.data(for: request)
        try Self.validate(response)
        guard let rows = try? JSONSerialization.jsonObject(with: data) as? [[Double]] else {
            throw MarketDataError.decoding
        }
        let candles: [Candle] = rows.compactMap { row in
            guard row.count >= 6 else { return nil }
            // Coinbase order: [ time, low, high, open, close, volume ]
            return Candle(time: Date(timeIntervalSince1970: row[0]),
                          low: row[1], high: row[2], open: row[3],
                          close: row[4], volume: row[5])
        }
        return candles.sorted { $0.time < $1.time }
    }

    /// Fetches candles for many products concurrently (bounded fan-out).
    func fetchCandles(productIDs: [String], granularity: Granularity) async -> [String: [Candle]] {
        await withTaskGroup(of: (String, [Candle]?).self) { group in
            for id in productIDs {
                group.addTask {
                    let candles = try? await fetchCandles(productID: id, granularity: granularity)
                    return (id, candles)
                }
            }
            var result: [String: [Candle]] = [:]
            for await (id, candles) in group {
                if let candles { result[id] = candles }
            }
            return result
        }
    }

    private static func validate(_ response: URLResponse) throws {
        guard let http = response as? HTTPURLResponse else { return }
        guard (200...299).contains(http.statusCode) else {
            throw MarketDataError.badResponse(http.statusCode)
        }
    }
}
