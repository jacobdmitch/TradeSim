import SwiftUI
import Charts

struct ChartView: View {
    @Environment(TradeSimModel.self) private var model

    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                granularityPicker

                if model.candles.isEmpty {
                    ContentUnavailableView(
                        "No data yet",
                        systemImage: "chart.xyaxis.line",
                        description: Text("Pull to refresh on the Dashboard.")
                    )
                    .frame(maxHeight: .infinity)
                } else {
                    priceChart
                    legend
                    Spacer()
                }
            }
            .padding()
            .navigationTitle("\(model.symbol) Chart")
        }
    }

    private var granularityPicker: some View {
        Picker("Granularity", selection: Binding(
            get: { model.granularity },
            set: { model.granularity = $0; Task { await model.refresh() } }
        )) {
            ForEach(Granularity.allCases) { g in
                Text(g.label).tag(g)
            }
        }
        .pickerStyle(.segmented)
    }

    private var priceChart: some View {
        let closes = model.candles.map(\.close)
        let shortSMA = movingAverage(closes, period: model.strategy.shortSMA)
        let longSMA = movingAverage(closes, period: model.strategy.longSMA)

        return Chart {
            ForEach(model.candles) { candle in
                LineMark(
                    x: .value("Time", candle.time),
                    y: .value("Price", candle.close),
                    series: .value("Series", "Price")
                )
                .foregroundStyle(.blue)
            }
            ForEach(Array(model.candles.enumerated()), id: \.offset) { idx, candle in
                if let v = shortSMA[idx] {
                    LineMark(
                        x: .value("Time", candle.time),
                        y: .value("Price", v),
                        series: .value("Series", "Fast SMA")
                    )
                    .foregroundStyle(.green)
                }
                if let v = longSMA[idx] {
                    LineMark(
                        x: .value("Time", candle.time),
                        y: .value("Price", v),
                        series: .value("Series", "Slow SMA")
                    )
                    .foregroundStyle(.orange)
                }
            }
            // Mark simulated trades on the chart.
            ForEach(model.trades) { trade in
                PointMark(
                    x: .value("Time", trade.timestamp),
                    y: .value("Price", trade.price)
                )
                .foregroundStyle(trade.action.color)
                .symbolSize(80)
            }
        }
        .chartYScale(domain: .automatic(includesZero: false))
        .frame(height: 320)
    }

    private var legend: some View {
        HStack(spacing: 16) {
            legendItem(.blue, "Price")
            legendItem(.green, "SMA \(model.strategy.shortSMA)")
            legendItem(.orange, "SMA \(model.strategy.longSMA)")
        }
        .font(.caption)
    }

    private func legendItem(_ color: Color, _ label: String) -> some View {
        HStack(spacing: 4) {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(label).foregroundStyle(.secondary)
        }
    }

    /// Returns an array aligned to `values`, with the SMA at each index (nil
    /// until enough history exists).
    private func movingAverage(_ values: [Double], period: Int) -> [Double?] {
        guard period > 0 else { return Array(repeating: nil, count: values.count) }
        var result = [Double?](repeating: nil, count: values.count)
        guard values.count >= period else { return result }
        var windowSum = values[0..<period].reduce(0, +)
        result[period - 1] = windowSum / Double(period)
        for i in period..<values.count {
            windowSum += values[i] - values[i - period]
            result[i] = windowSum / Double(period)
        }
        return result
    }
}

#Preview {
    ChartView().environment(TradeSimModel())
}
