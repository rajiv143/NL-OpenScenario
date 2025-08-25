import json
import math
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
import random


@dataclass
class EnhancedSpawnCriteria:
    """Enhanced spawn criteria with road intelligence"""
    # Basic constraints
    distance_range: Optional[Tuple[float, float]] = None
    same_road: Optional[bool] = None
    
    # Road context constraints
    road_context: Optional[str] = None  # "roundabout_entry", "highway_merge", "intersection_approach"
    junction_type: Optional[str] = None  # "roundabout", "signalized", "stop_sign", "uncontrolled"
    road_type: Optional[str] = None  # "highway", "arterial", "residential", "service"
    
    # Geometric constraints
    curvature_range: Optional[Tuple[float, float]] = None  # (min, max) curvature
    speed_limit_range: Optional[Tuple[float, float]] = None  # (min, max) speed limit
    
    # Junction proximity constraints
    distance_to_junction_range: Optional[Tuple[float, float]] = None  # Distance to nearest junction
    
    # Lane constraints
    lane_type: Optional[str] = None  # "driving", "parking", etc.
    min_lane_width: Optional[float] = None
    
    # Traffic complexity constraints
    intersection_complexity_range: Optional[Tuple[float, float]] = None  # (min, max) complexity 0-1
    
    # Zone constraints
    traffic_zone: Optional[str] = None  # "highway_zone", "urban_zone", "suburban_zone"


