import SwiftUI

/// Visual test suite for all TradeSim visual assets
/// Use this to quickly preview all visual components in one place
struct VisualTestSuite: View {
    @State private var selectedTab = 0
    
    var body: some View {
        TabView(selection: $selectedTab) {
            // Tab 1: Loading Screen
            loadingScreenTest
                .tabItem {
                    Label("Loading", systemImage: "hourglass")
                }
                .tag(0)
            
            // Tab 2: App Icons
            iconSizesTest
                .tabItem {
                    Label("Icons", systemImage: "app.fill")
                }
                .tag(1)
            
            // Tab 3: Home Screen Preview
            homeScreenTest
                .tabItem {
                    Label("Home", systemImage: "house.fill")
                }
                .tag(2)
            
            // Tab 4: Color Palette
            colorPaletteTest
                .tabItem {
                    Label("Colors", systemImage: "paintpalette.fill")
                }
                .tag(3)
        }
    }
    
    // MARK: - Loading Screen Test
    
    private var loadingScreenTest: some View {
        VStack(spacing: 20) {
            Text("Loading Screen Preview")
                .font(.title.bold())
                .padding()
            
            Text("This is what users see when launching the app")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            
            // Show actual loading view
            LoadingView()
                .frame(maxWidth: .infinity, maxHeight: 600)
                .clipShape(RoundedRectangle(cornerRadius: 20))
                .shadow(radius: 10)
                .padding()
            
            VStack(alignment: .leading, spacing: 8) {
                checkItem("Animated rotating icon", true)
                checkItem("Pulsing background circle", true)
                checkItem("Animated chart bars", true)
                checkItem("Loading text visible", true)
                checkItem("Smooth transitions", true)
            }
            .padding()
            
            Spacer()
        }
    }
    
    // MARK: - Icon Sizes Test
    
