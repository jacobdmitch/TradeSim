#!/bin/bash

# TradeSim Simulator Testing Setup
# This script sets up everything you need to test the app in the iOS Simulator
# 
# What it does:
#   - Generates a placeholder app icon using Swift/ImageIO
#   - Checks Xcode simulator availability
#   - Provides testing instructions
#
# Usage:
#   chmod +x setup_sim_testing.sh
#   ./setup_sim_testing.sh

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  TradeSim Simulator Testing Setup     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Check if Xcode is installed
if ! command -v xcodebuild &> /dev/null; then
    echo -e "${RED}✗ Error: Xcode is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Xcode is installed"

# Check for available simulators
echo -e "\n${BLUE}Available iOS Simulators:${NC}"
xcrun simctl list devices available | grep "iPhone" | head -n 5

# Check if we're in an Xcode project directory
if [ ! -f "*.xcodeproj" ] && [ ! -f "*.xcworkspace" ]; then
    echo -e "\n${YELLOW}⚠ Warning: No Xcode project found in current directory${NC}"
    echo "Make sure you run this script from your project root"
fi

# Generate a test master icon using sips (built into macOS)
echo -e "\n${BLUE}Generating test app icon...${NC}"

# Create a temporary Swift script to generate the icon
cat > /tmp/generate_test_icon.swift << 'SWIFT'
import AppKit
import CoreGraphics

let size: CGFloat = 1024
let image = NSImage(size: NSSize(width: size, height: size))

image.lockFocus()

// Gradient background (Blue to Cyan)
let gradient = NSGradient(colors: [
    NSColor(red: 0, green: 0.48, blue: 1.0, alpha: 1.0),     // Blue
    NSColor(red: 0.35, green: 0.78, blue: 0.98, alpha: 1.0)  // Cyan
])
let rect = NSRect(x: 0, y: 0, width: size, height: size)
gradient?.draw(in: rect, angle: -45)

// Add chart symbol representation (simple line chart)
let path = NSBezierPath()
path.lineWidth = 40

// Draw upward trending line
let points: [(CGFloat, CGFloat)] = [
    (200, 300),
    (350, 450),
    (450, 400),
    (600, 550),
    (750, 700)
]

path.move(to: NSPoint(x: points[0].0, y: points[0].1))
for i in 1..<points.count {
    path.line(to: NSPoint(x: points[i].0, y: points[i].1))
}

NSColor.white.setStroke()
path.stroke()

// Draw dots at points
for point in points {
    let dotRect = NSRect(x: point.0 - 25, y: point.1 - 25, width: 50, height: 50)
    let dotPath = NSBezierPath(ovalIn: dotRect)
    NSColor.white.setFill()
    dotPath.fill()
}

// Draw axes
let axisPath = NSBezierPath()
axisPath.lineWidth = 30
axisPath.move(to: NSPoint(x: 150, y: 200))
axisPath.line(to: NSPoint(x: 150, y: 750))
axisPath.move(to: NSPoint(x: 150, y: 200))
axisPath.line(to: NSPoint(x: 800, y: 200))
NSColor.white.withAlphaComponent(0.8).setStroke()
axisPath.stroke()

image.unlockFocus()

// Save as PNG
if let tiffData = image.tiffRepresentation,
   let bitmap = NSBitmapImageRep(data: tiffData),
   let pngData = bitmap.representation(using: .png, properties: [:]) {
    let fileURL = URL(fileURLWithPath: "AppIcon-1024.png")
    try? pngData.write(to: fileURL)
    print("✓ Generated AppIcon-1024.png")
} else {
    print("✗ Failed to generate icon")
}
SWIFT

# Run the Swift script
if swift /tmp/generate_test_icon.swift 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Created AppIcon-1024.png (test icon)"
else
    echo -e "${YELLOW}⚠${NC} Could not auto-generate icon, creating placeholder..."
    
    # Fallback: create a simple colored square
    if command -v sips &> /dev/null; then
        # Create a 1024x1024 blue image using sips
        sips -z 1024 1024 /System/Library/CoreServices/DefaultBackground.jpg --out AppIcon-1024-temp.png 2>/dev/null
        if [ -f "AppIcon-1024-temp.png" ]; then
            mv AppIcon-1024-temp.png AppIcon-1024.png
            echo -e "${GREEN}✓${NC} Created placeholder AppIcon-1024.png"
        fi
    fi
fi

# Check if ImageMagick is available for icon generation
echo -e "\n${BLUE}Checking icon generation tools...${NC}"
if command -v convert &> /dev/null; then
    echo -e "${GREEN}✓${NC} ImageMagick is installed"
    echo -e "  You can run ${BLUE}./generate_icons.sh${NC} to create all icon sizes"
else
    echo -e "${YELLOW}⚠${NC} ImageMagick not installed (optional)"
    echo -e "  Install with: ${BLUE}brew install imagemagick${NC}"
    echo -e "  Or use Xcode to manually add icons to Assets.xcassets"
