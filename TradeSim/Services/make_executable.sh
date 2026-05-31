#!/bin/bash

# Make all TradeSim scripts executable
# Run this once to enable all testing scripts

echo "Making scripts executable..."

chmod +x generate_icons.sh
echo "✓ generate_icons.sh"

chmod +x setup_sim_testing.sh
echo "✓ setup_sim_testing.sh"

chmod +x quick_test.sh
echo "✓ quick_test.sh"

chmod +x make_executable.sh
echo "✓ make_executable.sh (this script)"

echo ""
echo "All scripts are now executable!"
echo ""
echo "Next steps:"
echo "  1. Run ./setup_sim_testing.sh for initial setup"
echo "  2. Run ./quick_test.sh to build and test"
echo "  3. See TESTING_README.md for complete guide"
echo ""