class EnhancedSpawnSelector:
    def __init__(self, road_intelligence_db: Dict, network_analysis: Dict):
        self.road_db = road_intelligence_db
        self.network_analysis = network_analysis
        self.available_waypoints = self._build_waypoint_index()
    
    def _build_waypoint_index(self) -> Dict:
        """Build an indexed structure of all available waypoints with metadata"""
        waypoint_index = {}
        
        for road_id, waypoints in self.road_db.get('enhanced_waypoints', {}).items():
            road_id = int(road_id)
            
            for i, waypoint in enumerate(waypoints):
                waypoint_id = f"{road_id}_{i}"
                
                # Add network analysis context
                waypoint_context = waypoint.get('road_context', {}).copy()
                
                # Add intersection analysis if near junction
                if waypoint_context.get('is_intersection') and waypoint_context.get('distance_to_junction', float('inf')) < 50:
                    junction_id = self.road_db['roads'][str(road_id)].get('junction_id')
                    if junction_id and junction_id != -1:
                        intersection_data = self.network_analysis.get('intersection_analyses', {}).get(str(junction_id))
                        if intersection_data:
                            waypoint_context.update({
                                'intersection_type': intersection_data.get('intersection_type'),
                                'intersection_complexity': intersection_data.get('traffic_complexity', 0.0),
                                'approach_roads': intersection_data.get('approach_roads', [])
                            })
                
                # Add road segment information
                road_segments = self.network_analysis.get('road_segments', {}).get(str(road_id), [])
                for segment in road_segments:
                    if segment['start_s'] <= waypoint.get('s', 0) <= segment['end_s']:
                        waypoint_context.update({
                            'segment_type': segment['segment_type'],
                            'segment_curvature': segment['curvature'],
                            'speed_context': segment['speed_context']
                        })
                        break
                
                # Add traffic zone information
                traffic_zone = self._find_traffic_zone(road_id)
                if traffic_zone:
                    waypoint_context['traffic_zone'] = traffic_zone
                
                waypoint_index[waypoint_id] = {
                    'road_id': road_id,
                    'waypoint_index': i,
                    'position': {
                        'x': waypoint['x'],
                        'y': waypoint['y'],
                        'z': waypoint['z'],
                        'yaw': waypoint['yaw']
                    },
                    'lane_info': {
                        'lane_type': waypoint.get('lane_type'),
                        'lane_id': waypoint.get('lane_id')
                    },
                    'context': waypoint_context
                }
        
        return waypoint_index
    
    def _find_traffic_zone(self, road_id: int) -> Optional[str]:
        """Find which traffic zone a road belongs to"""
        for zone_type, zones in self.network_analysis.get('traffic_zones', {}).items():
            for zone in zones:
                if road_id in zone.get('roads', []):
                    return zone_type
        return None
    
    def find_matching_spawns(self, criteria: EnhancedSpawnCriteria, ego_position: Optional[Dict] = None, 
                           limit: int = 100) -> List[Dict]:
        """Find spawn points matching enhanced criteria"""
        matching_waypoints = []
        
        for waypoint_id, waypoint_data in self.available_waypoints.items():
            if self._waypoint_matches_criteria(waypoint_data, criteria, ego_position):
                matching_waypoints.append(waypoint_data)
        
        # Sort by relevance/distance if ego position provided
        if ego_position:
            matching_waypoints.sort(key=lambda wp: self._calculate_distance(
                wp['position'], ego_position
            ))
        
        return matching_waypoints[:limit]
    
    def _waypoint_matches_criteria(self, waypoint_data: Dict, criteria: EnhancedSpawnCriteria, 
                                  ego_position: Optional[Dict]) -> bool:
        """Check if waypoint matches the enhanced criteria"""
        context = waypoint_data['context']
        
        # Distance constraints
        if criteria.distance_range and ego_position:
            distance = self._calculate_distance(waypoint_data['position'], ego_position)
            if not (criteria.distance_range[0] <= distance <= criteria.distance_range[1]):
                return False
        
        # Same road constraint
        if criteria.same_road is not None and ego_position:
            ego_road_id = ego_position.get('road_id')
            if ego_road_id is not None:
                same_road = (waypoint_data['road_id'] == ego_road_id)
                if criteria.same_road != same_road:
                    return False
        
        # Road context constraints
        if criteria.road_context:
            waypoint_context = self._get_waypoint_road_context(waypoint_data)
            if waypoint_context != criteria.road_context:
                return False
        
        # Junction type constraints
        if criteria.junction_type:
            if context.get('intersection_type') != criteria.junction_type:
                return False
        
        # Road type constraints
        if criteria.road_type:
            if context.get('road_type') != criteria.road_type:
                return False
        
        # Curvature constraints
        if criteria.curvature_range:
            curvature = context.get('curvature', 0.0)
            if not (criteria.curvature_range[0] <= curvature <= criteria.curvature_range[1]):
                return False
        
        # Speed limit constraints
        if criteria.speed_limit_range:
            speed_limit = context.get('speed_limit')
            if speed_limit is None:
                return False
            if not (criteria.speed_limit_range[0] <= speed_limit <= criteria.speed_limit_range[1]):
                return False
        
        # Distance to junction constraints
        if criteria.distance_to_junction_range:
            dist_to_junction = context.get('distance_to_junction')
            if dist_to_junction is None:
                return False
            if not (criteria.distance_to_junction_range[0] <= dist_to_junction <= criteria.distance_to_junction_range[1]):
                return False
        
        # Lane type constraints
        if criteria.lane_type:
            if waypoint_data['lane_info'].get('lane_type') != criteria.lane_type:
                return False
        
        # Intersection complexity constraints
        if criteria.intersection_complexity_range:
            complexity = context.get('intersection_complexity', 0.0)
            if not (criteria.intersection_complexity_range[0] <= complexity <= criteria.intersection_complexity_range[1]):
                return False
        
        # Traffic zone constraints
        if criteria.traffic_zone:
            if context.get('traffic_zone') != criteria.traffic_zone:
                return False
        
        return True
    
    def _get_waypoint_road_context(self, waypoint_data: Dict) -> str:
        """Determine specific road context for waypoint"""
        context = waypoint_data['context']
        
        # Check for roundabout context
        if context.get('intersection_type') == 'roundabout':
            # Determine if entry, circulation, or exit
            distance_to_junction = context.get('distance_to_junction', float('inf'))
            if distance_to_junction < 20:  # Close to roundabout
                return 'roundabout_entry'
            else:
                return 'roundabout_approach'
        
        # Check for highway merge context
        if context.get('road_type') in ['motorway', 'trunk']:
            segment_type = context.get('segment_type')
            if segment_type == 'merge':
                return 'highway_merge'
            elif segment_type == 'diverge':
                return 'highway_diverge'
            else:
                return 'highway_cruising'
        
        # Check for intersection approach
        if context.get('is_intersection') or context.get('distance_to_junction', float('inf')) < 50:
            return 'intersection_approach'
        
        # Default contexts
        if context.get('segment_type') == 'curve':
            return 'curved_section'
        elif context.get('segment_type') == 'straight':
            return 'straight_section'
        
        return 'general_driving'
    
    def _calculate_distance(self, pos1: Dict, pos2: Dict) -> float:
        """Calculate Euclidean distance between two positions"""
        return math.sqrt(
            (pos1['x'] - pos2['x'])**2 + 
            (pos1['y'] - pos2['y'])**2
        )
    
    def generate_scenario_specific_spawns(self, scenario_type: str, ego_spawn: Dict, 
                                        num_actors: int = 3) -> List[Dict]:
        """Generate contextually appropriate spawns for specific scenario types"""
        
        if scenario_type == "roundabout_navigation":
            return self._generate_roundabout_spawns(ego_spawn, num_actors)
        elif scenario_type == "highway_merge":
            return self._generate_highway_merge_spawns(ego_spawn, num_actors)
        elif scenario_type == "intersection_crossing":
            return self._generate_intersection_spawns(ego_spawn, num_actors)
        elif scenario_type == "lane_change_urban":
            return self._generate_urban_lane_change_spawns(ego_spawn, num_actors)
        elif scenario_type == "parking_lot_navigation":
            return self._generate_parking_lot_spawns(ego_spawn, num_actors)
        else:
            return self._generate_general_spawns(ego_spawn, num_actors)
    
    def _generate_roundabout_spawns(self, ego_spawn: Dict, num_actors: int) -> List[Dict]:
        """Generate spawns appropriate for roundabout scenarios"""
        spawns = []
        
        # Find roundabout entry points
        entry_criteria = EnhancedSpawnCriteria(
            road_context="roundabout_entry",
            distance_range=(20, 100),
            junction_type="roundabout"
        )
        
        entry_points = self.find_matching_spawns(entry_criteria, ego_spawn, limit=num_actors*2)
        
        # Select diverse entry points
        for i in range(min(num_actors, len(entry_points))):
            spawn_point = entry_points[i]
            spawns.append({
                'x': spawn_point['position']['x'],
                'y': spawn_point['position']['y'],
                'z': spawn_point['position']['z'],
                'yaw': spawn_point['position']['yaw'],
                'road_id': spawn_point['road_id'],
                'context': 'roundabout_entry',
                'behavior_hint': 'yield_and_merge'
            })
        
        return spawns
    
    def _generate_highway_merge_spawns(self, ego_spawn: Dict, num_actors: int) -> List[Dict]:
        """Generate spawns appropriate for highway merge scenarios"""
        spawns = []
        
        # Main highway traffic
        highway_criteria = EnhancedSpawnCriteria(
            road_type="highway",
            distance_range=(50, 200),
            road_context="highway_cruising"
        )
        
        highway_spawns = self.find_matching_spawns(highway_criteria, ego_spawn, limit=num_actors)
        
        # On-ramp traffic
        merge_criteria = EnhancedSpawnCriteria(
            road_context="highway_merge",
            distance_range=(30, 150)
        )
        
        merge_spawns = self.find_matching_spawns(merge_criteria, ego_spawn, limit=2)
        
        # Combine spawns
        all_spawns = highway_spawns + merge_spawns
        
        for i, spawn_point in enumerate(all_spawns[:num_actors]):
            context = 'highway_cruising' if i < len(highway_spawns) else 'merging'
            behavior = 'maintain_speed' if context == 'highway_cruising' else 'accelerate_merge'
            
            spawns.append({
                'x': spawn_point['position']['x'],
                'y': spawn_point['position']['y'],
                'z': spawn_point['position']['z'],
                'yaw': spawn_point['position']['yaw'],
                'road_id': spawn_point['road_id'],
                'context': context,
                'behavior_hint': behavior
            })
        
        return spawns
    
    def _generate_intersection_spawns(self, ego_spawn: Dict, num_actors: int) -> List[Dict]:
        """Generate spawns appropriate for intersection scenarios"""
        spawns = []
        
        # Find intersection approach points from different directions
        intersection_criteria = EnhancedSpawnCriteria(
            road_context="intersection_approach",
            distance_range=(30, 100),
            distance_to_junction_range=(10, 50)
        )
        
        approach_points = self.find_matching_spawns(intersection_criteria, ego_spawn, limit=num_actors*2)
        
        # Select spawns from different approach roads
        selected_roads = set()
        for spawn_point in approach_points:
            if len(spawns) >= num_actors:
                break
            
            road_id = spawn_point['road_id']
            if road_id not in selected_roads:
                selected_roads.add(road_id)
                
                # Determine turning intention based on intersection layout
                intersection_type = spawn_point['context'].get('intersection_type', 'uncontrolled')
                behavior = self._get_intersection_behavior(intersection_type)
                
                spawns.append({
                    'x': spawn_point['position']['x'],
                    'y': spawn_point['position']['y'],
                    'z': spawn_point['position']['z'],
                    'yaw': spawn_point['position']['yaw'],
                    'road_id': spawn_point['road_id'],
                    'context': 'intersection_approach',
                    'behavior_hint': behavior,
                    'intersection_type': intersection_type
                })
        
        return spawns
    
    def _get_intersection_behavior(self, intersection_type: str) -> str:
        """Get appropriate behavior for intersection type"""
        behaviors = {
            'stop_sign': 'stop_and_proceed',
            'signalized': 'obey_signals',
            'yield': 'yield_to_traffic',
            'uncontrolled': 'proceed_with_caution',
            'roundabout': 'yield_and_merge'
        }
        return behaviors.get(intersection_type, 'proceed_with_caution')
    
    def _generate_urban_lane_change_spawns(self, ego_spawn: Dict, num_actors: int) -> List[Dict]:
        """Generate spawns appropriate for urban lane change scenarios"""
        spawns = []
        
        # Find urban/arterial roads with multiple lanes
        urban_criteria = EnhancedSpawnCriteria(
            traffic_zone="urban_zone",
            distance_range=(20, 150),
            road_context="straight_section"
        )
        
        urban_spawns = self.find_matching_spawns(urban_criteria, ego_spawn, limit=num_actors)
        
        for spawn_point in urban_spawns:
            # Vary lane change motivations
            motivations = ['slow_vehicle_ahead', 'turn_preparation', 'aggressive_driver', 'lane_preference']
            motivation = random.choice(motivations)
            
            spawns.append({
                'x': spawn_point['position']['x'],
                'y': spawn_point['position']['y'],
                'z': spawn_point['position']['z'],
                'yaw': spawn_point['position']['yaw'],
                'road_id': spawn_point['road_id'],
                'context': 'urban_driving',
                'behavior_hint': f'lane_change_{motivation}',
                'lane_change_motivation': motivation
            })
        
        return spawns
    
    def _generate_parking_lot_spawns(self, ego_spawn: Dict, num_actors: int) -> List[Dict]:
        """Generate spawns appropriate for parking lot scenarios"""
        spawns = []
        
        # Find service roads and parking areas
        parking_criteria = EnhancedSpawnCriteria(
            road_type="service",
            distance_range=(10, 100),
            lane_type="parking"
        )
        
        parking_spawns = self.find_matching_spawns(parking_criteria, ego_spawn, limit=num_actors)
        
        for spawn_point in parking_spawns:
            # Parking lot behaviors
            behaviors = ['parking', 'reversing', 'pedestrian_loading', 'slow_cruising']
            behavior = random.choice(behaviors)
            
            spawns.append({
                'x': spawn_point['position']['x'],
                'y': spawn_point['position']['y'],
                'z': spawn_point['position']['z'],
                'yaw': spawn_point['position']['yaw'],
                'road_id': spawn_point['road_id'],
                'context': 'parking_lot',
                'behavior_hint': behavior
            })
        
        return spawns
    
    def _generate_general_spawns(self, ego_spawn: Dict, num_actors: int) -> List[Dict]:
        """Generate general-purpose spawns with variety"""
        spawns = []
        
        # Mix of different contexts
        contexts = [
            ("straight_section", "maintain_speed"),
            ("curved_section", "adjust_for_curve"),
            ("intersection_approach", "prepare_for_intersection"),
            ("highway_cruising", "highway_following")
        ]
        
        for i in range(num_actors):
            context, behavior = contexts[i % len(contexts)]
            
            criteria = EnhancedSpawnCriteria(
                road_context=context,
                distance_range=(30, 200)
            )
            
            matching_spawns = self.find_matching_spawns(criteria, ego_spawn, limit=5)
            
            if matching_spawns:
                spawn_point = random.choice(matching_spawns)
                spawns.append({
                    'x': spawn_point['position']['x'],
                    'y': spawn_point['position']['y'],
                    'z': spawn_point['position']['z'],
                    'yaw': spawn_point['position']['yaw'],
                    'road_id': spawn_point['road_id'],
                    'context': context,
                    'behavior_hint': behavior
                })
        
        return spawns


