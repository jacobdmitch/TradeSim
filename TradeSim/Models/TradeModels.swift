import Foundation
import SwiftUI

/// The action a signal recommends.
enum SignalAction: String, Codable {
    case buy = "BUY"
    case sell = "SELL"
    case hold = "HOLD"

    var color: Color {
        switch self {
        case .buy: return .green
        case .sell: return .red
        case .hold: return .secondary
        }
    }

    var systemImage: String {
        switch self {
        case .buy: return "arrow.up.circle.fill"
        case .sell: return "arrow.down.circle.fill"
        case .hold: return "minus.circle.fill"
        }
    }
}

/// A trade alert produced by the signal engine.
struct TradeAlert: Identifiable, Codable, Hashable {
    var id = UUID()
    let action: SignalAction
    let price: Double
    let reason: String
    let timestamp: Date
}

/// A simulated (paper) trade executed by the simulator.
struct SimulatedTrade: Identifiable, Codable, Hashable {
    var id = UUID()
    let action: SignalAction      // .buy or .sell
    let price: Double             // execution price per token
    let quantity: Double          // tokens transacted
    let cashFlow: Double          // negative on buy, positive on sell
    let timestamp: Date
    /// Realized profit/loss for a closing (sell) trade, if known.
    let realizedPnL: Double?
}

/// Snapshot of the paper-trading portfolio at a point in time.
struct PortfolioSnapshot: Codable, Hashable {
    var cash: Double              // USD available
    var tokenQuantity: Double     // DIMO held
    var lastPrice: Double         // most recent mark price

    /// Mark-to-market value of token holdings.
    var holdingsValue: Double { tokenQuantity * lastPrice }

    /// Total account equity (cash + holdings).
    var totalValue: Double { cash + holdingsValue }
}
