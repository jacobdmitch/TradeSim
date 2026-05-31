import SwiftUI

struct SettingsView: View {
    @Environment(TradeSimModel.self) private var model
    @State private var resetBalance = "23.17"
    @State private var showResetConfirm = false

    var body: some View {
        @Bindable var model = model
        NavigationStack {
            Form {
                Section("Rotation strategy") {
                    Toggle("Auto-rotate in simulation", isOn: $model.rotation.autoRotate)
                    Stepper("Candidates analyzed: \(model.rotation.candidateCount)",
                            value: $model.rotation.candidateCount, in: 4...30)
                    Stepper("Momentum window: \(model.rotation.momentumLookback) bars",
                            value: $model.rotation.momentumLookback, in: 2...24)
                    sliderRow("Entry threshold", value: $model.rotation.enterThresholdPct,
                              range: 0...5, suffix: "%")
                    sliderRow("Rotation threshold", value: $model.rotation.rotationThresholdPct,
                              range: 0...8, suffix: "%")
                    sliderRow("Exit threshold", value: $model.rotation.exitThresholdPct,
                              range: -8...0, suffix: "%")
                }

                Section("Indicators") {
                    Stepper("Fast SMA: \(model.strategy.shortSMA)",
                            value: $model.strategy.shortSMA, in: 2...50)
                    Stepper("Slow SMA: \(model.strategy.longSMA)",
                            value: $model.strategy.longSMA, in: 5...200)
                    Stepper("RSI period: \(model.strategy.rsiPeriod)",
                            value: $model.strategy.rsiPeriod, in: 2...50)
                    sliderRow("RSI overbought", value: $model.strategy.rsiOverbought,
                              range: 55...90, suffix: "", step: 1)
                    sliderRow("RSI oversold", value: $model.strategy.rsiOversold,
                              range: 10...45, suffix: "", step: 1)
                }

                Section("Chart timeframe") {
                    Picker("Granularity", selection: $model.granularity) {
                        ForEach(Granularity.allCases) { Text($0.label).tag($0) }
                    }
                }

                Section("Simulation") {
                    HStack {
                        Text("Starting balance")
                        Spacer()
                        TextField("Balance", text: $resetBalance)
                            .keyboardType(.decimalPad)
                            .multilineTextAlignment(.trailing)
                            .frame(width: 100)
                    }
                    Button("Reset simulation", role: .destructive) { showResetConfirm = true }
                }

                Section("Data") {
                    LabeledContent("Seed holding", value: model.seedBase)
                    LabeledContent("Universe", value: "\(model.stats.count) USD markets")
                    LabeledContent("Rescan", value: "\(Int(model.refreshInterval))s")
                    LabeledContent("Source", value: "Coinbase (public)")
                }

                Section {
                    Text("Paper-trading simulator for education. It pulls live market data but executes no real trades and connects to no account. \"Predicted edge\" is a momentum/trend/RSI heuristic, not a forecast or financial advice. Crypto can lose value rapidly.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Settings")
            .confirmationDialog("Reset the simulation?", isPresented: $showResetConfirm,
                                titleVisibility: .visible) {
                Button("Reset to \(resetBalance)", role: .destructive) {
                    if let bal = Double(resetBalance) { model.resetSimulation(to: bal) }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("Clears all simulated trades and restarts from a \(model.seedBase) holding.")
            }
        }
    }

    private func sliderRow(_ title: String, value: Binding<Double>,
                           range: ClosedRange<Double>, suffix: String, step: Double = 0.5) -> some View {
        VStack(alignment: .leading) {
            Text("\(title): \(String(format: "%.1f", value.wrappedValue))\(suffix)")
            Slider(value: value, in: range, step: step)
        }
    }
}

#Preview {
    SettingsView().environment(TradeSimModel())
}
