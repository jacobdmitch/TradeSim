import Foundation
import UserNotifications

/// Wraps local notifications so the app can push a trade alert to the lock
/// screen / banner when a BUY or SELL signal fires.
@MainActor
final class NotificationManager {
    static let shared = NotificationManager()
    private init() {}

    private(set) var authorized = false

    /// Requests permission to show alerts, sounds and badges.
    func requestAuthorization() async {
        do {
            authorized = try await UNUserNotificationCenter.current()
                .requestAuthorization(options: [.alert, .sound, .badge])
        } catch {
            authorized = false
        }
    }

    /// Posts a notification for an actionable alert. HOLD alerts are ignored.
    func notify(for alert: TradeAlert, symbol: String) {
        guard alert.action != .hold else { return }

        let content = UNMutableNotificationContent()
        content.title = "\(alert.action.rawValue) \(symbol)"
        content.body = String(format: "Price $%.5f — %@", alert.price, alert.reason)
        content.sound = .default

        let request = UNNotificationRequest(
            identifier: alert.id.uuidString,
            content: content,
            trigger: nil // deliver immediately
        )
        UNUserNotificationCenter.current().add(request)
    }
}
