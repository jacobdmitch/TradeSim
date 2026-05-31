import SwiftUI

/// Exportable app icon generator using SwiftUI rendering
/// This view can be rendered to images for your app icon
/// 
/// Usage:
/// 1. Open this file in Xcode
/// 2. Use the Preview pane to view the icon
/// 3. Use ImageRenderer (iOS 16+) to export to PNG files
/// 4. Or take screenshots at 1x scale for quick testing

struct AppIconGenerator: View {
    var size: CGFloat = 1024
    
    var body: some View {
        iconDesign
            .frame(width: size, height: size)
    }
    
    // MARK: - Icon Design
    
    private var iconDesign: some View {
        ZStack {
            // Gradient background matching TradeSim brand
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
                .font(.system(size: size * 0.55, weight: .semibold))
                .foregroundStyle(.white)
        }
    }
}

// MARK: - Export Helper

#if DEBUG
/// Helper to export icons at specific sizes for testing
struct IconExportHelper {
    
    /// Generate all required icon sizes and save to a directory
    /// Note: This requires iOS 16+ for ImageRenderer
    @MainActor
    static func generateAllSizes() async {
        let sizes: [(name: String, size: CGFloat)] = [
            ("Icon-20@2x", 40),
            ("Icon-20@3x", 60),
            ("Icon-29@2x", 58),
            ("Icon-29@3x", 87),
            ("Icon-40@2x", 80),
            ("Icon-40@3x", 120),
            ("Icon-60@2x", 120),
            ("Icon-60@3x", 180),
            ("Icon-1024", 1024)
        ]
        
        for (name, size) in sizes {
            let icon = AppIconGenerator(size: size)
            let renderer = ImageRenderer(content: icon)
            renderer.scale = 1.0 // Always render at 1x since size is already correct
            
            if let image = renderer.uiImage,
               let data = image.pngData() {
                print("Generated: \(name).png (\(Int(size))x\(Int(size)))")
                // In a real app, save to Documents or export
                // For now, just confirming generation works
            }
        }
    }
    
    /// Export a single size - useful for App Store icon
    @MainActor
    static func exportAppStoreIcon() -> UIImage? {
        let icon = AppIconGenerator(size: 1024)
        let renderer = ImageRenderer(content: icon)
        renderer.scale = 1.0
        return renderer.uiImage
    }
}
#endif

// MARK: - Preview with Export Button

struct AppIconGeneratorPreview: View {
    @State private var exportedImage: UIImage?
    @State private var showingShare = false
    
    var body: some View {
        ScrollView {
            VStack(spacing: 30) {
                Text("TradeSim App Icon Generator")
                    .font(.title.bold())
                    .padding(.top)
                
                // Main 1024x1024 preview
                VStack(spacing: 12) {
                    Text("App Store Icon (1024×1024)")
                        .font(.headline)
                    
                    AppIconGenerator(size: 300)
                        .clipShape(RoundedRectangle(cornerRadius: 66, style: .continuous))
                        .shadow(color: .black.opacity(0.2), radius: 20, x: 0, y: 10)
                    
                    Button {
                        exportAppStoreIcon()
                    } label: {
                        Label("Export 1024×1024 PNG", systemImage: "square.and.arrow.up")
                            .padding()
                            .background(.blue)
                            .foregroundStyle(.white)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                }
                
                // Size previews
                Text("Icon Size Preview")
                    .font(.headline)
                    .padding(.top)
                
                LazyVGrid(columns: [
                    GridItem(.flexible()),
                    GridItem(.flexible()),
                    GridItem(.flexible())
                ], spacing: 20) {
                    iconPreview(size: 180, label: "iPhone\n60pt @3x")
                    iconPreview(size: 120, label: "Spotlight\n40pt @3x")
                    iconPreview(size: 87, label: "Settings\n29pt @3x")
                    iconPreview(size: 80, label: "Spotlight\n40pt @2x")
                    iconPreview(size: 60, label: "Notification\n20pt @3x")
                    iconPreview(size: 40, label: "Notification\n20pt @2x")
                }
                .padding()
                
                // Instructions
                VStack(alignment: .leading, spacing: 12) {
                    Text("Quick Export Instructions")
                        .font(.headline)
                    
                    VStack(alignment: .leading, spacing: 8) {
                        instructionRow(number: "1", text: "Take a screenshot of the 1024×1024 icon above")
                        instructionRow(number: "2", text: "Crop to exactly 1024×1024 pixels")
                        instructionRow(number: "3", text: "Save as 'AppIcon-1024.png'")
                        instructionRow(number: "4", text: "Run generate_icons.sh script")
                        instructionRow(number: "5", text: "Import to Xcode Assets.xcassets")
                    }
                }
                .padding()
                .background(.thinMaterial)
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .padding(.horizontal)
                
                // Alternative: Direct to Assets
                VStack(alignment: .leading, spacing: 12) {
                    Text("Or Add Directly to Xcode")
                        .font(.headline)
                    
                    Text("For quick testing, you can add just the 1024×1024 icon to your asset catalog and let Xcode generate the rest (though generating all sizes manually is better for production).")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                .padding()
                .background(.thinMaterial)
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .padding(.horizontal)
                
                Spacer(minLength: 40)
            }
        }
        .sheet(isPresented: $showingShare) {
            if let image = exportedImage {
                ShareSheet(items: [image])
            }
        }
    }
    
    private func iconPreview(size: CGFloat, label: String) -> some View {
        VStack(spacing: 8) {
            AppIconGenerator(size: size)
                .clipShape(RoundedRectangle(
                    cornerRadius: size * 0.2237,
                    style: .continuous
                ))
                .shadow(color: .black.opacity(0.1), radius: 3, x: 0, y: 2)
            
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(height: 35)
        }
    }
    
    private func instructionRow(number: String, text: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Text(number)
                .font(.system(.body, design: .rounded, weight: .bold))
                .foregroundStyle(.white)
                .frame(width: 28, height: 28)
                .background(.blue)
                .clipShape(Circle())
            
            Text(text)
                .font(.subheadline)
        }
    }
    
    @MainActor
    private func exportAppStoreIcon() {
        let icon = AppIconGenerator(size: 1024)
        let renderer = ImageRenderer(content: icon)
        renderer.scale = 1.0
        
        if let image = renderer.uiImage {
            exportedImage = image
            showingShare = true
        }
    }
}

// MARK: - Share Sheet

struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]
    
    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }
    
    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}

#Preview("Icon Generator") {
    AppIconGeneratorPreview()
}

#Preview("Single Icon (1024)") {
    AppIconGenerator(size: 1024)
}

#Preview("Single Icon (180)") {
    AppIconGenerator(size: 180)
        .clipShape(RoundedRectangle(cornerRadius: 40, style: .continuous))
}
