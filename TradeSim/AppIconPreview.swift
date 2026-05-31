import SwiftUI

/// Preview tool to visualize app icon designs at different sizes
/// Use this to test how your icon looks before creating final assets
struct AppIconPreview: View {
    var body: some View {
        ScrollView {
            VStack(spacing: 40) {
                Text("TradeSim App Icon Preview")
                    .font(.title.bold())
                    .padding(.top)
                
                // Large preview
                VStack(spacing: 12) {
                    Text("App Store (1024×1024)")
                        .font(.headline)
                    iconDesign
                        .frame(width: 300, height: 300)
                        .clipShape(RoundedRectangle(cornerRadius: 66, style: .continuous))
                        .shadow(color: .black.opacity(0.2), radius: 20, x: 0, y: 10)
                }
                
                // Size comparison grid
                VStack(spacing: 20) {
                    Text("Size Preview")
                        .font(.headline)
                    
                    LazyVGrid(columns: [
                        GridItem(.flexible()),
                        GridItem(.flexible()),
                        GridItem(.flexible())
                    ], spacing: 30) {
                        iconAtSize(180, label: "iPhone App\n60pt @3x")
                        iconAtSize(120, label: "Spotlight\n40pt @3x")
                        iconAtSize(87, label: "Settings\n29pt @3x")
                        iconAtSize(80, label: "Spotlight\n40pt @2x")
                        iconAtSize(60, label: "Notification\n20pt @3x")
                        iconAtSize(40, label: "Notification\n20pt @2x")
                    }
                    .padding()
                }
                
                // Alternative designs
                VStack(spacing: 20) {
                    Text("Alternative Color Schemes")
                        .font(.headline)
                    
                    HStack(spacing: 20) {
                        iconDesign
                            .frame(width: 120, height: 120)
                            .clipShape(RoundedRectangle(cornerRadius: 26, style: .continuous))
                        
                        alternativeIcon(colors: [.purple, .pink], symbol: "chart.bar.fill")
                            .frame(width: 120, height: 120)
                            .clipShape(RoundedRectangle(cornerRadius: 26, style: .continuous))
                        
                        alternativeIcon(colors: [.green, .mint], symbol: "arrow.triangle.2.circlepath")
                            .frame(width: 120, height: 120)
                            .clipShape(RoundedRectangle(cornerRadius: 26, style: .continuous))
                    }
                    
                    Text("Blue/Cyan (Recommended) • Purple/Pink • Green/Mint")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .padding()
                
                // Home screen preview
                VStack(spacing: 12) {
                    Text("iPhone Home Screen Preview")
                        .font(.headline)
                    
                    homeScreenPreview
                }
                .padding()
            }
            .padding(.bottom, 40)
        }
    }
    
    // MARK: - Main Icon Design
    
    private var iconDesign: some View {
        ZStack {
            // Gradient background
            LinearGradient(
                colors: [
                    Color(red: 0, green: 0.48, blue: 1.0),      // #007AFF Blue
                    Color(red: 0.35, green: 0.78, blue: 0.98)   // #5AC8FA Cyan
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            
            // Chart symbol
            Image(systemName: "chart.line.uptrend.xyaxis")
                .font(.system(size: 500, weight: .semibold))
                .foregroundStyle(.white)
                .scaleEffect(0.5)
        }
    }
    
    private func alternativeIcon(colors: [Color], symbol: String) -> some View {
        ZStack {
            LinearGradient(
                colors: colors,
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            
            Image(systemName: symbol)
                .font(.system(size: 500, weight: .semibold))
                .foregroundStyle(.white)
                .scaleEffect(0.5)
        }
    }
    
    // MARK: - Size Helpers
    
    private func iconAtSize(_ size: CGFloat, label: String) -> some View {
        VStack(spacing: 8) {
            iconDesign
                .frame(width: size, height: size)
                .clipShape(RoundedRectangle(
                    cornerRadius: size * 0.2237,  // iOS standard corner radius ratio
                    style: .continuous
                ))
                .shadow(color: .black.opacity(0.1), radius: 3, x: 0, y: 2)
            
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(height: 30)
        }
    }
    
    // MARK: - Home Screen Preview
    
    private var homeScreenPreview: some View {
        ZStack {
            // Simulated iPhone background
            LinearGradient(
                colors: [.blue.opacity(0.3), .purple.opacity(0.3)],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()
            
            VStack(spacing: 12) {
                // First row of apps
                HStack(spacing: 20) {
                    appIconOnHomeScreen(icon: iconDesign, name: "TradeSim")
                    dummyAppIcon(color: .red, symbol: "music.note", name: "Music")
                    dummyAppIcon(color: .blue, symbol: "safari", name: "Safari")
                    dummyAppIcon(color: .green, symbol: "message.fill", name: "Messages")
                }
                
                // Second row of apps
                HStack(spacing: 20) {
                    dummyAppIcon(color: .orange, symbol: "gear", name: "Settings")
                    dummyAppIcon(color: .purple, symbol: "photo", name: "Photos")
                    dummyAppIcon(color: .pink, symbol: "heart.fill", name: "Health")
                    dummyAppIcon(color: .indigo, symbol: "envelope.fill", name: "Mail")
                }
            }
        }
        .frame(height: 250)
        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        .shadow(radius: 10)
    }
    
    private func appIconOnHomeScreen(icon: some View, name: String) -> some View {
        VStack(spacing: 6) {
            icon
                .frame(width: 60, height: 60)
                .clipShape(RoundedRectangle(cornerRadius: 13.5, style: .continuous))
            
            Text(name)
                .font(.caption2)
                .foregroundStyle(.white)
                .shadow(color: .black.opacity(0.3), radius: 1, x: 0, y: 1)
        }
    }
    
    private func dummyAppIcon(color: Color, symbol: String, name: String) -> some View {
        VStack(spacing: 6) {
            ZStack {
                color
                Image(systemName: symbol)
                    .font(.title2)
                    .foregroundStyle(.white)
            }
            .frame(width: 60, height: 60)
            .clipShape(RoundedRectangle(cornerRadius: 13.5, style: .continuous))
            
            Text(name)
                .font(.caption2)
                .foregroundStyle(.white)
                .shadow(color: .black.opacity(0.3), radius: 1, x: 0, y: 1)
        }
    }
}

#Preview {
    AppIconPreview()
}
