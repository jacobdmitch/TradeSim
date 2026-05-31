#!/bin/bash

# Quick Launch Script for TradeSim Testing
# Builds and runs the app in the iOS Simulator
#
# Usage:
#   chmod +x quick_test.sh
#   ./quick_test.sh [device_name]
#
# Examples:
#   ./quick_test.sh                          # Uses default (iPhone 15 Pro)
#   ./quick_test.sh "iPhone SE (3rd gen)"    # Specific device
#   ./quick_test.sh "iPhone 15 Pro Max"      # Large screen test

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}╔════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     TradeSim Quick Launch              ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"
echo ""

# Determine device to use
if [ -n "$1" ]; then
    DEVICE="$1"
    echo -e "${BLUE}Using specified device:${NC} $DEVICE"
else
    DEVICE="iPhone 15 Pro"
    echo -e "${BLUE}Using default device:${NC} $DEVICE"
fi

# Find the project/workspace
if ls *.xcworkspace &> /dev/null; then
    WORKSPACE=$(ls *.xcworkspace | head -n 1)
    echo -e "${GREEN}✓${NC} Found workspace: $WORKSPACE"
    BUILD_CMD="-workspace $WORKSPACE"
elif ls *.xcodeproj &> /dev/null; then
    PROJECT=$(ls *.xcodeproj | head -n 1)
    echo -e "${GREEN}✓${NC} Found project: $PROJECT"
    BUILD_CMD="-project $PROJECT"
else
    echo -e "${RED}✗ Error: No Xcode project or workspace found${NC}"
    echo "Make sure you're in the project directory"
    exit 1
fi

# Determine scheme (usually same as project name)
SCHEME_NAME=$(basename "${WORKSPACE:-$PROJECT}" | sed 's/\.[^.]*$//')
echo -e "${BLUE}Scheme:${NC} $SCHEME_NAME"

# Check if simulator is available
echo -e "\n${BLUE}Checking simulator availability...${NC}"
if xcrun simctl list devices | grep -q "$DEVICE"; then
    echo -e "${GREEN}✓${NC} Simulator '$DEVICE' is available"
else
    echo -e "${YELLOW}⚠ Warning:${NC} Simulator '$DEVICE' not found"
    echo -e "\n${BLUE}Available devices:${NC}"
    xcrun simctl list devices available | grep "iPhone"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Boot the simulator if not already running
echo -e "\n${BLUE}Booting simulator...${NC}"
xcrun simctl boot "$DEVICE" 2>/dev/null || echo -e "${YELLOW}⚠${NC} Simulator already booted"

# Open Simulator app
open -a Simulator

# Build and run
echo -e "\n${BLUE}Building and running TradeSim...${NC}"
echo -e "${YELLOW}This may take a minute...${NC}"
echo ""

# Full build command
xcodebuild \
    $BUILD_CMD \
    -scheme "$SCHEME_NAME" \
    -destination "platform=iOS Simulator,name=$DEVICE" \
    -derivedDataPath .build \
    clean build

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✓ Build successful!${NC}"
    
    # Install the app
    echo -e "\n${BLUE}Installing app...${NC}"
    
    # Find the built app
    APP_PATH=$(find .build -name "*.app" -type d | head -n 1)
    
    if [ -n "$APP_PATH" ]; then
        # Get the bundle identifier
        BUNDLE_ID=$(defaults read "$APP_PATH/Info.plist" CFBundleIdentifier 2>/dev/null)
        
        if [ -n "$BUNDLE_ID" ]; then
            echo -e "${GREEN}✓${NC} Bundle ID: $BUNDLE_ID"
            
            # Install app
            xcrun simctl install "$DEVICE" "$APP_PATH"
            
            # Launch app
            echo -e "\n${BLUE}Launching app...${NC}"
            xcrun simctl launch --console "$DEVICE" "$BUNDLE_ID"
            
            echo -e "\n${GREEN}╔════════════════════════════════════════╗${NC}"
            echo -e "${GREEN}║  App Launched Successfully! 🚀         ║${NC}"
            echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
            echo ""
            echo -e "${BLUE}What to check:${NC}"
            echo -e "  ✓ Loading screen appears"
            echo -e "  ✓ Animated icon rotates"
            echo -e "  ✓ Chart bars animate"
            echo -e "  ✓ Smooth transition to main app"
            echo -e "  ✓ All tabs are visible"
            echo ""
            echo -e "${CYAN}Tip:${NC} Press Cmd+Shift+H in Simulator to see home screen icon"
            echo ""
        else
            echo -e "${RED}✗ Could not determine bundle identifier${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ App built but path not found${NC}"
        echo "Try opening Xcode and running manually"
    fi
else
    echo -e "\n${RED}✗ Build failed${NC}"
    echo ""
    echo -e "${YELLOW}Common solutions:${NC}"
    echo "  1. Open Xcode and check for build errors"
    echo "  2. Make sure all files are added to the target"
    echo "  3. Clean build folder: Cmd+Shift+K in Xcode"
    echo "  4. Try building from Xcode directly first"
    echo ""
    exit 1
fi

echo -e "${BLUE}════════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}Quick Actions:${NC}"
echo ""
echo -e "  Toggle Dark Mode:        ${YELLOW}Features → Toggle Appearance${NC}"
echo -e "  Go to Home Screen:       ${YELLOW}Cmd + Shift + H${NC}"
echo -e "  Shake Device:            ${YELLOW}Device → Shake${NC}"
echo -e "  Take Screenshot:         ${YELLOW}Cmd + S${NC}"
echo -e "  Restart App:             ${YELLOW}./quick_test.sh${NC}"
echo ""
echo -e "Open ${YELLOW}TESTING_CHECKLIST.md${NC} for full testing guide"
echo ""
