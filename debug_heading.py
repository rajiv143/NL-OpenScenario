#!/usr/bin/env python3
"""Debug the heading issue"""

import sys
import math

# Mock carla module
class MockCarla:
    def __getattr__(self, name):
        return None

sys.modules['carla'] = MockCarla()

from xosc_json import JsonToXoscConverter

def debug_heading():
    converter = JsonToXoscConverter()
    
    # Get spawn points for Town04, road 0, lane 1
    spawn_points = converter._get_spawn_points_for_map('Town04')
    road_0_lane_1 = [pt for pt in spawn_points 
                     if pt.get('road_id') == 0 and pt.get('lane_id') == 1]
    
    print(f"Road 0, Lane 1 spawn points: {len(road_0_lane_1)}")
    
    if road_0_lane_1:
        # Sort by position like the strategic spawn does
        sorted_candidates = sorted(road_0_lane_1, key=lambda pt: (pt.get('x', 0), pt.get('y', 0)))
        
        # Get the strategic range (positions 6-14 of 18)
        start_idx = len(sorted_candidates) // 3  # Skip first 33%
        end_idx = int(len(sorted_candidates) * 0.8)  # Stop at 80%
        strategic_candidates = sorted_candidates[start_idx:end_idx]
        
        print(f"Strategic range: positions {start_idx}-{end_idx} of {len(sorted_candidates)}")
        
        if strategic_candidates:
            # Get the middle candidate (what strategic spawn picks)
            best_candidate = strategic_candidates[len(strategic_candidates)//2]
            
            print(f"\nSelected strategic ego spawn:")
            print(f"  Position: x={best_candidate.get('x')}, y={best_candidate.get('y')}")
            print(f"  Raw yaw: {best_candidate.get('yaw')} radians")
            print(f"  Raw yaw in degrees: {math.degrees(best_candidate.get('yaw', 0)):.1f}°")
            
            # Check a lead vehicle spawn point for comparison
            lead_spawn = sorted_candidates[0]  # First point (ahead)
            print(f"\nLead vehicle spawn (first point):")
            print(f"  Position: x={lead_spawn.get('x')}, y={lead_spawn.get('y')}")
            print(f"  Raw yaw: {lead_spawn.get('yaw')} radians")
            print(f"  Raw yaw in degrees: {math.degrees(lead_spawn.get('yaw', 0)):.1f}°")
            
            # Check if they should have the same heading (same lane)
            print(f"\nHeading comparison:")
            print(f"  Ego heading: {math.degrees(best_candidate.get('yaw', 0)):.1f}°")
            print(f"  Lead heading: {math.degrees(lead_spawn.get('yaw', 0)):.1f}°")
            print(f"  Difference: {abs(math.degrees(best_candidate.get('yaw', 0)) - math.degrees(lead_spawn.get('yaw', 0))):.1f}°")

if __name__ == '__main__':
    debug_heading()