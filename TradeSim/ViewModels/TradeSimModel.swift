import Foundation
import SwiftUI
import Observation

/// Central observable model. Owns the market universe, the live scan, the
/// predictive scores, the rotation recommendation and the paper portfolio.
@MainActor
@Observable
final class TradeSimModel {
    // MARK: - Seed (your real-world starting point)
    let seedBase = "DIMO"
    let seedProductID = "DIMO-USD"

    // MARK: - Configuration
    var granularity: Granularity = .oneHour
    var strategy = StrategyConfig.default { didSet { persist() } }
    var rotation = RotationConfig.default { didSet { persist() } }
    /// How often (seconds) to rescan the market while in the foreground.
    var refreshInterval: TimeInterval = 120
    /// Minimum 24h USD volume for a coin to be considered a rotation candidate.
    var minLiquidityUSD: Double = 25_000

    // MARK: - Live state
    var products: [Product] = []
    var stats: [MarketStat] = []          // latest market-wide scan
    var scores: [CoinScore] = []          // ranked rotation candidates
    var holdingCandles: [Candle] = []     // candles for the current holding
    var trades: [SimulatedTrade] = []
    var recommendations: [RotationRecommendation] = []

    var portfolio: Portfolio
    private(set) var startingBalance: Double
    private var seeded = false

    var isScanning = false
    var lastError: String?
    var lastUpdated: Date?

    // MARK: - Dependencies
    private let market = MarketDataService()
    private let simulator = Simulator()
    private var pollTask: Task<Void, Never>?
    private let store = PersistenceStore()

    // MARK: - Init
    init(startingBalance: Double = 23.17) {
        let saved = PersistenceStore().load()
        self.startingBalance = saved?.startingBalance ?? startingBalance
        self.portfolio = saved?.portfolio ?? Portfolio(cash: startingBalance, position: nil)
        self.seeded = saved?.seeded ?? false
        self.trades = saved?.trades ?? []
        self.recommendations = saved?.recommendations ?? []
        if let s = saved?.strategy { self.strategy = s }
        if let r = saved?.rotation { self.rotation = r }
    }

    // MARK: - Derived
    var latestRecommendation: RotationRecommendation? { recommendations.first }
    var totalReturn: Double { portfolio.totalValue - startingBalance }
    var totalReturnPct: Double { startingBalance > 0 ? totalReturn / startingBalance * 100 : 0 }
    var realizedPnL: Double { trades.compactMap(\.realizedPnL).reduce(0, +) }

    /// Stats sorted for the Markets tab (top gainers first).
    var gainers: [MarketStat] { stats.sorted { $0.changePct > $1.changePct } }

    func stat(forBase base: String) -> MarketStat? { stats.first { $0.base == base } }

    // MARK: - Lifecycle
    func start() {
        guard pollTask == nil else { return }
        pollTask = Task { [weak self] in
            await self?.scan()
            while !Task.isCancelled {
                let interval = self?.refreshInterval ?? 120
                try? await Task.sleep(for: .seconds(interval))
                if Task.isCancelled { break }
                await self?.scan()
            }
        }
    }

    func stop() {
        pollTask?.cancel()
        pollTask = nil
    }

    /// Alias used by the app lifecycle hooks.
    func refresh() async { await scan() }

    /// On-demand candles for a single product (used by the coin detail screen).
    func fetchCandles(for productID: String) async -> [Candle] {
        (try? await market.fetchCandles(productID: productID, granularity: granularity)) ?? []
    }

    /// Predictive score for a base symbol, if it was analyzed in the last scan.
    func score(forBase base: String) -> CoinScore? { scores.first { $0.base == base } }

