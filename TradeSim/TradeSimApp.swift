import SwiftUI

@main
struct TradeSimApp: App {
    @State private var model = TradeSimModel()
    @State private var isLoading = true
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            ZStack {
                if isLoading {
                    LoadingView()
                        .transition(.opacity)
                } else {
                    RootView()
                        .environment(model)
                        .transition(.opacity)
                }
            }
            .task {
                await NotificationManager.shared.requestAuthorization()
                model.start()
                
                // Show loading screen for at least 1.5 seconds for smooth UX
                try? await Task.sleep(for: .seconds(1.5))
                
                withAnimation(.easeInOut(duration: 0.5)) {
                    isLoading = false
                }
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
