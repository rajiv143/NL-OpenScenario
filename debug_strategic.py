#!/usr/bin/env python3
"""Debug strategic ego spawn"""

import sys
import json

# Mock carla module
class MockCarla:
    def __getattr__(self, name):
        return None

sys.modules['carla'] = MockCarla()

from xosc_json import JsonToXoscConverter

def debug_strategic():
    # Load the JSON
    with open('generated_scenarios/basic_following_001_stop_and_go_traffic_01.json', 'r') as f:
        json_data = json.load(f)
    
    converter = JsonToXoscConverter()
    
    # Check what strategic analysis finds
    needs_ahead = False
    needs_behind = False
    same_lane_actors = False
    
    for actor in json_data.get('actors', []):
        if 'spawn' in actor:
            spawn_criteria = actor['spawn'].get('criteria', {})
            rel_pos = spawn_criteria.get('relative_position')
            lane_rel = spawn_criteria.get('lane_relationship')
            
            if rel_pos == 'ahead':
                needs_ahead = True
            elif rel_pos == 'behind':
                needs_behind = True
                
            if lane_rel in ['same_lane', 'adjacent_lane']:
                same_lane_actors = True
    
    print(f"Strategic analysis: needs_ahead={needs_ahead}, needs_behind={needs_behind}, same_lane_actors={same_lane_actors}")
    
    # Get spawn points for Town04
    spawn_points = converter._get_spawn_points_for_map('Town04')
    
    # Apply ego constraints
    ego_criteria = json_data['ego_spawn'].get('criteria', {})
    print(f"Ego criteria: {ego_criteria}")
    
    candidates = spawn_points
    if 'lane_id' in ego_criteria:
        lane_constraint = ego_criteria['lane_id']
        if isinstance(lane_constraint, dict):
            min_lane = lane_constraint.get('min', 1)
            max_lane = lane_constraint.get('max', 10)
            candidates = [pt for pt in candidates 
                        if min_lane <= pt.get('lane_id', 0) <= max_lane]
    
    print(f"Candidates after ego constraints: {len(candidates)}")
    
    # Group by road/lane  
    lane_groups = {}
    for candidate in candidates:
        road_id = candidate.get('road_id')
        lane_id = candidate.get('lane_id')
        key = (road_id, lane_id)
        if key not in lane_groups:
            lane_groups[key] = []
        lane_groups[key].append(candidate)
    
    print(f"Lane groups: {len(lane_groups)}")
    
    # Show groups with enough points
    suitable_groups = []
    for (road_id, lane_id), lane_candidates in lane_groups.items():
        if len(lane_candidates) >= 5:
            suitable_groups.append((road_id, lane_id, len(lane_candidates)))
    
    print(f"Suitable groups (>=5 points): {suitable_groups[:10]}")
    
    # Test the specific road 27 that was used before
    road_27_candidates = [pt for pt in candidates if pt.get('road_id') == 27]
    print(f"Road 27 candidates in ego constraints: {len(road_27_candidates)}")
    
    if road_27_candidates:
        lane_1_candidates = [pt for pt in road_27_candidates if pt.get('lane_id') == 1]
        print(f"Road 27, Lane 1 candidates: {len(lane_1_candidates)}")

if __name__ == '__main__':
    debug_strategic()