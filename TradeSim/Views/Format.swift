import Foundation

/// Shared number/date formatting helpers.
enum Format {
    static func usd(_ value: Double, fractionDigits: Int = 2) -> String {
        let f = NumberFormatter()
        f.numberStyle = .currency
        f.currencyCode = "USD"
        f.minimumFractionDigits = fractionDigits
        f.maximumFractionDigits = fractionDigits
        return f.string(from: NSNumber(value: value)) ?? "$\(value)"
    }

    /// Prices can be sub-cent, so show more precision for small prices.
    static func price(_ value: Double) -> String {
        if value == 0 { return "$0.00" }
        if value < 1 { return usd(value, fractionDigits: 5) }
        if value < 1000 { return usd(value, fractionDigits: 2) }
        return usd(value, fractionDigits: 0)
    }

    static func signedUSD(_ value: Double) -> String {
        (value >= 0 ? "+" : "") + usd(value)
    }

    static func pct(_ value: Double) -> String { String(format: "%+.2f%%", value) }

    static func tokens(_ value: Double) -> String {
        if value >= 1 { return String(format: "%.2f", value) }
        return String(format: "%.4f", value)
    }

    /// Compact dollar volume, e.g. "$1.2M".
    static func compactUSD(_ value: Double) -> String {
        switch value {
        case 1_000_000_000...: return String(format: "$%.1fB", value / 1_000_000_000)
        case 1_000_000...:     return String(format: "$%.1fM", value / 1_000_000)
        case 1_000...:         return String(format: "$%.0fK", value / 1_000)
        default:               return usd(value, fractionDigits: 0)
        }
    }

    static func time(_ date: Date) -> String {
        let f = DateFormatter(); f.dateFormat = "MMM d, h:mm a"; return f.string(from: date)
    }
    static func shortTime(_ date: Date) -> String {
        let f = DateFormatter(); f.dateFormat = "h:mm a"; return f.string(from: date)
    }
}
