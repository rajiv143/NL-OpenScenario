# CARLA Scenario Cycling Scripts

These scripts automatically cycle through all converted scenarios in CARLA ScenarioRunner.

## Files

- `cycle_scenarios.py` - Main Python script for running scenarios
- `launch_scenario_cycle.sh` - Interactive launcher script  
- `scenario_conversion_summary.txt` - Summary of scenario generation and conversion

## Quick Start

1. **Simple Interactive Launch:**
   ```bash
   ./launch_scenario_cycle.sh
   ```

2. **Direct Python Usage:**
   ```bash
   python3 cycle_scenarios.py --max-scenarios 10
   ```

## Prerequisites

- CARLA simulator installed and accessible
- ScenarioRunner installed and accessible  
- Python 3.6+ with subprocess module
- Converted scenarios in `converted_rebuilt_scenarios/` directory

## Configuration

Edit these paths in `launch_scenario_cycle.sh`:

```bash
CARLA_ROOT="/opt/carla-simulator"           # Your CARLA installation
SCENARIO_RUNNER_ROOT="../scenario_runner"  # Your ScenarioRunner path
SCENARIO_DIR="converted_rebuilt_scenarios" # Directory with .xosc files
```

## Usage Options

### Interactive Launcher
```bash
./launch_scenario_cycle.sh
```
Choose from menu:
- Run ALL scenarios (432 scenarios, may take 6+ hours)
- Run first 10 scenarios (test run, ~20 minutes)
- Run first 50 scenarios (sample batch, ~2 hours)
- Start from specific scenario
- Check setup only

### Command Line Options
```bash
python3 cycle_scenarios.py [OPTIONS]

Options:
  --scenario-dir DIR     Directory with XOSC files (default: converted_rebuilt_scenarios)
  --carla-root DIR       CARLA installation path (default: /opt/carla-simulator)
  --scenario-runner DIR  ScenarioRunner path (default: ../scenario_runner)
  --start-from NAME      Start from specific scenario name
  --max-scenarios NUM    Maximum number of scenarios to run
  --timeout SEC          Timeout per scenario in seconds (default: 120)
  --check-only           Only check setup, don't run scenarios
```

### Example Commands

**Test run with first 10 scenarios:**
```bash
python3 cycle_scenarios.py --max-scenarios 10
```

**Start from lane change scenarios:**
```bash
python3 cycle_scenarios.py --start-from lane_change_151
```

**Custom paths:**
```bash
python3 cycle_scenarios.py \
  --carla-root "/home/user/CARLA_0.9.15" \
  --scenario-runner "/home/user/scenario_runner" \
  --max-scenarios 25
```

## Features

### Automatic CARLA Management
- Detects if CARLA server is running
- Automatically starts CARLA if needed
- Uses optimized settings (no graphics, 20fps)

### Robust Execution
- Handles scenario timeouts gracefully
- Captures and analyzes all output
- Detects collisions and failures
- Continues execution even if individual scenarios fail

### Detailed Reporting  
- Real-time progress display with status emojis
- Comprehensive execution statistics
- Saves detailed JSON results file
- Shows problematic scenarios and error patterns

### Graceful Interruption
- Press Ctrl+C to stop execution cleanly
- Saves results before exiting
- Terminates current scenario safely

## Output

### Console Output
```
🎬 Running scenario: following_001
📁 File: converted_rebuilt_scenarios/following_001.xosc
⏳ Starting scenario execution...
✅ SUCCESS - 45.2s
   📏 Distance: 200m

[432/432] SCENARIO BATCH PROGRESS
========================================
SCENARIO EXECUTION SUMMARY  
========================================
📊 Total scenarios: 432
✅ Successful: 385 (89.1%)
❌ Failed: 28 (6.5%)
💥 Errors: 12 (2.8%)
⏰ Timeouts: 7 (1.6%)
```

### JSON Results File
Automatically saved as `scenario_results_YYYYMMDD_HHMMSS.json`:

```json
{
  "summary": {
    "total_scenarios": 432,
    "execution_time": 12847.3,
    "success_rate": 89.1
  },
  "results": [
    {
      "scenario": "following_001", 
      "status": "SUCCESS",
      "execution_time": 45.2,
      "collision_detected": false,
      "distance_completed": 200,
      "error": ""
    }
  ]
}
```

## Troubleshooting

### CARLA Not Starting
- Check CARLA path in configuration
- Ensure CARLA executable permissions
- Verify available system resources

### ScenarioRunner Errors
- Verify ScenarioRunner path
- Check Python environment
- Ensure all dependencies installed

### Scenario Failures
- Individual failures are expected and logged
- Check JSON results for error patterns
- Consider adjusting timeout values

### Performance Issues
- CARLA runs with graphics disabled by default
- Reduce FPS if system struggles: edit `-fps=20` to `-fps=10`
- Monitor system resources during execution

## Expected Results

Based on our testing:
- **Success Rate**: 85-95% expected
- **Common Issues**: Actor spawn conflicts, timeout on complex scenarios  
- **Execution Time**: ~30-90 seconds per scenario
- **Total Runtime**: 6-8 hours for all 432 scenarios

## Scenario Categories

- **following_001-150**: Vehicle following scenarios (150 scenarios)
- **lane_change_151-250**: Lane change scenarios (100 scenarios)  
- **pedestrian_251-330**: Pedestrian crossing scenarios (80 scenarios)
- **emergency_331-390**: Emergency vehicle scenarios (60 scenarios)
- **static_391-450**: Static obstacle scenarios (60 scenarios)

Each category tests different autonomous driving behaviors and edge cases.