    private var iconSizesTest: some View {
        ScrollView {
            VStack(spacing: 30) {
                Text("App Icon Sizes")
                    .font(.title.bold())
                    .padding(.top)
                
                Text("Check clarity at each size")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                
                // Large icon
                VStack(spacing: 12) {
                    Text("App Store Icon")
                        .font(.headline)
                    AppIconGenerator(size: 300)
                        .clipShape(RoundedRectangle(cornerRadius: 66, style: .continuous))
                        .shadow(radius: 10)
                    Text("1024×1024 pixels")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                
                // Grid of smaller sizes
                LazyVGrid(columns: [
                    GridItem(.flexible()),
                    GridItem(.flexible()),
                    GridItem(.flexible())
                ], spacing: 25) {
                    iconTest(size: 180, label: "iPhone App\n60pt @3x", check: true)
                    iconTest(size: 120, label: "Spotlight\n40pt @3x", check: true)
                    iconTest(size: 87, label: "Settings\n29pt @3x", check: true)
                    iconTest(size: 80, label: "Spotlight\n40pt @2x", check: true)
                    iconTest(size: 60, label: "Notification\n20pt @3x", check: false)
                    iconTest(size: 40, label: "Notification\n20pt @2x", check: false)
                }
                .padding()
                
                Text("✓ = Clear and recognizable")
                    .font(.caption)
                    .foregroundStyle(.green)
                
                Spacer(minLength: 40)
            }
        }
    }
    
    private func iconTest(size: CGFloat, label: String, check: Bool) -> some View {
        VStack(spacing: 8) {
            ZStack(alignment: .topTrailing) {
                AppIconGenerator(size: size)
                    .clipShape(RoundedRectangle(cornerRadius: size * 0.2237, style: .continuous))
                    .shadow(color: .black.opacity(0.1), radius: 3)
                
                if check {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundStyle(.white, .green)
                        .font(.system(size: size * 0.25))
                        .offset(x: 5, y: -5)
                }
            }
            
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(height: 35)
        }
    }
    
    // MARK: - Home Screen Test
    
    private var homeScreenTest: some View {
        VStack(spacing: 20) {
            Text("Home Screen Preview")
                .font(.title.bold())
                .padding()
            
            Text("How your icon looks among other apps")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            
            // iPhone home screen simulation
            ZStack {
                // Background
                LinearGradient(
                    colors: [.blue.opacity(0.3), .purple.opacity(0.3)],
                    startPoint: .top,
                    endPoint: .bottom
                )
                
                VStack(spacing: 40) {
                    Spacer()
                    
                    // Apps grid
                    VStack(spacing: 30) {
                        // Row 1
                        HStack(spacing: 30) {
                            appIcon(AppIconGenerator(size: 80), name: "TradeSim", highlight: true)
                            demoAppIcon(.red, "music.note", "Music")
                            demoAppIcon(.blue, "safari", "Safari")
                            demoAppIcon(.green, "message.fill", "Messages")
                        }
                        
                        // Row 2
                        HStack(spacing: 30) {
                            demoAppIcon(.orange, "gear", "Settings")
                            demoAppIcon(.purple, "photo", "Photos")
                            demoAppIcon(.cyan, "heart.fill", "Health")
                            demoAppIcon(.indigo, "envelope.fill", "Mail")
                        }
                        
                        // Row 3
                        HStack(spacing: 30) {
                            demoAppIcon(.pink, "calendar", "Calendar")
                            demoAppIcon(.yellow, "note.text", "Notes")
                            demoAppIcon(.brown, "book.fill", "Books")
                            demoAppIcon(.teal, "map.fill", "Maps")
                        }
                    }
                    
                    Spacer()
                    
                    // Dock
                    HStack(spacing: 30) {
                        demoAppIcon(.blue, "phone.fill", "Phone")
                        demoAppIcon(.green, "bubble.left.fill", "Messages")
                        demoAppIcon(.blue, "safari", "Safari")
                        demoAppIcon(.blue, "music.note", "Music")
                    }
                    .padding(.vertical, 15)
                    .padding(.horizontal, 20)
                    .background(.ultraThinMaterial)
                    .clipShape(RoundedRectangle(cornerRadius: 25))
                    .padding(.horizontal, 20)
                    .padding(.bottom, 30)
                }
            }
            .frame(maxWidth: 400, maxHeight: 600)
            .clipShape(RoundedRectangle(cornerRadius: 30))
            .shadow(radius: 20)
            .padding()
            
            VStack(alignment: .leading, spacing: 8) {
                checkItem("Icon is visible and clear", true)
                checkItem("Stands out from other apps", true)
                checkItem("Professional appearance", true)
                checkItem("Rounded corners look good", true)
            }
            .padding()
            
            Spacer()
        }
    }
    
    private func appIcon(_ icon: some View, name: String, highlight: Bool = false) -> some View {
        VStack(spacing: 6) {
            icon
                .frame(width: 80, height: 80)
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .stroke(highlight ? Color.yellow : Color.clear, lineWidth: 3)
                )
            
            Text(name)
                .font(.caption)
                .foregroundStyle(.white)
                .shadow(color: .black.opacity(0.3), radius: 2)
        }
    }
    
    private func demoAppIcon(_ color: Color, _ symbol: String, _ name: String) -> some View {
        VStack(spacing: 6) {
            ZStack {
                color
                Image(systemName: symbol)
                    .font(.title)
                    .foregroundStyle(.white)
            }
            .frame(width: 80, height: 80)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            
            Text(name)
                .font(.caption)
                .foregroundStyle(.white)
                .shadow(color: .black.opacity(0.3), radius: 2)
        }
    }
    
    // MARK: - Color Palette Test
    
