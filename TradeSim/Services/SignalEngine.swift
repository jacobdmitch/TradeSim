import Foundation

/// Tunable strategy parameters.
struct StrategyConfig: Codable, Equatable {
    var shortSMA: Int = 9      // fast moving-average period
    var longSMA: Int = 21      // slow moving-average period
    var rsiPeriod: Int = 14
    var rsiOverbought: Double = 70
    var rsiOversold: Double = 30

    static let `default` = StrategyConfig()
}

/// Indicator values computed for the latest bar (used by the dashboard).
struct IndicatorSnapshot {
    var shortSMA: Double?
    var longSMA: Double?
    var rsi: Double?
}

/// Computes technical indicators and turns them into BUY/SELL/HOLD signals.
///
/// Strategy: a moving-average crossover gated by RSI.
///  • BUY  when the fast SMA crosses *above* the slow SMA and RSI isn't overbought.
///  • SELL when the fast SMA crosses *below* the slow SMA, or RSI is overbought.
///  • HOLD otherwise.
struct SignalEngine {
    var config: StrategyConfig

    // MARK: - Indicators

    static func sma(_ values: [Double], period: Int) -> Double? {
        guard period > 0, values.count >= period else { return nil }
        let window = values.suffix(period)
        return window.reduce(0, +) / Double(period)
    }

    /// Wilder's RSI over the most recent `period` changes.
    static func rsi(_ values: [Double], period: Int) -> Double? {
        guard period > 0, values.count > period else { return nil }
        var gains = 0.0
        var losses = 0.0
        // Seed with the first `period` changes.
        for i in 1...period {
            let change = values[i] - values[i - 1]
            if change >= 0 { gains += change } else { losses -= change }
        }
        var avgGain = gains / Double(period)
        var avgLoss = losses / Double(period)
        // Smooth across the remaining changes.
        if values.count > period + 1 {
            for i in (period + 1)..<values.count {
                let change = values[i] - values[i - 1]
                let gain = max(change, 0)
                let loss = max(-change, 0)
                avgGain = (avgGain * Double(period - 1) + gain) / Double(period)
                avgLoss = (avgLoss * Double(period - 1) + loss) / Double(period)
            }
        }
        guard avgLoss != 0 else { return 100 }
        let rs = avgGain / avgLoss
        return 100 - (100 / (1 + rs))
    }

    /// Indicator snapshot for the latest bar.
    func indicators(for closes: [Double]) -> IndicatorSnapshot {
        IndicatorSnapshot(
            shortSMA: Self.sma(closes, period: config.shortSMA),
            longSMA: Self.sma(closes, period: config.longSMA),
            rsi: Self.rsi(closes, period: config.rsiPeriod)
        )
    }

    // MARK: - Signal

    /// Evaluates the strategy against a series of closing prices.
    /// Returns `nil` when there isn't enough history to decide.
    func evaluate(closes: [Double]) -> TradeAlert? {
        guard closes.count > config.longSMA + 1 else { return nil }

        let prev = Array(closes.dropLast())
        guard
            let shortNow = Self.sma(closes, period: config.shortSMA),
            let longNow = Self.sma(closes, period: config.longSMA),
            let shortPrev = Self.sma(prev, period: config.shortSMA),
            let longPrev = Self.sma(prev, period: config.longSMA),
            let rsi = Self.rsi(closes, period: config.rsiPeriod),
            let price = closes.last
        else { return nil }

        let crossedUp = shortPrev <= longPrev && shortNow > longNow
        let crossedDown = shortPrev >= longPrev && shortNow < longNow

        if crossedUp && rsi < config.rsiOverbought {
            return TradeAlert(
                action: .buy,
                price: price,
                reason: String(format: "Fast SMA crossed above slow SMA. RSI %.0f.", rsi),
                timestamp: Date()
            )
        }
        if crossedDown {
            return TradeAlert(
                action: .sell,
                price: price,
                reason: String(format: "Fast SMA crossed below slow SMA. RSI %.0f.", rsi),
                timestamp: Date()
            )
        }
        if rsi >= config.rsiOverbought {
            return TradeAlert(
                action: .sell,
                price: price,
                reason: String(format: "RSI %.0f is overbought (≥ %.0f).", rsi, config.rsiOverbought),
                timestamp: Date()
            )
        }
        if rsi <= config.rsiOversold && shortNow > longNow {
            return TradeAlert(
                action: .buy,
                price: price,
                reason: String(format: "RSI %.0f is oversold in an uptrend.", rsi),
                timestamp: Date()
            )
        }
        return TradeAlert(
            action: .hold,
            price: price,
            reason: String(format: "No crossover. RSI %.0f.", rsi),
            timestamp: Date()
        )
    }
}
