#!/bin/bash

# TradeSim App Icon Generator Script
# This script helps you generate all required icon sizes from a master 1024x1024 icon
# 
# Requirements:
#   - ImageMagick installed (brew install imagemagick)
#   - Master icon file named "AppIcon-1024.png" in the same directory
#
# Usage:
#   chmod +x generate_icons.sh
#   ./generate_icons.sh

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}TradeSim App Icon Generator${NC}"
echo "=================================="

# Check if ImageMagick is installed
if ! command -v convert &> /dev/null; then
    echo -e "${RED}Error: ImageMagick is not installed${NC}"
    echo "Install with: brew install imagemagick"
    exit 1
fi

# Check if master icon exists
MASTER_ICON="AppIcon-1024.png"
if [ ! -f "$MASTER_ICON" ]; then
    echo -e "${RED}Error: Master icon '$MASTER_ICON' not found${NC}"
    echo "Please create a 1024x1024 PNG file named '$MASTER_ICON'"
    exit 1
fi

# Create output directory
OUTPUT_DIR="AppIcons"
mkdir -p "$OUTPUT_DIR"

echo -e "${GREEN}Generating iOS app icons...${NC}"

# iOS App Icon sizes
# Format: size_name:pixels:scale
declare -a SIZES=(
    "Icon-20@2x:40:2x"
    "Icon-20@3x:60:3x"
    "Icon-29@2x:58:2x"
    "Icon-29@3x:87:3x"
    "Icon-40@2x:80:2x"
    "Icon-40@3x:120:3x"
    "Icon-60@2x:120:2x"
    "Icon-60@3x:180:3x"
    "Icon-1024:1024:1x"
)

# Generate each size
for size_info in "${SIZES[@]}"; do
    IFS=':' read -r name pixels scale <<< "$size_info"
    
    echo -e "  Generating ${name}.png (${pixels}x${pixels})..."
    
    convert "$MASTER_ICON" \
        -resize "${pixels}x${pixels}" \
        -strip \
        -colorspace sRGB \
        "$OUTPUT_DIR/${name}.png"
    
    if [ $? -eq 0 ]; then
        echo -e "    ${GREEN}✓${NC} Created ${name}.png"
    else
        echo -e "    ${RED}✗${NC} Failed to create ${name}.png"
    fi
done

echo ""
echo -e "${GREEN}Icon generation complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Open Xcode and navigate to Assets.xcassets"
echo "2. Create a new App Icon asset (or select existing)"
echo "3. Drag the generated icons from '$OUTPUT_DIR' to the appropriate slots"
echo ""
echo "Files are located in: ./$OUTPUT_DIR"

# Create Contents.json for the asset catalog
cat > "$OUTPUT_DIR/Contents.json" << 'EOF'
{
  "images" : [
    {
      "filename" : "Icon-20@2x.png",
      "idiom" : "iphone",
      "scale" : "2x",
      "size" : "20x20"
    },
    {
      "filename" : "Icon-20@3x.png",
      "idiom" : "iphone",
      "scale" : "3x",
      "size" : "20x20"
    },
    {
      "filename" : "Icon-29@2x.png",
      "idiom" : "iphone",
      "scale" : "2x",
      "size" : "29x29"
    },
    {
      "filename" : "Icon-29@3x.png",
      "idiom" : "iphone",
      "scale" : "3x",
      "size" : "29x29"
    },
    {
      "filename" : "Icon-40@2x.png",
      "idiom" : "iphone",
      "scale" : "2x",
      "size" : "40x40"
    },
    {
      "filename" : "Icon-40@3x.png",
      "idiom" : "iphone",
      "scale" : "3x",
      "size" : "40x40"
    },
    {
      "filename" : "Icon-60@2x.png",
      "idiom" : "iphone",
      "scale" : "2x",
      "size" : "60x60"
    },
    {
      "filename" : "Icon-60@3x.png",
      "idiom" : "iphone",
      "scale" : "3x",
      "size" : "60x60"
    },
    {
      "filename" : "Icon-1024.png",
      "idiom" : "ios-marketing",
      "scale" : "1x",
      "size" : "1024x1024"
    }
  ],
  "info" : {
    "author" : "xcode",
    "version" : 1
  }
}
EOF

echo -e "${GREEN}✓${NC} Created Contents.json for asset catalog"
echo ""
echo -e "${BLUE}Tip:${NC} You can drag the entire '$OUTPUT_DIR' folder to Xcode"
echo "     and rename it to 'AppIcon.appiconset' in the asset catalog."
