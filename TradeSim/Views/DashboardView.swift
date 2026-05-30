import SwiftUI

struct DashboardView: View {
    @Environment(TradeSimModel.self) private var model

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    priceCard
                    if let alert = model.latestActionableAlert {
                        signalCard(alert)
                    }
                    portfolioCard
                    indicatorsCard
                    manualTradeCard
                    disclaimer
                }
                .padding()
            }
            .navigationTitle(model.symbol)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Task { await model.refresh() }
                    } label: {
                        if model.isRefreshing {
                            ProgressView()
                        } else {
                            Image(systemName: "arrow.clockwise")
                        }
                    }
                }
            }
            .refreshable { await model.refresh() }
        }
    }

    // MARK: - Cards

    private var priceCard: some View {
        Card {
            VStack(alignment: .leading, spacing: 6) {
                Text("Spot Price")
                    .font(.subheadline).foregroundStyle(.secondary)
                HStack(alignment: .firstTextBaseline, spacing: 10) {
                    Text(model.quote.map { Format.price($0.price) } ?? "—")
                        .font(.system(size: 40, weight: .bold, design: .rounded))
                    if let change = sessionChangePct {
                        Text(Format.pct(change))
                            .font(.headline)
                            .foregroundStyle(change >= 0 ? .green : .red)
                    }
                }
                if let updated = model.lastUpdated {
                    Text("Updated \(Format.shortTime(updated))")
                        .font(.caption).foregroundStyle(.secondary)
                }
                if let err = model.lastError {
                    Label(err, systemImage: "exclamationmark.triangle.fill")
                        .font(.caption).foregroundStyle(.orange)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func signalCard(_ alert: TradeAlert) -> some View {
        Card {
            HStack(spacing: 14) {
                Image(systemName: alert.action.systemImage)
                    .font(.system(size: 36))
                    .foregroundStyle(alert.action.color)
                VStack(alignment: .leading, spacing: 4) {
                    Text("Latest Signal: \(alert.action.rawValue)")
                        .font(.headline)
                    Text(alert.reason)
                        .font(.subheadline).foregroundStyle(.secondary)
                    Text(Format.time(alert.timestamp))
                        .font(.caption).foregroundStyle(.tertiary)
                }
                Spacer()
            }
        }
    }

    private var portfolioCard: some View {
        Card {
            VStack(alignment: .leading, spacing: 12) {
                Text("Paper Portfolio").font(.headline)
                HStack {
                    stat("Total Value", Format.usd(model.portfolio.totalValue))
                    Spacer()
                    stat("Return",
                         Format.signedUSD(model.totalReturn),
                         color: model.totalReturn >= 0 ? .green : .red)
                }
                HStack {
                    stat("Cash", Format.usd(model.portfolio.cash))
                    Spacer()
                    stat("\(model.symbol)", Format.tokens(model.portfolio.tokenQuantity))
                }
                HStack {
                    stat("Total Return %",
                         Format.pct(model.totalReturnPct),
                         color: model.totalReturn >= 0 ? .green : .red)
                    Spacer()
                    stat("Realized P/L",
                         Format.signedUSD(model.realizedPnL),
                         color: model.realizedPnL >= 0 ? .green : .red)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var indicatorsCard: some View {
        Card {
            VStack(alignment: .leading, spacing: 12) {
                Text("Indicators (\(model.granularity.label))").font(.headline)
                HStack {
                    stat("SMA \(model.strategy.shortSMA)",
                         model.indicators.shortSMA.map { Format.price($0) } ?? "—")
                    Spacer()
                    stat("SMA \(model.strategy.longSMA)",
                         model.indicators.longSMA.map { Format.price($0) } ?? "—")
                    Spacer()
                    stat("RSI \(model.strategy.rsiPeriod)",
                         model.indicators.rsi.map { String(format: "%.0f", $0) } ?? "—",
                         color: rsiColor)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var manualTradeCard: some View {
        Card {
            VStack(alignment: .leading, spacing: 12) {
                Text("Manual Paper Trade").font(.headline)
                Text("Simulate acting on the alert yourself.")
                    .font(.caption).foregroundStyle(.secondary)
                HStack(spacing: 12) {
                    Button {
                        model.manualTrade(.buy)
                    } label: {
                        Label("Buy", systemImage: "arrow.up")
                            .frame(maxWidth: .infinity)
                    }
                    .tint(.green)
                    .disabled(model.portfolio.cash <= 0.01 || model.quote == nil)

                    Button {
                        model.manualTrade(.sell)
                    } label: {
                        Label("Sell", systemImage: "arrow.down")
                            .frame(maxWidth: .infinity)
                    }
                    .tint(.red)
                    .disabled(model.portfolio.tokenQuantity <= 0 || model.quote == nil)
                }
                .buttonStyle(.borderedProminent)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var disclaimer: some View {
        Text("Simulation only. No real funds are traded and signals are not financial advice. Crypto is volatile and you can lose money.")
            .font(.caption2)
            .foregroundStyle(.tertiary)
            .multilineTextAlignment(.center)
            .padding(.top, 4)
    }

    // MARK: - Helpers

    private func stat(_ title: String, _ value: String, color: Color = .primary) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            Text(value).font(.headline).foregroundStyle(color)
        }
    }

    private var rsiColor: Color {
        guard let rsi = model.indicators.rsi else { return .primary }
        if rsi >= model.strategy.rsiOverbought { return .red }
        if rsi <= model.strategy.rsiOversold { return .green }
        return .primary
    }

    private var sessionChangePct: Double? {
        guard let first = model.candles.first?.open,
              let last = model.quote?.price ?? model.candles.last?.close,
              first > 0 else { return nil }
        return (last - first) / first * 100
    }
}

/// Simple rounded-rectangle card container.
struct Card<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        content
            .padding()
            .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }
}

#Preview {
    DashboardView().environment(TradeSimModel())
}