def create_enhanced_spawn_constraints():
    """Create example enhanced spawn constraint configurations"""
    
    constraints_library = {
        "roundabout_entry_scenario": EnhancedSpawnCriteria(
            road_context="roundabout_entry",
            junction_type="roundabout",
            distance_range=(50, 150),
            speed_limit_range=(15, 35)
        ),
        
        "highway_merge_scenario": EnhancedSpawnCriteria(
            road_context="highway_merge",
            road_type="highway",
            distance_range=(100, 300),
            speed_limit_range=(45, 80),
            curvature_range=(0.0, 0.05)  # Mostly straight
        ),
        
        "urban_intersection_scenario": EnhancedSpawnCriteria(
            road_context="intersection_approach",
            traffic_zone="urban_zone",
            distance_to_junction_range=(20, 80),
            intersection_complexity_range=(0.3, 1.0),  # Medium to high complexity
            speed_limit_range=(25, 45)
        ),
        
        "residential_parking_scenario": EnhancedSpawnCriteria(
            road_type="residential",
            traffic_zone="suburban_zone",
            distance_range=(20, 100),
            speed_limit_range=(15, 30),
            lane_type="parking"
        ),
        
        "curved_mountain_road_scenario": EnhancedSpawnCriteria(
            road_context="curved_section",
            curvature_range=(0.1, 0.5),  # High curvature
            distance_range=(50, 200),
            speed_limit_range=(25, 55)
        ),
        
        "complex_intersection_scenario": EnhancedSpawnCriteria(
            junction_type="signalized",
            intersection_complexity_range=(0.7, 1.0),  # High complexity only
            distance_to_junction_range=(30, 100),
            road_type="arterial"
        )
    }
    
    return constraints_library


if __name__ == "__main__":
    # Example usage
    constraints = create_enhanced_spawn_constraints()
    
    print("Enhanced Spawn Constraint Examples:")
    for scenario_name, criteria in constraints.items():
        print(f"\n{scenario_name}:")
        print(f"  Road Context: {criteria.road_context}")
        print(f"  Junction Type: {criteria.junction_type}")
        print(f"  Distance Range: {criteria.distance_range}")
        print(f"  Speed Range: {criteria.speed_limit_range}")
        if criteria.curvature_range:
            print(f"  Curvature Range: {criteria.curvature_range}")
        if criteria.intersection_complexity_range:
            print(f"  Complexity Range: {criteria.intersection_complexity_range}")