    // MARK: - Market scan pipeline
    func scan() async {
        guard !isScanning else { return }
        isScanning = true
        defer { isScanning = false }

        do {
            if products.isEmpty {
                products = try await market.fetchUSDProducts()
            }
            let freshStats = try await market.fetchStats(for: products)
            guard !freshStats.isEmpty else { throw MarketDataError.decoding }
            stats = freshStats

            markPosition()
            seedIfNeeded()

            // Pick candidates, then deep-analyze just those with candles.
            let candidates = selectCandidates()
            let candleMap = await market.fetchCandles(productIDs: candidates.map(\.productID),
                                                      granularity: granularity)
            let predictor = Predictor(strategy: strategy, config: rotation)
            let scored: [CoinScore] = candidates.compactMap { stat in
                guard let closes = candleMap[stat.productID]?.map(\.close),
                      closes.count > strategy.longSMA + 1 else { return nil }
                return predictor.score(stat: stat, closes: closes)
            }
            scores = predictor.rank(scored)

            if let pos = portfolio.position, let candles = candleMap[pos.productID] {
                holdingCandles = candles
            }

            let rec = predictor.recommend(ranked: scores, portfolio: portfolio, feeRate: 0.006)
            register(rec)

            lastUpdated = Date()
            lastError = nil
            persist()
        } catch {
            lastError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }

    private func markPosition() {
        guard var pos = portfolio.position,
              let s = stats.first(where: { $0.base == pos.base }) else { return }
        pos.markPrice = s.last
        portfolio.position = pos
    }

    private func seedIfNeeded() {
        guard !seeded else { return }
        guard let dimo = stats.first(where: { $0.base == seedBase }) else { return }
        simulator.seedHolding(base: seedBase, productID: dimo.productID,
                              usdValue: startingBalance, price: dimo.last, portfolio: &portfolio)
        seeded = true
    }

    /// Liquid top movers plus the current holding and DIMO, capped at the
    /// configured candidate count.
    private func selectCandidates() -> [MarketStat] {
        let liquid = stats.filter { $0.volumeUSD >= minLiquidityUSD }
        var picked = Array(liquid.sorted { $0.changePct > $1.changePct }.prefix(rotation.candidateCount))
        for base in [portfolio.position?.base, seedBase].compactMap({ $0 }) {
            if !picked.contains(where: { $0.base == base }),
               let s = stats.first(where: { $0.base == base }) {
                picked.append(s)
            }
        }
        return picked
    }

    // MARK: - Recommendations & execution
    private func register(_ rec: RotationRecommendation) {
        // Only act/notify on a genuine change of recommendation.
        if let last = recommendations.first,
           last.action == rec.action, last.fromBase == rec.fromBase, last.toBase == rec.toBase {
            return
        }
        recommendations.insert(rec, at: 0)
        if recommendations.count > 100 { recommendations.removeLast(recommendations.count - 100) }

        if rec.action != .hold {
            NotificationManager.shared.notify(for: rec)
            if rotation.autoRotate { execute(rec) }
        }
    }

    /// Applies a recommendation to the paper portfolio.
    func execute(_ rec: RotationRecommendation) {
        switch rec.action {
        case .enter:
            if let toBase = rec.toBase, let s = stat(forBase: toBase),
               let t = simulator.enter(base: toBase, productID: s.productID, price: s.last, portfolio: &portfolio) {
                trades.insert(t, at: 0)
            }
        case .exit:
            if let pos = portfolio.position, let s = stat(forBase: pos.base),
               let t = simulator.exit(price: s.last, portfolio: &portfolio) {
                trades.insert(t, at: 0)
            }
        case .rotate:
            if let pos = portfolio.position, let toBase = rec.toBase, pos.base != toBase,
               let sell = stat(forBase: pos.base), let buy = stat(forBase: toBase) {
                let legs = simulator.rotate(toBase: toBase, toProductID: buy.productID,
                                            sellPrice: sell.last, buyPrice: buy.last, portfolio: &portfolio)
                for t in legs.reversed() { trades.insert(t, at: 0) }
            }
        case .hold:
            break
        }
        persist()
    }

    /// Applies the latest recommendation (used by the "Apply" button).
    func applyLatestRecommendation() {
        if let rec = latestRecommendation { execute(rec) }
    }

    // MARK: - Manual control (from the Markets list / coin detail)
    /// Buys `base` if in cash, or rotates into it from another coin.
    func manualBuy(base: String) {
        guard let target = stat(forBase: base) else { return }
        if portfolio.position == nil {
            if let t = simulator.enter(base: base, productID: target.productID, price: target.last, portfolio: &portfolio) {
                trades.insert(t, at: 0)
            }
        } else if portfolio.position?.base != base {
            guard let pos = portfolio.position, let sell = stat(forBase: pos.base) else { return }
            let legs = simulator.rotate(toBase: base, toProductID: target.productID,
                                        sellPrice: sell.last, buyPrice: target.last, portfolio: &portfolio)
            for t in legs.reversed() { trades.insert(t, at: 0) }
        }
        persist()
    }

    /// Liquidates the current position back to cash.
    func moveToCash() {
        guard let pos = portfolio.position, let s = stat(forBase: pos.base),
              let t = simulator.exit(price: s.last, portfolio: &portfolio) else { return }
        trades.insert(t, at: 0)
        persist()
    }

    /// Resets the whole simulation to a fresh DIMO holding worth `balance`.
    func resetSimulation(to balance: Double) {
        startingBalance = balance
        portfolio = Portfolio(cash: balance, position: nil)
        seeded = false
        trades.removeAll()
        recommendations.removeAll()
        persist()
        Task { await scan() }
    }

    // MARK: - Persistence
    private func persist() {
        store.save(.init(
            startingBalance: startingBalance,
            portfolio: portfolio,
            seeded: seeded,
            trades: Array(trades.prefix(200)),
            recommendations: Array(recommendations.prefix(50)),
            strategy: strategy,
            rotation: rotation
        ))
    }
}
