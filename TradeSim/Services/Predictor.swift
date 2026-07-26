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
    /// Minimum expected profit, net of round-trip fees, before a move is worth
    /// making. Percent thresholds alone hide fee drag on a small balance: at
    /// 0.6%/leg a $27 position pays ~$0.32 per round trip, so a 0.2% "edge" is
    /// 5c of upside against 32c of cost.
    var minNetProfitUSD: Double = 0.25

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

    /// Dollar cost/benefit of a pending action at the current account size.
    ///
    /// `feeLegs` is 2 for an entry or a rotation — the position has to be sold
    /// again, so the decision owns the whole round trip — and 1 for an exit.
    /// `edgePct` is the expected advantage of acting.
    private func economics(value: Double, feeLegs: Int, edgePct: Double,
                           feeRate: Double) -> (fee: Double, gross: Double, net: Double) {
        let tradeValue = max(value, 0)
        let fee = tradeValue * feeRate * Double(feeLegs)
        let gross = tradeValue * edgePct / 100
        return (fee, gross, gross - fee)
    }

    /// Decides what to do given the ranked scores and the current portfolio.
    /// `feeRate` is the per-trade fee (e.g. 0.006); a rotation pays it twice.
    ///
    /// Every gain-seeking move has to clear its trading cost twice over: once in
    /// percent (the thresholds plus the round trip) and once in dollars
    /// (`minNetProfitUSD` of expected profit after fees), so an edge that
    /// technically qualifies but only amounts to pennies never becomes a trade.
    func recommend(ranked: [CoinScore], portfolio: Portfolio, feeRate: Double) -> RotationRecommendation {
        let roundTripCostPct = feeRate * 2 * 100
        let accountValue = portfolio.totalValue
        let best = ranked.first

        // Currently in cash — look for a coin worth deploying into.
        guard let position = portfolio.position else {
            // Entering commits to a round trip, so the edge must cover both legs.
            if let best, best.predictedEdgePct > config.enterThresholdPct + roundTripCostPct {
                let e = economics(value: accountValue, feeLegs: 2,
                                  edgePct: best.predictedEdgePct, feeRate: feeRate)
                if e.net < minNetProfitUSD {
                    return RotationRecommendation(
                        action: .hold, fromBase: nil, toBase: nil,
                        rationale: String(format: "%@'s %.1f%% edge is only $%.2f on $%.2f; $%.2f of fees leaves $%.2f, under the $%.2f minimum. Not worth the trade — staying in cash.",
                                          best.base, best.predictedEdgePct, e.gross, accountValue,
                                          e.fee, e.net, minNetProfitUSD),
                        edgePct: best.predictedEdgePct, timestamp: Date())
                }
                return RotationRecommendation(
                    action: .enter, fromBase: nil, toBase: best.base,
                    rationale: String(format: "%@ leads with a %.1f%% predicted edge (24h %@%.1f%%): ~$%.2f on $%.2f less $%.2f round-trip fees = $%.2f net.",
                                      best.base, best.predictedEdgePct,
                                      best.change24h >= 0 ? "+" : "", best.change24h,
                                      e.gross, accountValue, e.fee, e.net),
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
                // Protective, so it isn't gated on expected profit — but the
                // cost of the leg is still stated.
                let e = economics(value: accountValue, feeLegs: 1, edgePct: 0, feeRate: feeRate)
                return RotationRecommendation(
                    action: .exit, fromBase: position.base, toBase: nil,
                    rationale: String(format: "%@ outlook turned negative (%.1f%%). Move to cash to protect value ($%.2f exit fee).",
                                      position.base, currentEdge, e.fee),
                    edgePct: currentEdge, timestamp: Date())
            }
        }

        // Rotate into a clearly stronger coin, accounting for round-trip fees.
        if let best, best.base != position.base,
           best.predictedEdgePct > currentEdge + config.rotationThresholdPct + roundTripCostPct {
            // Floor the holding's edge at 0 for the dollar math so a deeply
            // negative score can't project an outsized gain.
            let gainPct = best.predictedEdgePct - max(currentEdge, 0)
            let e = economics(value: accountValue, feeLegs: 2, edgePct: gainPct, feeRate: feeRate)
            let netEdgePct = best.predictedEdgePct - currentEdge - roundTripCostPct
            if e.net < minNetProfitUSD {
                return RotationRecommendation(
                    action: .hold, fromBase: position.base, toBase: nil,
                    rationale: String(format: "%@ (%.1f%%) beats %@ (%.1f%%), but only by $%.2f on $%.2f; $%.2f of rotation fees leaves $%.2f, under the $%.2f minimum. Holding %@.",
                                      best.base, best.predictedEdgePct, position.base, currentEdge,
                                      e.gross, accountValue, e.fee, e.net, minNetProfitUSD, position.base),
                    edgePct: netEdgePct, timestamp: Date())
            }
            return RotationRecommendation(
                action: .rotate, fromBase: position.base, toBase: best.base,
                rationale: String(format: "%@ (%.1f%%) beats %@ (%.1f%%) by more than the %.1f%% round-trip cost: ~$%.2f of edge on $%.2f less $%.2f fees = $%.2f net.",
                                  best.base, best.predictedEdgePct, position.base, currentEdge,
                                  roundTripCostPct, e.gross, accountValue, e.fee, e.net),
                edgePct: netEdgePct, timestamp: Date())
        }

        return RotationRecommendation(
            action: .hold, fromBase: position.base, toBase: nil,
            rationale: String(format: "Holding %@ — still the best risk-adjusted pick (%.1f%%).",
                              position.base, currentEdge),
            edgePct: currentEdge, timestamp: Date())
    }
}
