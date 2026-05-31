import Foundation

/// Tunable indicator parameters shared by the scoring engine.
struct StrategyConfig: Codable, Equatable {
    var shortSMA: Int = 9      // fast moving-average period
    var longSMA: Int = 21      // slow moving-average period
    var rsiPeriod: Int = 14
    var rsiOverbought: Double = 70
    var rsiOversold: Double = 30

    static let `default` = StrategyConfig()
}

/// Stateless technical-indicator math used by the `Predictor`.
enum SignalEngine {
    /// Simple moving average of the most recent `period` values.
    static func sma(_ values: [Double], period: Int) -> Double? {
        guard period > 0, values.count >= period else { return nil }
        return values.suffix(period).reduce(0, +) / Double(period)
    }

    /// Wilder's RSI over the supplied series.
    static func rsi(_ values: [Double], period: Int) -> Double? {
        guard period > 0, values.count > period else { return nil }
        var gains = 0.0
        var losses = 0.0
        for i in 1...period {
            let change = values[i] - values[i - 1]
            if change >= 0 { gains += change } else { losses -= change }
        }
        var avgGain = gains / Double(period)
        var avgLoss = losses / Double(period)
        if values.count > period + 1 {
            for i in (period + 1)..<values.count {
                let change = values[i] - values[i - 1]
                avgGain = (avgGain * Double(period - 1) + max(change, 0)) / Double(period)
                avgLoss = (avgLoss * Double(period - 1) + max(-change, 0)) / Double(period)
            }
        }
        guard avgLoss != 0 else { return 100 }
        let rs = avgGain / avgLoss
        return 100 - (100 / (1 + rs))
    }
}