    private var colorPaletteTest: some View {
        ScrollView {
            VStack(spacing: 30) {
                Text("TradeSim Color Palette")
                    .font(.title.bold())
                    .padding(.top)
                
                Text("Official brand colors")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                
                // Primary colors
                VStack(spacing: 20) {
                    Text("Primary Colors")
                        .font(.headline)
                    
                    colorSwatch(
                        color: Color(red: 0, green: 0.48, blue: 1.0),
                        name: "Primary Blue",
                        hex: "#007AFF",
                        rgb: "0, 122, 255",
                        usage: "Main brand color, trust, stability"
                    )
                    
                    colorSwatch(
                        color: Color(red: 0.35, green: 0.78, blue: 0.98),
                        name: "Accent Cyan",
                        hex: "#5AC8FA",
                        rgb: "90, 200, 250",
                        usage: "Energy, growth, digital"
                    )
                    
                    colorSwatch(
                        color: .white,
                        name: "Symbol White",
                        hex: "#FFFFFF",
                        rgb: "255, 255, 255",
                        usage: "Icons, text, maximum contrast",
                        darkBorder: true
                    )
                }
                .padding()
                
                // Gradient showcase
                VStack(spacing: 20) {
                    Text("Brand Gradient")
                        .font(.headline)
                    
                    LinearGradient(
                        colors: [
                            Color(red: 0, green: 0.48, blue: 1.0),
                            Color(red: 0.35, green: 0.78, blue: 0.98)
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                    .frame(height: 200)
                    .clipShape(RoundedRectangle(cornerRadius: 20))
                    .overlay(
                        Text("Used in icon and loading screen")
                            .font(.caption)
                            .foregroundStyle(.white)
                            .padding()
                    )
                }
                .padding()
                
                // Usage examples
                VStack(spacing: 20) {
                    Text("Color Usage Examples")
                        .font(.headline)
                    
                    HStack(spacing: 15) {
                        // Positive
                        VStack(spacing: 8) {
                            Image(systemName: "arrow.up.circle.fill")
                                .font(.system(size: 40))
                                .foregroundStyle(.green)
                            Text("Gains")
                                .font(.caption)
                        }
                        
                        // Negative
                        VStack(spacing: 8) {
                            Image(systemName: "arrow.down.circle.fill")
                                .font(.system(size: 40))
                                .foregroundStyle(.red)
                            Text("Losses")
                                .font(.caption)
                        }
                        
                        // Neutral
                        VStack(spacing: 8) {
                            Image(systemName: "minus.circle.fill")
                                .font(.system(size: 40))
                                .foregroundStyle(.gray)
                            Text("Neutral")
                                .font(.caption)
                        }
                        
                        // Info
                        VStack(spacing: 8) {
                            Image(systemName: "info.circle.fill")
                                .font(.system(size: 40))
                                .foregroundStyle(.blue)
                            Text("Info")
                                .font(.caption)
                        }
                    }
                }
                .padding()
                
                Spacer(minLength: 40)
            }
        }
    }
    
    private func colorSwatch(color: Color, name: String, hex: String, rgb: String, usage: String, darkBorder: Bool = false) -> some View {
        HStack(spacing: 15) {
            // Color sample
            RoundedRectangle(cornerRadius: 12)
                .fill(color)
                .frame(width: 80, height: 80)
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(darkBorder ? Color.gray : Color.clear, lineWidth: 1)
                )
                .shadow(radius: 3)
            
            // Color info
            VStack(alignment: .leading, spacing: 4) {
                Text(name)
                    .font(.headline)
                Text(hex)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text("RGB: \(rgb)")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
                Text(usage)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .italic()
            }
            
            Spacer()
        }
        .padding()
        .background(.thinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
    
    // MARK: - Helpers
    
    private func checkItem(_ text: String, _ checked: Bool) -> some View {
        HStack(spacing: 10) {
            Image(systemName: checked ? "checkmark.circle.fill" : "circle")
                .foregroundStyle(checked ? .green : .gray)
            Text(text)
                .font(.subheadline)
            Spacer()
        }
    }
}

#Preview {
    VisualTestSuite()
}
