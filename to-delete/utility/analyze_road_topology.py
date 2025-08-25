#!/usr/bin/env python3
"""
Road Topology Analyzer - Detailed analysis of road spawn point availability
Identifies why certain roads can't support specific scenario types (like cut-in scenarios)
"""

import json
import os
import math
from collections import defaultdict
from typing import Dict, List, Any, Tuple, Optional

class RoadTopologyAnalyzer:
    def __init__(self):
        """Initialize the analyzer with spawn and road intelligence data"""
        self.spawn_data = {}
        self.road_intelligence = {}
        self._load_data()
        
    def _load_data(self):
        """Load spawn points and road intelligence for all maps"""
        base_dir = os.path.dirname(__file__)
        
        # Load spawn data
        spawns_dir = os.path.join(base_dir, "spawns")
        for map_file in os.listdir(spawns_dir):
            if map_file.startswith("enhanced_Town") and map_file.endswith(".json"):
                map_name = map_file.replace("enhanced_", "").replace(".json", "")
                try:
                    with open(os.path.join(spawns_dir, map_file), 'r') as f:
                        data = json.load(f)
                        spawn_points = []
                        
                        # Handle nested structure like {"Carla/Maps/Town04": {"Driving": [...]}}
                        if isinstance(data, dict):
                            for map_key, map_data in data.items():
                                if isinstance(map_data, dict):
                                    for category_key, category_data in map_data.items():
                                        if isinstance(category_data, list):
                                            spawn_points.extend(category_data)
                                elif isinstance(map_data, list):
                                    spawn_points.extend(map_data)
                        elif isinstance(data, list):
                            spawn_points = data
                            
                        self.spawn_data[map_name] = spawn_points
                        print(f"Loaded {len(spawn_points)} spawn points for {map_name}")
                except Exception as e:
                    print(f"Error loading {map_file}: {e}")
        
        # Load road intelligence
        road_intel_dir = os.path.join(base_dir, "road_intelligence")
        for map_file in os.listdir(road_intel_dir):
            if map_file.endswith("_road_intelligence.json"):
                map_name = map_file.replace("_road_intelligence.json", "")
                try:
                    with open(os.path.join(road_intel_dir, map_file), 'r') as f:
                        self.road_intelligence[map_name] = json.load(f)
                except Exception as e:
                    print(f"Error loading {map_file}: {e}")
        
    def analyze_road(self, map_name: str, road_id: int) -> Dict:
        """Detailed analysis of what's available on a specific road"""
        if map_name not in self.spawn_data:
            return {"error": f"No spawn data for {map_name}"}
        
        spawn_points = self.spawn_data[map_name]
        road_spawns = [pt for pt in spawn_points if pt.get('road_id') == road_id]
        
        if not road_spawns:
            return {"error": f"No spawn points found on road {road_id} in {map_name}"}
        
        # Analyze lanes
        lanes_with_spawns = set()
        lane_groups = defaultdict(list)
        
        for pt in road_spawns:
            lane_id = pt.get('lane_id')
            if lane_id is not None:
                lanes_with_spawns.add(lane_id)
                lane_groups[lane_id].append(pt)
        
        # Find adjacent lane pairs
        adjacent_pairs = []
        sorted_lanes = sorted(lanes_with_spawns)
        for i, lane_id in enumerate(sorted_lanes):
            # Check for adjacent lanes (difference of 1 or -1)
            for other_lane in sorted_lanes[i+1:]:
                if abs(other_lane - lane_id) == 1:
                    adjacent_pairs.append((lane_id, other_lane))
        
        # Calculate spawn density and coverage
        spawn_density = {}
        coverage_gaps = {}
        for lane_id, points in lane_groups.items():
            if len(points) > 1:
                # Sort by position along the road
                points_sorted = sorted(points, key=lambda p: (p.get('x', 0)**2 + p.get('y', 0)**2))
                distances = []
                for i in range(len(points_sorted) - 1):
                    p1, p2 = points_sorted[i], points_sorted[i+1]
                    dist = math.sqrt((p2.get('x', 0) - p1.get('x', 0))**2 + 
                                   (p2.get('y', 0) - p1.get('y', 0))**2)
                    distances.append(dist)
                
                spawn_density[lane_id] = {
                    "points_count": len(points),
                    "avg_spacing": sum(distances) / len(distances) if distances else 0,
                    "max_gap": max(distances) if distances else 0,
                    "min_gap": min(distances) if distances else 0
                }
            else:
                spawn_density[lane_id] = {
                    "points_count": len(points),
                    "avg_spacing": 0,
                    "max_gap": 0,
                    "min_gap": 0
                }
        
        # Get road intelligence if available
        road_context = {}
        if map_name in self.road_intelligence:
            road_data = self.road_intelligence[map_name]
            if 'roads' in road_data and str(road_id) in road_data['roads']:
                road_info = road_data['roads'][str(road_id)]
                road_context = {
                    "type": road_info.get('type', 'unknown'),
                    "speed_limit": road_info.get('speed_limit', 'unknown'),
                    "lanes": road_info.get('lanes', {}),
                    "context": road_info.get('context', 'unknown'),
                    "curvature": road_info.get('curvature', 'unknown'),
                    "connectivity": road_info.get('connectivity', 'unknown')
                }
        
        return {
            "road_id": road_id,
            "map_name": map_name,
            "total_spawn_points": len(road_spawns),
            "lanes_with_spawns": sorted(list(lanes_with_spawns)),
            "adjacent_lane_pairs": adjacent_pairs,
            "spawn_density": spawn_density,
            "road_context": road_context,
            "supports_cut_in": len(adjacent_pairs) > 0,
            "supports_lane_change": len(adjacent_pairs) > 0,
            "supports_following": len(road_spawns) >= 2
        }
    
    def analyze_scenario_support(self, map_name: str) -> Dict:
        """Analyze which roads in a map support different scenario types"""
        if map_name not in self.spawn_data:
            return {"error": f"No spawn data for {map_name}"}
        
        spawn_points = self.spawn_data[map_name]
        road_groups = defaultdict(list)
        
        # Group spawn points by road
        for pt in spawn_points:
            road_id = pt.get('road_id')
            if road_id is not None:
                road_groups[road_id].append(pt)
        
        scenario_support = {
            "cut_in_roads": [],
            "lane_change_roads": [],
            "following_roads": [],
            "intersection_roads": [],
            "highway_roads": [],
            "unsuitable_roads": []
        }
        
        for road_id, points in road_groups.items():
            analysis = self.analyze_road(map_name, road_id)
            
            if "error" in analysis:
                continue
                
            # Check scenario support
            if analysis["supports_cut_in"]:
                scenario_support["cut_in_roads"].append(road_id)
            
            if analysis["supports_lane_change"]:
                scenario_support["lane_change_roads"].append(road_id)
            
            if analysis["supports_following"]:
                scenario_support["following_roads"].append(road_id)
            
            # Check road context if available
            context = analysis["road_context"]
            if context.get("type") == "highway":
                scenario_support["highway_roads"].append(road_id)
            
            if context.get("context") == "intersection":
                scenario_support["intersection_roads"].append(road_id)
            
            # Mark as unsuitable if it has very few spawn points or no adjacent lanes
            if (len(points) < 2 or 
                (not analysis["supports_cut_in"] and not analysis["supports_lane_change"])):
                scenario_support["unsuitable_roads"].append(road_id)
        
        return scenario_support
    
    def find_best_roads_for_scenario(self, scenario_type: str, map_name: str = None) -> Dict:
        """Find the best roads across all maps (or specific map) for a scenario type"""
        results = {}
        
        maps_to_check = [map_name] if map_name else list(self.spawn_data.keys())
        
        for map_name in maps_to_check:
            scenario_support = self.analyze_scenario_support(map_name)
            
            if "error" in scenario_support:
                continue
            
            if scenario_type == "cut_in":
                suitable_roads = scenario_support["cut_in_roads"]
            elif scenario_type == "lane_change":
                suitable_roads = scenario_support["lane_change_roads"]
            elif scenario_type == "following":
                suitable_roads = scenario_support["following_roads"]
            elif scenario_type == "highway":
                suitable_roads = scenario_support["highway_roads"]
            elif scenario_type == "intersection":
                suitable_roads = scenario_support["intersection_roads"]
            else:
                suitable_roads = []
            
            # Score roads based on spawn density and lane availability
            scored_roads = []
            for road_id in suitable_roads:
                analysis = self.analyze_road(map_name, road_id)
                if "error" not in analysis:
                    score = (analysis["total_spawn_points"] * 10 + 
                            len(analysis["adjacent_lane_pairs"]) * 20)
                    scored_roads.append((road_id, score, analysis))
            
            # Sort by score (highest first)
            scored_roads.sort(key=lambda x: x[1], reverse=True)
            results[map_name] = scored_roads
        
        return results
        
    def get_road_spawn_points(self, map_name: str, road_id: int) -> List[Dict]:
        """Get all spawn points for a specific road"""
        if map_name not in self.spawn_data:
            return []
            
        spawn_points = []
        data = self.spawn_data[map_name]
        
        # Handle different data structures
        if isinstance(data, dict):
            if 'spawn_points' in data:
                points = data['spawn_points']
            else:
                # Nested structure like enhanced_Town04.json
                points = []
                for lane_type, lane_data in data.items():
                    if isinstance(lane_data, dict):
                        for sub_key, sub_data in lane_data.items():
                            if isinstance(sub_data, list):
                                points.extend(sub_data)
        else:
            points = data
            
        # Filter by road_id
        for point in points:
            if point.get('road_id') == road_id:
                spawn_points.append(point)
                
        return spawn_points
        
    def find_adjacent_lane_pairs(self, lane_ids: List[int]) -> List[Tuple[int, int]]:
        """Find pairs of lanes that are adjacent (consecutive IDs)"""
        pairs = []
        sorted_lanes = sorted(lane_ids)
        
        for i in range(len(sorted_lanes) - 1):
            curr_lane = sorted_lanes[i]
            next_lane = sorted_lanes[i + 1]
            
            # Adjacent if consecutive and same direction
            if abs(next_lane - curr_lane) == 1:
                # Same direction check
                if (curr_lane > 0 and next_lane > 0) or (curr_lane < 0 and next_lane < 0):
                    pairs.append((curr_lane, next_lane))
                    
        return pairs
        
    def analyze_spawn_coverage(self, spawn_points: List[Dict]) -> Dict[str, Any]:
        """Analyze spawn point coverage along the road"""
        if not spawn_points:
            return {'gaps': [], 'min_distance': 0, 'max_distance': 0, 'avg_spacing': 0}
            
        # Extract distances (s coordinate)
        distances = []
        for sp in spawn_points:
            # Try different possible distance keys
            dist = sp.get('s', sp.get('distance', sp.get('position_s', 0)))
            distances.append(dist)
            
        distances.sort()
        
        # Find gaps
        gaps = []
        if len(distances) > 1:
            for i in range(len(distances) - 1):
                gap = distances[i + 1] - distances[i]
                if gap > 50:  # Gap larger than 50m
                    gaps.append({
                        'start': distances[i],
                        'end': distances[i + 1],
                        'size': gap
                    })
                    
        avg_spacing = (distances[-1] - distances[0]) / max(1, len(distances) - 1) if len(distances) > 1 else 0
        
        return {
            'gaps': gaps,
            'min_distance': distances[0] if distances else 0,
            'max_distance': distances[-1] if distances else 0,
            'avg_spacing': avg_spacing
        }
        
    def assess_scenario_suitability(self, analysis: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Assess how suitable this road is for different scenario types"""
        suitability = {}
        
        adjacent_pairs = analysis['adjacent_lane_pairs']
        lanes = analysis['lanes']
        spawn_count = len(analysis['spawn_points'])
        
        # Following scenarios
        same_lane_spawns = any(len(points) >= 2 for points in lanes.values())
        suitability['following'] = {
            'suitable': same_lane_spawns,
            'reason': f"Same-lane spawns available: {same_lane_spawns}"
        }
        
        # Cut-in scenarios
        has_adjacent = len(adjacent_pairs) > 0
        adequate_spawns = spawn_count >= 4
        suitability['cut_in'] = {
            'suitable': has_adjacent and adequate_spawns,
            'reason': f"Adjacent lanes: {has_adjacent}, Adequate spawns: {adequate_spawns}"
        }
        
        # Lane change scenarios
        suitability['lane_change'] = suitability['cut_in']  # Same requirements
        
        # Intersection scenarios
        # Need road intelligence data for proper assessment
        suitability['intersection'] = {
            'suitable': True,  # Most roads can support intersection scenarios
            'reason': "Road can be used for intersection approaches"
        }
        
        return suitability
        
    def generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations to improve road suitability"""
        recommendations = []
        
        adjacent_pairs = analysis['adjacent_lane_pairs']
        lanes = analysis['lanes']
        gaps = analysis['coverage_gaps']
        
        if not adjacent_pairs:
            recommendations.append("Generate spawn points for missing adjacent lanes")
            
        if len(gaps) > 3:
            recommendations.append(f"Fill {len(gaps)} coverage gaps larger than 50m")
            
        if len(analysis['spawn_points']) < 10:
            recommendations.append("Increase spawn point density for better scenario support")
            
        # Check if only opposite-direction lanes exist
        lane_ids = list(lanes.keys())
        if len(lane_ids) == 2 and (1 in lane_ids and -1 in lane_ids):
            recommendations.append("Add lanes 2 and -2 for true adjacent lane scenarios")
            
        return recommendations
        
    def compare_roads(self, map_name: str, road_ids: List[int]) -> Dict[str, Any]:
        """Compare multiple roads for scenario suitability"""
        print(f"\n📊 ROAD COMPARISON: {map_name}")
        print("=" * 60)
        
        comparison = {
            'map_name': map_name,
            'roads': {},
            'best_for_scenarios': {}
        }
        
        # Analyze each road
        for road_id in road_ids:
            analysis = self.analyze_road_detailed(map_name, road_id)
            comparison['roads'][road_id] = analysis
            
        # Find best roads for each scenario type
        scenario_types = ['following', 'cut_in', 'lane_change', 'intersection']
        
        for scenario_type in scenario_types:
            best_roads = []
            for road_id, analysis in comparison['roads'].items():
                suitability = analysis['scenario_suitability'].get(scenario_type, {})
                if suitability.get('suitable', False):
                    best_roads.append(road_id)
                    
            comparison['best_for_scenarios'][scenario_type] = best_roads
            
        print(f"\n🏆 Best Roads by Scenario Type:")
        for scenario_type, roads in comparison['best_for_scenarios'].items():
            if roads:
                print(f"   {scenario_type}: Roads {roads}")
            else:
                print(f"   {scenario_type}: ❌ No suitable roads found!")
                
        return comparison

def main():
    """Run analysis on specific problematic roads and scenarios"""
    analyzer = RoadTopologyAnalyzer()
    
    print("=== Road Topology Analysis ===\n")
    
    # Analyze Town04 road 27 specifically (the problematic one)
    print("1. Analysis of Town04 Road 27 (Problematic for cut-in scenarios):")
    road_27_analysis = analyzer.analyze_road("Town04", 27)
    
    if "error" in road_27_analysis:
        print(f"   ERROR: {road_27_analysis['error']}")
    else:
        print(f"   Total spawn points: {road_27_analysis['total_spawn_points']}")
        print(f"   Lanes with spawn points: {road_27_analysis['lanes_with_spawns']}")
        print(f"   Adjacent lane pairs: {road_27_analysis['adjacent_lane_pairs']}")
        print(f"   Supports cut-in scenarios: {road_27_analysis['supports_cut_in']}")
        print(f"   Supports lane change: {road_27_analysis['supports_lane_change']}")
        
        if road_27_analysis["road_context"]:
            ctx = road_27_analysis["road_context"]
            print(f"   Road type: {ctx.get('type', 'unknown')}")
            print(f"   Speed limit: {ctx.get('speed_limit', 'unknown')} km/h")
            print(f"   Context: {ctx.get('context', 'unknown')}")
    
    print("\n" + "="*50 + "\n")
    
    # Find best alternatives for cut-in scenarios
    print("2. Best roads for cut-in scenarios across all maps:")
    cut_in_roads = analyzer.find_best_roads_for_scenario("cut_in")
    
    for map_name, scored_roads in cut_in_roads.items():
        if scored_roads:
            print(f"\n   {map_name} - Top 5 roads for cut-in scenarios:")
            for i, (road_id, score, analysis) in enumerate(scored_roads[:5]):
                print(f"     #{i+1}: Road {road_id} (score: {score})")
                print(f"         Spawn points: {analysis['total_spawn_points']}")
                print(f"         Adjacent pairs: {len(analysis['adjacent_lane_pairs'])}")
                if analysis["road_context"]:
                    ctx = analysis["road_context"]
                    print(f"         Type: {ctx.get('type', 'unknown')}")
        else:
            print(f"\n   {map_name}: No suitable roads found for cut-in scenarios")
    
    print("\n" + "="*50 + "\n")
    
    # Analyze scenario support across all maps
    print("3. Scenario support summary:")
    for map_name in sorted(analyzer.spawn_data.keys()):
        scenario_support = analyzer.analyze_scenario_support(map_name)
        if "error" not in scenario_support:
            print(f"\n   {map_name}:")
            print(f"     Cut-in capable roads: {len(scenario_support['cut_in_roads'])} "
                  f"({scenario_support['cut_in_roads'][:5]}{'...' if len(scenario_support['cut_in_roads']) > 5 else ''})")
            print(f"     Lane-change capable roads: {len(scenario_support['lane_change_roads'])}")
            print(f"     Following capable roads: {len(scenario_support['following_roads'])}")
            print(f"     Highway roads: {len(scenario_support['highway_roads'])}")
            print(f"     Unsuitable roads: {len(scenario_support['unsuitable_roads'])} "
                  f"(including road 27: {27 in scenario_support['unsuitable_roads']})")

if __name__ == "__main__":
    main()