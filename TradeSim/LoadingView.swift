import SwiftUI

/// Beautiful loading screen for TradeSim with animated chart visualization
struct LoadingView: View {
    @State private var isAnimating = false
    @State private var chartProgress: CGFloat = 0
    @State private var pulseOpacity: Double = 0.3
    
    var body: some View {
        ZStack {
            // Background gradient
            LinearGradient(
                colors: [
                    Color(red: 0.1, green: 0.1, blue: 0.2),
                    Color(red: 0.05, green: 0.05, blue: 0.1)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
            
            VStack(spacing: 40) {
                Spacer()
                
                // App icon representation
                iconSymbol
                
                // App name
                VStack(spacing: 8) {
                    Text("TradeSim")
                        .font(.system(size: 42, weight: .bold, design: .rounded))
                        .foregroundStyle(.white)
                    
                    Text("Practice crypto trading")
                        .font(.subheadline)
                        .foregroundStyle(.white.opacity(0.7))
                }
                
                Spacer()
                
                // Animated chart visualization
                animatedChart
                
                Spacer()
                
                // Loading indicator
                VStack(spacing: 12) {
                    ProgressView()
                        .tint(.white)
                    
                    Text("Loading markets...")
                        .font(.caption)
                        .foregroundStyle(.white.opacity(0.6))
                }
                .padding(.bottom, 60)
            }
        }
        .onAppear {
            startAnimations()
        }
    }
    
    // MARK: - Icon Symbol
    
    private var iconSymbol: some View {
        ZStack {
            // Pulsing background circle
            Circle()
                .fill(.white.opacity(pulseOpacity))
                .frame(width: 120, height: 120)
                .scaleEffect(isAnimating ? 1.2 : 1.0)
            
            // Main icon circle
            Circle()
                .fill(
                    LinearGradient(
                        colors: [.blue, .cyan],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .frame(width: 100, height: 100)
                .shadow(color: .blue.opacity(0.5), radius: 20, x: 0, y: 10)
            
            // Chart symbol
            Image(systemName: "chart.line.uptrend.xyaxis")
                .font(.system(size: 44, weight: .semibold))
                .foregroundStyle(.white)
                .rotationEffect(.degrees(isAnimating ? 360 : 0))
        }
    }
    
    // MARK: - Animated Chart
    
    private var animatedChart: some View {
        GeometryReader { geometry in
            let width = geometry.size.width
            let height: CGFloat = 100
            
            Canvas { context, size in
                // Draw bars representing market data
                let barCount = 20
                let barWidth = size.width / CGFloat(barCount * 2)
                let spacing = barWidth
                
                for i in 0..<barCount {
                    let progress = chartProgress
                    let delay = Double(i) / Double(barCount)
                    let adjustedProgress = max(0, min(1, (progress - delay) * 2))
                    
                    // Vary heights with sine wave pattern
                    let baseHeight = sin(Double(i) * 0.5) * 0.3 + 0.5
                    let barHeight = size.height * baseHeight * adjustedProgress
                    
                    let x = CGFloat(i) * (barWidth + spacing) + barWidth / 2
                    let y = size.height - barHeight
                    
                    let rect = CGRect(
                        x: x,
                        y: y,
                        width: barWidth,
                        height: barHeight
                    )
                    
                    // Color based on position (gradient from blue to cyan to green)
                    let hue = 0.5 + (Double(i) / Double(barCount)) * 0.2
                    let color = Color(hue: hue, saturation: 0.8, brightness: 0.9)
                    
                    context.fill(
                        Path(roundedRect: rect, cornerRadius: barWidth / 2),
                        with: .color(color.opacity(0.8))
                    )
                }
            }
            .frame(width: width, height: height)
        }
        .frame(height: 100)
        .padding(.horizontal, 40)
    }
    
    // MARK: - Animations
    
    private func startAnimations() {
        // Icon rotation and pulse
        withAnimation(.easeInOut(duration: 2.0).repeatForever(autoreverses: false)) {
            isAnimating = true
        }
        
        withAnimation(.easeInOut(duration: 1.5).repeatForever(autoreverses: true)) {
            pulseOpacity = 0.1
        }
        
        // Chart bars animation
        withAnimation(.easeInOut(duration: 1.5).repeatForever(autoreverses: true)) {
            chartProgress = 1.0
        }
    }
}

#Preview {
    LoadingView()
}
