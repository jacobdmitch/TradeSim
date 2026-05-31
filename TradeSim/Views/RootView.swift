import SwiftUI

struct RootView: View {
    var body: some View {
        TabView {
            DashboardView()
                .tabItem { Label("Portfolio", systemImage: "briefcase.fill") }

            MarketsView()
                .tabItem { Label("Markets", systemImage: "chart.bar.fill") }

            RotationView()
                .tabItem { Label("Strategy", systemImage: "arrow.triangle.2.circlepath") }

            ActivityView()
                .tabItem { Label("Activity", systemImage: "bell.fill") }

            SettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape.fill") }
        }
    }
}

#Preview {
    RootView().environment(TradeSimModel())
}
