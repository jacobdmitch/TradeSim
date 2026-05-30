import Foundation
import SwiftUI
import Observation

/// Central observable model. Owns the market data, the running paper portfolio,
/// the alert history and the polling loop that drives live updates.
@MainActor
@Observable
final class TradeSimModel {
    // MARK: - Configuration
    let symbol = "DIMO"
    var productID = "DIMO-USD"
    var granularity: Granularity = .oneHour
    var strategy = StrategyConfig.default {
        didSet { persistConfig() }
    }
    /// How often (seconds) to poll for fresh data while in the foreground.
    var refreshInterval: TimeInterval = 60
    /// When true, actionable alerts are auto-applied to the paper portfolio.
    var autoTradeSimulation = true {
        didSet { persist() }
    }

    // MARK: - Live state
    var quote: Quote?
    var candles: [Candle] = []
    var indicators = IndicatorSnapshot()
    var alerts: [TradeAlert] = []
    var trades: [SimulatedTrade] = []
    var equityCurve: [PortfolioSnapshot] = []

    var portfolio: PortfolioSnapshot
    private var costBasis: Double = 0

    /// The original deposit, used to compute total return.
    private(set) var startingBalance: Double

    var isRefreshing = false
    var lastError: String?
    var lastUpdated: Date?

    // MARK: - Dependencies
    private var market: MarketDataService
    private let simulator = Simulator()
    private var pollTask: Task<Void, Never>?
    private let store = PersistenceStore()

    // MARK: - Init
    init(startingBalance: Double = 23.17) {
        let saved = PersistenceStore().load()
        self.startingBalance = saved?.startingBalance ?? startingBalance
        self.portfolio = saved?.portfolio
            ?? PortfolioSnapshot(cash: startingBalance, tokenQuantity: 0, lastPrice: 0)
        self.costBasis = saved?.costBasis ?? 0
        self.trades = saved?.trades ?? []
        self.alerts = saved?.alerts ?? []
        if let cfg = saved?.strategy { self.strategy = cfg }
        if let auto = saved?.autoTrade { self.autoTradeSimulation = auto }
        self.market = MarketDataService(productID: productID)
    }

    // MARK: - Derived values
    var totalReturn: Double { portfolio.totalValue - startingBalance }
    var totalReturnPct: Double {
        startingBalance > 0 ? (totalReturn / startingBalance) * 100 : 0
    }
    var realizedPnL: Double {
        trades.compactMap(\.realizedPnL).reduce(0, +)
    }
    var latestActionableAlert: TradeAlert? {
        alerts.first { $0.action != .hold }
    }

    // MARK: - Lifecycle
    func start() {
        guard pollTask == nil else { return }
        pollTask = Task { [weak self] in
            await self?.refresh()
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(self?.refreshInterval ?? 60))
                if Task.isCancelled { break }
                await self?.refresh()
            }
        }
    }

    func stop() {
        pollTask?.cancel()
        pollTask = nil
    }

    // MARK: - Refresh
    func refresh() async {
        guard !isRefreshing else { return }
        isRefreshing = true
        defer { isRefreshing = false }

        do {
            async let quoteResult = market.fetchSpotPrice()
            async let candleResult = market.fetchCandles(granularity: granularity)
            let (newQuote, newCandles) = try await (quoteResult, candleResult)

            self.quote = newQuote
            self.candles = newCandles
            self.portfolio.lastPrice = newQuote.price
            self.lastUpdated = Date()
            self.lastError = nil

            evaluateSignals()
            recordEquity()
            persist()
        } catch {
            self.lastError = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }

    private func evaluateSignals() {
        let closes = candles.map(\.close)
        let engine = SignalEngine(config: strategy)
        indicators = engine.indicators(for: closes)

        guard let alert = engine.evaluate(closes: closes) else { return }

        // Only record/notify on a *change* of signal. A condition that persists
        // across refreshes (e.g. RSI stays overbought) shouldn't re-fire.
        if let last = alerts.first, last.action == alert.action { return }
        alerts.insert(alert, at: 0)
        if alerts.count > 200 { alerts.removeLast(alerts.count - 200) }

        if alert.action != .hold {
            NotificationManager.shared.notify(for: alert, symbol: symbol)
            if autoTradeSimulation {
                if let trade = simulator.apply(alert: alert, to: &portfolio, costBasis: &costBasis) {
                    trades.insert(trade, at: 0)
                }
            }
        }
    }

    private func recordEquity() {
        equityCurve.append(portfolio)
        if equityCurve.count > 500 { equityCurve.removeFirst(equityCurve.count - 500) }
    }

    // MARK: - Manual paper trading
    func manualTrade(_ action: SignalAction) {
        guard let price = quote?.price else { return }
        let alert = TradeAlert(action: action, price: price, reason: "Manual paper trade", timestamp: Date())
        if let trade = simulator.apply(alert: alert, to: &portfolio, costBasis: &costBasis) {
            trades.insert(trade, at: 0)
            recordEquity()
            persist()
        }
    }

    /// Resets the paper portfolio back to a fresh deposit.
    func resetSimulation(to balance: Double) {
        startingBalance = balance
        portfolio = PortfolioSnapshot(cash: balance, tokenQuantity: 0, lastPrice: quote?.price ?? 0)
        costBasis = 0
        trades.removeAll()
        equityCurve.removeAll()
        persist()
    }

    // MARK: - Persistence
    private func persist() {
        store.save(.init(
            startingBalance: startingBalance,
            portfolio: portfolio,
            costBasis: costBasis,
            trades: trades,
            alerts: Array(alerts.prefix(50)),
            strategy: strategy,
            autoTrade: autoTradeSimulation
        ))
    }
    private func persistConfig() { persist() }
}
