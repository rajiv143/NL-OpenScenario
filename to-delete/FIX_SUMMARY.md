# CRITICAL FIX: Using Pre-Validated Spawn Points Only

## Problem
The system was GENERATING new coordinates by calculating positions along road geometry, which resulted in vehicles spawning in water (e.g., at coordinates 230.7, 311.2 in Town04).

## Root Cause
The `_generate_spawn_from_road_intelligence()` method was creating NEW coordinates by:
- Taking road geometry segments
- Calculating positions along them
- Adding lane offsets

This resulted in coordinates that were NOT validated and could be off-road or in water.

## Solution
Reverted to using ONLY the pre-validated spawn points from the enhanced spawn files:
- These files contain 17,289 validated spawn points for Town04
- Each point is guaranteed to be on a valid road
- Coordinates are taken directly from these files, NOT calculated

## Key Changes
1. Modified `_choose_spawn()` to ALWAYS use enhanced spawn files
2. Removed the road intelligence coordinate generation 
3. Now picks from actual validated spawn points

## Example Valid Spawns (Town04)
- x=246.7, y=-249.7 (Road 27, Lane -1) ✅
- x=214.7, y=-252.9 (Road 27, Lane -1) ✅
- x=379.7, y=-19.1 (Road 1602, Lane -4) ✅

## Result
All spawns are now GUARANTEED to be on valid roads, never in water or off-road, because we're using the exact coordinates from the pre-validated spawn files.

The enhanced spawn files are the source of truth for valid spawn positions.
