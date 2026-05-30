import Foundation
import SwiftUI

/// The action a per-coin signal recommends.
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

/// A single open coin position (the portfolio holds at most one at a time).
struct Position: Codable, Hashable {
    var base: String          // "DIMO"
    var productID: String     // "DIMO-USD"
    var quantity: Double      // coins held
    var costBasisUSD: Double  // USD deployed into this position (ex-fee)
    var markPrice: Double     // latest known price per coin

    var value: Double { quantity * markPrice }
}

/// The paper portfolio: USD cash plus at most one coin position.
struct Portfolio: Codable, Hashable {
    var cash: Double
    var position: Position?

    var totalValue: Double { cash + (position?.value ?? 0) }
    var holdingLabel: String { position?.base ?? "USD (cash)" }
    var isInCash: Bool { position == nil }
}

/// A simulated (paper) trade executed by the simulator.
struct SimulatedTrade: Identifiable, Codable, Hashable {
    var id = UUID()
    let action: SignalAction      // .buy or .sell
    let base: String              // coin transacted
    let price: Double             // execution price per coin
    let quantity: Double          // coins transacted
    let cashFlow: Double          // negative on buy, positive on sell
    let timestamp: Date
    /// Realized profit/loss for a closing (sell) trade, if known.
    let realizedPnL: Double?
}
