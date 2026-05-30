import SwiftUI

struct RotationView: View {
    @Environment(TradeSimModel.self) private var model

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    if let rec = model.latestRecommendation {
                        recommendationCard(rec)
                    }
                    ranksCard
                    explainer
                }
                .padding()
            }
            .navigationTitle("Strategy")
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

    private func recommendationCard(_ rec: RotationRecommendation) -> some View {
        Card {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 12) {
                    Image(systemName: rec.action.systemImage)
                        .font(.system(size: 30)).foregroundStyle(rec.action.color)
                    Text(rec.action.rawValue).font(.title3.bold())
                    Spacer()
                    if rec.action != .hold {
                        Text(Format.pct(rec.edgePct)).font(.headline)
                            .foregroundStyle(rec.action.color)
                    }
                }
                Text(rec.rationale).font(.subheadline).foregroundStyle(.secondary)
                if rec.action != .hold {
                    Button {
                        model.applyLatestRecommendation()
                    } label: {
                        Label("Apply in simulation", systemImage: "play.fill")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent).tint(rec.action.color)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var ranksCard: some View {
        Card {
            VStack(alignment: .leading, spacing: 12) {
                Text("Top Predicted Movers").font(.headline)
                if model.scores.isEmpty {
                    Text(model.isScanning ? "Analyzing candidates…" : "No candidates yet — pull to refresh.")
                        .font(.caption).foregroundStyle(.secondary)
                } else {
                    ForEach(Array(model.scores.enumerated()), id: \.element.id) { idx, score in
                        scoreRow(rank: idx + 1, score: score)
                        if idx < model.scores.count - 1 { Divider() }
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func scoreRow(rank: Int, score: CoinScore) -> some View {
        HStack(spacing: 12) {
            Text("\(rank)").font(.caption.monospacedDigit())
                .foregroundStyle(.secondary).frame(width: 18)
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(score.base).font(.headline)
                    if model.portfolio.position?.base == score.base {
                        Image(systemName: "briefcase.fill").font(.caption2).foregroundStyle(.tint)
                    }
                    Image(systemName: score.trendUp ? "arrow.up.right" : "arrow.down.right")
                        .font(.caption2).foregroundStyle(score.trendUp ? .green : .red)
                }
                Text("24h \(Format.pct(score.change24h)) · RSI \(score.rsi.map { String(format: "%.0f", $0) } ?? "—")")
                    .font(.caption2).foregroundStyle(.secondary)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text("edge").font(.caption2).foregroundStyle(.tertiary)
                Text(Format.pct(score.predictedEdgePct))
                    .font(.subheadline.monospacedDigit())
                    .foregroundStyle(score.predictedEdgePct >= 0 ? .green : .red)
            }
        }
    }

    private var explainer: some View {
        Card {
            VStack(alignment: .leading, spacing: 6) {
                Text("How this works").font(.headline)
                Text("Each scan ranks the most liquid Coinbase USD movers, then deep-analyzes the top candidates with momentum, SMA trend and RSI to estimate a short-term \"edge.\" The engine recommends entering, rotating, or retreating to cash only when the edge beats the current holding by more than the round-trip trading cost.")
                    .font(.caption).foregroundStyle(.secondary)
                Text("This is a heuristic screen, not a forecast or financial advice.")
                    .font(.caption2).foregroundStyle(.tertiary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

#Preview {
    RotationView().environment(TradeSimModel())
}
