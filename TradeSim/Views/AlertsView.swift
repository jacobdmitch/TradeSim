import SwiftUI

struct AlertsView: View {
    @Environment(TradeSimModel.self) private var model
    @State private var scope: Scope = .alerts

    enum Scope: String, CaseIterable, Identifiable {
        case alerts = "Signals"
        case trades = "Trades"
        var id: String { rawValue }
    }

    var body: some View {
        NavigationStack {
            VStack {
                Picker("Scope", selection: $scope) {
                    ForEach(Scope.allCases) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)

                switch scope {
                case .alerts: alertList
                case .trades: tradeList
                }
            }
            .navigationTitle("Activity")
        }
    }

    private var alertList: some View {
        Group {
            if model.alerts.isEmpty {
                ContentUnavailableView("No signals yet", systemImage: "bell.slash")
            } else {
                List(model.alerts) { alert in
                    HStack(spacing: 12) {
                        Image(systemName: alert.action.systemImage)
                            .foregroundStyle(alert.action.color)
                            .font(.title2)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(alert.action.rawValue).font(.headline)
                            Text(alert.reason).font(.caption).foregroundStyle(.secondary)
                            Text(Format.time(alert.timestamp))
                                .font(.caption2).foregroundStyle(.tertiary)
                        }
                        Spacer()
                        Text(Format.price(alert.price)).font(.subheadline.monospacedDigit())
                    }
                }
                .listStyle(.plain)
            }
        }
    }

    private var tradeList: some View {
        Group {
            if model.trades.isEmpty {
                ContentUnavailableView("No trades yet", systemImage: "tray")
            } else {
                List(model.trades) { trade in
                    HStack(spacing: 12) {
                        Image(systemName: trade.action.systemImage)
                            .foregroundStyle(trade.action.color)
                            .font(.title2)
                        VStack(alignment: .leading, spacing: 2) {
                            Text("\(trade.action.rawValue) \(Format.tokens(trade.quantity)) \(model.symbol)")
                                .font(.headline)
                            Text("@ \(Format.price(trade.price))")
                                .font(.caption).foregroundStyle(.secondary)
                            Text(Format.time(trade.timestamp))
                                .font(.caption2).foregroundStyle(.tertiary)
                        }
                        Spacer()
                        if let pnl = trade.realizedPnL {
                            Text(Format.signedUSD(pnl))
                                .font(.subheadline.monospacedDigit())
                                .foregroundStyle(pnl >= 0 ? .green : .red)
                        }
                    }
                }
                .listStyle(.plain)
            }
        }
    }
}

#Preview {
    AlertsView().environment(TradeSimModel())
}
