#!/bin/bash

# TradeSim TestFlight Preparation Script
# Checks that everything is ready for TestFlight distribution
#
# Usage:
#   chmod +x prepare_testflight.sh
#   ./prepare_testflight.sh

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                          ║${NC}"
echo -e "${CYAN}║        TradeSim TestFlight Preparation Check             ║${NC}"
echo -e "${CYAN}║                                                          ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Track overall status
ERRORS=0
WARNINGS=0

# Function to print check result
check_pass() {
    echo -e "  ${GREEN}✓${NC} $1"
}

check_warn() {
    echo -e "  ${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

check_fail() {
    echo -e "  ${RED}✗${NC} $1"
    ((ERRORS++))
}

# 1. Check for Xcode project
echo -e "${BLUE}1. Checking for Xcode project...${NC}"
if ls *.xcodeproj &> /dev/null; then
    PROJECT=$(ls *.xcodeproj | head -n 1)
    check_pass "Found project: $PROJECT"
elif ls *.xcworkspace &> /dev/null; then
    PROJECT=$(ls *.xcworkspace | head -n 1)
    check_pass "Found workspace: $PROJECT"
else
    check_fail "No Xcode project or workspace found"
fi
echo ""

# 2. Check for essential Swift files
echo -e "${BLUE}2. Checking essential Swift files...${NC}"
REQUIRED_FILES=(
    "TradeSimApp.swift"
    "LoadingView.swift"
    "RootView.swift"
    "DashboardView.swift"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        check_pass "$file exists"
    else
        check_fail "$file is missing"
    fi
done
echo ""

# 3. Check for app icon
echo -e "${BLUE}3. Checking app icon assets...${NC}"
if [ -f "AppIcon-1024.png" ]; then
    check_pass "Master icon (AppIcon-1024.png) found"
    
    # Check size
    if command -v sips &> /dev/null; then
        SIZE=$(sips -g pixelWidth -g pixelHeight "AppIcon-1024.png" | grep -E "pixelWidth|pixelHeight" | awk '{print $2}')
        if echo "$SIZE" | grep -q "1024"; then
            check_pass "Icon is correct size (1024×1024)"
        else
            check_warn "Icon may not be 1024×1024 pixels"
        fi
    fi
else
    check_warn "Master icon (AppIcon-1024.png) not found"
    echo -e "    ${YELLOW}→${NC} Run ./setup_sim_testing.sh to generate test icon"
    echo -e "    ${YELLOW}→${NC} Or create final icon with AppIconGenerator.swift"
fi

if [ -d "AppIcons" ] && [ -f "AppIcons/Icon-1024.png" ]; then
    check_pass "Generated icon set found in AppIcons/"
elif [ -f "AppIcon-1024.png" ]; then
    check_warn "Icon sizes not generated yet"
    echo -e "    ${YELLOW}→${NC} Run ./generate_icons.sh to create all sizes"
fi
echo ""

# 4. Check documentation
echo -e "${BLUE}4. Checking distribution documentation...${NC}"
DOCS=(
    "TESTFLIGHT_SETUP.md"
    "APP_STORE_METADATA.md"
)

for doc in "${DOCS[@]}"; do
    if [ -f "$doc" ]; then
        check_pass "$doc available"
    else
        check_warn "$doc not found"
    fi
done
echo ""

# 5. Check for Info.plist or project file
echo -e "${BLUE}5. Checking configuration files...${NC}"
if [ -f "Info.plist" ]; then
    check_pass "Info.plist found"
    
    # Check for notification usage description
    if grep -q "NSUserNotificationsUsageDescription" "Info.plist"; then
        check_pass "Notification usage description present"
    else
        check_warn "Notification usage description may be missing"
        echo -e "    ${YELLOW}→${NC} Add to Info.plist or target settings in Xcode"
    fi
else
    check_warn "Info.plist not in root (may be in project bundle)"
    echo -e "    ${YELLOW}→${NC} Check in Xcode: Target → Info tab"
fi
echo ""

# 6. Check for README and guides
echo -e "${BLUE}6. Checking setup guides...${NC}"
if [ -f "START_HERE.md" ]; then
    check_pass "Testing guide available"
fi
if [ -f "TESTING_CHECKLIST.md" ]; then
    check_pass "Testing checklist available"
fi
echo ""

# 7. Check build scripts
echo -e "${BLUE}7. Checking build scripts...${NC}"
SCRIPTS=(
    "generate_icons.sh"
    "setup_sim_testing.sh"
    "quick_test.sh"
)

for script in "${SCRIPTS[@]}"; do
    if [ -f "$script" ]; then
        if [ -x "$script" ]; then
            check_pass "$script (executable)"
        else
            check_warn "$script (not executable)"
            echo -e "    ${YELLOW}→${NC} Run: chmod +x $script"
        fi
    fi
done
echo ""

# 8. Check Xcode installation
echo -e "${BLUE}8. Checking development environment...${NC}"
if command -v xcodebuild &> /dev/null; then
    XCODE_VERSION=$(xcodebuild -version | head -n 1)
    check_pass "Xcode installed: $XCODE_VERSION"
else
    check_fail "Xcode not found or not in PATH"
fi

if command -v xcrun &> /dev/null; then
    check_pass "Xcode command line tools available"
else
    check_warn "Xcode command line tools may not be configured"
fi
echo ""

# 9. Check for Git (optional but recommended)
echo -e "${BLUE}9. Checking version control...${NC}"
if [ -d ".git" ]; then
    check_pass "Git repository initialized"
    
    # Check if there are uncommitted changes
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        check_warn "Uncommitted changes detected"
        echo -e "    ${YELLOW}→${NC} Consider committing before creating archive"
    else
        check_pass "Working directory clean"
    fi
    
    # Check for tags
    if git tag | grep -q .; then
        LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null)
        check_pass "Version tags found (latest: $LATEST_TAG)"
    else
        check_warn "No version tags found"
        echo -e "    ${YELLOW}→${NC} Consider tagging releases: git tag v1.0.0"
    fi
else
    check_warn "Not a Git repository"
    echo -e "    ${YELLOW}→${NC} Consider using version control: git init"
fi
echo ""

# 10. Simulator availability
echo -e "${BLUE}10. Checking iOS simulators...${NC}"
if command -v xcrun &> /dev/null; then
    SIM_COUNT=$(xcrun simctl list devices available | grep "iPhone" | wc -l)
    if [ "$SIM_COUNT" -gt 0 ]; then
        check_pass "$SIM_COUNT iPhone simulators available"
    else
        check_warn "No iPhone simulators found"
    fi
fi
echo ""

# Summary
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Summary${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo -e "  Your project appears ready for TestFlight distribution."
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ Passed with $WARNINGS warning(s)${NC}"
    echo -e "  Review warnings above before proceeding."
else
    echo -e "${RED}✗ Found $ERRORS error(s) and $WARNINGS warning(s)${NC}"
    echo -e "  Fix errors before attempting distribution."
fi

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Next Steps for TestFlight Distribution${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

if [ ! -f "AppIcon-1024.png" ] || [ ! -d "AppIcons" ]; then
    echo -e "${YELLOW}1. Generate App Icons${NC}"
    echo -e "   → Open AppIconGenerator.swift in Xcode"
    echo -e "   → Export 1024×1024 icon"
    echo -e "   → Save as AppIcon-1024.png"
    echo -e "   → Run: ./generate_icons.sh"
    echo -e "   → Import to Assets.xcassets in Xcode"
    echo ""
fi

echo -e "${BLUE}2. Configure Xcode Project${NC}"
echo -e "   → Open project in Xcode"
echo -e "   → Select target → General"
echo -e "   → Set Bundle Identifier (e.g., com.yourcompany.TradeSim)"
echo -e "   → Set Version (e.g., 1.0.0)"
echo -e "   → Set Build number (e.g., 1)"
echo -e "   → Go to Signing & Capabilities"
echo -e "   → Enable 'Automatically manage signing'"
echo -e "   → Select your Team"
echo ""

echo -e "${BLUE}3. Add Privacy Descriptions${NC}"
echo -e "   → In Xcode: Target → Info tab"
echo -e "   → Add key: 'Privacy - User Notifications Usage Description'"
echo -e "   → Value: 'TradeSim sends notifications about rotation recommendations.'"
echo ""

echo -e "${BLUE}4. Test on Physical Device${NC}"
echo -e "   → Connect iPhone/iPad"
echo -e "   → Select device in Xcode"
echo -e "   → Build and run (Cmd+R)"
echo -e "   → Test thoroughly!"
echo ""

echo -e "${BLUE}5. Create Archive${NC}"
echo -e "   → In Xcode scheme selector: Choose 'Any iOS Device'"
echo -e "   → Menu: Product → Archive"
echo -e "   → Wait for completion"
echo ""

echo -e "${BLUE}6. Upload to App Store Connect${NC}"
echo -e "   → Organizer opens automatically"
echo -e "   → Click 'Distribute App'"
echo -e "   → Choose 'TestFlight & App Store'"
echo -e "   → Follow prompts to upload"
echo ""

echo -e "${BLUE}7. Configure in App Store Connect${NC}"
echo -e "   → Visit https://appstoreconnect.apple.com"
echo -e "   → Go to TestFlight tab"
echo -e "   → Wait for build to process"
echo -e "   → Add test information"
echo -e "   → Add testers or create public link"
echo ""

echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Documentation Available${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${GREEN}→${NC} TESTFLIGHT_SETUP.md      (Complete step-by-step guide)"
echo -e "  ${GREEN}→${NC} APP_STORE_METADATA.md    (App descriptions & metadata)"
echo -e "  ${GREEN}→${NC} START_HERE.md            (Testing guide)"
echo -e "  ${GREEN}→${NC} TESTING_CHECKLIST.md     (Pre-upload checklist)"
echo ""

echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}Ready to proceed!${NC} Review TESTFLIGHT_SETUP.md for detailed instructions."
else
    echo -e "${RED}Please fix errors before proceeding.${NC}"
fi

echo ""
