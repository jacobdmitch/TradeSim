import SwiftUI

struct MarketsView: View {
    @Environment(TradeSimModel.self) private var model
    @State private var query = ""
    @State private var sort: Sort = .change

    enum Sort: String, CaseIterable, Identifiable {
        case change = "% Change"
        case volume = "Volume"
        case price = "Price"
        var id: String { rawValue }
    }

    private var rows: [MarketStat] {
        let base: [MarketStat]
        switch sort {
        case .change: base = model.stats.sorted { $0.changePct > $1.changePct }
        case .volume: base = model.stats.sorted { $0.volumeUSD > $1.volumeUSD }
        case .price:  base = model.stats.sorted { $0.last > $1.last }
        }
        guard !query.isEmpty else { return base }
        return base.filter { $0.base.localizedCaseInsensitiveContains(query) }
    }

    var body: some View {
        NavigationStack {
            Group {
                if model.stats.isEmpty {
                    ContentUnavailableView(
                        model.isScanning ? "Scanning markets…" : "No market data",
                        systemImage: "antenna.radiowaves.left.and.right",
                        description: Text("Pull to refresh.")
                    )
                } else {
                    List {
                        Section {
                            Picker("Sort", selection: $sort) {
                                ForEach(Sort.allCases) { Text($0.rawValue).tag($0) }
                            }
                            .pickerStyle(.segmented)
                            .listRowSeparator(.hidden)
                        }
                        Section("\(rows.count) USD markets") {
                            ForEach(rows) { stat in
                                NavigationLink {
                                    CoinDetailView(stat: stat)
                                } label: {
                                    MarketRow(stat: stat,
                                              isHeld: model.portfolio.position?.base == stat.base)
                                }
                            }
                        }
                    }
                    .listStyle(.plain)
                }
            }
            .navigationTitle("Markets")
            .searchable(text: $query, prompt: "Search coins")
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
}

struct MarketRow: View {
    let stat: MarketStat
    var isHeld: Bool = false

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(stat.base).font(.headline)
                    if isHeld {
                        Image(systemName: "briefcase.fill")
                            .font(.caption2).foregroundStyle(.tint)
                    }
                }
                Text("Vol \(Format.compactUSD(stat.volumeUSD))")
                    .font(.caption2).foregroundStyle(.secondary)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text(Format.price(stat.last)).font(.subheadline.monospacedDigit())
                Text(Format.pct(stat.changePct))
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(stat.changePct >= 0 ? .green : .red)
            }
        }
    }
}

#Preview {
    MarketsView().environment(TradeSimModel())
}
