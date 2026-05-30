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

/// Pulls live spot prices and historical candles from Coinbase's public
/// (no-auth) endpoints. The product id defaults to DIMO-USD.
struct MarketDataService {
    var productID: String

    private let session: URLSession = {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 20
        config.waitsForConnectivity = true
        return URLSession(configuration: config)
    }()

    init(productID: String = "DIMO-USD") {
        self.productID = productID
    }

    // MARK: - Spot price

    private struct SpotResponse: Decodable {
        struct DataField: Decodable { let amount: String }
        let data: DataField
    }

    /// Fetches the current spot price (USD) for the product.
    func fetchSpotPrice() async throws -> Quote {
        // e.g. https://api.coinbase.com/v2/prices/DIMO-USD/spot
        guard let url = URL(string: "https://api.coinbase.com/v2/prices/\(productID)/spot") else {
            throw MarketDataError.badURL
        }
        let (data, response) = try await session.data(from: url)
        try Self.validate(response)
        do {
            let decoded = try JSONDecoder().decode(SpotResponse.self, from: data)
            guard let price = Double(decoded.data.amount) else { throw MarketDataError.decoding }
            return Quote(price: price, timestamp: Date())
        } catch {
            throw MarketDataError.decoding
        }
    }

    // MARK: - Historical candles

    /// Fetches recent candles for the given granularity, returned oldest-first.
    func fetchCandles(granularity: Granularity) async throws -> [Candle] {
        // Coinbase Exchange returns [ time, low, high, open, close, volume ], newest-first.
        guard let url = URL(string: "https://api.exchange.coinbase.com/products/\(productID)/candles?granularity=\(granularity.rawValue)") else {
            throw MarketDataError.badURL
        }
        var request = URLRequest(url: url)
        // Coinbase Exchange requires a User-Agent on some edge nodes.
        request.setValue("TradeSim/1.0", forHTTPHeaderField: "User-Agent")

        let (data, response) = try await session.data(for: request)
        try Self.validate(response)

        guard let rows = try? JSONSerialization.jsonObject(with: data) as? [[Double]] else {
            throw MarketDataError.decoding
        }
        let candles: [Candle] = rows.compactMap { row in
            guard row.count >= 6 else { return nil }
            return Candle(
                time: Date(timeIntervalSince1970: row[0]),
                low: row[1],
                high: row[2],
                open: row[3],
                close: row[4],
                volume: row[5]
            )
        }
        return candles.sorted { $0.time < $1.time }
    }

    private static func validate(_ response: URLResponse) throws {
        guard let http = response as? HTTPURLResponse else { return }
        guard (200...299).contains(http.statusCode) else {
            throw MarketDataError.badResponse(http.statusCode)
        }
    }
}
