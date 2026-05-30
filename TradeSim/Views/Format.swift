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

    /// Prices can be sub-cent, so show more precision for the spot price.
    static func price(_ value: Double) -> String {
        usd(value, fractionDigits: value < 1 ? 5 : 2)
    }

    static func signedUSD(_ value: Double) -> String {
        (value >= 0 ? "+" : "") + usd(value)
    }

    static func pct(_ value: Double) -> String {
        String(format: "%+.2f%%", value)
    }

    static func tokens(_ value: Double) -> String {
        String(format: "%.2f", value)
    }

    static func time(_ date: Date) -> String {
        let f = DateFormatter()
        f.dateFormat = "MMM d, h:mm a"
        return f.string(from: date)
    }

    static func shortTime(_ date: Date) -> String {
        let f = DateFormatter()
        f.dateFormat = "h:mm a"
        return f.string(from: date)
    }
}
