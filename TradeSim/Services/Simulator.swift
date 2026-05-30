import Foundation

/// A pure paper-trading engine. It never touches real funds — it simulates
/// what would happen if you acted on every BUY/SELL alert with your balance.
struct Simulator {
    /// Coinbase taker fee approximation for small accounts (~0.6%).
    var feeRate: Double = 0.006

    /// Applies an actionable alert to the current portfolio.
    /// BUY converts all cash to tokens; SELL converts all tokens to cash.
    /// Returns the resulting trade, or `nil` if the alert wasn't actionable.
    func apply(alert: TradeAlert, to portfolio: inout PortfolioSnapshot, costBasis: inout Double) -> SimulatedTrade? {
        portfolio.lastPrice = alert.price

        switch alert.action {
        case .buy:
            guard portfolio.cash > 0.01 else { return nil }
            let spend = portfolio.cash
            let fee = spend * feeRate
            let invested = spend - fee
            let qty = invested / alert.price
            portfolio.cash = 0
            portfolio.tokenQuantity += qty
            costBasis = invested            // record what we paid (ex-fee)
            return SimulatedTrade(
                action: .buy,
                price: alert.price,
                quantity: qty,
                cashFlow: -spend,
                timestamp: alert.timestamp,
                realizedPnL: nil
            )

        case .sell:
            guard portfolio.tokenQuantity > 0 else { return nil }
            let qty = portfolio.tokenQuantity
            let gross = qty * alert.price
            let fee = gross * feeRate
            let proceeds = gross - fee
            portfolio.tokenQuantity = 0
            portfolio.cash += proceeds
            let pnl = proceeds - costBasis
            costBasis = 0
            return SimulatedTrade(
                action: .sell,
                price: alert.price,
                quantity: qty,
                cashFlow: proceeds,
                timestamp: alert.timestamp,
                realizedPnL: pnl
            )

        case .hold:
            return nil
        }
    }
}
