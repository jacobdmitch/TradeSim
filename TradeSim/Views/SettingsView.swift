import SwiftUI

struct SettingsView: View {
    @Environment(TradeSimModel.self) private var model
    @State private var resetBalance = "23.17"
    @State private var showResetConfirm = false

    var body: some View {
        @Bindable var model = model
        NavigationStack {
            Form {
                Section("Strategy") {
                    Stepper("Fast SMA: \(model.strategy.shortSMA)",
                            value: $model.strategy.shortSMA, in: 2...50)
                    Stepper("Slow SMA: \(model.strategy.longSMA)",
                            value: $model.strategy.longSMA, in: 5...200)
                    Stepper("RSI period: \(model.strategy.rsiPeriod)",
                            value: $model.strategy.rsiPeriod, in: 2...50)
                    VStack(alignment: .leading) {
                        Text("RSI overbought: \(Int(model.strategy.rsiOverbought))")
                        Slider(value: $model.strategy.rsiOverbought, in: 55...90, step: 1)
                    }
                    VStack(alignment: .leading) {
                        Text("RSI oversold: \(Int(model.strategy.rsiOversold))")
                        Slider(value: $model.strategy.rsiOversold, in: 10...45, step: 1)
                    }
                }

                Section("Simulation") {
                    Toggle("Auto-apply alerts to paper portfolio",
                           isOn: $model.autoTradeSimulation)
                    HStack {
                        Text("Starting balance")
                        Spacer()
                        TextField("Balance", text: $resetBalance)
                            .keyboardType(.decimalPad)
                            .multilineTextAlignment(.trailing)
                            .frame(width: 100)
                    }
                    Button("Reset simulation", role: .destructive) {
                        showResetConfirm = true
                    }
                }

                Section("Data") {
                    LabeledContent("Symbol", value: model.symbol)
                    LabeledContent("Product", value: model.productID)
                    LabeledContent("Refresh", value: "\(Int(model.refreshInterval))s")
                    LabeledContent("Source", value: "Coinbase (public)")
                }

                Section {
                    Text("This is a paper-trading simulator for education. It pulls live prices but executes no real trades. Technical signals are not financial advice; crypto can lose value rapidly.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Settings")
            .confirmationDialog("Reset the simulation?",
                                isPresented: $showResetConfirm,
                                titleVisibility: .visible) {
                Button("Reset to \(resetBalance)", role: .destructive) {
                    if let bal = Double(resetBalance) { model.resetSimulation(to: bal) }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("This clears all simulated trades and starts over.")
            }
        }
    }
}

#Preview {
    SettingsView().environment(TradeSimModel())
}
