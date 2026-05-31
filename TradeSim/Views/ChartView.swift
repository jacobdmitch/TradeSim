import SwiftUI
import Charts

/// Reusable line chart of closing prices with two SMA overlays and optional
/// trade markers. Used on the dashboard and in the coin detail screen.
struct PriceChartView: View {
    let candles: [Candle]
    var shortPeriod: Int = 9
    var longPeriod: Int = 21
    var trades: [SimulatedTrade] = []
    var height: CGFloat = 260

    var body: some View {
        if candles.isEmpty {
            ContentUnavailableView("No chart data", systemImage: "chart.xyaxis.line")
                .frame(height: height)
        } else {
            chart.frame(height: height)
            legend
        }
    }

    private var chart: some View {
        let closes = candles.map(\.close)
        let shortSMA = Self.movingAverage(closes, period: shortPeriod)
        let longSMA = Self.movingAverage(closes, period: longPeriod)

        return Chart {
            ForEach(candles) { candle in
                LineMark(x: .value("Time", candle.time),
                         y: .value("Price", candle.close),
                         series: .value("Series", "Price"))
                .foregroundStyle(.blue)
            }
            ForEach(Array(candles.enumerated()), id: \.offset) { idx, candle in
                if let v = shortSMA[idx] {
                    LineMark(x: .value("Time", candle.time), y: .value("Price", v),
                             series: .value("Series", "Fast SMA"))
                    .foregroundStyle(.green)
                }
                if let v = longSMA[idx] {
                    LineMark(x: .value("Time", candle.time), y: .value("Price", v),
                             series: .value("Series", "Slow SMA"))
                    .foregroundStyle(.orange)
                }
            }
            ForEach(trades) { trade in
                PointMark(x: .value("Time", trade.timestamp),
                          y: .value("Price", trade.price))
                .foregroundStyle(trade.action.color)
                .symbolSize(70)
            }
        }
        .chartYScale(domain: .automatic(includesZero: false))
    }

    private var legend: some View {
        HStack(spacing: 16) {
            legendItem(.blue, "Price")
            legendItem(.green, "SMA \(shortPeriod)")
            legendItem(.orange, "SMA \(longPeriod)")
        }
        .font(.caption)
    }

    private func legendItem(_ color: Color, _ label: String) -> some View {
        HStack(spacing: 4) {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(label).foregroundStyle(.secondary)
        }
    }

    /// SMA aligned to `values` (nil until enough history exists).
    static func movingAverage(_ values: [Double], period: Int) -> [Double?] {
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
