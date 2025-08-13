#!/usr/bin/env python3
"""Debug spawn point availability for road 27"""

import sys
import json

# Mock carla module
class MockCarla:
    def __getattr__(self, name):
        return None

sys.modules['carla'] = MockCarla()

from xosc_json import JsonToXoscConverter

def debug_spawns():
    converter = JsonToXoscConverter()
    
    # Get spawn points for Town04
    spawn_points = converter._get_spawn_points_for_map('Town04')
    
    # Filter to road 27
    road_27_points = [pt for pt in spawn_points if pt.get('road_id') == 27]
    
    print(f"Total spawn points in Town04: {len(spawn_points)}")
    print(f"Spawn points on road 27: {len(road_27_points)}")
    
    if road_27_points:
        print("\nRoad 27 spawn points by lane:")
        lanes = {}
        for pt in road_27_points:
            lane_id = pt.get('lane_id')
            if lane_id not in lanes:
                lanes[lane_id] = []
            lanes[lane_id].append(pt)
        
        for lane_id in sorted(lanes.keys()):
            print(f"  Lane {lane_id}: {len(lanes[lane_id])} points")
            # Show first few points
            for i, pt in enumerate(lanes[lane_id][:3]):
                print(f"    {i+1}. x={pt.get('x'):.1f}, y={pt.get('y'):.1f}, yaw={pt.get('yaw', 0):.1f}")
    
    # Test ego position
    ego_road = 27
    ego_lane = 1
    ego_x, ego_y = 246.76, -246.15
    
    print(f"\nEgo position: road={ego_road}, lane={ego_lane}, x={ego_x}, y={ego_y}")
    
    # Find same lane candidates with different distance ranges
    same_lane_candidates = [pt for pt in road_27_points 
                           if pt.get('lane_id') == ego_lane]
    
    print(f"Same lane candidates: {len(same_lane_candidates)}")
    
    if same_lane_candidates:
        print("Same lane candidates with distances:")
        for i, pt in enumerate(same_lane_candidates[:10]):
            dist = ((pt.get('x', 0) - ego_x)**2 + (pt.get('y', 0) - ego_y)**2)**0.5
            print(f"  {i+1}. x={pt.get('x'):.1f}, y={pt.get('y'):.1f}, distance={dist:.1f}m")

if __name__ == '__main__':
    debug_spawns()