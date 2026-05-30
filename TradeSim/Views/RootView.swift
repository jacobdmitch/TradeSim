import SwiftUI

struct RootView: View {
    var body: some View {
        TabView {
            DashboardView()
                .tabItem { Label("Dashboard", systemImage: "chart.bar.fill") }

            ChartView()
                .tabItem { Label("Chart", systemImage: "chart.xyaxis.line") }

            AlertsView()
                .tabItem { Label("Alerts", systemImage: "bell.fill") }

            SettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape.fill") }
        }
    }
}

#Preview {
    RootView().environment(TradeSimModel())
}
