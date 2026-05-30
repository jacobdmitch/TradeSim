import SwiftUI

struct DashboardView: View {
    @Environment(TradeSimModel.self) private var model

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    valueCard
                    if let rec = model.latestRecommendation {
                        recommendationCard(rec)
                    }
                    holdingCard
                    if !model.holdingCandles.isEmpty {
                        Card {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("\(model.portfolio.holdingLabel) — \(model.granularity.label)")
                                    .font(.headline)
                                PriceChartView(candles: model.holdingCandles,
                                               shortPeriod: model.strategy.shortSMA,
                                               longPeriod: model.strategy.longSMA,
                                               trades: model.trades.filter { $0.base == model.portfolio.position?.base })
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    disclaimer
                }
                .padding()
            }
            .navigationTitle("Portfolio")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { Task { await model.scan() } } label: {
                        if model.isScanning { ProgressView() }
                        else { Image(systemName: "arrow.clockwise") }
                    }
                }
            }
            .refreshable { await model.scan() }
        }
    }

    // MARK: - Cards

    private var valueCard: some View {
        Card {
            VStack(alignment: .leading, spacing: 6) {
                Text("Total Value").font(.subheadline).foregroundStyle(.secondary)
                Text(Format.usd(model.portfolio.totalValue))
                    .font(.system(size: 40, weight: .bold, design: .rounded))
                HStack(spacing: 12) {
                    Text(Format.signedUSD(model.totalReturn))
                    Text("(\(Format.pct(model.totalReturnPct)))")
                }
                .font(.headline)
                .foregroundStyle(model.totalReturn >= 0 ? .green : .red)
                Text("Started from \(Format.usd(model.startingBalance)) in \(model.seedBase)")
                    .font(.caption).foregroundStyle(.secondary)
                if let updated = model.lastUpdated {
                    Text("Scanned \(Format.shortTime(updated)) · \(model.stats.count) markets")
                        .font(.caption2).foregroundStyle(.tertiary)
                }
                if let err = model.lastError {
                    Label(err, systemImage: "exclamationmark.triangle.fill")
                        .font(.caption).foregroundStyle(.orange)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func recommendationCard(_ rec: RotationRecommendation) -> some View {
        Card {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 12) {
                    Image(systemName: rec.action.systemImage)
                        .font(.system(size: 32)).foregroundStyle(rec.action.color)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(recommendationTitle(rec)).font(.headline)
                        Text(Format.time(rec.timestamp)).font(.caption2).foregroundStyle(.tertiary)
                    }
                    Spacer()
                }
                Text(rec.rationale).font(.subheadline).foregroundStyle(.secondary)
                if rec.action != .hold {
                    Button {
                        model.applyLatestRecommendation()
                    } label: {
                        Label("Apply in simulation", systemImage: "play.fill")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(rec.action.color)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var holdingCard: some View {
        Card {
            VStack(alignment: .leading, spacing: 12) {
                Text("Current Holding").font(.headline)
                if let pos = model.portfolio.position {
                    HStack {
                        stat("Coin", pos.base)
                        Spacer()
                        stat("Amount", Format.tokens(pos.quantity))
                        Spacer()
                        stat("Value", Format.usd(pos.value))
                    }
                    HStack {
                        stat("Price", Format.price(pos.markPrice))
                        Spacer()
                        stat("Cost basis", Format.usd(pos.costBasisUSD))
                        Spacer()
                        stat("Unrealized",
                             Format.signedUSD(pos.value - pos.costBasisUSD),
                             color: pos.value - pos.costBasisUSD >= 0 ? .green : .red)
                    }
                    Button("Move to cash (USD)", role: .destructive) { model.moveToCash() }
                        .font(.subheadline)
                } else {
                    HStack {
                        stat("Holding", "USD cash")
                        Spacer()
                        stat("Cash", Format.usd(model.portfolio.cash))
                    }
                    Text("In cash — waiting for an entry signal.")
                        .font(.caption).foregroundStyle(.secondary)
                }
                HStack {
                    stat("Realized P/L",
                         Format.signedUSD(model.realizedPnL),
                         color: model.realizedPnL >= 0 ? .green : .red)
                    Spacer()
                    stat("Trades", "\(model.trades.count)")
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var disclaimer: some View {
        Text("Simulation only — no real funds are traded. \"Predicted edge\" is a momentum/trend heuristic, not a forecast or financial advice. Crypto is volatile and you can lose money.")
            .font(.caption2).foregroundStyle(.tertiary)
            .multilineTextAlignment(.center).padding(.top, 4)
    }

    // MARK: - Helpers

    private func recommendationTitle(_ rec: RotationRecommendation) -> String {
        switch rec.action {
        case .enter:  return "Enter \(rec.toBase ?? "")"
        case .rotate: return "Rotate \(rec.fromBase ?? "") → \(rec.toBase ?? "")"
        case .exit:   return "Exit \(rec.fromBase ?? "") to cash"
        case .hold:   return "Hold \(rec.fromBase ?? "position")"
        }
    }

    private func stat(_ title: String, _ value: String, color: Color = .primary) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            Text(value).font(.headline).foregroundStyle(color)
        }
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
