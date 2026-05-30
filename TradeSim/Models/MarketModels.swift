import Foundation

/// A single OHLC candle for a time interval.
struct Candle: Identifiable, Hashable {
    let time: Date
    let low: Double
    let high: Double
    let open: Double
    let close: Double
    let volume: Double

    var id: TimeInterval { time.timeIntervalSince1970 }
}

/// The latest spot quote for the tracked asset.
struct Quote: Hashable {
    let price: Double
    let timestamp: Date
}

/// Supported candle granularities (seconds), matching the Coinbase Exchange API.
enum Granularity: Int, CaseIterable, Identifiable {
    case oneMinute = 60
    case fiveMinutes = 300
    case fifteenMinutes = 900
    case oneHour = 3600
    case sixHours = 21600
    case oneDay = 86400

    var id: Int { rawValue }

    var label: String {
        switch self {
        case .oneMinute: return "1m"
        case .fiveMinutes: return "5m"
        case .fifteenMinutes: return "15m"
        case .oneHour: return "1H"
        case .sixHours: return "6H"
        case .oneDay: return "1D"
        }
    }
}
