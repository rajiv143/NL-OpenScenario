#!/usr/bin/env python3
"""
Direct test of the actual constraint matching logic from xosc_json.py
to understand why scenarios are failing to find spawn points.
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

class ActualConstraintTester:
    def __init__(self):
        self.spawns_dir = Path("spawns")
        self.maps_data = {}
        
    def load_spawn_data_for_map(self, map_name: str):
        """Load spawn data exactly like xosc_json.py does"""
        spawn_file = self.spawns_dir / f"enhanced_{map_name}.json"
        
        try:
            with open(spawn_file, 'r') as f:
                data = json.load(f)
                
                # Handle the actual data structure used by xosc_json.py
                spawn_points = []
                if isinstance(data, dict):
                    for map_key, map_data in data.items():
                        if isinstance(map_data, dict):
                            for lane_type, points in map_data.items():
                                if isinstance(points, list):
                                    spawn_points.extend(points)
                
                self.maps_data[map_name] = spawn_points
                print(f"✅ Loaded {len(spawn_points)} spawn points for {map_name}")
                return True
        except Exception as e:
            print(f"❌ Failed to load {spawn_file}: {e}")
            return False
    
    def are_same_direction_lanes(self, ego_lane_id: int, candidate_lane_id: int) -> bool:
        """Exact copy of the logic from xosc_json.py"""
        if ego_lane_id == 0 or candidate_lane_id == 0:
            return True  # Center lane (reference line) is compatible with both directions
        return (ego_lane_id > 0) == (candidate_lane_id > 0)
    
    def filter_by_lane_relationship(self, candidates: List[Dict], relationship: str, ego_lane: Optional[Tuple[int, int]]) -> List[Dict]:
        """Exact copy of the lane relationship filter from xosc_json.py"""
        ego_road_id, ego_lane_id = ego_lane if ego_lane else (None, None)
        
        if relationship == 'same_lane' and ego_lane:
            result = [pt for pt in candidates 
                    if pt.get('road_id') == ego_road_id and pt.get('lane_id') == ego_lane_id]
            print(f"Lane relationship 'same_lane': filtering to road_id={ego_road_id}, lane_id={ego_lane_id} -> {len(result)} candidates")
            return result
        elif relationship == 'adjacent_lane' and ego_lane:
            # For adjacent lanes, ensure same direction by default (same sign of lane_id)
            adjacent_candidates = []
            for pt in candidates:
                if pt.get('road_id') == ego_road_id:
                    pt_lane_id = pt.get('lane_id', 0)
                    # Adjacent means distance of 1 AND same direction (same sign)
                    if (abs(pt_lane_id - ego_lane_id) == 1 and 
                        self.are_same_direction_lanes(ego_lane_id, pt_lane_id)):
                        adjacent_candidates.append(pt)
            
            print(f"Lane relationship 'adjacent_lane': filtering to road_id={ego_road_id}, same-direction lanes adjacent to {ego_lane_id} -> {len(adjacent_candidates)} candidates")
            return adjacent_candidates
        else:  # 'any_lane' or ego not positioned yet
            print(f"Lane relationship '{relationship}': no filtering -> {len(candidates)} candidates")
            return candidates
    
    def test_problematic_scenarios(self, map_name: str = "Town04"):
        """Test the scenarios that are known to be problematic"""
        if not self.load_spawn_data_for_map(map_name):
            return
        
        spawn_points = self.maps_data[map_name]
        print(f"\n📍 Testing with {len(spawn_points)} spawn points from {map_name}")
        
        # Test the scenarios that were showing fallback issues
        test_cases = [
            {
                "name": "Following same_lane test",
                "ego_road": 27,
                "ego_lane": 1,
                "constraint": "same_lane"
            },
            {
                "name": "Adjacent lane test",
                "ego_road": 27,
                "ego_lane": 1,
                "constraint": "adjacent_lane"
            },
            {
                "name": "Following same_lane negative lane",
                "ego_road": 27,
                "ego_lane": -1,
                "constraint": "same_lane"
            },
            {
                "name": "Adjacent lane negative lane",
                "ego_road": 27,
                "ego_lane": -1,
                "constraint": "adjacent_lane"
            }
        ]
        
        for test_case in test_cases:
            print(f"\n🔬 {test_case['name']}")
            print(f"   Ego: Road {test_case['ego_road']}, Lane {test_case['ego_lane']}")
            
            # Filter to same road first
            same_road_candidates = [pt for pt in spawn_points if pt.get('road_id') == test_case['ego_road']]
            print(f"   Same road candidates: {len(same_road_candidates)}")
            
            if same_road_candidates:
                # Show lane distribution on this road
                lane_counts = {}
                for pt in same_road_candidates:
                    lane_id = pt.get('lane_id')
                    lane_counts[lane_id] = lane_counts.get(lane_id, 0) + 1
                print(f"   Lane distribution: {dict(sorted(lane_counts.items()))}")
                
                # Filter by driving lanes only
                driving_candidates = [pt for pt in same_road_candidates if pt.get('lane_type') == 'Driving']
                print(f"   Driving lanes: {len(driving_candidates)}")
                
                # Apply lane relationship filter
                ego_lane_tuple = (test_case['ego_road'], test_case['ego_lane'])
                result = self.filter_by_lane_relationship(driving_candidates, test_case['constraint'], ego_lane_tuple)
                
                print(f"   Final result: {len(result)} spawn points")
                
                if result:
                    print(f"   ✅ SUCCESS - Found valid spawn points")
                    # Show a few examples
                    for i, pt in enumerate(result[:3]):
                        print(f"      {i+1}: Lane {pt.get('lane_id')}, pos({pt.get('x'):.1f}, {pt.get('y'):.1f})")
                else:
                    print(f"   ❌ FAILED - No spawn points found")
                    
                    # Diagnostic information
                    if test_case['constraint'] == 'same_lane':
                        target_lane = test_case['ego_lane']
                        lane_count = lane_counts.get(target_lane, 0)
                        print(f"      Lane {target_lane} has {lane_count} total spawn points on road {test_case['ego_road']}")
                        
                        # Check if any are driving lanes
                        driving_on_lane = len([pt for pt in same_road_candidates 
                                             if pt.get('lane_id') == target_lane and pt.get('lane_type') == 'Driving'])
                        print(f"      Lane {target_lane} has {driving_on_lane} driving spawn points")
                        
                    elif test_case['constraint'] == 'adjacent_lane':
                        ego_lane_id = test_case['ego_lane']
                        adjacent_lanes = [ego_lane_id - 1, ego_lane_id + 1]
                        
                        print(f"      Looking for adjacent lanes: {adjacent_lanes}")
                        for adj_lane in adjacent_lanes:
                            if adj_lane in lane_counts:
                                same_dir = self.are_same_direction_lanes(ego_lane_id, adj_lane)
                                print(f"         Lane {adj_lane}: {lane_counts[adj_lane]} points, same direction: {same_dir}")
                            else:
                                print(f"         Lane {adj_lane}: No spawn points")
            else:
                print(f"   ❌ FAILED - Road {test_case['ego_road']} has no spawn points at all")
    
    def analyze_lane_patterns(self, map_name: str = "Town04"):
        """Analyze lane ID patterns to understand the structure"""
        if not self.load_spawn_data_for_map(map_name):
            return
        
        spawn_points = self.maps_data[map_name]
        
        # Group by road
        roads = {}
        for pt in spawn_points:
            road_id = pt.get('road_id')
            if road_id not in roads:
                roads[road_id] = {'lanes': {}, 'total': 0}
            
            lane_id = pt.get('lane_id')
            lane_type = pt.get('lane_type', 'Unknown')
            
            if lane_id not in roads[road_id]['lanes']:
                roads[road_id]['lanes'][lane_id] = {'types': {}, 'count': 0}
            
            roads[road_id]['lanes'][lane_id]['count'] += 1
            roads[road_id]['lanes'][lane_id]['types'][lane_type] = roads[road_id]['lanes'][lane_id]['types'].get(lane_type, 0) + 1
            roads[road_id]['total'] += 1
        
        # Find roads with most spawn points for analysis
        top_roads = sorted(roads.items(), key=lambda x: x[1]['total'], reverse=True)[:10]
        
        print(f"\n📊 Top 10 roads by spawn point count in {map_name}:")
        for road_id, road_data in top_roads:
            print(f"\n🛤️  Road {road_id}: {road_data['total']} spawn points")
            sorted_lanes = sorted(road_data['lanes'].items())
            
            for lane_id, lane_data in sorted_lanes:
                types_str = ", ".join([f"{t}:{c}" for t, c in lane_data['types'].items()])
                print(f"     Lane {lane_id:3d}: {lane_data['count']:3d} points ({types_str})")
            
            # Check for adjacent lane availability
            lane_ids = list(road_data['lanes'].keys())
            driving_lanes = [lid for lid, ldata in road_data['lanes'].items() 
                           if 'Driving' in ldata['types']]
            
            print(f"     Driving lanes: {sorted(driving_lanes)}")
            
            # Check for adjacent pairs in driving lanes
            adjacent_pairs = []
            for i, lane_id in enumerate(sorted(driving_lanes)):
                for j in range(i+1, len(driving_lanes)):
                    other_lane = driving_lanes[j]
                    if abs(lane_id - other_lane) == 1:
                        same_dir = self.are_same_direction_lanes(lane_id, other_lane)
                        adjacent_pairs.append((lane_id, other_lane, same_dir))
            
            if adjacent_pairs:
                print(f"     Adjacent pairs: {adjacent_pairs}")
            else:
                print(f"     ⚠️  No adjacent lane pairs found!")

def main():
    tester = ActualConstraintTester()
    
    # First, analyze the lane patterns
    print("🔍 Analyzing lane patterns in Town04...")
    tester.analyze_lane_patterns("Town04")
    
    # Then test problematic scenarios
    print("\n🔬 Testing problematic constraint scenarios...")
    tester.test_problematic_scenarios("Town04")

if __name__ == "__main__":
    main()