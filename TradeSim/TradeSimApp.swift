import SwiftUI

@main
struct TradeSimApp: App {
    @State private var model = TradeSimModel()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(model)
                .task {
                    await NotificationManager.shared.requestAuthorization()
                    model.start()
                }
        }
        .onChange(of: scenePhase) { _, phase in
            switch phase {
            case .active:
                model.start()
            case .background, .inactive:
                Task { await model.refresh() }
            @unknown default:
                break
            }
        }
    }
}
