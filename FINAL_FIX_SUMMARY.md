# Fixed: Road Intelligence Spawn Generation Issues

## Problems Identified and Fixed

### 1. Relative Position Not Handled
**Issue**: The `relative_position` constraint in spawn criteria was being ignored
**Fix**: 
- Added relative position checking during road selection
- Roads are now scored based on whether they'll place the actor ahead/behind ego
- Geometry segments are tested to find best relative position match

### 2. Vehicles Placed Off-Road  
**Issue**: Lane offset calculation was wrong, multiplying lane count by width
**Fix**:
- Now correctly sums lane widths from center to target lane
- Accounts for varying lane widths (shoulder: 0.5m, driving: 3.5m, etc.)
- Places vehicle in lane center, not at arbitrary offset

### 3. Speed Limit Comparison Error
**Issue**: Comparison with NoneType when speed_limit was None
**Fix**: Added null check with `or 0` fallback

### 4. Road Context Mismatch
**Issue**: Road data uses 'town' but criteria uses 'urban'
**Fix**: Added mapping between common context names and road types

## Test Results

Testing with `generated_001.json`:
- ✅ Relative position "ahead" correctly enforced
- ✅ Vehicle placed on shoulder lane as requested
- ✅ Distance constraint (18-25m) respected  
- ✅ Spawns generated from actual road geometry

## Code Changes

1. **`_generate_spawn_from_road_intelligence()`**:
   - Better road selection based on relative position
   - Improved lane offset calculation
   - Added relative position verification and adjustment

2. **`_choose_spawn()`**:
   - Prioritizes road intelligence over pre-computed spawns
   - Falls back gracefully when road intelligence fails

The system now generates more accurate and reliable spawn positions based on actual road geometry and properly respects all spawn constraints.
