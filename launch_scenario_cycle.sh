#!/bin/bash
"""
Simple launcher for CARLA scenario cycling
"""

# Default paths (adjust these to match your setup)
export ROOT="$HOME/EvoDrive"
export CARLA_ROOT="${ROOT}/CARLA"
export LEADERBOARD_ROOT="${ROOT}/leaderboard"
export SCENARIO_RUNNER_ROOT="${ROOT}/scenario_runner"
export SCENARIO_DIR="${SCENARIO_RUNNER_ROOT}/converted_rebuilt_scenarios"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚗 CARLA Scenario Cycle Launcher${NC}"
echo "=================================="

# Check if scenario directory exists
if [ ! -d "$SCENARIO_DIR" ]; then
    echo -e "${RED}❌ Scenario directory not found: $SCENARIO_DIR${NC}"
    echo "   Make sure you've converted scenarios first."
    exit 1
fi

# Count scenarios
SCENARIO_COUNT=$(find "$SCENARIO_DIR" -name "*.xosc" | wc -l)
echo -e "${GREEN}✅ Found $SCENARIO_COUNT scenarios${NC}"

# Check if CARLA is running
if pgrep -f "CarlaUE4" > /dev/null; then
    echo -e "${GREEN}✅ CARLA server is running${NC}"
else
    echo -e "${YELLOW}⚠️  CARLA server not detected${NC}"
    echo "   The script will try to start it automatically."
fi

echo ""
echo "Options:"
echo "1. Run ALL scenarios (may take hours)"
echo "2. Run first 10 scenarios (test run)"
echo "3. Run first 50 scenarios (sample batch)"
echo "4. Start from specific scenario"
echo "5. Check setup only"
echo ""

read -p "Choose option (1-5): " choice

case $choice in
    1)
        echo -e "${YELLOW}🚀 Running ALL $SCENARIO_COUNT scenarios...${NC}"
        python3 cycle_scenarios.py --carla-root "$CARLA_ROOT" --scenario-runner "$SCENARIO_RUNNER_ROOT"
        ;;
    2)
        echo -e "${YELLOW}🚀 Running first 10 scenarios...${NC}"
        python3 cycle_scenarios.py --max-scenarios 10 --carla-root "$CARLA_ROOT" --scenario-runner "$SCENARIO_RUNNER_ROOT"
        ;;
    3)
        echo -e "${YELLOW}🚀 Running first 50 scenarios...${NC}"
        python3 cycle_scenarios.py --max-scenarios 50 --carla-root "$CARLA_ROOT" --scenario-runner "$SCENARIO_RUNNER_ROOT"
        ;;
    4)
        echo ""
        echo "Available scenario types:"
        echo "- following_XXX (vehicle following scenarios)"
        echo "- lane_change_XXX (lane change scenarios)" 
        echo "- pedestrian_XXX (pedestrian crossing scenarios)"
        echo "- emergency_XXX (emergency vehicle scenarios)"
        echo "- static_XXX (static obstacle scenarios)"
        echo ""
        read -p "Enter scenario name or pattern: " start_scenario
        echo -e "${YELLOW}🚀 Starting from scenario: $start_scenario${NC}"
        python3 cycle_scenarios.py --start-from "$start_scenario" --carla-root "$CARLA_ROOT" --scenario-runner "$SCENARIO_RUNNER_ROOT"
        ;;
    5)
        echo -e "${YELLOW}🔍 Checking setup only...${NC}"
        python3 cycle_scenarios.py --check-only --carla-root "$CARLA_ROOT" --scenario-runner "$SCENARIO_RUNNER_ROOT"
        ;;
    *)
        echo -e "${RED}❌ Invalid option${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✅ Scenario cycling completed!${NC}"
echo "📊 Check the generated JSON results file for detailed statistics."