#!/usr/bin/env python3
"""Debug detailed filtering process"""

import sys
import json
import math

# Mock carla module
class MockCarla:
    def __getattr__(self, name):
        return None

sys.modules['carla'] = MockCarla()

from xosc_json import JsonToXoscConverter

def debug_detailed():
    converter = JsonToXoscConverter()
    
    # Get spawn points for Town04
    spawn_points = converter._get_spawn_points_for_map('Town04')
    
    # Filter to road 27, lane 1
    road_27_lane_1 = [pt for pt in spawn_points 
                      if pt.get('road_id') == 27 and pt.get('lane_id') == 1]
    
    print(f"Road 27, Lane 1 candidates: {len(road_27_lane_1)}")
    
    # Test criteria from the JSON
    ego_pos = (246.76, -246.15, 0.0, 6.28)  # x, y, z, yaw
    criteria = {
        'lane_type': 'Driving',
        'road_relationship': 'same_road',
        'lane_relationship': 'same_lane',
        'distance_to_ego': {'min': 18, 'max': 48},
        'relative_position': 'ahead'
    }
    
    print(f"\nTesting criteria: {criteria}")
    print(f"Ego position: x={ego_pos[0]}, y={ego_pos[1]}, yaw={ego_pos[3]:.2f} rad")
    
    # Test each candidate manually
    valid_candidates = []
    for i, pt in enumerate(road_27_lane_1):
        x, y = pt.get('x', 0), pt.get('y', 0)
        dist = math.hypot(x - ego_pos[0], y - ego_pos[1])
        
        # Test distance constraint
        distance_ok = criteria['distance_to_ego']['min'] <= dist <= criteria['distance_to_ego']['max']
        
        # Test relative position (ahead)
        # Use the converter's method
        rel_pos = converter._get_relative_position(ego_pos, pt)
        position_ok = rel_pos == 'ahead'
        
        print(f"  {i+1}. x={x:.1f}, y={y:.1f}, dist={dist:.1f}m, rel_pos='{rel_pos}', "
              f"distance_ok={distance_ok}, position_ok={position_ok}")
        
        if distance_ok and position_ok:
            valid_candidates.append(pt)
    
    print(f"\nValid candidates after all filtering: {len(valid_candidates)}")

if __name__ == '__main__':
    debug_detailed()