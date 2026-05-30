import Foundation

/// Lightweight JSON-in-UserDefaults persistence for the paper-trading state.
struct PersistenceStore {
    struct State: Codable {
        var startingBalance: Double
        var portfolio: Portfolio
        var seeded: Bool
        var trades: [SimulatedTrade]
        var recommendations: [RotationRecommendation]
        var strategy: StrategyConfig
        var rotation: RotationConfig
    }

    private let key = "tradesim.state.v2"
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
