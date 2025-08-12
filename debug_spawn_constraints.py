#!/usr/bin/env python3
"""
Spawn Constraint Debugger

Provides detailed debugging of spawn constraint matching to understand
exactly why scenarios are failing to find suitable spawn points.
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Tuple
import sys

class SpawnConstraintDebugger:
    def __init__(self, spawns_dir: str = "spawns"):
        self.spawns_dir = Path(spawns_dir)
        self.maps_data = {}
        self.debug_log = []
        
    def load_spawn_data_for_map(self, map_name: str):
        """Load spawn data for a specific map"""
        spawn_file = self.spawns_dir / f"enhanced_{map_name}.json"
        
        if not spawn_file.exists():
            self.log(f"❌ Spawn file not found: {spawn_file}")
            return False
            
        try:
            with open(spawn_file, 'r') as f:
                data = json.load(f)
                
                # Handle different data structures
                spawn_points = []
                if isinstance(data, dict):
                    for map_key, map_data in data.items():
                        if isinstance(map_data, dict):
                            for lane_type, points in map_data.items():
                                if isinstance(points, list):
                                    spawn_points.extend(points)
                
                self.maps_data[map_name] = spawn_points
                self.log(f"✅ Loaded {len(spawn_points)} spawn points for {map_name}")
                return True
        except Exception as e:
            self.log(f"❌ Failed to load {spawn_file}: {e}")
            return False
    
    def log(self, message: str):
        """Add message to debug log"""
        self.debug_log.append(message)
        print(message)
    
    def debug_scenario_constraints(self, scenario_file: str, target_map: str = None):
        """Debug constraint matching for a specific scenario"""
        self.debug_log.clear()
        self.log(f"🔍 Debugging scenario: {scenario_file}")
        
        # Load scenario
        try:
            with open(scenario_file, 'r') as f:
                scenario = json.load(f)
        except Exception as e:
            self.log(f"❌ Failed to load scenario: {e}")
            return
        
        scenario_name = scenario.get('scenario_name', 'unknown')
        self.log(f"📋 Scenario: {scenario_name}")
        
        # Determine target map
        if not target_map:
            target_map = "Town04"  # Default to Town04 like the converter
        
        self.log(f"🗺️  Target map: {target_map}")
        
        # Load spawn data
        if not self.load_spawn_data_for_map(target_map):
            return
        
        spawn_points = self.maps_data[target_map]
        self.log(f"📍 Available spawn points: {len(spawn_points)}")
        
        # Simulate ego spawn (pick a common road/lane for testing)
        ego_spawn = self._pick_representative_ego_spawn(spawn_points)
        if not ego_spawn:
            self.log("❌ No suitable ego spawn found")
            return
            
        self.log(f"🚗 Simulated ego spawn: Road {ego_spawn['road_id']}, Lane {ego_spawn['lane_id']}")
        
        # Debug each actor
        actors = scenario.get('actors', [])
        self.log(f"👥 Actors to spawn: {len(actors)}")
        
        for i, actor in enumerate(actors):
            self.log(f"\n--- ACTOR {i+1}: {actor.get('id', 'unnamed')} ---")
            self._debug_actor_constraints(actor, ego_spawn, spawn_points)
    
    def _pick_representative_ego_spawn(self, spawn_points: List[Dict]) -> Dict:
        """Pick a representative ego spawn point for testing"""
        # Find a spawn point on a road with multiple lanes
        road_lane_counts = {}
        for spawn in spawn_points:
            road_id = spawn.get('road_id')
            if road_id is not None:
                road_lane_counts[road_id] = road_lane_counts.get(road_id, 0) + 1
        
        # Pick road with most spawn points
        if road_lane_counts:
            best_road = max(road_lane_counts.items(), key=lambda x: x[1])[0]
            for spawn in spawn_points:
                if spawn.get('road_id') == best_road and spawn.get('lane_type') == 'Driving':
                    return spawn
        
        # Fallback to first driving spawn
        for spawn in spawn_points:
            if spawn.get('lane_type') == 'Driving':
                return spawn
                
        return None
    
    def _debug_actor_constraints(self, actor: Dict, ego_spawn: Dict, spawn_points: List[Dict]):
        """Debug constraint matching for a single actor"""
        actor_id = actor.get('id', 'unnamed')
        actor_type = actor.get('type', 'vehicle')
        
        spawn_criteria = actor.get('spawn', {}).get('criteria', {})
        self.log(f"🎯 Actor: {actor_id} ({actor_type})")
        self.log(f"🔧 Constraints: {spawn_criteria}")
        
        if not spawn_criteria:
            self.log("⚠️  No spawn criteria defined!")
            return
        
        # Apply constraints step by step
        candidates = spawn_points.copy()
        self.log(f"📊 Initial candidates: {len(candidates)}")
        
        # Filter by lane_type
        if 'lane_type' in spawn_criteria:
            lane_type = spawn_criteria['lane_type']
            before_count = len(candidates)
            candidates = [s for s in candidates if s.get('lane_type') == lane_type]
            self.log(f"🛣️  After lane_type='{lane_type}': {len(candidates)} (filtered out {before_count - len(candidates)})")
            
            if len(candidates) == 0:
                self.log("❌ FAILURE: No spawn points match lane_type constraint")
                self._suggest_lane_type_fixes(spawn_points, lane_type)
                return
        
        # Filter by road_relationship
        if 'road_relationship' in spawn_criteria:
            road_rel = spawn_criteria['road_relationship']
            before_count = len(candidates)
            
            if road_rel == 'same_road':
                ego_road = ego_spawn['road_id']
                candidates = [s for s in candidates if s.get('road_id') == ego_road]
                self.log(f"🛤️  After road_relationship='same_road' (road {ego_road}): {len(candidates)} (filtered out {before_count - len(candidates)})")
                
            elif road_rel == 'different_road':
                ego_road = ego_spawn['road_id']
                candidates = [s for s in candidates if s.get('road_id') != ego_road]
                self.log(f"🛤️  After road_relationship='different_road' (!= {ego_road}): {len(candidates)} (filtered out {before_count - len(candidates)})")
            
            if len(candidates) == 0:
                self.log(f"❌ FAILURE: No spawn points match road_relationship='{road_rel}' constraint")
                self._suggest_road_relationship_fixes(spawn_points, ego_spawn, road_rel)
                return
        
        # Filter by lane_relationship
        if 'lane_relationship' in spawn_criteria:
            lane_rel = spawn_criteria['lane_relationship']
            before_count = len(candidates)
            ego_lane = ego_spawn['lane_id']
            
            if lane_rel == 'same_lane':
                candidates = [s for s in candidates if s.get('lane_id') == ego_lane]
                self.log(f"🛣️  After lane_relationship='same_lane' (lane {ego_lane}): {len(candidates)} (filtered out {before_count - len(candidates)})")
                
            elif lane_rel == 'adjacent_lane':
                # Adjacent means lane ID differs by 1
                adjacent_candidates = []
                for spawn in candidates:
                    spawn_lane = spawn.get('lane_id')
                    if spawn_lane is not None and abs(spawn_lane - ego_lane) == 1:
                        adjacent_candidates.append(spawn)
                candidates = adjacent_candidates
                self.log(f"🛣️  After lane_relationship='adjacent_lane' (to lane {ego_lane}): {len(candidates)} (filtered out {before_count - len(candidates)})")
                
            elif lane_rel == 'any':
                # No filtering needed
                self.log(f"🛣️  After lane_relationship='any': {len(candidates)} (no filtering)")
            
            if len(candidates) == 0:
                self.log(f"❌ FAILURE: No spawn points match lane_relationship='{lane_rel}' constraint")
                self._suggest_lane_relationship_fixes(spawn_points, ego_spawn, lane_rel)
                return
        
        # Filter by distance
        if 'distance_to_ego' in spawn_criteria:
            distance_range = spawn_criteria['distance_to_ego']
            min_dist = distance_range.get('min', 0)
            max_dist = distance_range.get('max', 1000)
            
            before_count = len(candidates)
            distance_candidates = []
            
            for spawn in candidates:
                distance = self._calculate_distance(ego_spawn, spawn)
                if min_dist <= distance <= max_dist:
                    distance_candidates.append((spawn, distance))
            
            candidates = [s[0] for s in distance_candidates]
            self.log(f"📏 After distance_to_ego ({min_dist}-{max_dist}m): {len(candidates)} (filtered out {before_count - len(candidates)})")
            
            if len(candidates) == 0:
                self.log(f"❌ FAILURE: No spawn points within distance range {min_dist}-{max_dist}m")
                self._suggest_distance_fixes(spawn_points, ego_spawn, min_dist, max_dist)
                return
            
            # Show distance distribution of remaining candidates
            distances = [s[1] for s in distance_candidates]
            if distances:
                self.log(f"📊 Distance range of candidates: {min(distances):.1f}m - {max(distances):.1f}m (avg: {np.mean(distances):.1f}m)")
        
        # Filter by relative_position
        if 'relative_position' in spawn_criteria:
            rel_pos = spawn_criteria['relative_position']
            before_count = len(candidates)
            
            # This is a simplification - in reality this would use heading vectors
            self.log(f"📍 After relative_position='{rel_pos}': {len(candidates)} (position check simplified)")
        
        # Success!
        if candidates:
            self.log(f"✅ SUCCESS: Found {len(candidates)} valid spawn candidates")
            
            # Show details of first few candidates
            for i, spawn in enumerate(candidates[:3]):
                distance = self._calculate_distance(ego_spawn, spawn)
                self.log(f"  Candidate {i+1}: Road {spawn['road_id']}, Lane {spawn['lane_id']}, Distance {distance:.1f}m")
        else:
            self.log("❌ FAILURE: No valid spawn points found after all constraints")
    
    def _calculate_distance(self, spawn1: Dict, spawn2: Dict) -> float:
        """Calculate 2D distance between two spawn points"""
        x1, y1 = spawn1.get('x', 0), spawn1.get('y', 0)
        x2, y2 = spawn2.get('x', 0), spawn2.get('y', 0)
        return ((x2 - x1)**2 + (y2 - y1)**2)**0.5
    
    def _suggest_lane_type_fixes(self, spawn_points: List[Dict], target_lane_type: str):
        """Suggest fixes for lane_type constraint failures"""
        lane_type_counts = {}
        for spawn in spawn_points:
            lt = spawn.get('lane_type', 'Unknown')
            lane_type_counts[lt] = lane_type_counts.get(lt, 0) + 1
        
        self.log(f"💡 Available lane types: {dict(lane_type_counts)}")
        
        if target_lane_type == 'Sidewalk' and lane_type_counts.get('Sidewalk', 0) < 50:
            self.log("💡 SUGGESTION: Add more Sidewalk spawn points for pedestrian scenarios")
        elif target_lane_type == 'Driving' and lane_type_counts.get('Driving', 0) < 1000:
            self.log("💡 SUGGESTION: Add more Driving spawn points")
    
    def _suggest_road_relationship_fixes(self, spawn_points: List[Dict], ego_spawn: Dict, road_rel: str):
        """Suggest fixes for road_relationship constraint failures"""
        ego_road = ego_spawn['road_id']
        road_counts = {}
        
        for spawn in spawn_points:
            road_id = spawn.get('road_id')
            if road_id is not None:
                road_counts[road_id] = road_counts.get(road_id, 0) + 1
        
        if road_rel == 'same_road':
            same_road_count = road_counts.get(ego_road, 0)
            self.log(f"💡 Ego road {ego_road} has {same_road_count} spawn points total")
            if same_road_count < 10:
                self.log(f"💡 SUGGESTION: Add more spawn points to road {ego_road}")
        
        elif road_rel == 'different_road':
            other_roads = [r for r in road_counts.keys() if r != ego_road]
            self.log(f"💡 Available other roads: {len(other_roads)} (ego is on road {ego_road})")
    
    def _suggest_lane_relationship_fixes(self, spawn_points: List[Dict], ego_spawn: Dict, lane_rel: str):
        """Suggest fixes for lane_relationship constraint failures"""
        ego_road = ego_spawn['road_id']
        ego_lane = ego_spawn['lane_id']
        
        # Find all lanes on the same road as ego
        same_road_lanes = {}
        for spawn in spawn_points:
            if spawn.get('road_id') == ego_road:
                lane_id = spawn.get('lane_id')
                if lane_id is not None:
                    same_road_lanes[lane_id] = same_road_lanes.get(lane_id, 0) + 1
        
        self.log(f"💡 Lanes on ego road {ego_road}: {dict(same_road_lanes)}")
        
        if lane_rel == 'same_lane':
            same_lane_count = same_road_lanes.get(ego_lane, 0)
            self.log(f"💡 Ego lane {ego_lane} has {same_lane_count} spawn points")
            if same_lane_count < 2:
                self.log(f"💡 SUGGESTION: Add more spawn points to road {ego_road}, lane {ego_lane}")
        
        elif lane_rel == 'adjacent_lane':
            adjacent_lanes = [ego_lane - 1, ego_lane + 1]
            available_adjacent = [l for l in adjacent_lanes if l in same_road_lanes]
            self.log(f"💡 Adjacent lanes ({adjacent_lanes}) available: {available_adjacent}")
            
            if not available_adjacent:
                self.log(f"💡 SUGGESTION: Add spawn points to adjacent lanes of lane {ego_lane} on road {ego_road}")
    
    def _suggest_distance_fixes(self, spawn_points: List[Dict], ego_spawn: Dict, min_dist: float, max_dist: float):
        """Suggest fixes for distance constraint failures"""
        distances = []
        for spawn in spawn_points:
            if (spawn.get('road_id') == ego_spawn['road_id'] and 
                spawn.get('lane_id') == ego_spawn['lane_id']):
                distance = self._calculate_distance(ego_spawn, spawn)
                distances.append(distance)
        
        if distances:
            distances.sort()
            self.log(f"💡 Actual distances on same road/lane: {[f'{d:.1f}m' for d in distances[:5]]}...")
            self.log(f"💡 Range: {min(distances):.1f}m - {max(distances):.1f}m")
            
            closest = min(distances)
            if closest > max_dist:
                self.log(f"💡 SUGGESTION: Increase max_dist to at least {closest:.0f}m")
            
            furthest = max(distances)
            if furthest < min_dist:
                self.log(f"💡 SUGGESTION: Decrease min_dist to at most {furthest:.0f}m")
        else:
            self.log("💡 SUGGESTION: Add more spawn points on the same road/lane for distance constraints")
    
    def save_debug_log(self, output_file: str):
        """Save debug log to file"""
        with open(output_file, 'w') as f:
            for line in self.debug_log:
                f.write(line + '\n')
        print(f"📄 Debug log saved: {output_file}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_spawn_constraints.py <scenario_file> [map_name]")
        print("Example: python debug_spawn_constraints.py demo_scenarios/basic_following_001_stop_and_go_traffic_01.json Town04")
        return
    
    scenario_file = sys.argv[1]
    map_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    debugger = SpawnConstraintDebugger()
    debugger.debug_scenario_constraints(scenario_file, map_name)
    
    # Save debug log
    output_file = f"debug_{Path(scenario_file).stem}.txt"
    debugger.save_debug_log(output_file)

if __name__ == "__main__":
    main()