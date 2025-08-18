#!/usr/bin/env python3
"""
Smart Constraint Relaxation Strategy

Implements intelligent fallback strategies for spawn constraint matching
to handle cases where strict constraints can't be satisfied due to map topology.
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

class SmartConstraintRelaxer:
    def __init__(self, spawns_dir: str = "spawns"):
        self.spawns_dir = Path(spawns_dir)
        self.maps_data = {}
        self.road_topology_cache = {}
        
    def load_spawn_data_for_map(self, map_name: str):
        """Load spawn data for analysis"""
        spawn_file = self.spawns_dir / f"enhanced_{map_name}.json"
        
        try:
            with open(spawn_file, 'r') as f:
                data = json.load(f)
                
                spawn_points = []
                if isinstance(data, dict):
                    for map_key, map_data in data.items():
                        if isinstance(map_data, dict):
                            for lane_type, points in map_data.items():
                                if isinstance(points, list):
                                    spawn_points.extend(points)
                
                self.maps_data[map_name] = spawn_points
                return True
        except Exception as e:
            print(f"❌ Failed to load {spawn_file}: {e}")
            return False
    
    def analyze_road_topology(self, map_name: str) -> Dict[int, Dict]:
        """Analyze road topology to understand lane availability"""
        if map_name in self.road_topology_cache:
            return self.road_topology_cache[map_name]
        
        if not self.load_spawn_data_for_map(map_name):
            return {}
        
        spawn_points = self.maps_data[map_name]
        road_topology = {}
        
        # Group by road and analyze lanes
        for pt in spawn_points:
            road_id = pt.get('road_id')
            if road_id not in road_topology:
                road_topology[road_id] = {
                    'lanes': {},
                    'driving_lanes': [],
                    'has_adjacent_lanes': False,
                    'is_highway': False,
                    'total_spawn_points': 0,
                    'lane_structure': 'unknown'
                }
            
            lane_id = pt.get('lane_id')
            lane_type = pt.get('lane_type', 'Unknown')
            
            if lane_id not in road_topology[road_id]['lanes']:
                road_topology[road_id]['lanes'][lane_id] = {
                    'types': {},
                    'count': 0
                }
            
            road_topology[road_id]['lanes'][lane_id]['types'][lane_type] = \
                road_topology[road_id]['lanes'][lane_id]['types'].get(lane_type, 0) + 1
            road_topology[road_id]['lanes'][lane_id]['count'] += 1
            road_topology[road_id]['total_spawn_points'] += 1
        
        # Analyze each road
        for road_id, road_data in road_topology.items():
            # Find driving lanes
            driving_lanes = []
            for lane_id, lane_info in road_data['lanes'].items():
                if 'Driving' in lane_info['types']:
                    driving_lanes.append(lane_id)
            
            road_data['driving_lanes'] = sorted(driving_lanes)
            
            # Check for adjacent lanes
            has_adjacent = False
            for i, lane_id in enumerate(road_data['driving_lanes']):
                for j in range(i+1, len(road_data['driving_lanes'])):
                    other_lane = road_data['driving_lanes'][j]
                    if abs(lane_id - other_lane) == 1:
                        has_adjacent = True
                        break
                if has_adjacent:
                    break
            
            road_data['has_adjacent_lanes'] = has_adjacent
            
            # Classify road type
            if len(road_data['driving_lanes']) >= 6:
                road_data['is_highway'] = True
                road_data['lane_structure'] = 'highway'
            elif len(road_data['driving_lanes']) == 2 and has_adjacent:
                road_data['lane_structure'] = 'arterial'
            elif len(road_data['driving_lanes']) == 2 and not has_adjacent:
                road_data['lane_structure'] = 'simple_bidirectional'
            elif len(road_data['driving_lanes']) == 1:
                road_data['lane_structure'] = 'single_lane'
            else:
                road_data['lane_structure'] = 'complex'
        
        self.road_topology_cache[map_name] = road_topology
        return road_topology
    
    def get_relaxation_strategy(self, constraint_type: str, scenario_type: str, road_topology: Dict) -> List[Dict]:
        """Get intelligent relaxation strategies based on scenario and road topology"""
        
        strategies = []
        
        if constraint_type == 'lane_relationship':
            if scenario_type in ['following', 'brake_check', 'stop_and_go']:
                # Following scenarios - prioritize same direction
                strategies = [
                    {
                        'constraint': 'same_lane',
                        'description': 'Ideal: exact same lane',
                        'priority': 100
                    },
                    {
                        'constraint': 'same_direction_lane',
                        'description': 'Good: any lane in same direction',
                        'priority': 80,
                        'custom_filter': self._same_direction_filter
                    },
                    {
                        'constraint': 'closest_driving_lane',
                        'description': 'Fallback: closest driving lane on same road',
                        'priority': 60,
                        'custom_filter': self._closest_lane_filter
                    },
                    {
                        'constraint': 'any_lane',
                        'description': 'Last resort: any driving lane on same road',
                        'priority': 40
                    }
                ]
                
            elif scenario_type in ['cut_in', 'lane_change', 'merge', 'overtake']:
                # Lane change scenarios - need adjacent or nearby lanes
                strategies = [
                    {
                        'constraint': 'adjacent_lane',
                        'description': 'Ideal: truly adjacent lane',
                        'priority': 100
                    },
                    {
                        'constraint': 'same_direction_nearby',
                        'description': 'Good: nearby lane in same direction',
                        'priority': 80,
                        'custom_filter': self._nearby_same_direction_filter
                    },
                    {
                        'constraint': 'parallel_road',
                        'description': 'Alternative: parallel road',
                        'priority': 70,
                        'custom_filter': self._parallel_road_filter
                    },
                    {
                        'constraint': 'any_lane',
                        'description': 'Fallback: any driving lane',
                        'priority': 50
                    }
                ]
                
            elif scenario_type in ['intersection', 'cross_traffic']:
                # Intersection scenarios - different roads are key
                strategies = [
                    {
                        'constraint': 'different_road',
                        'description': 'Ideal: different road at intersection',
                        'priority': 100,
                        'requires_road_relationship': 'different_road'
                    },
                    {
                        'constraint': 'nearby_intersection',
                        'description': 'Good: spawn near intersection',
                        'priority': 80,
                        'custom_filter': self._intersection_proximity_filter
                    },
                    {
                        'constraint': 'any_lane',
                        'description': 'Fallback: any road',
                        'priority': 60
                    }
                ]
        
        elif constraint_type == 'road_relationship':
            if scenario_type in ['following', 'cut_in', 'lane_change', 'overtake']:
                strategies = [
                    {
                        'constraint': 'same_road',
                        'description': 'Ideal: same road as ego',
                        'priority': 100
                    },
                    {
                        'constraint': 'parallel_road',
                        'description': 'Alternative: parallel road',
                        'priority': 70,
                        'custom_filter': self._parallel_road_filter
                    },
                    {
                        'constraint': 'nearby_road',
                        'description': 'Fallback: nearby road',
                        'priority': 50,
                        'custom_filter': self._nearby_road_filter
                    }
                ]
            
            elif scenario_type in ['intersection', 'cross_traffic']:
                strategies = [
                    {
                        'constraint': 'different_road',
                        'description': 'Ideal: different road',
                        'priority': 100
                    },
                    {
                        'constraint': 'any_road',
                        'description': 'Fallback: any road',
                        'priority': 60
                    }
                ]
        
        return strategies
    
    def _same_direction_filter(self, candidates: List[Dict], ego_lane: Tuple[int, int]) -> List[Dict]:
        """Filter for same direction lanes"""
        ego_road_id, ego_lane_id = ego_lane
        return [
            pt for pt in candidates
            if (pt.get('road_id') == ego_road_id and 
                self._are_same_direction_lanes(ego_lane_id, pt.get('lane_id', 0)))
        ]
    
    def _closest_lane_filter(self, candidates: List[Dict], ego_lane: Tuple[int, int]) -> List[Dict]:
        """Filter for closest lanes to ego"""
        ego_road_id, ego_lane_id = ego_lane
        same_road_candidates = [pt for pt in candidates if pt.get('road_id') == ego_road_id]
        
        # Sort by lane ID distance
        same_road_candidates.sort(key=lambda pt: abs(pt.get('lane_id', 0) - ego_lane_id))
        
        # Return top candidates
        return same_road_candidates[:10] if len(same_road_candidates) > 10 else same_road_candidates
    
    def _nearby_same_direction_filter(self, candidates: List[Dict], ego_lane: Tuple[int, int]) -> List[Dict]:
        """Filter for nearby lanes in same direction"""
        ego_road_id, ego_lane_id = ego_lane
        
        nearby_candidates = []
        for pt in candidates:
            if pt.get('road_id') == ego_road_id:
                pt_lane_id = pt.get('lane_id', 0)
                # Within 2 lanes and same direction
                if (abs(pt_lane_id - ego_lane_id) <= 2 and 
                    self._are_same_direction_lanes(ego_lane_id, pt_lane_id)):
                    nearby_candidates.append(pt)
        
        return nearby_candidates
    
    def _parallel_road_filter(self, candidates: List[Dict], ego_lane: Tuple[int, int]) -> List[Dict]:
        """Filter for parallel roads (simplified - based on spawn density)"""
        ego_road_id, ego_lane_id = ego_lane
        
        # Group by road and find roads with similar spawn density
        road_groups = {}
        for pt in candidates:
            road_id = pt.get('road_id')
            if road_id != ego_road_id:
                if road_id not in road_groups:
                    road_groups[road_id] = []
                road_groups[road_id].append(pt)
        
        # Return candidates from roads with good spawn density
        parallel_candidates = []
        for road_id, road_points in road_groups.items():
            if len(road_points) >= 10:  # Arbitrary threshold for "parallel" roads
                parallel_candidates.extend(road_points[:20])  # Limit per road
        
        return parallel_candidates
    
    def _nearby_road_filter(self, candidates: List[Dict], ego_lane: Tuple[int, int]) -> List[Dict]:
        """Filter for nearby roads based on spawn point distance"""
        # This is a simplified implementation - in practice would use road network topology
        return candidates  # Return all for now
    
    def _intersection_proximity_filter(self, candidates: List[Dict], ego_lane: Tuple[int, int]) -> List[Dict]:
        """Filter for spawn points near intersections"""
        # This would require intersection topology data
        # For now, return candidates from different roads
        ego_road_id, ego_lane_id = ego_lane
        return [pt for pt in candidates if pt.get('road_id') != ego_road_id]
    
    def _are_same_direction_lanes(self, ego_lane_id: int, candidate_lane_id: int) -> bool:
        """Check if two lane IDs represent lanes with same traffic direction"""
        if ego_lane_id == 0 or candidate_lane_id == 0:
            return True
        return (ego_lane_id > 0) == (candidate_lane_id > 0)
    
    def create_relaxed_constraints(self, original_constraints: Dict, scenario_type: str, 
                                 road_topology: Dict, ego_lane: Tuple[int, int]) -> List[Dict]:
        """Create a sequence of relaxed constraint sets"""
        relaxed_sets = []
        
        # Start with original constraints
        relaxed_sets.append({
            'constraints': original_constraints.copy(),
            'description': 'Original strict constraints',
            'priority': 100
        })
        
        # Apply lane relationship relaxation
        if 'lane_relationship' in original_constraints:
            strategies = self.get_relaxation_strategy('lane_relationship', scenario_type, road_topology)
            
            for strategy in strategies[1:]:  # Skip the first (original)
                relaxed_constraints = original_constraints.copy()
                relaxed_constraints['lane_relationship'] = strategy['constraint']
                
                relaxed_sets.append({
                    'constraints': relaxed_constraints,
                    'description': f"Relaxed lane: {strategy['description']}",
                    'priority': strategy['priority']
                })
        
        # Apply road relationship relaxation
        if 'road_relationship' in original_constraints:
            road_strategies = self.get_relaxation_strategy('road_relationship', scenario_type, road_topology)
            
            for strategy in road_strategies[1:]:  # Skip the first (original)
                relaxed_constraints = original_constraints.copy()
                relaxed_constraints['road_relationship'] = strategy['constraint']
                
                relaxed_sets.append({
                    'constraints': relaxed_constraints,
                    'description': f"Relaxed road: {strategy['description']}",
                    'priority': strategy['priority']
                })
        
        # Widen distance constraints
        if 'distance_to_ego' in original_constraints:
            dist_constraint = original_constraints['distance_to_ego']
            min_dist = dist_constraint.get('min', 20)
            max_dist = dist_constraint.get('max', 60)
            
            # Gradually widen distance
            wider_distances = [
                (min_dist * 0.5, max_dist * 1.5),  # 50% wider
                (min_dist * 0.3, max_dist * 2.0),  # 100% wider
                (min_dist * 0.1, max_dist * 3.0),  # Much wider
            ]
            
            for min_d, max_d in wider_distances:
                relaxed_constraints = original_constraints.copy()
                relaxed_constraints['distance_to_ego'] = {'min': min_d, 'max': max_d}
                
                relaxed_sets.append({
                    'constraints': relaxed_constraints,
                    'description': f"Widened distance: {min_d:.0f}-{max_d:.0f}m",
                    'priority': 70 - (max_d - max_dist) // 20  # Lower priority for wider distances
                })
        
        # Final fallback - minimal constraints
        if original_constraints.get('lane_type') == 'Driving':
            relaxed_sets.append({
                'constraints': {'lane_type': 'Driving'},
                'description': 'Minimal fallback: any driving lane',
                'priority': 30
            })
        
        # Sort by priority
        relaxed_sets.sort(key=lambda x: x['priority'], reverse=True)
        
        return relaxed_sets
    
    def generate_scenario_fixes(self, map_name: str = "Town04") -> Dict[str, Any]:
        """Generate fixes for problematic scenario patterns"""
        road_topology = self.analyze_road_topology(map_name)
        
        fixes = {
            'map_name': map_name,
            'road_analysis': {},
            'problematic_roads': [],
            'scenario_fixes': {},
            'recommendations': []
        }
        
        # Analyze problematic roads
        for road_id, road_data in road_topology.items():
            if not road_data['has_adjacent_lanes'] and road_data['lane_structure'] == 'simple_bidirectional':
                fixes['problematic_roads'].append({
                    'road_id': road_id,
                    'issue': 'No adjacent lanes available',
                    'lanes': road_data['driving_lanes'],
                    'structure': road_data['lane_structure']
                })
        
        # Generate scenario-specific fixes
        scenario_types = ['following', 'cut_in', 'overtake', 'intersection']
        
        for scenario_type in scenario_types:
            original_constraints = self._get_typical_constraints_for_scenario(scenario_type)
            
            # Test with a problematic road
            if fixes['problematic_roads']:
                problem_road = fixes['problematic_roads'][0]
                ego_lane = (problem_road['road_id'], problem_road['lanes'][0])
                
                relaxed_sets = self.create_relaxed_constraints(
                    original_constraints, scenario_type, road_topology, ego_lane
                )
                
                fixes['scenario_fixes'][scenario_type] = {
                    'original_constraints': original_constraints,
                    'relaxed_strategies': relaxed_sets[:5],  # Top 5 strategies
                    'recommended_fix': relaxed_sets[1] if len(relaxed_sets) > 1 else None
                }
        
        # Generate recommendations
        fixes['recommendations'] = [
            "Implement intelligent constraint relaxation in xosc_json.py",
            "Prefer highway roads (45, 35, 38) for scenarios requiring adjacent lanes",
            f"Add more spawn points to roads with limited lane options",
            "Use fallback strategies when strict constraints can't be satisfied",
            "Consider road topology when selecting ego spawn points"
        ]
        
        return fixes
    
    def _get_typical_constraints_for_scenario(self, scenario_type: str) -> Dict:
        """Get typical constraints for scenario types"""
        constraints = {
            'following': {
                'lane_type': 'Driving',
                'road_relationship': 'same_road',
                'lane_relationship': 'same_lane',
                'distance_to_ego': {'min': 30, 'max': 60},
                'relative_position': 'ahead'
            },
            'cut_in': {
                'lane_type': 'Driving',
                'road_relationship': 'same_road',
                'lane_relationship': 'adjacent_lane',
                'distance_to_ego': {'min': 20, 'max': 50},
                'relative_position': 'ahead'
            },
            'overtake': {
                'lane_type': 'Driving',
                'road_relationship': 'same_road',
                'lane_relationship': 'adjacent_lane',
                'distance_to_ego': {'min': 20, 'max': 40},
                'relative_position': 'behind'
            },
            'intersection': {
                'lane_type': 'Driving',
                'road_relationship': 'different_road',
                'distance_to_ego': {'min': 40, 'max': 80},
                'is_intersection': True
            }
        }
        
        return constraints.get(scenario_type, {})

def main():
    relaxer = SmartConstraintRelaxer()
    
    print("🔧 Generating smart constraint relaxation strategies...")
    fixes = relaxer.generate_scenario_fixes("Town04")
    
    # Save results
    with open("constraint_relaxation_fixes.json", 'w') as f:
        json.dump(fixes, f, indent=2)
    
    print(f"\n📊 Analysis Results:")
    print(f"   Problematic roads found: {len(fixes['problematic_roads'])}")
    print(f"   Scenario fixes generated: {len(fixes['scenario_fixes'])}")
    
    print(f"\n🚧 Problematic Roads (no adjacent lanes):")
    for road in fixes['problematic_roads'][:5]:
        print(f"   Road {road['road_id']}: {road['lanes']} ({road['structure']})")
    
    print(f"\n💡 Key Recommendations:")
    for rec in fixes['recommendations']:
        print(f"   • {rec}")
    
    print(f"\n📄 Detailed report saved: constraint_relaxation_fixes.json")

if __name__ == "__main__":
    main()