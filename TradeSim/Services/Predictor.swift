import Foundation

/// Scores coins and recommends how to rotate the portfolio between them.
///
/// The "prediction" here is an explicit, transparent heuristic — *not* a
/// statistical forecast. It blends recent momentum, trend direction and RSI
/// into a single expected short-term edge so candidates can be ranked
/// consistently. Treat it as a screening tool, never as a guarantee.
struct Predictor {
    var strategy: StrategyConfig
    var config: RotationConfig

    // MARK: - Scoring

    /// Builds a score for one coin from its stat and recent closing prices.
    func score(stat: MarketStat, closes: [Double]) -> CoinScore {
        let look = min(config.momentumLookback, max(closes.count - 1, 1))
        let momentum: Double = {
            guard closes.count > look, let last = closes.last else { return stat.changePct }
            let past = closes[closes.count - 1 - look]
            return past > 0 ? (last - past) / past * 100 : 0
        }()

        let shortSMA = SignalEngine.sma(closes, period: strategy.shortSMA)
        let longSMA = SignalEngine.sma(closes, period: strategy.longSMA)
        let trendUp = (shortSMA ?? 0) > (longSMA ?? 0)
        let rsi = SignalEngine.rsi(closes, period: strategy.rsiPeriod)

        // Blend: momentum is the base expectation, scaled by trend and RSI.
        var edge = momentum
        if !trendUp { edge *= 0.3 }                       // fade counter-trend moves
        if let rsi {
            if rsi >= strategy.rsiOverbought { edge *= 0.4 }            // likely to revert
            else if rsi <= strategy.rsiOversold && trendUp { edge *= 1.3 } // oversold bounce
        }

        return CoinScore(
            productID: stat.productID,
            base: stat.base,
            last: stat.last,
            change24h: stat.changePct,
            momentum: momentum,
            rsi: rsi,
            trendUp: trendUp,
            predictedEdgePct: edge
        )
    }

    /// Ranks every scored candidate, strongest predicted edge first.
    func rank(_ scores: [CoinScore]) -> [CoinScore] {
        scores.sorted { $0.predictedEdgePct > $1.predictedEdgePct }
    }

    // MARK: - Recommendation

    /// Decides what to do given the ranked scores and the current portfolio.
    /// `feeRate` is the per-trade fee (e.g. 0.006); a rotation pays it twice.
    func recommend(ranked: [CoinScore], portfolio: Portfolio, feeRate: Double) -> RotationRecommendation {
        let roundTripCostPct = feeRate * 2 * 100
        let best = ranked.first

        // Currently in cash — look for a coin worth deploying into.
        guard let position = portfolio.position else {
            if let best, best.predictedEdgePct > config.enterThresholdPct + feeRate * 100 {
                return RotationRecommendation(
                    action: .enter, fromBase: nil, toBase: best.base,
                    rationale: String(format: "%@ leads with a %.1f%% predicted edge (24h %@%.1f%%).",
                                      best.base, best.predictedEdgePct,
                                      best.change24h >= 0 ? "+" : "", best.change24h),
                    edgePct: best.predictedEdgePct, timestamp: Date())
            }
            return RotationRecommendation(
                action: .hold, fromBase: nil, toBase: nil,
                rationale: "No coin clears the entry threshold. Staying in cash.",
                edgePct: best?.predictedEdgePct ?? 0, timestamp: Date())
        }

        // Currently holding a coin.
        let current = ranked.first { $0.base == position.base }
        let currentEdge = current?.predictedEdgePct ?? 0

        // Retreat to cash if the held coin's outlook has turned negative and
        // nothing better is clearly available.
        if currentEdge < config.exitThresholdPct {
            let betterExists = best.map { $0.base != position.base && $0.predictedEdgePct > config.enterThresholdPct } ?? false
            if !betterExists {
                return RotationRecommendation(
                    action: .exit, fromBase: position.base, toBase: nil,
                    rationale: String(format: "%@ outlook turned negative (%.1f%%). Move to cash to protect value.",
                                      position.base, currentEdge),
                    edgePct: currentEdge, timestamp: Date())
            }
        }

        // Rotate into a clearly stronger coin, accounting for round-trip fees.
        if let best, best.base != position.base,
           best.predictedEdgePct > currentEdge + config.rotationThresholdPct + roundTripCostPct {
            return RotationRecommendation(
                action: .rotate, fromBase: position.base, toBase: best.base,
                rationale: String(format: "%@ (%.1f%%) beats %@ (%.1f%%) by more than the %.1f%% round-trip cost.",
                                  best.base, best.predictedEdgePct, position.base, currentEdge, roundTripCostPct),
                edgePct: best.predictedEdgePct - currentEdge - roundTripCostPct, timestamp: Date())
        }

        return RotationRecommendation(
            action: .hold, fromBase: position.base, toBase: nil,
            rationale: String(format: "Holding %@ — still the best risk-adjusted pick (%.1f%%).",
                              position.base, currentEdge),
            edgePct: currentEdge, timestamp: Date())
    }
}
