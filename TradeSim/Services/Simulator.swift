import Foundation

/// A pure paper-trading engine for a single-position, cash-or-coin portfolio.
/// It never touches real funds — it simulates rotating your balance between
/// coins (always routing through USD, paying a fee on each leg).
struct Simulator {
    /// Coinbase taker fee approximation for small accounts (~0.6%).
    var feeRate: Double = 0.006

    /// Deploys all available cash into `target` at `price`.
    func enter(base: String, productID: String, price: Double, portfolio: inout Portfolio) -> SimulatedTrade? {
        guard portfolio.position == nil, portfolio.cash > 0.01, price > 0 else { return nil }
        let spend = portfolio.cash
        let invested = spend * (1 - feeRate)
        let qty = invested / price
        portfolio.cash = 0
        portfolio.position = Position(base: base, productID: productID,
                                      quantity: qty, costBasisUSD: invested, markPrice: price)
        return SimulatedTrade(action: .buy, base: base, price: price, quantity: qty,
                              cashFlow: -spend, timestamp: Date(), realizedPnL: nil)
    }

    /// Liquidates the current position back to USD cash at `price`.
    func exit(price: Double, portfolio: inout Portfolio) -> SimulatedTrade? {
        guard let position = portfolio.position, position.quantity > 0, price > 0 else { return nil }
        let gross = position.quantity * price
        let proceeds = gross * (1 - feeRate)
        let pnl = proceeds - position.costBasisUSD
        portfolio.cash += proceeds
        portfolio.position = nil
        return SimulatedTrade(action: .sell, base: position.base, price: price,
                              quantity: position.quantity, cashFlow: proceeds,
                              timestamp: Date(), realizedPnL: pnl)
    }

    /// Rotates from the current coin into `target`: exit to cash, then enter.
    /// Returns both legs (sell, then buy).
    func rotate(toBase: String, toProductID: String, sellPrice: Double, buyPrice: Double,
                portfolio: inout Portfolio) -> [SimulatedTrade] {
        var trades: [SimulatedTrade] = []
        if let sell = exit(price: sellPrice, portfolio: &portfolio) { trades.append(sell) }
        if let buy = enter(base: toBase, productID: toProductID, price: buyPrice, portfolio: &portfolio) {
            trades.append(buy)
        }
        return trades
    }

    /// Seeds the portfolio with an existing coin holding (no fee — it models
    /// coins you already own, e.g. your DIMO), converting `usdValue` at `price`.
    func seedHolding(base: String, productID: String, usdValue: Double, price: Double, portfolio: inout Portfolio) {
        guard price > 0, usdValue > 0 else { return }
        let qty = usdValue / price
        portfolio.cash = 0
        portfolio.position = Position(base: base, productID: productID,
                                      quantity: qty, costBasisUSD: usdValue, markPrice: price)
    }
}
