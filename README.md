# TradeSim — DIMO Paper-Trading Simulator

A native SwiftUI iPhone app that pulls **live DIMO prices** from Coinbase's
public API, runs a configurable technical-analysis strategy, sends **trade
alerts** as push notifications, and runs a **paper-trading simulation** so you
can see how acting on those alerts would have grown a starting balance —
without risking real money.

> ⚠️ **This is a simulator and an educational tool.** It executes **no real
> trades** and connects to **no exchange account**. The signals are simple
> technical indicators, *not* financial advice. Crypto is volatile and you can
> lose money. Nothing here guarantees a profit.

---

## What it does

- **Live data** — spot price + historical candles for `DIMO-USD` straight from
  Coinbase's public (no-auth) endpoints.
- **Signal engine** — a moving-average crossover gated by RSI:
  - **BUY** when the fast SMA crosses above the slow SMA and RSI isn't overbought.
  - **SELL** when the fast SMA crosses below the slow SMA, or RSI is overbought.
  - **HOLD** otherwise.
- **Trade alerts** — actionable signals fire a local push notification
  (`BUY DIMO` / `SELL DIMO`) so you get pinged on your phone.
- **Paper portfolio** — starts with your **$23.17** and (optionally) auto-applies
  every alert, tracking cash, holdings, realized P/L and total return. You can
  also tap **Buy/Sell** manually to simulate trades yourself.
- **Chart** — price with both SMAs overlaid and your simulated trades marked.
- **Tunable strategy** — change SMA periods, RSI period and thresholds, the
  starting balance, and reset the simulation any time. Everything persists
  between launches.

## Project layout

```
TradeSim/
├── TradeSimApp.swift           App entry, polling lifecycle, notification setup
├── Models/                     Candle, Quote, alerts, trades, portfolio
├── Services/
│   ├── MarketDataService.swift Coinbase spot + candles
│   ├── SignalEngine.swift      SMA / RSI indicators + signal logic
│   ├── Simulator.swift         Paper-trading engine (with ~0.6% fee model)
│   ├── NotificationManager.swift  Local push notifications
│   └── PersistenceStore.swift  Saves state to UserDefaults
├── ViewModels/
│   └── TradeSimModel.swift     Observable app state + polling loop
└── Views/                      Dashboard, Chart, Alerts, Settings
```

The Xcode project uses a **file-system-synchronized group**, so any file you add
under `TradeSim/` is picked up automatically — no need to edit the project file.

---

## Build it (Xcode)

Requirements: **macOS with Xcode 16+** (the project targets **iOS 17+**).

1. Open `TradeSim.xcodeproj` in Xcode.
2. Select the **TradeSim** scheme and an iPhone simulator (or your device).
3. Press **⌘R** to run.

No third-party dependencies — it uses only SwiftUI, Swift Charts, and
UserNotifications. The API endpoints are HTTPS, so no App Transport Security
exceptions are needed.

---

## Publish to your own phone via TestFlight

You need a (free or paid) **Apple Developer** account. TestFlight distribution
requires the **paid Apple Developer Program** ($99/yr); for purely local
self-hosting you can instead just run on your device from Xcode with a free
account (the build expires after 7 days).

### One-time setup
1. In Xcode: **Settings → Accounts** → add your Apple ID.
2. Select the project → **TradeSim** target → **Signing & Capabilities**.
3. Set **Team** to your account. The bundle id defaults to
   `com.jacobdmitch.TradeSim` — change it if that id is taken
   (it must be globally unique).

### Ship a TestFlight build
1. Create the app record at <https://appstoreconnect.apple.com> →
   **My Apps → +** with the same bundle id.
2. In Xcode pick **Any iOS Device (arm64)** as the run destination.
3. **Product → Archive**.
4. In the **Organizer** window that opens, select the archive →
   **Distribute App → TestFlight (Internal Only)** → upload.
5. In App Store Connect → **TestFlight**, add yourself as an **Internal Tester**.
6. Install **TestFlight** from the App Store on your iPhone and accept the build.

Each archive uploaded this way is good for 90 days. Bump **MARKETING_VERSION**
or **CURRENT_PROJECT_VERSION** in the target build settings for each new upload.

### Run directly without TestFlight (free account)
Plug in your iPhone, select it as the destination, press **⌘R**. Trust the
developer cert under **Settings → General → VPN & Device Management** on the
phone. This build lasts 7 days before you need to re-run from Xcode.

---

## Notes & ideas for next steps

- **Background alerts:** the app polls and notifies while open or recently
  backgrounded. For always-on alerts even when the app is closed, add
  `BGAppRefreshTask` (BackgroundTasks framework) — left out of v1 to keep the
  build dependency-free and reliable.
- **Strategy:** SMA-crossover + RSI is a starting point. You could add MACD,
  Bollinger Bands, or a trailing stop in `SignalEngine.swift`.
- **Backtesting:** the `Simulator` is pure and side-effect-free, so it's easy to
  run it across the full candle history to backtest before going live.
