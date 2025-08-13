#!/usr/bin/env python3
"""Debug why road 27 wasn't chosen"""

import sys
import json

# Mock carla module
class MockCarla:
    def __getattr__(self, name):
        return None

sys.modules['carla'] = MockCarla()

from xosc_json import JsonToXoscConverter

def debug_strategic2():
    # Load the JSON
    with open('generated_scenarios/basic_following_001_stop_and_go_traffic_01.json', 'r') as f:
        json_data = json.load(f)
    
    converter = JsonToXoscConverter()
    
    # Get spawn points for Town04
    spawn_points = converter._get_spawn_points_for_map('Town04')
    
    # Apply ego constraints
    ego_criteria = json_data['ego_spawn'].get('criteria', {})
    candidates = spawn_points
    if 'lane_id' in ego_criteria:
        lane_constraint = ego_criteria['lane_id']
        if isinstance(lane_constraint, dict):
            min_lane = lane_constraint.get('min', 1)
            max_lane = lane_constraint.get('max', 10)
            candidates = [pt for pt in candidates 
                        if min_lane <= pt.get('lane_id', 0) <= max_lane]
    
    # Group by road/lane and show details for road 27
    lane_groups = {}
    for candidate in candidates:
        road_id = candidate.get('road_id')
        lane_id = candidate.get('lane_id')
        key = (road_id, lane_id)
        if key not in lane_groups:
            lane_groups[key] = []
        lane_groups[key].append(candidate)
    
    print("Road 27 analysis:")
    road_27_groups = {k: v for k, v in lane_groups.items() if k[0] == 27}
    for (road_id, lane_id), lane_candidates in road_27_groups.items():
        print(f"  Road {road_id}, Lane {lane_id}: {len(lane_candidates)} candidates")
        if len(lane_candidates) >= 5:
            print(f"    ✓ Suitable (>=5 points)")
        else:
            print(f"    ✗ Not suitable (<5 points)")
    
    # Check which group gets selected first
    print("\nFirst few suitable groups:")
    count = 0
    for (road_id, lane_id), lane_candidates in lane_groups.items():
        if len(lane_candidates) >= 5:
            print(f"  {count+1}. Road {road_id}, Lane {lane_id}: {len(lane_candidates)} candidates")
            count += 1
            if count >= 10:
                break
    
    # Check if road 27 has the 'is_intersection': False constraint
    print("\nRoad 27 intersection check:")
    road_27_candidates = [pt for pt in candidates if pt.get('road_id') == 27]
    if road_27_candidates:
        sample = road_27_candidates[0]
        print(f"  Sample point: {sample}")
        is_intersection = sample.get('is_intersection', False)
        print(f"  is_intersection: {is_intersection}")
        
        # Apply intersection filter
        if 'is_intersection' in ego_criteria:
            wanted_intersection = ego_criteria['is_intersection']
            print(f"  Wanted intersection: {wanted_intersection}")
            if wanted_intersection != is_intersection:
                print(f"  ✗ Filtered out by intersection constraint")
            else:
                print(f"  ✓ Passes intersection constraint")

if __name__ == '__main__':
    debug_strategic2()