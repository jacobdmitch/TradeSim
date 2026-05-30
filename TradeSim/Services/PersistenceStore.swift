import Foundation

/// Lightweight JSON-in-UserDefaults persistence for the paper-trading state.
struct PersistenceStore {
    struct State: Codable {
        var startingBalance: Double
        var portfolio: PortfolioSnapshot
        var costBasis: Double
        var trades: [SimulatedTrade]
        var alerts: [TradeAlert]
        var strategy: StrategyConfig
        var autoTrade: Bool
    }

    private let key = "tradesim.state.v1"
    private let defaults = UserDefaults.standard

    init() {}

    func save(_ state: State) {
        if let data = try? JSONEncoder().encode(state) {
            defaults.set(data, forKey: key)
        }
    }

    func load() -> State? {
        guard let data = defaults.data(forKey: key) else { return nil }
        return try? JSONDecoder().decode(State.self, from: data)
    }
}
