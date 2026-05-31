import SwiftUI

struct CoinDetailView: View {
    @Environment(TradeSimModel.self) private var model
    let stat: MarketStat

    @State private var candles: [Candle] = []
    @State private var loading = true

    private var isHeld: Bool { model.portfolio.position?.base == stat.base }
    private var score: CoinScore? { model.score(forBase: stat.base) }

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                headerCard
                if let score { scoreCard(score) }
                Card {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Price — \(model.granularity.label)").font(.headline)
                        if loading {
                            ProgressView().frame(maxWidth: .infinity).frame(height: 260)
                        } else {
                            PriceChartView(candles: candles,
                                           shortPeriod: model.strategy.shortSMA,
                                           longPeriod: model.strategy.longSMA,
                                           trades: model.trades.filter { $0.base == stat.base })
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                actionButton
                Text("Simulated action only — no real order is placed.")
                    .font(.caption2).foregroundStyle(.tertiary)
            }
            .padding()
        }
        .navigationTitle(stat.base)
        .navigationBarTitleDisplayMode(.inline)
        .task {
            loading = true
            candles = await model.fetchCandles(for: stat.productID)
            loading = false
        }
    }

    private var headerCard: some View {
        Card {
            VStack(alignment: .leading, spacing: 6) {
                Text(stat.productID).font(.caption).foregroundStyle(.secondary)
                HStack(alignment: .firstTextBaseline, spacing: 10) {
                    Text(Format.price(stat.last))
                        .font(.system(size: 34, weight: .bold, design: .rounded))
                    Text(Format.pct(stat.changePct))
                        .font(.headline)
                        .foregroundStyle(stat.changePct >= 0 ? .green : .red)
                }
                HStack(spacing: 16) {
                    label("24h High", Format.price(stat.high))
                    label("24h Low", Format.price(stat.low))
                    label("Volume", Format.compactUSD(stat.volumeUSD))
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func scoreCard(_ score: CoinScore) -> some View {
        Card {
            VStack(alignment: .leading, spacing: 10) {
                Text("Predicted Edge").font(.headline)
                Text(Format.pct(score.predictedEdgePct))
                    .font(.system(size: 28, weight: .bold, design: .rounded))
                    .foregroundStyle(score.predictedEdgePct >= 0 ? .green : .red)
                HStack(spacing: 16) {
                    label("Momentum", Format.pct(score.momentum))
                    label("RSI", score.rsi.map { String(format: "%.0f", $0) } ?? "—")
                    label("Trend", score.trendUp ? "Up" : "Down")
                }
                Text("Heuristic blend of momentum, trend and RSI — a screen, not a forecast.")
                    .font(.caption2).foregroundStyle(.tertiary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    @ViewBuilder private var actionButton: some View {
        if isHeld {
            Button("Move to cash (USD)", role: .destructive) { model.moveToCash() }
                .buttonStyle(.bordered)
        } else {
            Button {
                model.manualBuy(base: stat.base)
            } label: {
                Label(model.portfolio.position == nil ? "Buy \(stat.base)" : "Rotate into \(stat.base)",
                      systemImage: model.portfolio.position == nil ? "arrow.down" : "arrow.triangle.2.circlepath")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(.green)
        }
    }

    private func label(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.caption2).foregroundStyle(.secondary)
            Text(value).font(.subheadline)
        }
    }
}
