import Foundation
import UserNotifications

/// Wraps local notifications so the app can push a rotation alert to the lock
/// screen / banner when the engine recommends acting.
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

    /// Posts a notification for an actionable rotation recommendation.
    func notify(for rec: RotationRecommendation) {
        guard rec.action != .hold else { return }

        let content = UNMutableNotificationContent()
        switch rec.action {
        case .enter:  content.title = "ENTER \(rec.toBase ?? "")"
        case .rotate: content.title = "ROTATE \(rec.fromBase ?? "") → \(rec.toBase ?? "")"
        case .exit:   content.title = "EXIT \(rec.fromBase ?? "") → cash"
        case .hold:   return
        }
        content.body = rec.rationale
        content.sound = .default

        let request = UNNotificationRequest(identifier: rec.id.uuidString, content: content, trigger: nil)
        UNUserNotificationCenter.current().add(request)
    }
}
