import SwiftUI

struct ActivityView: View {
    @Environment(TradeSimModel.self) private var model
    @State private var scope: Scope = .recommendations

    enum Scope: String, CaseIterable, Identifiable {
        case recommendations = "Signals"
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
                case .recommendations: recommendationList
                case .trades: tradeList
                }
            }
            .navigationTitle("Activity")
        }
    }

    private var recommendationList: some View {
        Group {
            if model.recommendations.isEmpty {
                ContentUnavailableView("No signals yet", systemImage: "bell.slash")
            } else {
                List(model.recommendations) { rec in
                    HStack(spacing: 12) {
                        Image(systemName: rec.action.systemImage)
                            .foregroundStyle(rec.action.color).font(.title2)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(title(rec)).font(.headline)
                            Text(rec.rationale).font(.caption).foregroundStyle(.secondary)
                            Text(Format.time(rec.timestamp)).font(.caption2).foregroundStyle(.tertiary)
                        }
                        Spacer()
                        if rec.action != .hold {
                            Text(Format.pct(rec.edgePct))
                                .font(.subheadline.monospacedDigit())
                                .foregroundStyle(rec.action.color)
                        }
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
                            .foregroundStyle(trade.action.color).font(.title2)
                        VStack(alignment: .leading, spacing: 2) {
                            Text("\(trade.action.rawValue) \(Format.tokens(trade.quantity)) \(trade.base)")
                                .font(.headline)
                            Text("@ \(Format.price(trade.price))")
                                .font(.caption).foregroundStyle(.secondary)
                            Text(Format.time(trade.timestamp)).font(.caption2).foregroundStyle(.tertiary)
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

    private func title(_ rec: RotationRecommendation) -> String {
        switch rec.action {
        case .enter:  return "Enter \(rec.toBase ?? "")"
        case .rotate: return "Rotate \(rec.fromBase ?? "") → \(rec.toBase ?? "")"
        case .exit:   return "Exit \(rec.fromBase ?? "") to cash"
        case .hold:   return "Hold"
        }
    }
}

#Preview {
    ActivityView().environment(TradeSimModel())
}