fi

# Create a test configuration file
cat > SimulatorTestConfig.txt << 'EOF'
================================================================================
TradeSim - Simulator Testing Guide
================================================================================

QUICK START:
1. Open your project in Xcode
2. Select an iPhone simulator (iPhone 15 Pro recommended)
3. Press Cmd+R to build and run
4. Watch for the loading screen animation

WHAT TO TEST:

Loading Screen (LoadingView.swift):
  ✓ Appears on app launch
  ✓ Animated rotating icon
  ✓ Pulsing circle effect
  ✓ Animated chart bars
  ✓ Smooth transition to main app (1.5 seconds)
  ✓ "Loading markets..." text visible

App Icon Preview (AppIconPreview.swift):
  ✓ Open in Xcode and run in Preview pane
  ✓ Check icon at different sizes
  ✓ Verify colors and clarity
  ✓ Test alternative color schemes

Main App Flow:
  ✓ Loading screen → Tab bar appears
  ✓ Portfolio tab shows properly
  ✓ All 5 tabs are visible
  ✓ Navigation works smoothly

TESTING IN DIFFERENT SIMULATORS:

iPhone 15 Pro Max (6.7"):
  xcrun simctl boot "iPhone 15 Pro Max"
  
iPhone SE (3rd gen) (4.7"):
  xcrun simctl boot "iPhone SE (3rd generation)"

iPad Pro 12.9":
  xcrun simctl boot "iPad Pro (12.9-inch)"

TESTING TIPS:

1. Test Dark Mode:
   - Simulator menu → Features → Toggle Appearance

2. Test Different Network Conditions:
   - Simulator menu → Features → Network Link Conditioner

3. Reset Simulator:
   - Simulator menu → Device → Erase All Content and Settings

4. View App Icon on Home Screen:
   - After running app, press Cmd+Shift+H to go to home screen
   - See your icon among other apps

5. Test Notifications (if applicable):
   - Make sure notification permissions work
   - Check banner appearance

DEBUGGING LOADING SCREEN:

If loading screen doesn't show:
  - Check TradeSimApp.swift has @State private var isLoading = true
  - Verify LoadingView() is in the ZStack
  - Check task block is executing
  - Look for errors in Xcode console

If animations are choppy:
  - Normal in Simulator (better on real device)
  - Try iPhone simulator with fewer running apps
  - Metal performance is limited in Simulator

PERFORMANCE TESTING:

To test loading time:
  1. Add print statements in TradeSimApp task block
  2. Monitor console for timing
  3. Adjust sleep duration if needed (currently 1.5s)

NEXT STEPS:

1. ✓ Run app in Simulator to see loading screen
2. ✓ Preview AppIconPreview.swift to visualize icon
3. ⚠ Create final app icon design (currently using test icon)
4. ⚠ Generate all icon sizes with generate_icons.sh
5. ⚠ Add icons to Assets.xcassets in Xcode
6. ⚠ Test on physical device for true performance

================================================================================
EOF

echo -e "${GREEN}✓${NC} Created SimulatorTestConfig.txt"

# List available schemes
echo -e "\n${BLUE}Setting up build configuration...${NC}"
if [ -f *.xcodeproj/project.pbxproj ]; then
    echo -e "${GREEN}✓${NC} Xcode project detected"
else
    echo -e "${YELLOW}⚠${NC} No Xcode project file found in current directory"
fi

# Summary
echo -e "\n${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Setup Complete!                       ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo ""
echo -e "1. Open your project in Xcode:"
echo -e "   ${YELLOW}open *.xcodeproj${NC} or ${YELLOW}open *.xcworkspace${NC}"
echo ""
echo -e "2. Select a simulator target (iPhone 15 Pro recommended)"
echo ""
echo -e "3. Build and run (${YELLOW}Cmd+R${NC})"
echo ""
echo -e "4. Test the loading screen and app flow"
echo ""
echo -e "5. Preview the icon design:"
echo -e "   Open ${YELLOW}AppIconPreview.swift${NC} in Xcode and use Live Preview"
echo ""
echo -e "${BLUE}Quick Commands:${NC}"
echo -e "  • List simulators:  ${YELLOW}xcrun simctl list devices${NC}"
echo -e "  • Boot simulator:   ${YELLOW}xcrun simctl boot 'iPhone 15 Pro'${NC}"
echo -e "  • Build from CLI:   ${YELLOW}xcodebuild -scheme TradeSim -destination 'platform=iOS Simulator,name=iPhone 15 Pro'${NC}"
echo ""
echo -e "${BLUE}Generated Files:${NC}"
if [ -f "AppIcon-1024.png" ]; then
    echo -e "  ${GREEN}✓${NC} AppIcon-1024.png (test master icon)"
fi
echo -e "  ${GREEN}✓${NC} SimulatorTestConfig.txt (testing guide)"
echo ""
echo -e "Read ${YELLOW}SimulatorTestConfig.txt${NC} for detailed testing instructions!"
echo ""
