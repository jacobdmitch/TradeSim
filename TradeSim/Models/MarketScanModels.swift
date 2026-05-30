import Foundation
import SwiftUI

/// A tradable product on Coinbase (e.g. DIMO-USD).
struct Product: Identifiable, Hashable, Codable {
    let id: String           // "DIMO-USD"
    let base: String         // "DIMO"
    let quote: String        // "USD"
    let status: String
    let tradingDisabled: Bool
}

/// 24-hour statistics for a single product, from the bulk `/products/stats` feed.
struct MarketStat: Identifiable, Hashable {
    let productID: String
    let base: String
    let open: Double
    let high: Double
    let low: Double
    let last: Double
    let volume: Double        // 24h volume in base units

    var id: String { productID }
    var changePct: Double { open > 0 ? (last - open) / open * 100 : 0 }
    var volumeUSD: Double { volume * last }
}

/// A heuristic predictive score for one coin, used to rank rotation candidates.
struct CoinScore: Identifiable, Hashable {
    let productID: String
    let base: String
    let last: Double
    let change24h: Double
    let momentum: Double          // recent short-window return %
    let rsi: Double?
    let trendUp: Bool
    let predictedEdgePct: Double  // blended heuristic "expected" short-term move

    var id: String { productID }
}

/// What the rotation engine recommends doing right now.
enum RotationAction: String, Codable {
    case enter = "ENTER"     // move cash into a coin
    case rotate = "ROTATE"   // move from current coin into a stronger one
    case exit = "EXIT"       // move current coin back to cash (USD)
    case hold = "HOLD"       // stay put

    var color: Color {
        switch self {
        case .enter, .rotate: return .green
        case .exit: return .orange
        case .hold: return .secondary
        }
    }
    var systemImage: String {
        switch self {
        case .enter: return "arrow.down.right.circle.fill"
        case .rotate: return "arrow.triangle.2.circlepath.circle.fill"
        case .exit: return "arrow.up.left.circle.fill"
        case .hold: return "pause.circle.fill"
        }
    }
}

/// A concrete rotation recommendation with the rationale and projected edge.
struct RotationRecommendation: Identifiable, Codable, Hashable {
    var id = UUID()
    let action: RotationAction
    let fromBase: String?     // currently held (nil if in cash)
    let toBase: String?       // target coin (nil if exiting to cash)
    let rationale: String
    let edgePct: Double       // predicted advantage of acting, net of fees
    let timestamp: Date
}

/// Tunable parameters for the cross-market rotation strategy.
struct RotationConfig: Codable, Equatable {
    var candidateCount: Int = 12      // how many top movers to deeply analyze
    var momentumLookback: Int = 6     // bars used for the momentum window
    var enterThresholdPct: Double = 0.5   // edge needed to deploy cash
    var rotationThresholdPct: Double = 1.5 // extra edge needed to switch coins
    var exitThresholdPct: Double = -1.0    // edge below which we retreat to cash
    var autoRotate: Bool = true

    static let `default` = RotationConfig()
}
