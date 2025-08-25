#!/usr/bin/env python3
"""
JSON to OpenSCENARIO (XOSC) Converter for CARLA
Converts flat, LLM-friendly JSON to valid OpenSCENARIO XML files
"""

import json
import sys
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional, Set
import xml.etree.ElementTree as ET
from xml.dom import minidom
import jsonschema
import os
import math
import argparse
import copy
import glob
import random
import logging

# CARLA-specific model catalogs for validation
CARLA_VEHICLES = {
    # Generation 2 vehicles
    'vehicle.dodge.charger_2020', 'vehicle.lincoln.mkz_2020', 'vehicle.mercedes.coupe_2020',
    'vehicle.mini.cooper_s_2021', 'vehicle.nissan.patrol_2021', 'vehicle.carlamotors.european_hgv',
    'vehicle.tesla.cybertruck', 'vehicle.dodge.charger_police_2020', 'vehicle.carlamotors.firetruck',
    'vehicle.ford.ambulance', 'vehicle.mercedes.sprinter', 'vehicle.volkswagen.t2_2021',
    'vehicle.mitsubishi.fusorosa',
    # Generation 1 vehicles
    'vehicle.audi.a2', 'vehicle.audi.etron', 'vehicle.audi.tt', 'vehicle.bmw.grandtourer',
    'vehicle.chevrolet.impala', 'vehicle.citroen.c3', 'vehicle.dodge.charger_police',
    'vehicle.ford.crown', 'vehicle.ford.mustang', 'vehicle.jeep.wrangler_rubicon',
    'vehicle.lincoln.mkz_2017', 'vehicle.mercedes.coupe', 'vehicle.micro.microlino',
    'vehicle.nissan.micra', 'vehicle.nissan.patrol', 'vehicle.seat.leon',
    'vehicle.tesla.model3', 'vehicle.toyota.prius', 'vehicle.volkswagen.t2',
    # Motorcycles and bicycles
    'vehicle.harley-davidson.low_rider', 'vehicle.kawasaki.ninja', 'vehicle.vespa.zx125',
    'vehicle.yamaha.yzf', 'vehicle.bh.crossbike', 'vehicle.diamondback.century',
    'vehicle.gazelle.omafiets'
}

CARLA_PEDESTRIANS = {f'walker.pedestrian.{i:04d}' for i in range(1, 52)}

# Bicycle models that don't support lane changes
BICYCLE_MODELS = {
    'vehicle.bh.crossbike', 
    'vehicle.diamondback.century', 
    'vehicle.gazelle.omafiets'
}

CARLA_MAPS = {
    'Town01', 'Town02', 'Town03', 'Town04', 'Town05'
}

# Weather presets mapping
WEATHER_PRESETS = {
    'clear': {'cloudiness': 0, 'precipitation': 0, 'sun_intensity': 0.85},
    'cloudy': {'cloudiness': 80, 'precipitation': 0, 'sun_intensity': 0.35},
    'wet': {'cloudiness': 20, 'precipitation': 20, 'sun_intensity': 0.65},
    'wet_cloudy': {'cloudiness': 80, 'precipitation': 20, 'sun_intensity': 0.35},
    'soft_rain': {'cloudiness': 70, 'precipitation': 30, 'sun_intensity': 0.35},
    'mid_rain': {'cloudiness': 80, 'precipitation': 60, 'sun_intensity': 0.25},
    'hard_rain': {'cloudiness': 90, 'precipitation': 90, 'sun_intensity': 0.15},
    'clear_noon': {'cloudiness': 0, 'precipitation': 0, 'sun_intensity': 1.0},
    'clear_sunset': {'cloudiness': 0, 'precipitation': 0, 'sun_intensity': 0.35}
}


class ValidationError(Exception):
    """Raised when JSON validation fails"""
    pass


class JsonToXoscConverter:
    def __init__(self, schema_path: Optional[str] = None):
        """Initialize converter with optional schema path"""
        self.schema = None
        if schema_path and os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                self.schema = json.load(f)
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Load spawn and waypoint data for all maps
        self.spawn_meta: Dict[str, List[Dict]] = {}
        self.waypoint_meta: Dict[str, Dict[str, List[Dict]]] = {}
        self._load_map_data()
        
        # Load road intelligence data for all maps
        self.road_intelligence: Dict[str, Dict] = {}
        self._load_road_intelligence()
        
        # Extract spawn points from road intelligence
        self.road_intelligence_spawns: Dict[str, List[Dict]] = {}
        self._extract_spawns_from_road_intelligence()
        
        self._ego_pos: Optional[Tuple[float, float, float, float]] = None
        self._ego_lane: Optional[Tuple[int, int]] = None # road_id, lane_id)
        self._selected_map: Optional[str] = None
        self._last_pick: Optional[Dict] = None
    def _load_map_data(self):
        """Load spawn and waypoint data for all available maps"""
        base_dir = os.path.dirname(__file__)
        
        # First try to load merged spawn files (enhanced coordinates + XODR lane types)
        for town in ['Town01', 'Town02', 'Town03', 'Town04', 'Town05']:
            merged_file = f"{town}_merged_spawns.json"
            if os.path.exists(merged_file):
                try:
                    with open(merged_file) as f:
                        data = json.load(f)
                        spawn_points = data.get('spawn_points', [])
                        self.spawn_meta[town] = spawn_points
                        self.logger.info(f"Loaded {len(spawn_points)} spawn points for {town} from merged file (includes {data.get('statistics', {}).get('Shoulder', 0)} shoulder spawns)")
                except Exception as e:
                    self.logger.warning(f"Could not load merged spawn data from {merged_file}: {e}")
        
        # Load enhanced spawn files for maps without merged data
        spawns_dir = os.path.join(base_dir, "spawns")
        for path in glob.glob(os.path.join(spawns_dir, "enhanced_Town*.json")):
            # Extract town name from enhanced_TownX.json -> TownX
            filename = os.path.basename(path)
            town = filename.replace("enhanced_", "").replace(".json", "")
            
            # Skip if already loaded from XODR
            if town in self.spawn_meta:
                continue
            
            try:
                with open(path) as f:
                    data = json.load(f)
                    # Handle both list format and dict format
                    if isinstance(data, dict) and any(key.startswith('Carla/Maps/') for key in data.keys()):
                        # Enhanced format with categories
                        spawn_points = []
                        for map_key, categories in data.items():
                            if isinstance(categories, dict):
                                for category, points in categories.items():
                                    spawn_points.extend(points)
                            else:
                                spawn_points.extend(categories)
                        self.spawn_meta[town] = spawn_points
                    else:
                        # Simple list format
                        self.spawn_meta[town] = data
                self.logger.info(f"Loaded {len(self.spawn_meta[town])} spawn points for {town} from enhanced file")
            except Exception as e:
                self.logger.warning(f"Could not load enhanced spawn data from {path}: {e}")
        
        # Load waypoint data (rich format)
        waypoints_dir = os.path.join(base_dir, "waypoints")
        for path in glob.glob(os.path.join(waypoints_dir, "Town*.json")):
            town = os.path.splitext(os.path.basename(path))[0]
            try:
                with open(path) as f:
                    data = json.load(f)
                    # Store the full structure
                    self.waypoint_meta[town] = data
                self.logger.info(f"Loaded waypoint data for {town}")
            except Exception as e:
                self.logger.warning(f"Could not load waypoint data from {path}: {e}")
    
    def _load_road_intelligence(self):
        """Load road intelligence data for all available maps"""
        base_dir = os.path.dirname(__file__)
        
        # Load road intelligence files (*_road_intelligence.json) from road_intelligence folder
        road_intel_dir = os.path.join(base_dir, "road_intelligence")
        for path in glob.glob(os.path.join(road_intel_dir, "*_road_intelligence.json")):
            # Extract town name from TownX_road_intelligence.json -> TownX
            filename = os.path.basename(path)
            town = filename.replace("_road_intelligence.json", "")
            
            try:
                with open(path) as f:
                    data = json.load(f)
                    self.road_intelligence[town] = data
                self.logger.info(f"Loaded road intelligence for {town} ({data.get('header', {}).get('total_roads', 0)} roads)")
            except Exception as e:
                self.logger.warning(f"Could not load road intelligence from {path}: {e}")
        
        # Identify 4-way junctions for each town
        self._identify_four_way_junctions()
    
    def _identify_four_way_junctions(self):
        """Identify 4-way junctions in each town for better intersection scenarios"""
        self.four_way_junctions = {}
        
        for town, road_data in self.road_intelligence.items():
            junctions = road_data.get('junctions', {})
            four_way_list = []
            
            for jid, jinfo in junctions.items():
                connections = jinfo.get('connections', [])
                incoming_roads = set()
                for conn in connections:
                    if 'incomingRoad' in conn:
                        incoming_roads.add(conn['incomingRoad'])
                
                # Consider it a 4-way junction if it has 4 or more incoming roads
                if len(incoming_roads) >= 4:
                    four_way_list.append({
                        'junction_id': jid,
                        'incoming_roads': list(incoming_roads),
                        'num_roads': len(incoming_roads),
                        'bounding_box': jinfo.get('bounding_box', {})
                    })
            
            self.four_way_junctions[town] = four_way_list
            if four_way_list:
                self.logger.info(f"Found {len(four_way_list)} 4-way junctions in {town}")
    
    def _extract_spawns_from_road_intelligence(self):
        """Extract spawn points from road intelligence geometry for all maps"""
        for town, road_data in self.road_intelligence.items():
            spawns = self._extract_lane_spawn_points(road_data, sample_interval=10.0)
            self.road_intelligence_spawns[town] = spawns
            
            # Count by lane type for logging
            lane_type_counts = {}
            for sp in spawns:
                lt = sp.get('lane_type', 'unknown')
                lane_type_counts[lt] = lane_type_counts.get(lt, 0) + 1
            
            self.logger.info(f"Extracted {len(spawns)} spawn points from {town} road intelligence: {lane_type_counts}")
    
    def _extract_lane_spawn_points(self, road_intelligence: Dict, sample_interval: float = 10.0) -> List[Dict]:
        """Extract spawn points for all lane types from road intelligence data"""
        spawn_points = []
        roads = road_intelligence.get('roads', {})
        
        for road_id, road_info in roads.items():
            geometry = road_info.get('geometry', [])
            if not geometry:
                continue
                
            lanes = road_info.get('lanes', {})
            if not lanes:
                continue
            
            # Process each geometry segment
            for geom_segment in geometry:
                segment_length = geom_segment.get('length', 0)
                if segment_length <= 0:
                    continue
                    
                start_x = geom_segment.get('x', 0)
                start_y = geom_segment.get('y', 0)
                heading = geom_segment.get('hdg', 0)  # in radians
                geom_type = geom_segment.get('geometry_type', 'line')
                
                # Sample points along the segment
                num_samples = max(1, int(segment_length / sample_interval))
                for i in range(num_samples + 1):
                    t = i / num_samples if num_samples > 0 else 0.5
                    s = t * segment_length
                    
                    # Calculate position along road centerline
                    if geom_type == 'line':
                        center_x = start_x + s * math.cos(heading)
                        center_y = start_y + s * math.sin(heading)
                        point_heading = heading
                    elif geom_type == 'arc':
                        # Simplified arc calculation
                        center_x = start_x + s * math.cos(heading)
                        center_y = start_y + s * math.sin(heading)
                        point_heading = heading
                    else:
                        center_x = start_x + s * math.cos(heading)
                        center_y = start_y + s * math.sin(heading)
                        point_heading = heading
                    
                    # Calculate position for each lane
                    for lane_id_str, lane_info in lanes.items():
                        lane_type = lane_info.get('lane_type', 'unknown').lower()
                        if lane_type == 'none':
                            continue  # Skip centerline
                            
                        lane_id = int(lane_id_str)
                        lane_width = lane_info.get('width', 3.5)
                        
                        # Calculate lateral offset from centerline to lane center
                        lateral_offset = self._calculate_lane_offset(lanes, lane_id)
                        
                        # Apply lateral offset
                        lane_x = center_x + lateral_offset * math.cos(point_heading + math.pi/2)
                        lane_y = center_y + lateral_offset * math.sin(point_heading + math.pi/2)
                        
                        # Create spawn point - capitalize lane_type to match existing convention
                        spawn_point = {
                            'x': round(lane_x, 3),
                            'y': round(lane_y, 3),
                            'z': 0.5,
                            'yaw': round(math.degrees(point_heading), 3),
                            'lane_type': lane_info.get('lane_type', 'unknown').capitalize(),  # Capitalize to match convention
                            'road_id': int(road_id),
                            'lane_id': lane_id,
                            'lane_width': lane_width,
                            'is_intersection': road_info.get('junction_id', -1) != -1,
                            'road_type': road_info.get('road_type', 'unknown'),
                            'speed_limit': road_info.get('speed_limit', 0)
                        }
                        
                        spawn_points.append(spawn_point)
        
        return spawn_points
    
    def _detect_highway_roads(self, map_name: str) -> Set[int]:
        """Dynamically detect highway roads from XODR file analysis
        
        Returns a set of road IDs that are likely highways based on:
        - Speed limit >= 60 mph (96 km/h)
        - At least 4 driving lanes
        - Road length > 100 meters
        - Not junction roads
        """
        highway_roads = set()
        
        # Try to load and parse XODR file
        xodr_path = os.path.join(os.path.dirname(__file__), 'maps', f'{map_name}.xodr')
        if not os.path.exists(xodr_path):
            self.logger.warning(f"XODR file not found: {xodr_path}")
            return highway_roads
        
        try:
            tree = ET.parse(xodr_path)
            root = tree.getroot()
            
            for road in root.findall('.//road'):
                road_id = road.get('id')
                if not road_id:
                    continue
                    
                # Skip junction roads
                junction_id = road.get('junction', '-1')
                if junction_id != '-1':
                    continue
                
                road_length = float(road.get('length', 0))
                if road_length < 100:  # Skip short roads
                    continue
                
                # Get speed limit
                speed_elem = road.find('.//speed')
                if speed_elem is None:
                    continue
                    
                speed_val = float(speed_elem.get('max', 0))
                unit = speed_elem.get('unit', 'mph')
                
                # Convert to km/h for comparison
                if unit == 'mph':
                    speed_kmh = speed_val * 1.60934
                elif unit == 'kph' or unit == 'km/h':
                    speed_kmh = speed_val
                else:
                    speed_kmh = speed_val  # Assume km/h if unknown
                
                # Highway typically has speed >= 60 mph (96 km/h)
                if speed_kmh < 96:
                    continue
                
                # Count driving lanes
                total_driving_lanes = 0
                for lane_section in road.findall('.//laneSection'):
                    # Count left side driving lanes
                    left_lanes = lane_section.findall('./left/lane[@type="driving"]')
                    # Count right side driving lanes  
                    right_lanes = lane_section.findall('./right/lane[@type="driving"]')
                    section_lanes = len(left_lanes) + len(right_lanes)
                    total_driving_lanes = max(total_driving_lanes, section_lanes)
                
                # Highway should have at least 4 driving lanes total
                if total_driving_lanes >= 4:
                    highway_roads.add(int(road_id))
                    self.logger.debug(f"Detected highway road {road_id}: {speed_kmh:.0f} km/h, {total_driving_lanes} lanes, {road_length:.0f}m")
                    
        except Exception as e:
            self.logger.warning(f"Error parsing XODR file for {map_name}: {e}")
        
        return highway_roads
    
    def _calculate_lane_offset(self, lanes: Dict, target_lane_id: int) -> float:
        """Calculate the lateral offset from road centerline to a specific lane center"""
        offset = 0.0
        
        if target_lane_id == 0:
            return 0.0  # Centerline
        
        if target_lane_id > 0:
            # Left side - sum widths from lane 1 to target
            for lane_id in range(1, target_lane_id + 1):
                lane = lanes.get(str(lane_id))
                if lane:
                    width = lane.get('width', 3.5)
                    if lane_id == target_lane_id:
                        offset += width / 2  # Go to center of target lane
                    else:
                        offset += width  # Add full width of intermediate lanes
        else:
            # Right side (negative lane IDs) 
            for lane_id in range(-1, target_lane_id - 1, -1):
                lane = lanes.get(str(lane_id))
                if lane:
                    width = lane.get('width', 3.5)
                    if lane_id == target_lane_id:
                        offset -= width / 2  # Go to center of target lane
                    else:
                        offset -= width  # Add full width of intermediate lanes
        
        return offset
    
    def _detect_scenario_type(self, data: Dict[str, Any]) -> str:
        """Detect scenario type based on scenario content"""
        # Check for multi-actor scenarios with lane changes - these need highways
        actors_count = len(data.get('actors', []))
        has_lane_change = False
        
        # Check if any action is a lane change
        for action in data.get('actions', []):
            if action.get('action_type') == 'lane_change':
                has_lane_change = True
                break
        
        # If there are multiple actors and lane changes, use highway map
        if actors_count > 1 and has_lane_change:
            self.logger.info(f"Detected multi-actor scenario with lane change ({actors_count} actors) - using highway map")
            return 'highway'
        
        # First check ego spawn criteria for road_context (most reliable)
        if 'ego_spawn' in data and 'criteria' in data['ego_spawn']:
            road_context = data['ego_spawn']['criteria'].get('road_context', '').lower()
            if road_context == 'highway':
                return 'highway'
            elif road_context == 'urban':
                # Could be various urban scenarios
                pass  # Continue to check other indicators
        
        scenario_name = data.get('scenario_name', '').lower()
        description = data.get('description', '').lower()
        
        # Check for highway scenarios in name/description as fallback
        if any(keyword in scenario_name or keyword in description for keyword in
               ['highway', 'freeway', 'motorway']):
            return 'highway'
        
        # Check for lane change related scenarios
        if any(keyword in scenario_name or keyword in description for keyword in 
               ['cut_in', 'lane_change', 'overtake', 'merge', 'aggressive_merge']):
            return 'cut_in'
        
        # Check for intersection scenarios
        if any(keyword in scenario_name or keyword in description for keyword in
               ['intersection', 'cross', 'traffic_light', 'stop_sign']):
            return 'intersection'
        
        # Check for following scenarios
        if any(keyword in scenario_name or keyword in description for keyword in
               ['following', 'brake', 'stop_and_go', 'slow_leader']):
            return 'following'
        
        # Check actor lane relationships for additional hints (only if not already classified)
        for actor in data.get('actors', []):
            if 'spawn' in actor and 'criteria' in actor['spawn']:
                criteria = actor['spawn']['criteria']
                if criteria.get('lane_relationship') in ['adjacent_lane']:
                    # Only classify as cut_in if not already a highway scenario
                    return 'cut_in'
        
        return 'general'

    def _calculate_map_suitability_score(self, map_name: str, scenario_type: str, spawn_criteria: List[Dict]) -> float:
        """Calculate how suitable a map is for a given scenario type"""
        score = 0.0
        
        try:
            spawn_points = self._get_spawn_points_for_map(map_name)
            total_spawns = len(spawn_points)
            
            # Base score from spawn point count
            score += total_spawns * 0.1
            
            # Analyze road topology for scenario-specific scoring
            road_groups = {}
            for pt in spawn_points:
                road_id = pt.get('road_id')
                if road_id not in road_groups:
                    road_groups[road_id] = []
                road_groups[road_id].append(pt)
            
            # Count roads with different capabilities
            adjacent_lane_roads = 0
            multi_spawn_roads = 0
            
            for road_id, points in road_groups.items():
                # Check if road has adjacent lanes (for cut-in scenarios)
                lanes = set(pt.get('lane_id') for pt in points if pt.get('lane_id') is not None)
                sorted_lanes = sorted(lanes)
                has_adjacent = False
                for i in range(len(sorted_lanes) - 1):
                    if abs(sorted_lanes[i+1] - sorted_lanes[i]) == 1:
                        has_adjacent = True
                        break
                
                if has_adjacent:
                    adjacent_lane_roads += 1
                
                if len(points) >= 4:  # Good spawn density
                    multi_spawn_roads += 1
            
            # Apply scenario-specific scoring
            if scenario_type == 'cut_in':
                score += adjacent_lane_roads * 50  # Heavily favor maps with adjacent lanes
                score += multi_spawn_roads * 10
                
                # Penalty for maps with few suitable roads
                if adjacent_lane_roads < 3:
                    score *= 0.5
                    
            elif scenario_type == 'following':
                score += multi_spawn_roads * 20
                
            elif scenario_type == 'highway':
                # Known highway maps get high scores
                if map_name in ['Town04', 'Town05', 'Town03']:
                    score += 1000  # High score for known highway maps
                    self.logger.debug(f"Map {map_name} is a known highway map, boosting score")
                
                # Also check road intelligence for additional highway roads
                road_data = self.road_intelligence.get(map_name, {})
                highway_roads = 0
                if 'roads' in road_data:
                    for road_info in road_data['roads'].values():
                        speed_limit = road_info.get('speed_limit')
                        if road_info.get('type') == 'highway' or (speed_limit is not None and speed_limit > 70):
                            highway_roads += 1
                score += highway_roads * 30
                
            elif scenario_type == 'intersection':
                # Favor maps with 4-way junctions for intersection scenarios
                if hasattr(self, 'four_way_junctions'):
                    num_4way = len(self.four_way_junctions.get(map_name, []))
                    if num_4way > 0:
                        score += 500 + (num_4way * 100)  # High score for maps with 4-way junctions
                        self.logger.debug(f"Map {map_name} has {num_4way} 4-way junctions, boosting score")
                
            # Bonus for maps that can satisfy all spawn criteria
            criteria_satisfied = 0
            for criteria in spawn_criteria:
                if any(self._matches_criteria(pt, criteria, map_name) for pt in spawn_points):
                    criteria_satisfied += 1
            
            if criteria_satisfied == len(spawn_criteria):
                score *= 2.0  # Double score for full compatibility
            else:
                score *= (criteria_satisfied / max(1, len(spawn_criteria)))  # Proportional penalty
                
        except Exception as e:
            self.logger.warning(f"Error calculating suitability for {map_name}: {e}")
            import traceback
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
            score = 0.0
        
        return score

    def _detect_best_map(self, data: Dict[str, Any]) -> str:
        """Auto-detect the best map by trying each until constraints can be satisfied"""
        # If map is explicitly specified, validate and use it
        if 'map_name' in data:
            map_name = data['map_name']
            if map_name in self.spawn_meta or map_name in self.waypoint_meta:
                self.logger.info(f"Using explicitly specified map: {map_name}")
                return map_name
            else:
                self.logger.warning(f"Specified map {map_name} not found, attempting auto-detection")
        
        # Detect scenario type
        scenario_type = self._detect_scenario_type(data)
        self._current_scenario_type = scenario_type  # Store for use in other methods
        self.logger.info(f"Detected scenario type: {scenario_type}")
        
        # Collect all spawn criteria
        spawn_criteria = []
        if 'ego_spawn' in data:
            spawn_criteria.append(data['ego_spawn'].get('criteria', {}))
        
        for actor in data.get('actors', []):
            if 'spawn' in actor:
                spawn_criteria.append(actor['spawn'].get('criteria', {}))
        
        if not spawn_criteria:
            # No criteria specified, use scenario type to pick best default
            default_maps = {
                'cut_in': 'Town04',  # Has many multi-lane roads
                'highway': 'Town04',  # Has highway-like roads  
                'intersection': 'Town01',  # Good intersection variety
                'following': 'Town02',  # Good for basic following
                'general': 'Town01'
            }
            default_map = default_maps.get(scenario_type, 'Town01')
            self.logger.info(f"No spawn criteria found, using scenario-based default map: {default_map}")
            return default_map
        
        # Score each available map based on scenario requirements
        available_maps = list(set(self.spawn_meta.keys()) | set(self.waypoint_meta.keys()))
        map_scores = {}
        
        for map_name in available_maps:
            score = self._calculate_map_suitability_score(map_name, scenario_type, spawn_criteria)
            map_scores[map_name] = score
            self.logger.debug(f"Map {map_name} suitability score: {score:.1f}")
        
        # Sort maps by score (highest first)
        sorted_maps = sorted(map_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Try each map in order of score to see if it can satisfy the constraints
        self.logger.info("Checking maps for constraint satisfaction...")
        for map_name, score in sorted_maps:
            if score <= 0:
                continue  # Skip maps with no score
                
            self.logger.info(f"Trying map {map_name} (score: {score:.1f})...")
            
            # Check if this map can satisfy all spawn constraints
            if self._can_map_satisfy_constraints(map_name, data):
                self.logger.info(f"✓ Selected map: {map_name} - can satisfy all constraints")
                return map_name
            else:
                self.logger.info(f"✗ Map {map_name} cannot satisfy all constraints, trying next...")
        
        # If no map can satisfy all constraints, return the highest scoring one
        if sorted_maps and sorted_maps[0][1] > 0:
            best_map = sorted_maps[0][0]
            self.logger.warning(f"No map can satisfy all constraints perfectly. Using highest scoring: {best_map}")
            return best_map
        
        # Fall back to scenario-based default with warning
        default_maps = {
            'cut_in': 'Town04',
            'highway': 'Town04',
            'intersection': 'Town01', 
            'following': 'Town02',
            'general': 'Town01'
        }
        default_map = default_maps.get(scenario_type, 'Town01')
        self.logger.warning(f"No suitable maps found, falling back to scenario-based default: {default_map}")
        return default_map
    
    def _can_map_satisfy_constraints(self, map_name: str, data: Dict[str, Any]) -> bool:
        """Check if a map can satisfy all spawn constraints without actually spawning"""
        try:
            pts = self._get_spawn_points_for_map(map_name)
            if not pts:
                return False
            
            # Check ego spawn
            if 'ego_spawn' in data:
                ego_crit = data['ego_spawn'].get('criteria', {})
                # Check if there are enough points matching ego criteria
                ego_matches = [pt for pt in pts if self._matches_spawn_criteria(pt, ego_crit, None, None)]
                if len(ego_matches) < 5:  # Need at least 5 options for ego
                    return False
            
            # Check actor spawns
            for actor in data.get('actors', []):
                if 'spawn' in actor:
                    actor_crit = actor['spawn'].get('criteria', {})
                    # For actors with special lane types like Shoulder, check availability
                    if 'lane_type' in actor_crit:
                        lane_types = actor_crit['lane_type'] if isinstance(actor_crit['lane_type'], list) else [actor_crit['lane_type']]
                        matching_points = [pt for pt in pts if pt.get('lane_type') in lane_types]
                        
                        # For Shoulder lanes with same_road constraint, check road variety
                        if 'Shoulder' in lane_types and actor_crit.get('road_relationship') == 'same_road':
                            # Count how many different roads have Shoulder lanes
                            roads_with_shoulder = set(pt.get('road_id') for pt in matching_points if pt.get('road_id'))
                            if len(roads_with_shoulder) < 10:  # Need variety of roads with Shoulder lanes
                                self.logger.debug(f"Map {map_name} has Shoulder lanes on only {len(roads_with_shoulder)} roads")
                                return False
                        elif len(matching_points) < 3:  # For other lane types, just need 3 options
                            self.logger.debug(f"Map {map_name} has only {len(matching_points)} {lane_types} spawns")
                            return False
            
            return True
            
        except Exception as e:
            self.logger.debug(f"Error checking constraints for {map_name}: {e}")
            return False
    
    def _get_spawn_points_for_map(self, map_name: str) -> List[Dict]:
        """Get spawn points for a map - prefer accurate CARLA extracts"""
        points = []
        
        # First try accurate CARLA spawns (with correct lane types)
        carla_spawn_file = f"carla_accurate_spawns/{map_name}_spawns.json"
        if os.path.exists(carla_spawn_file):
            self.logger.info(f"Using accurate CARLA spawns from {carla_spawn_file}")
            with open(carla_spawn_file, 'r') as f:
                data = json.load(f)
                return data.get('spawn_points', [])
        
        # Fallback to enhanced spawn data
        if map_name in self.spawn_meta:
            self.logger.info(f"Using enhanced spawns for {map_name}")
            points.extend(self.spawn_meta[map_name])
        
        return points
    
    def _matches_criteria(self, point: Dict, criteria: Dict, map_name: str = None) -> bool:
        """Check if a spawn point matches the given criteria"""
        for key, value in criteria.items():
            if key == 'road_id':
                if value == 'same_as_ego':
                    continue  # Skip ego-relative checks in initial compatibility
                if isinstance(value, list) and point.get('road_id') not in value:
                    return False
                elif not isinstance(value, list) and point.get('road_id') != value:
                    return False
            
            elif key == 'lane_id':
                if value == 'same_as_ego':
                    continue  # Skip ego-relative checks
                point_lane = point.get('lane_id')
                if isinstance(value, list) and point_lane not in value:
                    return False
                elif isinstance(value, dict):
                    if not (value.get('min', float('-inf')) <= point_lane <= value.get('max', float('inf'))):
                        return False
                elif not isinstance(value, (list, dict)) and point_lane != value:
                    return False
            
            elif key == 'lane_type':
                valid_types = value if isinstance(value, list) else [value]
                if point.get('lane_type') not in valid_types:
                    return False
            
            elif key == 'is_intersection':
                if point.get('is_intersection') != value:
                    return False
                    
            # NEW: Road intelligence criteria
            elif key == 'road_context' and map_name:
                if not self._matches_road_context(point, value, map_name):
                    return False
                    
            elif key == 'junction_proximity' and map_name:
                if not self._matches_junction_proximity(point, value, map_name):
                    return False
                    
            elif key == 'junction_type' and map_name:
                if not self._matches_junction_type(point, value, map_name):
                    return False
                    
            elif key == 'road_curvature' and map_name:
                if not self._matches_road_curvature(point, value, map_name):
                    return False
                    
            elif key == 'speed_limit' and map_name:
                if not self._matches_speed_limit(point, value, map_name):
                    return False
                    
            elif key == 'road_connectivity' and map_name:
                if not self._matches_road_connectivity(point, value, map_name):
                    return False
        
        return True
    
    def _matches_road_context(self, point: Dict, context: str, map_name: str) -> bool:
        """Check if spawn point matches road context (highway/urban/suburban)"""
        road_data = self.road_intelligence.get(map_name, {})
        if not road_data:
            return True  # Skip if no intelligence data
            
        road_info = road_data.get('roads', {}).get(str(point.get('road_id', '')), {})
        road_type = road_info.get('road_type', 'unknown')
        speed_limit = road_info.get('speed_limit', 0) or 0  # Handle None values
        
        if context == 'highway' and speed_limit >= 60:
            return True
        elif context == 'urban' and road_type in ['town', 'city'] and speed_limit <= 50:
            return True
        elif context == 'suburban' and 30 <= speed_limit <= 60:
            return True
        elif context == 'service' and road_type == 'service':
            return True
        
        return False
    
    def _matches_junction_proximity(self, point: Dict, proximity: Dict, map_name: str) -> bool:
        """Check if spawn point matches junction proximity constraints"""
        road_data = self.road_intelligence.get(map_name, {})
        if not road_data:
            return True
            
        junctions = road_data.get('junctions', {})
        if not junctions:
            return True
            
        point_x, point_y = point.get('x', 0), point.get('y', 0)
        min_distance = float('inf')
        
        # Find nearest junction
        for junction_data in junctions.values():
            junction_center = junction_data.get('center', {})
            jx, jy = junction_center.get('x', 0), junction_center.get('y', 0)
            distance = math.hypot(point_x - jx, point_y - jy)
            min_distance = min(min_distance, distance)
        
        min_prox = proximity.get('min', 0)
        max_prox = proximity.get('max', 1000)
        return min_prox <= min_distance <= max_prox
    
    def _matches_junction_type(self, point: Dict, junction_type: str, map_name: str) -> bool:
        """Check if spawn point is near the specified junction type"""
        road_data = self.road_intelligence.get(map_name, {})
        if not road_data:
            return True
            
        if junction_type == 'roundabout':
            roundabouts = road_data.get('roundabouts', [])
            if not roundabouts and junction_type == 'roundabout':
                return False
            # Check if point is near a roundabout
            point_x, point_y = point.get('x', 0), point.get('y', 0)
            for roundabout in roundabouts:
                center = roundabout.get('center', {})
                rx, ry = center.get('x', 0), center.get('y', 0)
                radius = roundabout.get('radius', 20)
                distance = math.hypot(point_x - rx, point_y - ry)
                if distance <= radius * 2:  # Within 2x radius
                    return True
            return False
            
        elif junction_type == 'intersection':
            # Check if near regular junctions
            junctions = road_data.get('junctions', {})
            point_x, point_y = point.get('x', 0), point.get('y', 0)
            for junction_data in junctions.values():
                junction_center = junction_data.get('center', {})
                jx, jy = junction_center.get('x', 0), junction_center.get('y', 0)
                distance = math.hypot(point_x - jx, point_y - jy)
                if distance <= 50:  # Within 50m of junction
                    return True
            return False
            
        elif junction_type == 'none':
            # Check that it's NOT near any junction
            return not self._matches_junction_type(point, 'intersection', map_name)
            
        return True
    
    def _matches_road_curvature(self, point: Dict, curvature: str, map_name: str) -> bool:
        """Check if spawn point is on road with specified curvature"""
        road_data = self.road_intelligence.get(map_name, {})
        if not road_data:
            return True
            
        road_info = road_data.get('roads', {}).get(str(point.get('road_id', '')), {})
        geometry = road_info.get('geometry', [])
        
        has_curves = any(g.get('geometry_type') == 'arc' for g in geometry)
        
        if curvature == 'straight':
            return not has_curves
        elif curvature == 'curved':
            return has_curves
        elif curvature == 'any':
            return True
            
        return True
    
    def _matches_speed_limit(self, point: Dict, speed_limit: Dict, map_name: str) -> bool:
        """Check if spawn point is on road with specified speed limit"""
        road_data = self.road_intelligence.get(map_name, {})
        if not road_data:
            return True
            
        road_info = road_data.get('roads', {}).get(str(point.get('road_id', '')), {})
        actual_speed = road_info.get('speed_limit', 0) or 0  # Handle None values
        
        min_speed = speed_limit.get('min', 0)
        max_speed = speed_limit.get('max', 1000)
        
        return min_speed <= actual_speed <= max_speed
    
    def _matches_road_connectivity(self, point: Dict, connectivity: str, map_name: str) -> bool:
        """Check if spawn point is on road with specified connectivity"""
        road_data = self.road_intelligence.get(map_name, {})
        if not road_data:
            return True
            
        road_info = road_data.get('roads', {}).get(str(point.get('road_id', '')), {})
        predecessor = road_info.get('predecessor')
        successor = road_info.get('successor')
        
        if connectivity == 'well_connected':
            return predecessor is not None and successor is not None
        elif connectivity == 'isolated':
            return predecessor is None and successor is None
        elif connectivity == 'terminal':
            return (predecessor is None) != (successor is None)  # XOR - exactly one connection
            
        return True
    
    def validate_json(self, data: Dict[str, Any]) -> None:
        """Validate JSON data against schema and CARLA-specific requirements"""
        # Schema validation if available
        if self.schema:
            try:
                jsonschema.validate(data, self.schema)
            except jsonschema.ValidationError as e:
                raise ValidationError(f"Schema validation failed: {e.message}")
        
        # Don't auto-detect map here anymore - it's done in convert()
        # Just validate if a map is explicitly specified
        if 'map_name' in data:
            map_name = data['map_name']
            if map_name not in CARLA_MAPS:
                self.logger.warning(f"Specified map {map_name} not in CARLA_MAPS list, proceeding anyway")
        
        # Validate ego vehicle model
        ego_model = data.get('ego_vehicle_model', 'vehicle.tesla.model3')
        if ego_model not in CARLA_VEHICLES:
            raise ValidationError(f"Invalid ego vehicle model: {ego_model}")
        
        # Validate actors
        for actor in data.get('actors', []):
            if actor['type'] == 'vehicle':
                if actor['model'] not in CARLA_VEHICLES:
                    raise ValidationError(f"Invalid vehicle model: {actor['model']}")
            elif actor['type'] in ['pedestrian', 'cyclist']:
                if actor['model'] not in CARLA_PEDESTRIANS:
                    raise ValidationError(f"Invalid pedestrian model: {actor['model']}")
            
            # Validate color format if present
            if 'color' in actor:
                try:
                    r, g, b = map(int, actor['color'].split(','))
                    if not all(0 <= c <= 255 for c in [r, g, b]):
                        raise ValueError
                except:
                    raise ValidationError(f"Invalid color format: {actor['color']}")
    
    def parse_position(self, pos_str: str, map_name: str = None) -> Tuple[float, float, float, float]:
        """Parse position string 'x,y,z,yaw' with defaults and auto-computed heading"""
        parts = pos_str.split(',')
        x = float(parts[0])
        y = float(parts[1])
        z = float(parts[2]) if len(parts) > 2 else 0.5
        yaw = float(parts[3]) if len(parts) > 3 else None
        
        # Auto-compute heading if not specified and map is available
        if yaw is None and map_name:
            yaw_rad = self._auto_compute_heading_from_position(x, y, map_name)
            self.logger.info(f"Auto-computed heading for position ({x:.1f}, {y:.1f}): {math.degrees(yaw_rad):.1f}°")
        else:
            # Convert yaw from degrees to radians
            yaw_rad = math.radians(yaw) if yaw is not None else 0.0
            
        return x, y, z, yaw_rad
    
    def create_file_header(self) -> ET.Element:
        """Create FileHeader element"""
        header = ET.Element('FileHeader')
        header.set('revMajor', '1')
        header.set('revMinor', '0')
        header.set('date', datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
        header.set('description', 'CARLA:GeneratedFromJSON')
        header.set('author', 'JSON2XOSC Converter')
        return header
    
    def create_environment(self, weather: str) -> ET.Element:
        """Create Environment element with weather settings"""
        env = ET.Element('Environment')
        env.set('name', 'Environment1')
        
        # TimeOfDay
        tod = ET.SubElement(env, 'TimeOfDay')
        tod.set('animation', 'false')
        tod.set('dateTime', '2020-01-01T12:00:00')
        
        # Weather
        weather_elem = ET.SubElement(env, 'Weather')
        weather_elem.set('cloudState', 'free')
        
        preset = WEATHER_PRESETS.get(weather, WEATHER_PRESETS['clear'])
        
        sun = ET.SubElement(weather_elem, 'Sun')
        sun.set('intensity', str(preset['sun_intensity']))
        sun.set('azimuth', '0')
        sun.set('elevation', '1.31')
        
        fog = ET.SubElement(weather_elem, 'Fog')
        fog.set('visualRange', '100000.0')
        
        precip = ET.SubElement(weather_elem, 'Precipitation')
        precip.set('precipitationType', 'rain' if preset['precipitation'] > 0 else 'dry')
        precip.set('intensity', str(preset['precipitation'] / 100.0))
        
        # RoadCondition
        road = ET.SubElement(env, 'RoadCondition')
        road.set('frictionScaleFactor', '1.0')
        
        return env
    
    def create_entities(self, data: Dict[str, Any]) -> ET.Element:
        """Create Entities section"""
        entities = ET.Element('Entities')
        
        # Ego vehicle
        ego = ET.SubElement(entities, 'ScenarioObject')
        ego.set('name', 'hero')
        
        ego_vehicle = ET.SubElement(ego, 'Vehicle')
        ego_vehicle.set('name', data.get('ego_vehicle_model', 'vehicle.tesla.model3'))
        ego_vehicle.set('vehicleCategory', 'car')
        
        # Standard vehicle elements
        ET.SubElement(ego_vehicle, 'ParameterDeclarations')
        
        perf = ET.SubElement(ego_vehicle, 'Performance')
        perf.set('maxSpeed', '69.444')
        perf.set('maxAcceleration', '200')
        perf.set('maxDeceleration', '10.0')
        
        bbox = ET.SubElement(ego_vehicle, 'BoundingBox')
        center = ET.SubElement(bbox, 'Center')
        center.set('x', '1.5')
        center.set('y', '0.0')
        center.set('z', '0.9')
        dim = ET.SubElement(bbox, 'Dimensions')
        dim.set('width', '2.1')
        dim.set('length', '4.5')
        dim.set('height', '1.8')
        
        axles = ET.SubElement(ego_vehicle, 'Axles')
        front = ET.SubElement(axles, 'FrontAxle')
        front.set('maxSteering', '0.5')
        front.set('wheelDiameter', '0.6')
        front.set('trackWidth', '1.8')
        front.set('positionX', '3.1')
        front.set('positionZ', '0.3')
        rear = ET.SubElement(axles, 'RearAxle')
        rear.set('maxSteering', '0.0')
        rear.set('wheelDiameter', '0.6')
        rear.set('trackWidth', '1.8')
        rear.set('positionX', '0.0')
        rear.set('positionZ', '0.3')
        
        props = ET.SubElement(ego_vehicle, 'Properties')
        prop = ET.SubElement(props, 'Property')
        prop.set('name', 'type')
        prop.set('value', 'ego_vehicle')
        
        # Other actors
        for actor in data.get('actors', []):
            obj = ET.SubElement(entities, 'ScenarioObject')
            obj.set('name', actor['id'])
            
            if actor['type'] in ['vehicle', 'cyclist']:
                vehicle = ET.SubElement(obj, 'Vehicle')
                # Fix vehicle model for lane change scenarios - bicycles can't do lane changes
                model = self._fix_vehicle_model_for_actions(actor, data)
                vehicle.set('name', model)
                vehicle.set('vehicleCategory', 'bicycle' if actor['type'] == 'cyclist' and 'bicycle' in model else 'car')
                
                # Copy standard vehicle elements
                ET.SubElement(vehicle, 'ParameterDeclarations')
                vehicle.append(copy.deepcopy(perf))
                vehicle.append(copy.deepcopy(bbox))
                vehicle.append(copy.deepcopy(axles))
                
                props = ET.SubElement(vehicle, 'Properties')
                prop = ET.SubElement(props, 'Property')
                prop.set('name', 'type')
                prop.set('value', 'simulation')
                
                # Add color property - use specified color or default white
                color_value = actor.get('color', '255,255,255')  # Default white
                color_prop = ET.SubElement(props, 'Property')
                color_prop.set('name', 'color')
                color_prop.set('value', color_value)
                    
            elif actor['type'] == 'pedestrian':
                ped = ET.SubElement(obj, 'Pedestrian')
                ped.set('model', actor['model'])
                ped.set('mass', '90.0')
                ped.set('name', actor['model'])
                ped.set('pedestrianCategory', 'pedestrian')
                
                ET.SubElement(ped, 'ParameterDeclarations')
                ped.append(copy.deepcopy(bbox))
                
                props = ET.SubElement(ped, 'Properties')
                prop = ET.SubElement(props, 'Property')
                prop.set('name', 'type')
                prop.set('value', 'simulation')
                
            elif actor['type'] == 'static_object':
                misc = ET.SubElement(obj, 'MiscObject')
                misc.set('mass', '500.0')
                misc.set('name', actor['model'])
                misc.set('miscObjectCategory', 'obstacle')
                
                ET.SubElement(misc, 'ParameterDeclarations')
                misc.append(copy.deepcopy(bbox))
                
                props = ET.SubElement(misc, 'Properties')
                prop = ET.SubElement(props, 'Property')
                prop.set('name', 'type')
                prop.set('value', 'simulation')
        
        return entities
    
    def _fix_vehicle_model_for_actions(self, actor: Dict, data: Dict[str, Any]) -> str:
        """Fix vehicle model for compatibility with planned actions"""
        original_model = actor.get('model', 'vehicle.toyota.prius')
        
        # Check if this actor has lane change actions
        has_lane_change = False
        for action in data.get('actions', []):
            if (action.get('actor_id') == actor['id'] and 
                action.get('action_type') == 'lane_change'):
                has_lane_change = True
                break
        
        # If actor has lane change actions but is a bicycle/motorcycle, replace with car
        if has_lane_change and any(bike_type in original_model.lower() for bike_type in 
                                  ['crossbike', 'bicycle', 'ninja', 'harley', 'vespa', 'yamaha']):
            self.logger.info(f"Replacing bicycle/motorcycle {original_model} with car for lane change compatibility")
            return 'vehicle.toyota.prius'  # Safe default car model
        
        return original_model
    
    def log_spawn_details(self, ego_spawn: Dict, actor_spawns: List[Dict]):
        """Log spawn positions for debugging"""
        print("\n=== SPAWN SUMMARY ===")
        print(f"EGO Position:")
        print(f"  Road: {ego_spawn.get('road_id', 'unknown')}, Lane: {ego_spawn.get('lane_id', 'unknown')}")
        print(f"  Coordinates: x={ego_spawn.get('x', 0):.2f}, y={ego_spawn.get('y', 0):.2f}")
        
        # Normalize heading to -180 to 180 degrees
        ego_yaw_rad = ego_spawn.get('yaw', 0)
        ego_yaw_deg = math.degrees(ego_yaw_rad)
        while ego_yaw_deg > 180:
            ego_yaw_deg -= 360
        while ego_yaw_deg < -180:
            ego_yaw_deg += 360
        print(f"  Heading: {ego_yaw_rad:.2f} rad ({ego_yaw_deg:.1f}°)")
        
        for actor_spawn in actor_spawns:
            actor_name = actor_spawn.get('actor_name', 'unknown')
            spawn = actor_spawn.get('spawn', {})
            print(f"\n{actor_name} Position:")
            print(f"  Road: {spawn.get('road_id', 'unknown')}, Lane: {spawn.get('lane_id', 'unknown')}")
            print(f"  Coordinates: x={spawn.get('x', 0):.2f}, y={spawn.get('y', 0):.2f}")
            
            # Calculate distance to ego
            ego_x, ego_y = ego_spawn.get('x', 0), ego_spawn.get('y', 0)
            actor_x, actor_y = spawn.get('x', 0), spawn.get('y', 0)
            distance = math.sqrt((actor_x - ego_x)**2 + (actor_y - ego_y)**2)
            print(f"  Distance from ego: {distance:.1f}m")
            
            # Determine relative position more accurately
            relative_pos = "unknown"
            if distance > 0:
                ego_yaw = ego_spawn.get('yaw', 0)
                dx, dy = actor_x - ego_x, actor_y - ego_y
                
                # Calculate angle from ego to actor
                angle_to_actor = math.atan2(dy, dx)
                
                # Calculate relative angle (normalized to -pi to pi)
                relative_angle = angle_to_actor - ego_yaw
                while relative_angle > math.pi:
                    relative_angle -= 2 * math.pi
                while relative_angle < -math.pi:
                    relative_angle += 2 * math.pi
                
                # Determine position based on relative angle
                relative_angle_deg = math.degrees(relative_angle)
                if -45 <= relative_angle_deg <= 45:
                    relative_pos = "ahead"
                elif 135 <= abs(relative_angle_deg) <= 180:
                    relative_pos = "behind"
                elif 45 < relative_angle_deg < 135:
                    relative_pos = "right"
                elif -135 < relative_angle_deg < -45:
                    relative_pos = "left"
            
            print(f"  Relative position: {relative_pos}")
            
            # Normalize actor heading
            actor_yaw_rad = spawn.get('yaw', 0)
            actor_yaw_deg = math.degrees(actor_yaw_rad)
            while actor_yaw_deg > 180:
                actor_yaw_deg -= 360
            while actor_yaw_deg < -180:
                actor_yaw_deg += 360
            print(f"  Heading: {actor_yaw_rad:.2f} rad ({actor_yaw_deg:.1f}°)")
            
            # Check for issues
            issues = []
            if distance > 100:
                issues.append("Too far from ego (>100m)")
            if distance < 5:
                issues.append("Too close to ego (<5m)")
                
            # Check if actually in same lane (considering direction)
            ego_road = ego_spawn.get('road_id')
            ego_lane = ego_spawn.get('lane_id')
            actor_road = spawn.get('road_id')
            actor_lane = spawn.get('lane_id')
            
            if ego_road == actor_road and ego_lane == actor_lane:
                issues.append("Same lane as ego")
            elif ego_road == actor_road and ego_lane and actor_lane:
                # Check if lanes are going in opposite directions
                if (ego_lane > 0) != (actor_lane > 0):
                    issues.append("Opposite direction lane (collision risk!)")
            
            if issues:
                print(f"  Issues: {', '.join(issues)}")
        
        print("=" * 40)

    def _detect_scenario_type_from_name(self, scenario_name: str) -> str:
        """Detect the scenario type from the name only (legacy function)"""
        # Handle case where we get a dict instead of string
        if isinstance(scenario_name, dict):
            scenario_name = scenario_name.get('scenario_name', '')
        name_lower = scenario_name.lower()
        if 'cut_in' in name_lower or 'cut-in' in name_lower or 'lane_change' in name_lower:
            return 'cut_in'
        elif 'following' in name_lower or 'follow' in name_lower:
            return 'following'
        elif 'brake' in name_lower and 'sudden' in name_lower:
            return 'sudden_brake'
        elif 'slowdown' in name_lower or 'gradual' in name_lower:
            return 'gradual_slowdown'
        elif 'parked' in name_lower:
            return 'parked_vehicle'
        elif 'pedestrian' in name_lower or 'crossing' in name_lower:
            return 'pedestrian'
        elif 'intersection' in name_lower or 'junction' in name_lower:
            return 'intersection'
        else:
            return 'general'
    
    def _enforce_minimum_distance(self, criteria: Dict[str, Any], scenario_type: str, actor_type: str = '') -> Dict[str, Any]:
        """Enforce minimum distance constraints based on scenario type"""
        MIN_DISTANCES = {
            'cut_in': 25,
            'following': 20,
            'gradual_slowdown': 20,
            'sudden_brake': 20,
            'parked_vehicle': 15,
            'pedestrian': 10,
            'intersection': 30,
            'general': 10
        }
        
        min_d = MIN_DISTANCES.get(scenario_type, 10)
        
        # Special handling for pedestrians
        if 'pedestrian' in actor_type.lower():
            min_d = max(min_d, 10)  # At least 10m for pedestrians
        
        # Get or create distance constraints
        dist_constraint = criteria.setdefault('distance_to_ego', {})
        
        # Get current min/max values
        current_min = dist_constraint.get('min', min_d)
        current_max = dist_constraint.get('max', min_d * 3)
        
        # Enforce minimum distance
        if current_min < min_d:
            self.logger.info(f"Enforcing minimum distance for {scenario_type}: {current_min}m -> {min_d}m")
            dist_constraint['min'] = min_d
        
        # Ensure max is reasonable relative to min (but don't expand too much)
        # Only adjust if the range is impossibly small (< 2m)
        min_range = dist_constraint.get('min', min_d)
        if current_max - min_range < 2:
            # Add a reasonable range (at least 10m range, or double the min)
            new_max = min_range + max(10, min_range * 0.5)
            self.logger.info(f"Adjusting maximum distance for {scenario_type}: {current_max}m -> {new_max}m (range too small)")
            dist_constraint['max'] = new_max
        else:
            # Keep the original max
            dist_constraint['max'] = current_max
        
        # Cap pedestrian max distance to 50m
        if 'pedestrian' in actor_type.lower() and dist_constraint.get('max', 0) > 50:
            self.logger.info(f"Capping pedestrian spawn distance to 50m (was {dist_constraint['max']}m)")
            dist_constraint['max'] = 50
        
        return criteria

    def _fix_spawn_criteria(self, criteria: Dict[str, Any], actor: Dict[str, Any], scenario_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply intelligent fixes to spawn criteria to prevent common issues"""
        fixed_criteria = criteria.copy()
        scenario_name = scenario_data.get('scenario_name', '').lower()
        actor_type = actor.get('type', '')
        
        # Normalize lane_relationship: "my_lane" -> "same_lane"
        if fixed_criteria.get('lane_relationship') == 'my_lane':
            fixed_criteria['lane_relationship'] = 'same_lane'
            self.logger.debug(f"Normalized 'my_lane' to 'same_lane' for actor {actor.get('id', 'unknown')}")
        
        # Detect scenario type and enforce minimum distances
        scenario_type = self._detect_scenario_type_from_name(scenario_name)
        fixed_criteria = self._enforce_minimum_distance(fixed_criteria, scenario_type, actor_type)
        self.logger.debug(f"Enforced minimum distance for {scenario_type} scenario: {fixed_criteria.get('distance_to_ego', {})}")
        
        # Fix 1: Cut-in scenarios - ensure actors spawn ahead, not alongside
        if ('cut_in' in scenario_name or 'lane_change' in scenario_name):
            # Only apply cut-in fixes if it's actually a cut-in/lane change scenario
            # Don't assume adjacent_lane always means cut-in
            
            self.logger.debug(f"Applying cut-in fixes for {actor['id']}")
            
            # Force ahead position for cut-ins
            fixed_criteria['relative_position'] = 'ahead'
            
            # Ensure minimum distance so they're not alongside
            if 'distance_to_ego' in fixed_criteria:
                min_dist = fixed_criteria['distance_to_ego'].get('min', 20)
                max_dist = fixed_criteria['distance_to_ego'].get('max', 60)
                fixed_criteria['distance_to_ego']['min'] = max(min_dist, 25)  # At least 25m ahead
                fixed_criteria['distance_to_ego']['max'] = max(max_dist, 60)  # Up to 60m ahead
            else:
                fixed_criteria['distance_to_ego'] = {'min': 25, 'max': 60}
        
        # Fix 2: Intersection constraint logic - fix contradictory constraints
        if fixed_criteria.get('road_relationship') == 'different_road':
            self.logger.debug(f"Fixing intersection constraints for {actor['id']}")
            
            # Can't have adjacent lane on different road
            if 'lane_relationship' in fixed_criteria:
                self.logger.warning(f"Removing contradictory 'lane_relationship' for different_road actor {actor['id']}")
                del fixed_criteria['lane_relationship']
            
            # For cross-traffic at intersections
            fixed_criteria['is_intersection'] = True
            if 'relative_position' not in fixed_criteria:
                fixed_criteria['relative_position'] = 'perpendicular'  # or 'crossing'
        
        # Fix 3: Pedestrian distance constraints (already handled by enforce_minimum_distance)
        # Keep this for additional pedestrian-specific logic if needed
        
        # Fix 4: Following scenarios - ensure proper distance and same road
        if ('following' in scenario_name or 'brake' in scenario_name or 
            'stop_and_go' in scenario_name or 'slow_leader' in scenario_name):
            
            self.logger.debug(f"Applying following scenario fixes for {actor['id']}")
            
            # Force same road AND same lane for following scenarios
            fixed_criteria['road_relationship'] = 'same_road'
            fixed_criteria['lane_relationship'] = 'same_lane'  # Critical for following scenarios!
            fixed_criteria['relative_position'] = 'ahead'
            
            # Distance already handled by enforce_minimum_distance
        
        # Fix 5: General distance constraints to prevent extreme spawns
        if 'distance_to_ego' in fixed_criteria:
            min_dist = fixed_criteria['distance_to_ego'].get('min', 0)
            max_dist = fixed_criteria['distance_to_ego'].get('max', 1000)
            
            # Cap maximum distance to prevent extreme spawns
            if max_dist > 200:
                self.logger.warning(f"Capping excessive spawn distance for {actor['id']}: {max_dist}m -> 200m")
                fixed_criteria['distance_to_ego']['max'] = 200
            
            # Ensure absolute minimum distance for safety (5m regardless of scenario)
            if min_dist < 5:
                self.logger.warning(f"Enforcing absolute minimum distance of 5m for {actor['id']} (was {min_dist}m)")
                fixed_criteria['distance_to_ego']['min'] = 5
        
        # Log changes if any were made
        if fixed_criteria != criteria:
            changes = [k for k in fixed_criteria if k not in criteria or fixed_criteria[k] != criteria[k]]
            self.logger.info(f"Applied spawn fixes for {actor['id']}: {len(changes)} changes - {changes}")
            self.logger.info(f"  Before: {criteria}")
            self.logger.info(f"  After: {fixed_criteria}")
        else:
            self.logger.debug(f"No spawn fixes needed for {actor['id']}")
        
        return fixed_criteria

    def create_init(self, data: Dict[str, Any]) -> ET.Element:
        """Create Init section with positions and environment"""
        init = ET.Element('Init')
        actions = ET.SubElement(init, 'Actions')
        
        # Global actions (environment)
        global_action = ET.SubElement(actions, 'GlobalAction')
        env_action = ET.SubElement(global_action, 'EnvironmentAction')
        env_action.append(self.create_environment(data.get('weather', 'clear')))
        
        # Decide whether to position actors first (for special lanes) or ego first
        actors_first = self._should_position_actors_first(data)
        
        if actors_first:
            self.logger.info("Using actor-first spawn strategy for special lane types")
            return self._create_init_actors_first(init, actions, data)
        
        # Standard ego-first positioning
        # Ego vehicle position
        ego_private = ET.SubElement(actions, 'Private')
        ego_private.set('entityRef', 'hero')
        
        ego_action = ET.SubElement(ego_private, 'PrivateAction')
        teleport = ET.SubElement(ego_action, 'TeleportAction')
        position = ET.SubElement(teleport, 'Position')
        world_pos = ET.SubElement(position, 'WorldPosition')
        
        x,y,z,yaw = None, None, None, None
        map_name = self._selected_map or data.get('map_name', 'Town01')
        
        if 'ego_spawn' in data:
            crit = data['ego_spawn'].get('criteria', {}).copy()  # Make a copy to avoid modifying original
            
            # Check if this is a multi-actor scenario with lane changes
            actors_count = len(data.get('actors', []))
            has_lane_change = any(action.get('action_type') == 'lane_change' for action in data.get('actions', []))
            
            # For multi-actor scenarios with lane changes, enforce multiple lanes in same direction
            if actors_count > 1 and has_lane_change:
                if 'min_lanes_same_direction' not in crit:
                    crit['min_lanes_same_direction'] = 2  # Require at least 2 lanes in same direction
                    self.logger.info(f"Multi-actor lane change scenario: requiring minimum 2 lanes in same direction")
            
            # No longer forcing highway road context - cut-in scenarios can work on any road type
            # Allow the scenario to use whatever road_context is specified in the JSON
            
            x,y,z,yaw = self._choose_strategic_ego_spawn(data, map_name, crit)
            meta = self._last_pick
            if meta:
                self._ego_lane = (meta.get('road_id'), meta.get('lane_id'))
                self._ego_spawn_info = meta  # Store ego spawn info for logging
            self._ego_pos = (x, y, z, yaw)
        else:
            x,y,z,yaw = self.parse_position(data['ego_start_position'], map_name)
            self._ego_pos  = (x, y, z, yaw)
            # Infer ego's road and lane from coordinates using spawn metadata
            self._ego_lane = self._infer_road_lane_from_position(x, y, map_name)
            self._ego_spawn_info = {'road_id': self._ego_lane[0], 'lane_id': self._ego_lane[1]} if self._ego_lane else {}   
        
        world_pos.set('x', str(x))
        world_pos.set('y', str(y))
        world_pos.set('z', str(z))
        world_pos.set('h', str(yaw))
        
        # Controller assignment
        ctrl_action = ET.SubElement(ego_private, 'PrivateAction')
        ctrl = ET.SubElement(ctrl_action, 'ControllerAction')
        assign = ET.SubElement(ctrl, 'AssignControllerAction')
        controller = ET.SubElement(assign, 'Controller')
        controller.set('name', 'HeroAgent')
        ctrl_props = ET.SubElement(controller, 'Properties')
        ctrl_prop = ET.SubElement(ctrl_props, 'Property')
        ctrl_prop.set('name', 'module')
        ctrl_prop.set('value', 'external_control')
        
        override = ET.SubElement(ctrl, 'OverrideControllerValueAction')
        for control in ['Throttle', 'Brake', 'Clutch', 'ParkingBrake', 'SteeringWheel', 'Gear']:
            elem = ET.SubElement(override, control)
            if control == 'Gear':
                elem.set('number', '0')
            else:
                elem.set('value', '0')
            elem.set('active', 'false')
        
        # Add initial speed action for ego if start speed is specified
        ego_start_speed = data.get('ego_start_speed', 0)
        if ego_start_speed > 0:
            speed_action = ET.SubElement(ego_private, 'PrivateAction')
            long_action = ET.SubElement(speed_action, 'LongitudinalAction')
            speed_elem = ET.SubElement(long_action, 'SpeedAction')
            dynamics = ET.SubElement(speed_elem, 'SpeedActionDynamics')
            dynamics.set('dynamicsDimension', 'time')
            dynamics.set('dynamicsShape', 'linear')  # Use linear ramp instead of step
            dynamics.set('value', '3.0')  # Take 3 seconds to reach target speed
            target = ET.SubElement(speed_elem, 'SpeedActionTarget')
            ET.SubElement(target, 'AbsoluteTargetSpeed', {'value': str(ego_start_speed)})
        
        # Other actors positions
        actor_spawns = []
        for actor in data.get('actors', []):
            private = ET.SubElement(actions, 'Private')
            private.set('entityRef', actor['id'])
            
            action = ET.SubElement(private, 'PrivateAction')
            teleport = ET.SubElement(action, 'TeleportAction')
            position = ET.SubElement(teleport, 'Position')
            world_pos = ET.SubElement(position, 'WorldPosition')
    
            if 'spawn' in actor:
                crit = actor['spawn'].get('criteria', {})
                # Apply fixes before spawning
                crit = self._fix_spawn_criteria(crit, actor, data)
                ax, ay, az, ayaw = self._choose_spawn(
                    map_name, crit,
                    ego_pos=self._ego_pos,
                    ego_lane=self._ego_lane
                )
            else:
                ax, ay, az, ayaw = self.parse_position(actor['start_position'], map_name)
            
            # For pedestrians on sidewalks, orient perpendicular to road for crossing
            if actor.get('type') == 'pedestrian':
                # Check if pedestrian has a speed action (indicating movement)
                has_movement = False
                for action in data.get('actions', []):
                    if (action.get('actor_id') == actor['id'] and 
                        action.get('action_type') in ['speed'] and
                        action.get('speed_value', 0) > 0):
                        has_movement = True
                        break
                
                # If pedestrian will move and is on a sidewalk, orient perpendicular to road
                if has_movement and self._last_pick and self._last_pick.get('lane_type') == 'Sidewalk':
                    original_yaw = ayaw  # Store original sidewalk direction
                    
                    # If ego is positioned, use it to determine crossing direction
                    if self._ego_pos:
                        ego_x, ego_y = self._ego_pos[0], self._ego_pos[1]
                        
                        # Calculate if ego is to the left or right of the pedestrian's forward direction
                        forward_x = math.cos(original_yaw)
                        forward_y = math.sin(original_yaw)
                        to_ego_x = ego_x - ax
                        to_ego_y = ego_y - ay
                        
                        # Cross product to determine which side ego is on
                        cross = forward_x * to_ego_y - forward_y * to_ego_x
                        
                        # Turn toward the side where the road is (where ego is)
                        if cross > 0:
                            # Ego is to the left, turn left (add 90 degrees)
                            test_yaw = original_yaw + math.pi/2
                        else:
                            # Ego is to the right, turn right (subtract 90 degrees)
                            test_yaw = original_yaw - math.pi/2
                        
                        # Verify this faces toward the road, not away from it
                        # Check if the new direction points generally toward the ego
                        test_forward_x = math.cos(test_yaw)
                        test_forward_y = math.sin(test_yaw)
                        dot_to_ego = test_forward_x * to_ego_x + test_forward_y * to_ego_y
                        
                        if dot_to_ego < 0:
                            # Facing away from road, flip 180 degrees
                            ayaw = test_yaw + math.pi
                            self.logger.info(f"Flipped pedestrian direction to face toward road")
                        else:
                            ayaw = test_yaw
                        
                        self.logger.info(f"Rotated pedestrian {actor['id']} perpendicular to road for crossing (from {math.degrees(original_yaw):.1f}° to {math.degrees(ayaw):.1f}°)")
                    else:
                        # Fallback: rotate 90 degrees from sidewalk direction
                        ayaw = original_yaw + math.pi/2
                        self.logger.info(f"Rotated pedestrian {actor['id']} by 90° (ego position unknown)")
            
            world_pos.set('x', str(ax))
            world_pos.set('y', str(ay))
            world_pos.set('z', str(az))
            world_pos.set('h', str(ayaw))
            
            # Collect spawn data for debugging
            spawn_info = self._last_pick or {}
            actor_spawns.append({
                'actor_name': actor['id'],
                'spawn': {
                    'x': ax, 'y': ay, 'z': az, 'yaw': ayaw,
                    'road_id': spawn_info.get('road_id'),
                    'lane_id': spawn_info.get('lane_id')
                }
            })
        
        # Log spawn details for debugging
        if self.logger.level <= logging.INFO:  # Only if INFO level or below
            ego_spawn_info = getattr(self, '_ego_spawn_info', {})
            ego_spawn = {
                'x': x, 'y': y, 'z': z, 'yaw': yaw,
                'road_id': ego_spawn_info.get('road_id'),
                'lane_id': ego_spawn_info.get('lane_id')
            }
            self.log_spawn_details(ego_spawn, actor_spawns)
        
        return init
    
    def _should_position_actors_first(self, data: Dict[str, Any]) -> bool:
        """Determine if we should position actors before ego for better special lane utilization"""
        # Check if any actor needs special lanes (shoulder, parking, sidewalk, etc.)
        special_lane_types = ['Shoulder', 'Parking', 'Sidewalk', 'Biking', 'Emergency']
        
        for actor in data.get('actors', []):
            if 'spawn' in actor:
                criteria = actor['spawn'].get('criteria', {})
                lane_type = criteria.get('lane_type')
                if lane_type:
                    # Check if it's a special lane type
                    if isinstance(lane_type, list):
                        if any(lt in special_lane_types for lt in lane_type):
                            return True
                    elif lane_type in special_lane_types:
                        return True
        
        return False
    
    def _create_init_actors_first(self, init: ET.Element, actions: ET.Element, data: Dict[str, Any]) -> ET.Element:
        """Create init with actors positioned first, then ego relative to them"""
        map_name = self._selected_map or data.get('map_name', 'Town01')
        
        # First, position actors with special lane requirements
        actor_positions = {}
        special_actor = None
        
        for actor in data.get('actors', []):
            if 'spawn' in actor and not special_actor:
                criteria = actor['spawn'].get('criteria', {})
                lane_type = criteria.get('lane_type')
                special_lane_types = ['Shoulder', 'Parking', 'Sidewalk', 'Biking', 'Emergency']
                
                is_special = False
                if lane_type:
                    if isinstance(lane_type, list):
                        is_special = any(lt in special_lane_types for lt in lane_type)
                    else:
                        is_special = lane_type in special_lane_types
                
                if is_special:
                    # Position this actor first
                    special_actor = actor
                    # Remove distance_to_ego constraint since ego isn't positioned yet
                    clean_criteria = criteria.copy()
                    clean_criteria.pop('distance_to_ego', None)
                    clean_criteria.pop('relative_position', None)
                    clean_criteria.pop('road_relationship', None)
                    
                    ax, ay, az, ayaw = self._choose_spawn(map_name, clean_criteria)
                    actor_positions[actor['id']] = (ax, ay, az, ayaw)
                    
                    # Store actor spawn info
                    self._actor_spawn_info = self._last_pick
                    actor_road = self._last_pick.get('road_id') if self._last_pick else None
                    actor_lane = self._last_pick.get('lane_id') if self._last_pick else None
                    
                    self.logger.info(f"Positioned {actor['id']} first on {lane_type} lane at ({ax:.1f}, {ay:.1f})")
                    break
        
        # Now position ego relative to the special actor
        if special_actor and special_actor['id'] in actor_positions:
            actor_pos = actor_positions[special_actor['id']]
            ego_criteria = data.get('ego_spawn', {}).get('criteria', {}).copy()
            
            # Check if this is a multi-actor scenario with lane changes
            actors_count = len(data.get('actors', []))
            has_lane_change = any(action.get('action_type') == 'lane_change' for action in data.get('actions', []))
            
            # For multi-actor scenarios with lane changes, enforce multiple lanes in same direction
            if actors_count > 1 and has_lane_change:
                if 'min_lanes_same_direction' not in crit:
                    crit['min_lanes_same_direction'] = 2  # Require at least 2 lanes in same direction
                    self.logger.info(f"Multi-actor lane change scenario: requiring minimum 2 lanes in same direction")
            
            # No longer forcing highway road context - cut-in scenarios can work on any road type
            # Allow the scenario to use whatever road_context is specified in the JSON
            
            # Modify ego criteria to be relative to actor
            if 'spawn' in special_actor:
                actor_spawn_criteria = special_actor['spawn'].get('criteria', {})
                desired_distance = actor_spawn_criteria.get('distance_to_ego', {})
                
                # Find ego position near the actor
                ego_criteria_modified = ego_criteria.copy()
                # Remove constraints that might conflict
                ego_criteria_modified.pop('is_intersection', None)
                
                # Try to position ego at desired distance from actor
                if desired_distance:
                    min_dist = desired_distance.get('min', 10)
                    max_dist = desired_distance.get('max', 50)
                    target_dist = (min_dist + max_dist) / 2
                    
                    # Find driving lanes near the actor
                    all_spawns = self._get_spawn_points_for_map(map_name)
                    driving_spawns = [s for s in all_spawns if s.get('lane_type') == 'Driving']
                    
                    # Filter by distance to actor
                    import math
                    suitable_ego_spawns = []
                    for spawn in driving_spawns:
                        dist = math.hypot(spawn['x'] - actor_pos[0], spawn['y'] - actor_pos[1])
                        if min_dist <= dist <= max_dist * 1.5:  # Allow some flexibility
                            suitable_ego_spawns.append((dist, spawn))
                    
                    if suitable_ego_spawns:
                        # Sort by distance and pick one close to target
                        suitable_ego_spawns.sort(key=lambda x: abs(x[0] - target_dist))
                        best_spawn = suitable_ego_spawns[0][1]
                        
                        x, y, z = best_spawn['x'], best_spawn['y'], best_spawn.get('z', 0.5)
                        yaw = math.radians(best_spawn.get('yaw', 0))
                        
                        self._ego_pos = (x, y, z, yaw)
                        self._ego_lane = (best_spawn.get('road_id'), best_spawn.get('lane_id'))
                        self.logger.info(f"Positioned ego at ({x:.1f}, {y:.1f}) relative to actor")
                    else:
                        # Fallback to standard ego positioning
                        x, y, z, yaw = self._choose_strategic_ego_spawn(data, map_name, ego_criteria)
                        self._ego_pos = (x, y, z, yaw)
                else:
                    x, y, z, yaw = self._choose_strategic_ego_spawn(data, map_name, ego_criteria)
                    self._ego_pos = (x, y, z, yaw)
            else:
                x, y, z, yaw = self._choose_strategic_ego_spawn(data, map_name, ego_criteria)
                self._ego_pos = (x, y, z, yaw)
        else:
            # No special actors, use standard positioning
            if 'ego_spawn' in data:
                crit = data['ego_spawn'].get('criteria', {}).copy()
                
                # Check if this is a multi-actor scenario with lane changes
                actors_count = len(data.get('actors', []))
                has_lane_change = any(action.get('action_type') == 'lane_change' for action in data.get('actions', []))
                
                # No longer forcing highway road context - cut-in scenarios can work on any road type
                # Allow the scenario to use whatever road_context is specified in the JSON
                
                x, y, z, yaw = self._choose_strategic_ego_spawn(data, map_name, crit)
                self._ego_pos = (x, y, z, yaw)
            else:
                x, y, z, yaw = self.parse_position(data['ego_start_position'], map_name)
                self._ego_pos = (x, y, z, yaw)
        
        # Create ego position element
        ego_private = ET.SubElement(actions, 'Private')
        ego_private.set('entityRef', 'hero')
        ego_action = ET.SubElement(ego_private, 'PrivateAction')
        teleport = ET.SubElement(ego_action, 'TeleportAction')
        position = ET.SubElement(teleport, 'Position')
        world_pos = ET.SubElement(position, 'WorldPosition')
        world_pos.set('x', str(self._ego_pos[0]))
        world_pos.set('y', str(self._ego_pos[1]))
        world_pos.set('z', str(self._ego_pos[2]))
        world_pos.set('h', str(self._ego_pos[3]))
        
        # Add ego controller and speed
        ctrl_action = ET.SubElement(ego_private, 'PrivateAction')
        ctrl = ET.SubElement(ctrl_action, 'ControllerAction')
        assign = ET.SubElement(ctrl, 'AssignControllerAction')
        controller = ET.SubElement(assign, 'Controller')
        controller.set('name', 'HeroAgent')
        ctrl_props = ET.SubElement(controller, 'Properties')
        ctrl_prop = ET.SubElement(ctrl_props, 'Property')
        ctrl_prop.set('name', 'module')
        ctrl_prop.set('value', 'external_control')
        
        override = ET.SubElement(ctrl, 'OverrideControllerValueAction')
        for control in ['Throttle', 'Brake', 'Clutch', 'ParkingBrake', 'SteeringWheel', 'Gear']:
            elem = ET.SubElement(override, control)
            if control == 'Gear':
                elem.set('number', '0')
            else:
                elem.set('value', '0')
            elem.set('active', 'false')
        
        # Add initial speed for ego
        ego_start_speed = data.get('ego_start_speed', 0)
        if ego_start_speed > 0:
            speed_action = ET.SubElement(ego_private, 'PrivateAction')
            long_action = ET.SubElement(speed_action, 'LongitudinalAction')
            speed_elem = ET.SubElement(long_action, 'SpeedAction')
            dynamics = ET.SubElement(speed_elem, 'SpeedActionDynamics')
            dynamics.set('dynamicsDimension', 'time')
            dynamics.set('dynamicsShape', 'linear')  # Use linear ramp instead of step
            dynamics.set('value', '3.0')  # Take 3 seconds to reach target speed
            target = ET.SubElement(speed_elem, 'SpeedActionTarget')
            ET.SubElement(target, 'AbsoluteTargetSpeed', {'value': str(ego_start_speed)})
        
        # Position remaining actors
        for actor in data.get('actors', []):
            if actor['id'] in actor_positions:
                # Already positioned
                ax, ay, az, ayaw = actor_positions[actor['id']]
            else:
                # Position relative to ego
                if 'spawn' in actor:
                    crit = actor['spawn'].get('criteria', {})
                    crit = self._fix_spawn_criteria(crit, actor, data)
                    ax, ay, az, ayaw = self._choose_spawn(
                        map_name, crit,
                        ego_pos=self._ego_pos,
                        ego_lane=self._ego_lane
                    )
                else:
                    ax, ay, az, ayaw = self.parse_position(actor['start_position'], map_name)
                
                actor_positions[actor['id']] = (ax, ay, az, ayaw)
            
            # For pedestrians on sidewalks, orient them perpendicular to road for crossing
            if actor.get('type') == 'pedestrian':
                # Check if pedestrian has a speed action (indicating movement)
                has_movement = False
                for action_item in data.get('actions', []):
                    if (action_item.get('actor_id') == actor['id'] and 
                        action_item.get('action_type') in ['speed'] and
                        action_item.get('speed_value', 0) > 0):
                        has_movement = True
                        break
                
                # If pedestrian will move and is on a sidewalk, orient perpendicular to road
                if has_movement:
                    # Check if on sidewalk (need to get spawn info)
                    is_sidewalk = False
                    original_yaw = ayaw  # Store original sidewalk direction
                    if 'spawn' in actor:
                        lane_type = actor['spawn'].get('criteria', {}).get('lane_type')
                        is_sidewalk = lane_type == 'Sidewalk'
                    
                    if is_sidewalk:
                        # The original yaw is along the sidewalk/road direction
                        # To cross the road, rotate 90 degrees perpendicular
                        # We need to determine which way to turn (left or right)
                        
                        # If ego is positioned, use it to determine crossing direction
                        if self._ego_pos:
                            ego_x, ego_y = self._ego_pos[0], self._ego_pos[1]
                            
                            # Calculate if ego is to the left or right of the pedestrian's forward direction
                            # Using cross product to determine side
                            forward_x = math.cos(original_yaw)
                            forward_y = math.sin(original_yaw)
                            to_ego_x = ego_x - ax
                            to_ego_y = ego_y - ay
                            
                            # Cross product to determine which side ego is on
                            cross = forward_x * to_ego_y - forward_y * to_ego_x
                            
                            # Turn toward the side where the road is (where ego is)
                            if cross > 0:
                                # Ego is to the left, turn left (add 90 degrees)
                                test_yaw = original_yaw + math.pi/2
                            else:
                                # Ego is to the right, turn right (subtract 90 degrees)
                                test_yaw = original_yaw - math.pi/2
                            
                            # Verify this faces toward the road, not away from it
                            # Check if the new direction points generally toward the ego
                            test_forward_x = math.cos(test_yaw)
                            test_forward_y = math.sin(test_yaw)
                            dot_to_ego = test_forward_x * to_ego_x + test_forward_y * to_ego_y
                            
                            if dot_to_ego < 0:
                                # Facing away from road, flip 180 degrees
                                ayaw = test_yaw + math.pi
                                self.logger.info(f"Flipped pedestrian direction to face toward road")
                            else:
                                ayaw = test_yaw
                            
                            self.logger.info(f"Rotated pedestrian {actor['id']} perpendicular to road for crossing (from {math.degrees(original_yaw):.1f}° to {math.degrees(ayaw):.1f}°)")
                        else:
                            # No ego position, just turn 90 degrees (default to right)
                            ayaw = original_yaw - math.pi/2
                            self.logger.info(f"Rotated pedestrian {actor['id']} 90° for road crossing")
            
            # Create actor position element
            private = ET.SubElement(actions, 'Private')
            private.set('entityRef', actor['id'])
            action = ET.SubElement(private, 'PrivateAction')
            teleport = ET.SubElement(action, 'TeleportAction')
            position = ET.SubElement(teleport, 'Position')
            world_pos = ET.SubElement(position, 'WorldPosition')
            world_pos.set('x', str(ax))
            world_pos.set('y', str(ay))
            world_pos.set('z', str(az))
            world_pos.set('h', str(ayaw))
        
        return init
    
    def create_storyboard(self, data: Dict[str, Any]) -> ET.Element:
        """Create Storyboard with Init + one Story/Act + ManeuverGroups + valid StopTrigger"""
        sb = ET.Element('Storyboard')
        sb.append(self.create_init(data))

        # --- one Story with one Act ---
        story = ET.SubElement(sb, 'Story', {'name': 'MyStory'})
        act   = ET.SubElement(story, 'Act',   {'name': 'Behavior'})

        # group actions by actor
        actor_groups: Dict[str, List[Dict[str,Any]]] = {}
        for action in data.get('actions', []):
            actor_groups.setdefault(action['actor_id'], []).append(action)

        for actor_id, actions in actor_groups.items():
            # Add a final wait action to keep the scenario running if timeout is specified
            if 'timeout' in data and data['timeout'] > 0:
                # Find the last action's trigger time and speed
                last_trigger_time = 0
                last_speed = 0
                for action in actions:
                    if action.get('trigger_type') == 'time':
                        trigger_time = action.get('trigger_value', 0)
                        # Add action duration if it's a speed action
                        if action.get('action_type') in ['speed', 'stop']:
                            trigger_time += action.get('dynamics_value', 2.0)
                            # Track the last speed value
                            if action.get('action_type') == 'speed':
                                last_speed = action.get('speed_value', 0)
                            elif action.get('action_type') == 'stop':
                                last_speed = 0
                        last_trigger_time = max(last_trigger_time, trigger_time)
                
                # Add a wait action that triggers immediately after the last action
                # This keeps the actor at constant speed until timeout
                wait_trigger_time = last_trigger_time + 0.1  # Start right after last action
                if wait_trigger_time < data['timeout'] - 2:
                    wait_action = {
                        'actor_id': actor_id,
                        'action_type': 'wait',
                        'trigger_type': 'time',
                        'trigger_value': wait_trigger_time,
                        'wait_duration': data['timeout'] - wait_trigger_time - 2,  # Wait until almost timeout
                        'maintain_speed': last_speed  # Store the speed to maintain
                    }
                    actions.append(wait_action)
                    self.logger.info(f"Added wait action for {actor_id} at {wait_trigger_time}s to maintain speed {last_speed} m/s")
            
            mg = ET.SubElement(act, 'ManeuverGroup', {
                'maximumExecutionCount': '1',
                'name':                  f'{actor_id}ManeuverGroup'
            })
            actors = ET.SubElement(mg, 'Actors', {
                'selectTriggeringEntities': 'false'
            })
            ET.SubElement(actors, 'EntityRef', {
                'entityRef': 'hero' if actor_id=='ego' else actor_id
            })

            man = ET.SubElement(mg, 'Maneuver', {
                'name': f'{actor_id}Maneuver'
            })

            # iterate and chain events
            for i, action in enumerate(actions):
                # Check for bicycle lane change incompatibility
                atype = action['action_type']
                if atype == 'lane_change':
                    # Find the actor model to check if it's a bicycle
                    actor_model = None
                    for actor in data.get('actors', []):
                        if actor['id'] == actor_id:
                            actor_model = actor['model']
                            break
                    
                    # Prevent bicycles from doing lane changes
                    if actor_model in BICYCLE_MODELS:
                        self.logger.warning(f"Skipping lane_change action for bicycle {actor_id} ({actor_model}) - not supported")
                        continue  # Skip this action entirely
                
                ev_name = f"{actor_id}Event{i}"
                ac_name = f"{actor_id}Action{i}"

                ev = ET.SubElement(man, 'Event', {
                    'name':     ev_name,
                    'priority': 'overwrite'
                })
                ac = ET.SubElement(ev, 'Action', {'name': ac_name})
                pa = ET.SubElement(ac, 'PrivateAction')

                # --- build the PrivateAction body ---
                if atype == 'wait':
                    # Implement wait as maintaining a specific absolute speed for a duration
                    la = ET.SubElement(pa, 'LongitudinalAction')
                    sa = ET.SubElement(la, 'SpeedAction')
                    
                    # Wait duration with minimum
                    wait_duration = max(action.get('wait_duration', 2.0), 0.5)  # Minimum 0.5 seconds
                    
                    # Get the speed to maintain (from the last speed action)
                    maintain_speed = action.get('maintain_speed', 0)
                    
                    ET.SubElement(sa, 'SpeedActionDynamics', {
                        'dynamicsDimension': 'time',
                        'dynamicsShape':     'step',  # Instant to target speed (already at speed)
                        'value':             str(wait_duration)  # Continue for the full wait duration
                    })
                    tgt = ET.SubElement(sa, 'SpeedActionTarget')
                    # Use AbsoluteTargetSpeed to maintain specific speed
                    ET.SubElement(tgt, 'AbsoluteTargetSpeed', {
                        'value': str(maintain_speed)
                    })

                elif atype in ('speed','stop'):
                    la = ET.SubElement(pa, 'LongitudinalAction')
                    sa = ET.SubElement(la, 'SpeedAction')
                    speed_val = 0 if atype=='stop' else action.get('speed_value',0)
                    
                    # Ensure minimum duration for sequential timing
                    dynamics_value = action.get('dynamics_value', 2.0)
                    dynamics_dimension = action.get('dynamics_dimension', 'time')
                    dynamics_shape = action.get('dynamics_shape', 'linear')  # Changed from 'step' for smoother transitions
                    
                    # Apply minimum durations to prevent instant completion
                    if dynamics_dimension == 'time' and dynamics_value < 0.5:
                        dynamics_value = 0.5  # Minimum 0.5 seconds
                    
                    ET.SubElement(sa, 'SpeedActionDynamics', {
                        'dynamicsDimension': dynamics_dimension,
                        'dynamicsShape':     dynamics_shape,
                        'value':             str(dynamics_value)
                    })
                    tgt = ET.SubElement(sa, 'SpeedActionTarget')
                    ET.SubElement(tgt, 'AbsoluteTargetSpeed', {'value': str(speed_val)})
                elif atype == 'brake':
                    la = ET.SubElement(pa, 'LongitudinalAction')
                    sa = ET.SubElement(la, 'SpeedAction')
                    ET.SubElement(sa, 'SpeedActionDynamics', {
                        'dynamicsDimension': action.get('dynamics_dimension','time'),
                        'dynamicsShape':     action.get('dynamics_shape','step'),
                        'value':             str(action.get('dynamics_value',1))
                    })
                    tgt = ET.SubElement(sa, 'SpeedActionTarget')
                    # Convert brake_force to speed reduction
                    brake_force = action.get('brake_force', 0.5)
                    target_speed = max(0, 5 * (1 - brake_force))  # Simple conversion
                    ET.SubElement(tgt, 'AbsoluteTargetSpeed', {'value': str(target_speed)})
                elif atype == 'lane_change':
                    la = ET.SubElement(pa, 'LateralAction')
                    lc = ET.SubElement(la, 'LaneChangeAction')
                    
                    # Use distance-based dynamics for lane changes instead of time
                    dynamics_value = action.get('dynamics_value', 20.0)  # Default 20 meters
                    dynamics_dimension = 'distance'  # Always use distance
                    dynamics_shape = action.get('dynamics_shape', 'linear')
                    
                    # Apply minimum distance for safe lane changes
                    if dynamics_value < 15.0:
                        dynamics_value = 15.0  # Minimum 15 meters for lane change
                    
                    ET.SubElement(lc, 'LaneChangeActionDynamics', {
                        'dynamicsDimension': dynamics_dimension,
                        'dynamicsShape':     dynamics_shape,
                        'value':            str(dynamics_value)
                    })
                    tgt = ET.SubElement(lc, 'LaneChangeTarget')
                    # Use RelativeTargetLane with ego as reference
                    # value=0: same lane as ego
                    # value=1: one lane to the right of ego
                    # value=-1: one lane to the left of ego
                    
                    # Check if we have target_lane (numeric) - preferred
                    if 'target_lane' in action:
                        lane_value = action.get('target_lane')
                    # Fallback to lane_direction for backward compatibility
                    elif 'lane_direction' in action:
                        direction = action.get('lane_direction')
                        if direction == 'left':
                            lane_value = -1
                        elif direction == 'right':
                            lane_value = 1
                        elif direction == 'ego_lane' or direction == 'same':
                            lane_value = 0
                        else:
                            lane_value = 1  # Default to right
                    else:
                        # Default for cut-in scenarios
                        lane_value = 0
                    
                    # For lane changes, we need to be smart about the reference entity
                    # Check if this actor was spawned in same lane as ego
                    actor_lane_relationship = None
                    for actor in data.get('actors', []):
                        if actor['id'] == actor_id:
                            spawn_criteria = actor.get('spawn', {}).get('criteria', {})
                            actor_lane_relationship = spawn_criteria.get('lane_relationship', '')
                            break
                    
                    # Determine the best reference entity and adjust lane value if needed
                    if actor_lane_relationship in ['same_lane', 'my_lane']:
                        # Actor is in same lane as ego
                        # Use actor itself as reference to avoid trying to move to ego's position
                        reference_entity = actor_id
                        # If target is 0 (ego's lane), that doesn't make sense - default to moving left
                        if lane_value == 0:
                            lane_value = -1  # Move left for overtaking
                    elif actor_lane_relationship == 'adjacent_lane':
                        # Actor is in adjacent lane
                        # Can use ego as reference for cut-in (lane_value = 0) or moving away
                        reference_entity = 'hero'
                        # lane_value stays as specified
                    else:
                        # Default case - use ego as reference
                        reference_entity = 'hero'
                    
                    ET.SubElement(tgt, 'RelativeTargetLane', {
                        'entityRef': reference_entity,
                        'value':     str(lane_value)
                    })

                # --- StartTrigger under this Event ---
                st = ET.SubElement(ev, 'StartTrigger')
                cg = ET.SubElement(st, 'ConditionGroup')
                cond = ET.SubElement(cg, 'Condition', {
                    'name':         f'StartCondition{i}',
                    'delay':        '0',
                    'conditionEdge':'rising'
                })

                ttype = action['trigger_type']
                if ttype=='time':
                    bv = ET.SubElement(cond, 'ByValueCondition')
                    ET.SubElement(bv, 'SimulationTimeCondition', {
                        'value': str(action.get('trigger_value',0)),
                        'rule':  'greaterThan'
                    })

                elif ttype=='distance_to_ego':
                    be = ET.SubElement(cond, 'ByEntityCondition')
                    te = ET.SubElement(be, 'TriggeringEntities', {
                        'triggeringEntitiesRule':'any'
                    })
                    ET.SubElement(te, 'EntityRef', {'entityRef':'hero'})
                    ec = ET.SubElement(be, 'EntityCondition')
                    ET.SubElement(ec, 'RelativeDistanceCondition', {
                        'entityRef':            actor_id,
                        'relativeDistanceType': 'longitudinal',
                        'value':                str(action.get('trigger_value',10)),
                        'freespace':            'false',
                        'rule':                 {'<':'lessThan','>':'greaterThan'}.get(
                                                action.get('trigger_comparison','<'),
                                                'lessThan')
                    })

                elif ttype=='after_previous':
                    # chain on previous action completion with small delay
                    prev_ref = f"{actor_id}Action{i-1}"
                    
                    # Add small delay to prevent immediate firing after previous action
                    trigger_delay = str(action.get('delay', 0.2))  # 200ms default delay
                    cond.set('delay', trigger_delay)
                    
                    bv = ET.SubElement(cond, 'ByValueCondition')
                    ET.SubElement(bv, 'StoryboardElementStateCondition', {
                        'storyboardElementType': 'action',
                        'storyboardElementRef':  prev_ref,
                        'state':                 'completeState'
                    })

        # --- Act-level StartTrigger: Wait for ego movement ---
        ast = ET.SubElement(act, 'StartTrigger')
        acg = ET.SubElement(ast, 'ConditionGroup')
        aco = ET.SubElement(acg, 'Condition', {
            'name': 'OverallStartCondition',
            'delay': '0.5',  # Small delay to ensure ego is ready
            'conditionEdge': 'rising'
        })
        
        # Wait for ego to start moving (speed > 1 m/s)
        be = ET.SubElement(aco, 'ByEntityCondition')
        te = ET.SubElement(be, 'TriggeringEntities', {
            'triggeringEntitiesRule': 'any'
        })
        ET.SubElement(te, 'EntityRef', {'entityRef': 'hero'})
        ec = ET.SubElement(be, 'EntityCondition')
        ET.SubElement(ec, 'SpeedCondition', {
            'value': '1.0',
            'rule': 'greaterThan'
        })

        # --- Act-level StopTrigger: use timeout if specified, otherwise driven distance ---
        astp = ET.SubElement(act, 'StopTrigger')
        scg  = ET.SubElement(astp, 'ConditionGroup')
        
        # If timeout is specified, use that as the primary stop condition
        if 'timeout' in data and data['timeout'] > 0:
            # Use simulation time for Act stop
            sco = ET.SubElement(scg, 'Condition', {
                'name':'TimeLimit','delay':'0','conditionEdge':'rising'
            })
            bvc = ET.SubElement(sco, 'ByValueCondition')
            stc = ET.SubElement(bvc, 'SimulationTimeCondition')
            stc.set('value', str(data['timeout']))
            stc.set('rule', 'greaterThan')
        else:
            # Use driven distance as before
            sco  = ET.SubElement(scg, 'Condition', {
                'name':'EndCondition','delay':'0','conditionEdge':'rising'
            })
            be   = ET.SubElement(sco, 'ByEntityCondition')
            te   = ET.SubElement(be, 'TriggeringEntities', {'triggeringEntitiesRule':'any'})
            ET.SubElement(te, 'EntityRef', {'entityRef':'hero'})
            ec   = ET.SubElement(be, 'EntityCondition')
            ET.SubElement(ec, 'TraveledDistanceCondition', {
                'value': str(data.get('success_distance', 100)),
            })

        # --- Storyboard-level StopTrigger: timeout + collision ---
        sbt = ET.SubElement(sb, 'StopTrigger')
        scg2 = ET.SubElement(sbt, 'ConditionGroup')
        # Add criteria conditions

        # Only include essential criteria that work reliably with ScenarioRunner
        criteria = ['DrivenDistanceTest']  # Only keep the distance-based success criterion
        
        # Add collision test only if explicitly allowed in scenario
        if not data.get('collision_allowed', True):  # If collisions are NOT allowed
            criteria.append('CollisionTest')
        
        # Add timeout condition if specified
        if 'timeout' in data and data['timeout'] > 0:
            criteria.append('Timeout')
        
        for criterion in criteria:
            crit_cond = ET.SubElement(scg2, 'Condition')
            crit_cond.set('name', f'criteria_{criterion}')
            crit_cond.set('delay', '0')
            crit_cond.set('conditionEdge', 'rising')
            crit_by_value = ET.SubElement(crit_cond, 'ByValueCondition')
            
            if criterion == 'DrivenDistanceTest':
                # Distance-based success criterion - scenario succeeds when ego travels this distance
                param_cond = ET.SubElement(crit_by_value, 'ParameterCondition')
                param_cond.set('parameterRef', 'distance_success')
                param_cond.set('value', str(data.get('success_distance', 200)))
                param_cond.set('rule', 'greaterThan')  # Changed to greaterThan for success condition
            elif criterion == 'CollisionTest':
                # Collision test - scenario fails if collision occurs
                param_cond = ET.SubElement(crit_by_value, 'ParameterCondition')
                param_cond.set('parameterRef', 'collision_count')
                param_cond.set('value', '0')  # No collisions allowed
                param_cond.set('rule', 'greaterThan')  # Fails if collision_count > 0
            elif criterion == 'Timeout':
                # Timeout condition - scenario ends after specified time
                sim_time_cond = ET.SubElement(crit_by_value, 'SimulationTimeCondition')
                sim_time_cond.set('value', str(data.get('timeout', 60)))
                sim_time_cond.set('rule', 'greaterThan')

        return sb


    def _choose_spawn(self, map_name: str, crit: Dict[str, Any],
                    ego_pos: Optional[Tuple[float, float, float, float]] = None,
                    ego_lane: Optional[Tuple[int, int]] = None) -> Tuple[float, float, float, float]:
        """Return a spawn (x,y,z,yaw) that meets the criteria - use validated enhanced spawn points"""
        # Use enhanced spawn files which have been validated to be on actual roads
        pts = self._get_spawn_points_for_map(map_name)
        if not pts:
            self.logger.error(f"No enhanced spawn data available for map {map_name}")
            raise ValidationError(f"No spawn points available for map {map_name}.")
        
        self.logger.info(f"Using spawn points for {map_name} ({len(pts)} points)")
        
        # Use the legacy spawn selection which picks from actual spawn points
        return self._legacy_choose_spawn(map_name, crit, ego_pos, ego_lane, pts)
    
    def _generate_spawn_from_road_intelligence(self, map_name: str, crit: Dict[str, Any], 
                                              ego_pos: Optional[Tuple[float, float, float, float]] = None,
                                              ego_lane: Optional[Tuple[int, int]] = None) -> Tuple[float, float, float, float]:
        """Generate spawn points directly from road intelligence geometry"""
        
        road_data = self.road_intelligence.get(map_name, {})
        if not road_data or 'roads' not in road_data:
            raise RuntimeError(f"No road intelligence data for {map_name}")
        
        roads = road_data['roads']
        
        # Filter roads by criteria
        candidate_roads = []
        for road_id, road_info in roads.items():
            # Check if road has the required lane type
            if 'lane_type' in crit:
                required_types = crit['lane_type'] if isinstance(crit['lane_type'], list) else [crit['lane_type']]
                lanes = road_info.get('lanes', {})
                
                has_required_lane = False
                for lane_id, lane_info in lanes.items():
                    if lane_info.get('lane_type', '').lower() in [lt.lower() for lt in required_types]:
                        has_required_lane = True
                        break
                
                if not has_required_lane:
                    continue
            
            # Check road context (map between criteria names and road_type values)
            if 'road_context' in crit:
                road_type = road_info.get('road_type', '').lower()
                context = crit['road_context'].lower()
                
                # Map common context names to road types
                context_mapping = {
                    'urban': ['town', 'city', 'urban'],
                    'highway': ['highway', 'motorway', 'freeway'],
                    'rural': ['rural', 'country'],
                    'suburban': ['suburban', 'residential']
                }
                
                # Check if road_type matches the context
                matched = False
                if context in context_mapping:
                    matched = road_type in context_mapping[context]
                else:
                    matched = road_type == context
                
                if not matched:
                    continue
            
            # Check speed limits
            if 'speed_limit' in crit:
                speed = road_info.get('speed_limit') or 0  # Handle None values
                min_speed = crit['speed_limit'].get('min', 0)
                max_speed = crit['speed_limit'].get('max', 1000)
                if not (min_speed <= speed <= max_speed):
                    continue
            
            # Check road relationship
            if ego_lane and crit.get('road_relationship') == 'same_road':
                if int(road_id) != ego_lane[0]:
                    continue
            elif ego_lane and crit.get('road_relationship') == 'different_road':
                if int(road_id) == ego_lane[0]:
                    continue
            
            candidate_roads.append((road_id, road_info))
        
        if not candidate_roads:
            raise RuntimeError(f"No roads match criteria: {crit}")
        
        # Select a road - if relative_position is specified, try to find a suitable road
        selected_road_id = None
        selected_road = None
        
        if ego_pos and 'relative_position' in crit:
            rel_pos = crit['relative_position']
            ego_yaw = ego_pos[3] if len(ego_pos) > 3 else 0
            
            # Try to find a road that would place the spawn in the correct relative position
            best_road = None
            best_score = -1
            
            for road_id, road_info in candidate_roads:
                geometry = road_info.get('geometry', [])
                if not geometry:
                    continue
                    
                # Check middle segment
                geom = geometry[len(geometry) // 2] if len(geometry) > 2 else geometry[0]
                test_x = geom['x'] + geom['length'] / 2 * math.cos(geom['hdg'])
                test_y = geom['y'] + geom['length'] / 2 * math.sin(geom['hdg'])
                
                # Check relative position
                dx, dy = test_x - ego_pos[0], test_y - ego_pos[1]
                forward_dist = dx * math.cos(ego_yaw) + dy * math.sin(ego_yaw)
                test_rel_pos = "ahead" if forward_dist > 0 else "behind"
                
                # Score based on matching relative position and distance
                dist = math.hypot(dx, dy)
                if 'distance_to_ego' in crit:
                    min_dist = crit['distance_to_ego'].get('min', 0)
                    max_dist = crit['distance_to_ego'].get('max', 100)
                    if min_dist <= dist <= max_dist and test_rel_pos == rel_pos:
                        score = 1.0 - abs(dist - (min_dist + max_dist) / 2) / max_dist
                        if score > best_score:
                            best_score = score
                            best_road = (road_id, road_info)
            
            if best_road:
                selected_road_id, selected_road = best_road
        
        # Fallback to deterministic selection if no best road found
        if not selected_road:
            # Sort by road_id for deterministic selection
            candidate_roads.sort(key=lambda x: int(x[0]))
            selected_road_id, selected_road = candidate_roads[0]
        
        # Generate spawn point from road geometry
        geometry = selected_road.get('geometry', [])
        if not geometry:
            raise RuntimeError(f"Road {selected_road_id} has no geometry")
        
        # Select a geometry segment (prefer middle segments for stability)
        if len(geometry) > 2:
            geom = geometry[len(geometry) // 2]  # Middle segment
        else:
            geom = geometry[0]
        
        # Calculate spawn position
        road_x = geom['x']
        road_y = geom['y']
        road_hdg = geom['hdg']  # heading in radians
        road_length = geom['length']
        
        # Sample a point along the road considering relative position
        if ego_pos and 'distance_to_ego' in crit:
            # Try to place at desired distance from ego
            target_dist = (crit['distance_to_ego']['min'] + crit['distance_to_ego']['max']) / 2
            
            # Calculate best position along road for target distance
            # Consider relative_position if specified
            if 'relative_position' in crit:
                rel_pos = crit['relative_position']
                # For ahead/behind, try to position appropriately along the road
                if rel_pos == 'ahead':
                    # Place further along the road
                    s = min(road_length * 0.8, road_length - 5)
                elif rel_pos == 'behind':
                    # Place earlier along the road
                    s = max(road_length * 0.2, 5)
                else:
                    s = road_length / 2
            else:
                s = min(road_length * 0.7, road_length / 2)  # Avoid road endpoints
        else:
            s = road_length / 2  # Middle of road segment
        
        # Calculate position along road centerline
        x = road_x + s * math.cos(road_hdg)
        y = road_y + s * math.sin(road_hdg)
        
        # Adjust for specific lane
        lanes = selected_road.get('lanes', {})
        selected_lane_id = None
        selected_lane = None
        
        # Find appropriate lane
        if 'lane_type' in crit:
            required_types = crit['lane_type'] if isinstance(crit['lane_type'], list) else [crit['lane_type']]
            for lane_id, lane_info in lanes.items():
                if lane_info.get('lane_type', '').lower() in [lt.lower() for lt in required_types]:
                    selected_lane_id = int(lane_id)
                    selected_lane = lane_info
                    break
        
        if not selected_lane:
            # Default to first driving lane
            for lane_id, lane_info in lanes.items():
                if lane_info.get('lane_type', '').lower() == 'driving':
                    selected_lane_id = int(lane_id)
                    selected_lane = lane_info
                    break
        
        # Calculate lateral offset for the lane
        lateral_offset = 0
        if selected_lane_id and selected_lane_id != 0:
            # Calculate offset from centerline to lane center by summing lane widths
            # Need to sum all lane widths from center (0) to target lane
            
            if selected_lane_id > 0:  # Left side
                # Sum widths from lane 1 to selected_lane_id
                for i in range(1, selected_lane_id + 1):
                    lane = lanes.get(str(i))
                    if lane:
                        width = lane.get('width', 3.5)
                        if i == selected_lane_id:
                            # For target lane, go to its center
                            lateral_offset += width / 2
                        else:
                            # For intermediate lanes, add full width
                            lateral_offset += width
            else:  # Right side (negative lane IDs)
                # Sum widths from lane -1 to selected_lane_id
                for i in range(-1, selected_lane_id - 1, -1):
                    lane = lanes.get(str(i))
                    if lane:
                        width = lane.get('width', 3.5)
                        if i == selected_lane_id:
                            # For target lane, go to its center
                            lateral_offset -= width / 2
                        else:
                            # For intermediate lanes, add full width
                            lateral_offset -= width
        
        # Apply lateral offset perpendicular to road heading
        x += lateral_offset * math.cos(road_hdg + math.pi/2)
        y += lateral_offset * math.sin(road_hdg + math.pi/2)
        
        # Z coordinate (height)
        z = 0.5  # Default ground level with small offset
        
        # Apply additional distance and relative position constraints if ego position is provided
        if ego_pos:
            actual_dist = math.hypot(x - ego_pos[0], y - ego_pos[1])
            
            # Check relative position constraint
            if 'relative_position' in crit:
                rel_pos = crit['relative_position']
                ego_yaw = ego_pos[3] if len(ego_pos) > 3 else 0
                dx, dy = x - ego_pos[0], y - ego_pos[1]
                # Project onto ego's forward direction
                forward_dist = dx * math.cos(ego_yaw) + dy * math.sin(ego_yaw)
                actual_rel_pos = "ahead" if forward_dist > 0 else "behind"
                
                # If relative position doesn't match, try to adjust
                if rel_pos in ['ahead', 'behind'] and actual_rel_pos != rel_pos:
                    # Try different geometry segments to find one that matches
                    for geom_idx, alt_geom in enumerate(geometry):
                        if geom_idx == geometry.index(geom):
                            continue  # Skip current segment
                        
                        # Try this segment
                        alt_x = alt_geom['x'] + s * math.cos(alt_geom['hdg'])
                        alt_y = alt_geom['y'] + s * math.sin(alt_geom['hdg'])
                        
                        # Apply lane offset
                        if lateral_offset != 0:
                            alt_x += lateral_offset * math.cos(alt_geom['hdg'] + math.pi/2)
                            alt_y += lateral_offset * math.sin(alt_geom['hdg'] + math.pi/2)
                        
                        # Check if this position matches relative position
                        alt_dx, alt_dy = alt_x - ego_pos[0], alt_y - ego_pos[1]
                        alt_forward = alt_dx * math.cos(ego_yaw) + alt_dy * math.sin(ego_yaw)
                        alt_rel_pos = "ahead" if alt_forward > 0 else "behind"
                        
                        if alt_rel_pos == rel_pos:
                            # Use this position instead
                            x, y = alt_x, alt_y
                            road_hdg = alt_geom['hdg']
                            break
            
            if 'distance_to_ego' in crit:
                actual_dist = math.hypot(x - ego_pos[0], y - ego_pos[1])
                min_dist = crit['distance_to_ego'].get('min', 5)
                max_dist = crit['distance_to_ego'].get('max', 100)
                if not (min_dist <= actual_dist <= max_dist):
                    # Adjust position along road to meet distance constraint
                    # This is a simplified adjustment
                    if actual_dist < min_dist:
                        scale = min_dist / max(actual_dist, 0.1)
                        x = ego_pos[0] + (x - ego_pos[0]) * scale
                        y = ego_pos[1] + (y - ego_pos[1]) * scale
                    elif actual_dist > max_dist:
                        scale = max_dist / actual_dist
                        x = ego_pos[0] + (x - ego_pos[0]) * scale
                        y = ego_pos[1] + (y - ego_pos[1]) * scale
        
        self.logger.info(f"Generated spawn from road intelligence:")
        self.logger.info(f"  Road {selected_road_id}, Lane {selected_lane_id} ({selected_lane.get('lane_type') if selected_lane else 'unknown'})")
        self.logger.info(f"  Position: ({x:.1f}, {y:.1f}, {z:.1f})")
        self.logger.info(f"  Heading: {math.degrees(road_hdg):.1f}°")
        
        return x, y, z, road_hdg
    
    def _interpolate_spawn_points_for_distance(self, candidates: List[Dict], 
                                               ego_pos: Tuple[float, float, float, float],
                                               min_dist: float, max_dist: float,
                                               relative_position: Optional[str] = None) -> List[Dict]:
        """Generate interpolated spawn points to achieve exact distance requirements"""
        interpolated = []
        
        # Find the two closest points that bracket our desired distance
        best_before = None
        best_after = None
        target_dist = (min_dist + max_dist) / 2  # Aim for middle of range
        
        for pt in candidates:
            d = math.hypot(pt.get('x', 0) - ego_pos[0], pt.get('y', 0) - ego_pos[1])
            
            # Check relative position
            if relative_position:
                dx = pt.get('x', 0) - ego_pos[0]
                dy = pt.get('y', 0) - ego_pos[1]
                angle_to_point = math.atan2(dy, dx)
                relative_angle = angle_to_point - ego_pos[3]
                
                # Normalize
                while relative_angle > math.pi:
                    relative_angle -= 2 * math.pi
                while relative_angle < -math.pi:
                    relative_angle += 2 * math.pi
                
                is_ahead = abs(relative_angle) < math.pi/2
                if (relative_position == 'ahead' and not is_ahead) or \
                   (relative_position == 'behind' and is_ahead):
                    continue  # Skip wrong direction
            
            # Track closest points before and after target distance
            if d < target_dist:
                if not best_before or d > math.hypot(best_before.get('x', 0) - ego_pos[0], 
                                                     best_before.get('y', 0) - ego_pos[1]):
                    best_before = pt
            elif d > target_dist:
                if not best_after or d < math.hypot(best_after.get('x', 0) - ego_pos[0], 
                                                    best_after.get('y', 0) - ego_pos[1]):
                    best_after = pt
        
        # If we have bracketing points, interpolate
        if best_before and best_after:
            d_before = math.hypot(best_before.get('x', 0) - ego_pos[0], best_before.get('y', 0) - ego_pos[1])
            d_after = math.hypot(best_after.get('x', 0) - ego_pos[0], best_after.get('y', 0) - ego_pos[1])
            
            # Check they're on the same road/lane and reasonably close
            if (best_before.get('road_id') == best_after.get('road_id') and 
                best_before.get('lane_id') == best_after.get('lane_id') and
                math.hypot(best_after['x'] - best_before['x'], best_after['y'] - best_before['y']) < 20):
                
                # Calculate interpolation factor
                t = (target_dist - d_before) / (d_after - d_before)
                
                # Interpolate position
                interp_x = best_before['x'] + t * (best_after['x'] - best_before['x'])
                interp_y = best_before['y'] + t * (best_after['y'] - best_before['y'])
                interp_z = best_before.get('z', 0) + t * (best_after.get('z', 0) - best_before.get('z', 0))
                
                # Interpolate yaw
                yaw1 = best_before.get('yaw', 0)
                yaw2 = best_after.get('yaw', 0)
                if abs(yaw2 - yaw1) > 180:
                    if yaw2 > yaw1:
                        yaw1 += 360
                    else:
                        yaw2 += 360
                interp_yaw = yaw1 + t * (yaw2 - yaw1)
                if interp_yaw > 180:
                    interp_yaw -= 360
                
                # Create interpolated spawn point
                interp_pt = {
                    'x': interp_x,
                    'y': interp_y,
                    'z': interp_z,
                    'yaw': interp_yaw,
                    'road_id': best_before.get('road_id'),
                    'lane_id': best_before.get('lane_id'),
                    'lane_type': best_before.get('lane_type'),
                    'interpolated': True
                }
                
                actual_dist = math.hypot(interp_x - ego_pos[0], interp_y - ego_pos[1])
                self.logger.info(f"Created interpolated spawn at {actual_dist:.1f}m (target: {target_dist:.1f}m)")
                interpolated.append(interp_pt)
                return interpolated
        
        # Fallback to original method
        sorted_candidates = sorted(candidates, key=lambda pt: (pt.get('x', 0), pt.get('y', 0)))
        
        # Find pairs of consecutive spawn points and interpolate between them
        for i in range(len(sorted_candidates) - 1):
            pt1 = sorted_candidates[i]
            pt2 = sorted_candidates[i + 1]
            
            # Calculate distances from ego
            d1 = math.hypot(pt1.get('x', 0) - ego_pos[0], pt1.get('y', 0) - ego_pos[1])
            d2 = math.hypot(pt2.get('x', 0) - ego_pos[0], pt2.get('y', 0) - ego_pos[1])
            
            # Check if we need to interpolate between these points
            # (one is too close, other is too far, or vice versa)
            if (d1 < min_dist and d2 > min_dist) or (d1 > max_dist and d2 < max_dist) or \
               (d1 < min_dist and d2 > max_dist) or (min(d1, d2) < min_dist and max(d1, d2) > min_dist):
                
                # Calculate how many interpolation points we need
                gap_distance = math.hypot(pt2['x'] - pt1['x'], pt2['y'] - pt1['y'])
                num_points = max(2, int(gap_distance / 2.0))  # One point every ~2m
                
                for j in range(1, num_points):
                    t = j / num_points
                    
                    # Interpolate position
                    interp_x = pt1['x'] + t * (pt2['x'] - pt1['x'])
                    interp_y = pt1['y'] + t * (pt2['y'] - pt1['y'])
                    interp_z = pt1.get('z', 0) + t * (pt2.get('z', 0) - pt1.get('z', 0))
                    
                    # Interpolate yaw (handling angle wrapping)
                    yaw1 = pt1.get('yaw', 0)
                    yaw2 = pt2.get('yaw', 0)
                    # Handle angle wrapping
                    if abs(yaw2 - yaw1) > 180:
                        if yaw2 > yaw1:
                            yaw1 += 360
                        else:
                            yaw2 += 360
                    interp_yaw = yaw1 + t * (yaw2 - yaw1)
                    if interp_yaw > 180:
                        interp_yaw -= 360
                    
                    # Check distance from ego
                    interp_dist = math.hypot(interp_x - ego_pos[0], interp_y - ego_pos[1])
                    
                    # Check if it's in the desired range
                    if min_dist <= interp_dist <= max_dist:
                        # Check relative position if specified
                        if relative_position:
                            dx = interp_x - ego_pos[0]
                            dy = interp_y - ego_pos[1]
                            angle_to_point = math.atan2(dy, dx)
                            relative_angle = angle_to_point - ego_pos[3]
                            
                            # Normalize
                            while relative_angle > math.pi:
                                relative_angle -= 2 * math.pi
                            while relative_angle < -math.pi:
                                relative_angle += 2 * math.pi
                            
                            is_ahead = abs(relative_angle) < math.pi/2
                            if (relative_position == 'ahead' and not is_ahead) or \
                               (relative_position == 'behind' and is_ahead):
                                continue  # Skip this interpolated point
                        
                        # Create interpolated spawn point
                        interp_pt = {
                            'x': interp_x,
                            'y': interp_y,
                            'z': interp_z,
                            'yaw': interp_yaw,
                            'road_id': pt1.get('road_id'),
                            'lane_id': pt1.get('lane_id'),
                            'lane_type': pt1.get('lane_type'),
                            'interpolated': True  # Mark as interpolated
                        }
                        interpolated.append(interp_pt)
        
        return interpolated
    
    def _legacy_choose_spawn(self, map_name: str, crit: Dict[str, Any],
                           ego_pos: Optional[Tuple[float, float, float, float]] = None,
                           ego_lane: Optional[Tuple[int, int]] = None,
                           pts: List[Dict] = None) -> Tuple[float, float, float, float]:
        """Fallback to original spawn selection logic when no road intelligence is available"""
        if pts is None:
            pts = self._get_spawn_points_for_map(map_name)
            
        candidates = pts
        
        # Apply legacy filtering logic
        if 'road_relationship' in crit:
            candidates = self._filter_by_road_relationship(candidates, crit, ego_lane)
            self.logger.debug(f"Road relationship filter: {len(pts)} -> {len(candidates)} candidates")
        
        if 'lane_relationship' in crit:
            candidates = self._filter_by_lane_relationship(candidates, crit, ego_lane)
            self.logger.debug(f"Lane relationship filter: -> {len(candidates)} candidates")
        
        # Filter for roads with multiple lanes in same direction if required
        if 'min_lanes_same_direction' in crit:
            min_lanes = crit['min_lanes_same_direction']
            multi_lane_candidates = []
            
            # Group candidates by road and lane direction (sign of lane_id)
            # In CARLA/OpenDRIVE: negative lanes go one way, positive lanes go the other way
            road_direction_lanes = {}
            for pt in candidates:
                road_id = pt.get('road_id')
                lane_id = pt.get('lane_id')
                lane_type = pt.get('lane_type', '').lower()
                
                # Only count Driving lanes for multi-lane requirement
                if road_id and lane_id is not None and lane_type == 'driving':
                    # Group by road and lane sign (direction)
                    direction = 'positive' if lane_id > 0 else 'negative'
                    key = (road_id, direction)
                    if key not in road_direction_lanes:
                        road_direction_lanes[key] = set()
                    road_direction_lanes[key].add(lane_id)
            
            # Find road/direction combinations with enough driving lanes
            valid_road_directions = set()
            for (road_id, direction), lane_set in road_direction_lanes.items():
                if len(lane_set) >= min_lanes:
                    valid_road_directions.add((road_id, direction))
                    self.logger.debug(f"Road {road_id} {direction} direction has {len(lane_set)} driving lanes: {sorted(lane_set)}")
            
            # Filter candidates to only those on valid road/direction combinations
            for pt in candidates:
                road_id = pt.get('road_id')
                lane_id = pt.get('lane_id')
                if road_id and lane_id is not None:
                    direction = 'positive' if lane_id > 0 else 'negative'
                    if (road_id, direction) in valid_road_directions:
                        multi_lane_candidates.append(pt)
            
            if multi_lane_candidates:
                candidates = multi_lane_candidates
                self.logger.info(f"Filtered to {len(candidates)} spawn points on road sections with {min_lanes}+ driving lanes in same direction")
            else:
                self.logger.warning(f"No road sections found with {min_lanes}+ driving lanes in same direction, keeping all candidates")
        
        if 'lane_type' in crit:
            # Use intelligent lane type filtering with fallbacks
            road_context = self._get_road_context_from_criteria(crit, ego_lane, map_name)
            candidates = self._filter_by_lane_type_with_fallbacks(candidates, crit, road_context)
            self.logger.debug(f"Lane type filter (with fallbacks): -> {len(candidates)} candidates")
            
            # If no candidates after lane type filtering, return a random spawn point as last resort
            if not candidates:
                self.logger.warning(f"No candidates after lane type filtering, returning random spawn point")
                if pts:
                    pt = random.choice(pts)
                    return (pt.get('x', 0), pt.get('y', 0), pt.get('z', 0), pt.get('yaw', 0))
                else:
                    raise ValueError(f"No spawn points available for map {map_name}")
        
        if 'distance_to_ego' in crit and ego_pos:
            # Define low and hi outside the loop to avoid UnboundLocalError
            low = crit['distance_to_ego'].get('min', 0)
            hi = crit['distance_to_ego'].get('max', 1000)
            
            distance_filtered = []
            for pt in candidates:
                d = math.hypot(pt.get('x', 0) - ego_pos[0], pt.get('y', 0) - ego_pos[1])
                if low <= d <= hi:
                    distance_filtered.append(pt)
            
            # If we don't have enough candidates and we're filtering same road/lane, try interpolation or find best available  
            if len(distance_filtered) < 3 and ego_lane and 'road_relationship' in crit and crit['road_relationship'] == 'same_road':
                self.logger.info(f"Only {len(distance_filtered)} candidates in distance range {low}-{hi}m, trying interpolation...")
                
                # First try interpolation to get exact distance
                interpolated = self._interpolate_spawn_points_for_distance(
                    candidates, ego_pos, low, hi, crit.get('relative_position')
                )
                if interpolated:
                    distance_filtered.extend(interpolated)
                    self.logger.info(f"Added {len(interpolated)} interpolated spawn points")
                else:
                    # Interpolation failed, try modest relaxation (20% expansion max)
                    range_size = hi - low
                    relaxed_min = max(5, low - range_size * 0.2)  # Allow 20% below min
                    relaxed_max = hi + range_size * 0.2  # Allow 20% above max
                    
                    best_alternative = None
                    best_distance = float('inf')
                    
                    for pt in candidates:
                        d = math.hypot(pt.get('x', 0) - ego_pos[0], pt.get('y', 0) - ego_pos[1])
                        
                        # Skip if outside relaxed range
                        if d < relaxed_min or d > relaxed_max:
                            continue
                        
                        # Check relative position if specified
                        if 'relative_position' in crit:
                            dx = pt.get('x', 0) - ego_pos[0]
                            dy = pt.get('y', 0) - ego_pos[1]
                            angle_to_point = math.atan2(dy, dx)
                            relative_angle = angle_to_point - ego_pos[3]
                            
                            # Normalize angle
                            while relative_angle > math.pi:
                                relative_angle -= 2 * math.pi
                            while relative_angle < -math.pi:
                                relative_angle += 2 * math.pi
                            
                            is_ahead = abs(relative_angle) < math.pi/2
                            if crit['relative_position'] == 'ahead' and not is_ahead:
                                continue
                            elif crit['relative_position'] == 'behind' and is_ahead:
                                continue
                        
                        # Find closest to original range
                        target = (low + hi) / 2
                        distance_from_target = abs(d - target)
                        if distance_from_target < best_distance:
                            best_distance = distance_from_target
                            best_alternative = pt
                    
                    if best_alternative:
                        actual_dist = math.hypot(best_alternative.get('x', 0) - ego_pos[0], 
                                               best_alternative.get('y', 0) - ego_pos[1])
                        self.logger.warning(f"Using spawn at {actual_dist:.1f}m (requested {low}-{hi}m, relaxed to {relaxed_min:.1f}-{relaxed_max:.1f}m)")
                        distance_filtered.append(best_alternative)
                    elif not distance_filtered:
                        self.logger.error(f"Cannot find spawn points even with 20% relaxation ({relaxed_min:.1f}-{relaxed_max:.1f}m)")
                        # Don't add any alternatives - let fallback strategy handle it
            
            candidates = distance_filtered
            self.logger.debug(f"Distance filter: -> {len(candidates)} candidates")
        
        # Apply remaining filters
        filtered_candidates = []
        for pt in candidates:
            if self._matches_spawn_criteria(pt, crit, ego_pos, ego_lane):
                filtered_candidates.append(pt)
        
        self.logger.debug(f"Remaining criteria filter: {len(candidates)} -> {len(filtered_candidates)} candidates")
        
        # Use fallback strategy if no matches
        final_candidates = self._apply_fallback_strategy(filtered_candidates, candidates, pts, crit, ego_pos, ego_lane)
        
        # Filter out candidates that are too close to ego (< 5m)
        if ego_pos and final_candidates:
            safe_candidates = []
            for pt in final_candidates:
                dist = math.hypot(pt.get('x', 0) - ego_pos[0], pt.get('y', 0) - ego_pos[1])
                if dist >= 5.0:  # Minimum 5m distance from ego
                    safe_candidates.append(pt)
                else:
                    self.logger.warning(f"Rejecting spawn at distance {dist:.1f}m from ego (too close)")
            final_candidates = safe_candidates
        
        # Score and select best spawn point
        if not final_candidates:
            # For highway scenarios in first 3 maps, try ultra-relaxed fallback
            is_highway_map = map_name in ['Town04', 'Town05', 'Town03']
            has_flag = hasattr(self, '_allow_final_fallback')
            flag_value = getattr(self, '_allow_final_fallback', False) if has_flag else False
            self.logger.info(f"Ultra-relaxed check: map={map_name}, is_highway_map={is_highway_map}, has_flag={has_flag}, flag_value={flag_value}")
            if is_highway_map and hasattr(self, '_allow_final_fallback') and self._allow_final_fallback:
                self.logger.warning(f"Highway map {map_name}: attempting ultra-relaxed fallback for actor spawn")
                # Try to find ANY driving lane spawn at reasonable distance
                ultra_candidates = []
                for pt in pts[:1000]:  # Check many points
                    # Basic filtering: Driving lanes and reasonable distance
                    if pt.get('lane_type', '').lower() == 'driving':
                        if ego_pos:
                            dist = math.hypot(pt.get('x', 0) - ego_pos[0], pt.get('y', 0) - ego_pos[1])
                            if 15 <= dist <= 200:  # Wide range for highways
                                ultra_candidates.append(pt)
                        else:
                            ultra_candidates.append(pt)
                    
                    if len(ultra_candidates) >= 50:  # Get enough candidates
                        break
                
                if ultra_candidates:
                    # Sort by distance to preferred range
                    target_dist = (crit.get('distance_to_ego', {}).get('min', 40) + 
                                 crit.get('distance_to_ego', {}).get('max', 60)) / 2
                    if ego_pos:
                        ultra_candidates.sort(key=lambda p: abs(
                            math.hypot(p.get('x', 0) - ego_pos[0], p.get('y', 0) - ego_pos[1]) - target_dist
                        ))
                    final_candidates = ultra_candidates[:10]
                    self.logger.info(f"Ultra-relaxed fallback found {len(final_candidates)} candidates for highway scenario")
            
            if not final_candidates:
                # Provide detailed error message to help debug the issue
                error_msg = f"No valid spawn points found for actor in map {map_name}. "
                if ego_pos:
                    error_msg += f"All candidate spawns were too close to ego (< 5m). "
                error_msg += f"Criteria: {crit}. "
                error_msg += "Try: 1) Increasing distance range, 2) Relaxing lane constraints, 3) Using a different map, or 4) Checking spawn data availability."
                raise RuntimeError(error_msg)
        
        if len(final_candidates) == 1:
            pick = final_candidates[0]
        else:
            scored_candidates = [(self._score_spawn_point(pt, crit, ego_pos, ego_lane), pt) for pt in final_candidates]
            scored_candidates.sort(reverse=True, key=lambda x: x[0])
            pick = scored_candidates[0][1]
        
        self._last_pick = pick
        self._log_spawn_decision(pick, ego_pos, ego_lane, crit)
        
        # Apply lateral offset if this was a fallback lane type
        x, y, z, yaw = pick['x'], pick['y'], pick['z'], math.radians(pick['yaw'])
        
        # Add proper z-offset to ensure vehicles spawn above ground (prevents getting stuck)
        # Use 0.3m for safety - enough to clear ground but not so high that vehicles get damaged
        z += 0.3  # Lift vehicle 30cm above road surface
        
        if 'lateral_offset_fallback' in pick:
            offset = pick['lateral_offset_fallback']
            # Apply offset perpendicular to the heading direction
            x += offset * math.cos(yaw + math.pi/2)
            y += offset * math.sin(yaw + math.pi/2)
            self.logger.info(f"Applied lateral offset of {offset}m to position due to lane type fallback")
        
        # Only apply explicit lateral_offset if we didn't get the exact lane type requested
        # (i.e., if we're using a fallback or want fine-tuning within the same lane)
        if 'lateral_offset' in crit:
            # Check if we got the exact lane type requested
            requested_lane_type = crit.get('lane_type')
            actual_lane_type = pick.get('lane_type')
            
            # Only apply offset if it's a different lane type or explicitly a fallback
            if 'lateral_offset_fallback' in pick or (requested_lane_type and actual_lane_type and 
                                                      requested_lane_type.lower() != actual_lane_type.lower()):
                extra_offset = crit['lateral_offset']
                x += extra_offset * math.cos(yaw + math.pi/2)
                y += extra_offset * math.sin(yaw + math.pi/2)
                self.logger.info(f"Applied additional lateral offset of {extra_offset}m from criteria (lane type mismatch)")
            else:
                self.logger.info(f"Skipping lateral_offset from criteria - already on correct {actual_lane_type} lane")
        
        return x, y, z, yaw
    
    def _get_scenario_type_from_criteria(self, crit: Dict[str, Any]) -> str:
        """Detect scenario type from spawn criteria"""
        if crit.get('lane_relationship') in ['adjacent_lane']:
            return 'cut_in'
        elif crit.get('road_relationship') == 'same_road':
            return 'following'
        elif crit.get('is_intersection'):
            return 'intersection'
        else:
            return 'general'
    
    def _get_road_context_from_criteria(self, crit: Dict[str, Any], ego_lane: Optional[Tuple[int, int]], map_name: str) -> str:
        """Determine road context from criteria and available data"""
        # Check explicit road_context in criteria
        if 'road_context' in crit:
            return crit['road_context']
        
        # Infer from speed limits if present
        if 'speed_limit' in crit:
            speed_limit = crit['speed_limit']
            if isinstance(speed_limit, dict):
                max_speed = speed_limit.get('max', 0)
                if max_speed >= 80:
                    return 'highway'
                elif max_speed <= 30:
                    return 'urban'
                else:
                    return 'suburban'
        
        # Check road intelligence data if available
        if ego_lane and map_name in self.road_intelligence:
            road_id = ego_lane[0]
            road_data = self.road_intelligence[map_name].get('roads', {}).get(str(road_id), {})
            if 'context' in road_data:
                return road_data['context']
        
        # Default based on common patterns
        return 'urban'  # Safe default
    
    def _get_context_aware_fallbacks(self, lane_type: str, road_context: str) -> List[str]:
        """Get context-aware fallback lane types based on road context"""
        fallback_map = {
            'highway': {
                'Shoulder': ['Emergency', 'Exit', 'Entry', 'Driving'],
                'Emergency': ['Shoulder', 'Exit', 'Entry', 'Driving'],
                'Exit': ['Entry', 'Shoulder', 'Emergency', 'Driving'],
                'Entry': ['Exit', 'Shoulder', 'Emergency', 'Driving'],
                'Parking': ['Shoulder', 'Emergency', 'Driving'],  # Parking rare on highways
                'Driving': ['Driving'],  # No fallback needed
                'Sidewalk': ['Sidewalk']  # Keep pedestrians off vehicle lanes on highways
            },
            'urban': {
                'Shoulder': ['Parking', 'Biking', 'Driving'],
                'Emergency': ['Parking', 'Shoulder', 'Driving'],
                'Parking': ['Shoulder', 'Biking', 'Driving'],
                'Biking': ['Parking', 'Shoulder', 'Driving'],
                'Driving': ['Driving'],
                'Sidewalk': ['Sidewalk'],  # Keep pedestrians on sidewalk in urban
                'Exit': ['Entry', 'Driving'],
                'Entry': ['Exit', 'Driving']
            },
            'suburban': {
                'Shoulder': ['Parking', 'Driving'],
                'Emergency': ['Shoulder', 'Parking', 'Driving'],
                'Parking': ['Shoulder', 'Driving'],
                'Biking': ['Shoulder', 'Parking', 'Driving'],
                'Driving': ['Driving'],
                'Sidewalk': ['Sidewalk'],  # Keep pedestrians on sidewalk only
                'Exit': ['Entry', 'Driving'],
                'Entry': ['Exit', 'Driving']
            },
            'rural': {
                'Shoulder': ['Driving'],  # Rural roads often lack shoulders
                'Emergency': ['Shoulder', 'Driving'],
                'Parking': ['Shoulder', 'Driving'],
                'Driving': ['Driving'],
                'Sidewalk': ['Sidewalk'],  # Don't put pedestrians on driving lanes
                'Biking': ['Shoulder', 'Driving']
            },
            'construction': {
                'Shoulder': ['Driving'],  # Construction zones have limited shoulders
                'Emergency': ['Driving'],
                'Parking': ['Driving'],
                'Driving': ['Driving'],
                'Sidewalk': ['Sidewalk'],  # Keep pedestrians safe in construction zones
                'Biking': ['Driving']
            },
            'parking': {
                'Parking': ['Parking', 'Driving'],
                'Shoulder': ['Parking', 'Driving'],
                'Driving': ['Driving'],
                'Sidewalk': ['Sidewalk']  # Keep pedestrians on sidewalk only
            },
            'town': {  # Added specific handling for town context
                'Shoulder': ['Parking', 'Driving'],
                'Emergency': ['Shoulder', 'Parking', 'Driving'],
                'Parking': ['Shoulder', 'Driving'],
                'Biking': ['Shoulder', 'Parking', 'Driving'],
                'Driving': ['Driving'],  # No fallback, must use driving lanes
                'Sidewalk': ['Sidewalk'],  # Never put vehicles on sidewalks
                'Exit': ['Entry', 'Driving'],
                'Entry': ['Exit', 'Driving']
            }
        }
        
        # Get fallbacks for the specific context and lane type
        context_fallbacks = fallback_map.get(road_context, fallback_map['urban'])
        fallbacks = context_fallbacks.get(lane_type, ['Driving'])  # Default to Driving if not found
        
        # CRITICAL: Never allow Sidewalk as a fallback for Driving lanes
        if lane_type == 'Driving' and 'Sidewalk' in fallbacks:
            fallbacks = [f for f in fallbacks if f != 'Sidewalk']
            if not fallbacks:
                fallbacks = ['Driving']  # Must have at least Driving as fallback
        
        return fallbacks
    
    def _filter_by_lane_type_with_fallbacks(self, candidates: List[Dict], crit: Dict[str, Any], road_context: str) -> List[Dict]:
        """Filter by lane type with intelligent context-aware fallbacks"""
        requested_types = crit['lane_type'] if isinstance(crit['lane_type'], list) else [crit['lane_type']]
        
        # First try exact matches (case-insensitive)
        exact_matches = []
        requested_types_lower = [rt.lower() if isinstance(rt, str) else rt for rt in requested_types]
        for pt in candidates:
            pt_lane_type = pt.get('lane_type', '')
            if isinstance(pt_lane_type, str) and pt_lane_type.lower() in requested_types_lower:
                exact_matches.append(pt)
        
        if exact_matches:
            self.logger.info(f"Found {len(exact_matches)} exact matches for lane types: {requested_types}")
            return exact_matches
        
        # No exact matches, use context-aware fallbacks
        self.logger.warning(f"No exact matches for lane types {requested_types} in {road_context} context, trying fallbacks")
        
        fallback_candidates = []
        fallback_types_used = set()
        lateral_offset_needed = 0.0
        
        for requested_type in requested_types:
            fallback_types = self._get_context_aware_fallbacks(requested_type, road_context)
            
            for fallback_type in fallback_types:
                for pt in candidates:
                    pt_lane_type = pt.get('lane_type', '')
                    if isinstance(pt_lane_type, str) and pt_lane_type.lower() == fallback_type.lower() and pt not in fallback_candidates:
                        # Calculate lateral offset needed when using fallback
                        if fallback_type != requested_type:
                            lateral_offset_needed = self._calculate_lateral_offset_for_fallback(
                                requested_type, fallback_type, road_context
                            )
                            if lateral_offset_needed != 0:
                                # Store offset info in the point for later use
                                pt = pt.copy()  # Don't modify original
                                pt['lateral_offset_fallback'] = lateral_offset_needed
                                pt['original_lane_type'] = requested_type
                                pt['fallback_lane_type'] = fallback_type
                        
                        fallback_candidates.append(pt)
                        fallback_types_used.add(fallback_type)
                
                if fallback_candidates:
                    break  # Found fallback candidates, stop searching
            
            if fallback_candidates:
                break  # Found fallback candidates for this requested type
        
        if fallback_candidates:
            self.logger.warning(f"Using fallback lane types {fallback_types_used} instead of {requested_types} in {road_context} context")
            if lateral_offset_needed != 0:
                self.logger.info(f"Will apply lateral offset of {lateral_offset_needed}m to simulate {requested_types[0]} lane")
        else:
            self.logger.error(f"No fallback lanes found for {requested_types} in {road_context} context")
        
        return fallback_candidates
    
    def _calculate_lateral_offset_for_fallback(self, requested_type: str, fallback_type: str, road_context: str) -> float:
        """Calculate lateral offset needed when using a fallback lane type"""
        # Define typical lane widths and positions
        lane_offsets = {
            ('Shoulder', 'Driving', 'highway'): 3.5,  # Shoulder is ~3.5m to the right on highways
            ('Shoulder', 'Driving', 'urban'): 2.5,    # Narrower in urban areas
            ('Shoulder', 'Driving', 'suburban'): 3.0,
            ('Parking', 'Driving', 'urban'): 2.5,      # Parking lane offset
            ('Parking', 'Driving', 'suburban'): 2.5,
            ('Emergency', 'Driving', 'highway'): 3.5,
            ('Biking', 'Driving', 'urban'): 1.5,       # Bike lane is narrower
            ('Sidewalk', 'Driving', 'urban'): 4.0,     # Sidewalk offset from driving lane
            ('Sidewalk', 'Shoulder', 'highway'): 1.5,  # From shoulder to edge
        }
        
        key = (requested_type, fallback_type, road_context)
        return lane_offsets.get(key, 0.0)  # Return 0 if no specific offset defined

    def _filter_unsuitable_roads(self, candidates: List[Dict], scenario_type: str, map_name: str, crit: Dict[str, Any]) -> List[Dict]:
        """Filter out roads that can't support the scenario requirements and suggest alternatives"""
        if scenario_type != 'cut_in':
            return candidates  # Only filter for cut-in scenarios for now
        
        # Get roads that need adjacent lanes
        needs_adjacent = crit.get('lane_relationship') in ['adjacent_lane']
        if not needs_adjacent:
            return candidates
        
        # Group candidates by road
        road_groups = {}
        for candidate in candidates:
            road_id = candidate.get('road_id')
            if road_id not in road_groups:
                road_groups[road_id] = []
            road_groups[road_id].append(candidate)
        
        suitable_roads = []
        unsuitable_roads = []
        
        # Check each road for adjacent lane support
        for road_id, road_candidates in road_groups.items():
            lanes = set(c.get('lane_id') for c in road_candidates if c.get('lane_id') is not None)
            sorted_lanes = sorted(lanes)
            
            # Check for adjacent lanes
            has_adjacent = False
            for i in range(len(sorted_lanes) - 1):
                if abs(sorted_lanes[i+1] - sorted_lanes[i]) == 1:
                    has_adjacent = True
                    break
            
            if has_adjacent and len(road_candidates) >= 4:  # Need adequate spawn points too
                suitable_roads.extend(road_candidates)
            else:
                unsuitable_roads.extend(road_candidates)
                self.logger.warning(f"Road {road_id} lacks adjacent lanes or adequate spawns for cut-in scenario (lanes: {sorted_lanes}, spawns: {len(road_candidates)})")
        
        if suitable_roads:
            self.logger.info(f"Filtered out {len(unsuitable_roads)} spawns from unsuitable roads, keeping {len(suitable_roads)} from suitable roads")
            
            # If we have good alternatives, exclude problematic roads entirely
            if len(suitable_roads) >= 10:  # Enough alternatives
                return suitable_roads
        
        # If no suitable roads or very few alternatives, try to find better roads
        if not suitable_roads or len(suitable_roads) < 5:
            self.logger.warning(f"Very few suitable roads found, attempting to find better alternatives...")
            better_candidates = self._find_alternative_roads(map_name, scenario_type, crit)
            if better_candidates:
                self.logger.info(f"Found {len(better_candidates)} alternative spawn points on better roads")
                return better_candidates
        
        # Return what we have (may include unsuitable roads as fallback)
        return suitable_roads if suitable_roads else candidates

    def _find_alternative_roads(self, map_name: str, scenario_type: str, crit: Dict[str, Any]) -> List[Dict]:
        """Find spawn points on roads that better support the scenario"""
        all_spawns = self._get_spawn_points_for_map(map_name)
        
        if scenario_type == 'cut_in':
            # Look for roads with many lanes and spawn points (like highways)
            road_groups = {}
            for spawn in all_spawns:
                road_id = spawn.get('road_id')
                if road_id not in road_groups:
                    road_groups[road_id] = []
                road_groups[road_id].append(spawn)
            
            # Score roads based on suitability for cut-in scenarios
            scored_roads = []
            for road_id, road_spawns in road_groups.items():
                if len(road_spawns) < 10:  # Skip roads with too few spawns
                    continue
                
                lanes = set(s.get('lane_id') for s in road_spawns if s.get('lane_id') is not None)
                sorted_lanes = sorted(lanes)
                
                # Count adjacent lane pairs
                adjacent_pairs = 0
                for i in range(len(sorted_lanes) - 1):
                    if abs(sorted_lanes[i+1] - sorted_lanes[i]) == 1:
                        adjacent_pairs += 1
                
                if adjacent_pairs > 0:
                    score = adjacent_pairs * 50 + len(road_spawns) * 2
                    scored_roads.append((score, road_id, road_spawns))
            
            # Return spawns from the best roads
            if scored_roads:
                scored_roads.sort(reverse=True)  # Highest score first
                
                # Take spawns from top 3 roads 
                best_spawns = []
                for _, road_id, road_spawns in scored_roads[:3]:
                    best_spawns.extend(road_spawns)
                    self.logger.info(f"Using alternative road {road_id} with {len(road_spawns)} spawns for cut-in scenario")
                
                return best_spawns
        
        return []

    def _intelligent_choose_spawn(self, map_name: str, road_data: Dict, crit: Dict[str, Any],
                                ego_pos: Optional[Tuple[float, float, float, float]] = None,
                                ego_lane: Optional[Tuple[int, int]] = None,
                                pts: List[Dict] = None) -> Tuple[float, float, float, float]:
        """Enhanced spawn selection using road intelligence data"""
        if pts is None:
            pts = self._get_spawn_points_for_map(map_name)
            
        self.logger.info(f"Using intelligent spawn selection with road intelligence for {map_name}")
        
        # Step 1: Get enhanced spawn candidates with road context
        candidates = self._get_enhanced_spawn_candidates(pts, road_data)
        
        # Step 1.5: Apply lane type filter EARLY with fallbacks to preserve special lanes
        if 'lane_type' in crit:
            road_context = self._get_road_context_from_criteria(crit, ego_lane, map_name)
            lane_filtered = self._filter_by_lane_type_with_fallbacks(candidates, crit, road_context)
            if lane_filtered:
                candidates = lane_filtered
                self.logger.debug(f"Lane type filter (early): -> {len(candidates)} candidates")
            else:
                self.logger.warning("No lanes matched requested type even with fallbacks, keeping all candidates")
        
        # Step 2: Filter out unsuitable roads and find alternatives
        scenario_type = self._get_scenario_type_from_criteria(crit)
        candidates = self._filter_unsuitable_roads(candidates, scenario_type, map_name, crit)
        self.logger.debug(f"Road suitability filter: -> {len(candidates)} candidates")
        
        # Step 3: Apply road intelligence filters in priority order
        candidates = self._filter_by_road_context(candidates, crit, map_name)
        self.logger.debug(f"Road context filter: -> {len(candidates)} candidates")
        
        candidates = self._filter_by_junction_context(candidates, crit, map_name)
        self.logger.debug(f"Junction context filter: -> {len(candidates)} candidates")
        
        candidates = self._filter_by_road_relationships(candidates, crit, ego_lane, road_data)
        self.logger.debug(f"Road relationships filter: -> {len(candidates)} candidates")
        
        candidates = self._filter_by_geometry(candidates, crit, road_data)
        self.logger.debug(f"Geometry filter: -> {len(candidates)} candidates")
        
        # Step 4: Apply remaining constraint filters (excluding lane_type since we did it early)
        filtered_crit = crit.copy()
        if 'lane_type' in filtered_crit:
            del filtered_crit['lane_type']  # Remove to avoid double-filtering
        candidates = self._apply_legacy_filters(candidates, filtered_crit, ego_pos, ego_lane)
        self.logger.debug(f"Legacy filters: -> {len(candidates)} candidates")
        
        # Step 5: Score and select best candidate
        return self._score_and_select_spawn(candidates, crit, ego_pos, ego_lane, road_data, pts)
    
    def _choose_strategic_ego_spawn(self, data: Dict[str, Any], map_name: str, ego_criteria: Dict[str, Any]) -> Tuple[float, float, float, float]:
        """Choose ego spawn position strategically based on actor requirements"""
        # Analyze what actors need relative to ego
        needs_ahead = False
        needs_behind = False
        same_lane_actors = False
        
        for actor in data.get('actors', []):
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
        
        self.logger.info(f"Strategic ego spawn analysis: needs_ahead={needs_ahead}, needs_behind={needs_behind}, same_lane_actors={same_lane_actors}")
        
        # Get all potential ego spawn points
        spawn_points = self._get_spawn_points_for_map(map_name)
        candidates = spawn_points  # Start with all points
        
        # Apply min_lanes_same_direction filter EARLY if specified
        if 'min_lanes_same_direction' in ego_criteria:
            min_lanes = ego_criteria['min_lanes_same_direction']
            self.logger.info(f"Filtering for roads with {min_lanes}+ driving lanes in same direction")
            
            # Group candidates by road and lane direction
            road_direction_lanes = {}
            for pt in candidates:
                road_id = pt.get('road_id')
                lane_id = pt.get('lane_id')
                lane_type = pt.get('lane_type', '').lower()
                
                # Only count Driving lanes
                if road_id and lane_id is not None and lane_type == 'driving':
                    direction = 'positive' if lane_id > 0 else 'negative'
                    key = (road_id, direction)
                    if key not in road_direction_lanes:
                        road_direction_lanes[key] = set()
                    road_direction_lanes[key].add(lane_id)
            
            # Find road/direction combinations with enough driving lanes
            valid_road_directions = set()
            for (road_id, direction), lane_set in road_direction_lanes.items():
                if len(lane_set) >= min_lanes:
                    valid_road_directions.add((road_id, direction))
                    self.logger.debug(f"Road {road_id} {direction} direction: {len(lane_set)} lanes {sorted(lane_set)}")
            
            # Filter candidates to only valid road/direction combinations
            multi_lane_candidates = []
            for pt in candidates:
                road_id = pt.get('road_id')
                lane_id = pt.get('lane_id')
                if road_id and lane_id is not None:
                    direction = 'positive' if lane_id > 0 else 'negative'
                    if (road_id, direction) in valid_road_directions:
                        multi_lane_candidates.append(pt)
            
            if multi_lane_candidates:
                candidates = multi_lane_candidates
                self.logger.info(f"Filtered to {len(candidates)} points on roads with {min_lanes}+ lanes")
            else:
                self.logger.warning(f"No roads with {min_lanes}+ lanes in same direction found!")
        
        # For intersection scenarios, prefer spawns near 4-way junctions
        if ego_criteria.get('is_intersection'):
            if hasattr(self, 'four_way_junctions'):
                four_way_roads = set()
                four_way_list = self.four_way_junctions.get(map_name, [])
                
                if four_way_list:
                    # Get all roads connected to 4-way junctions
                    for junction in four_way_list:
                        four_way_roads.update(junction['incoming_roads'])
                    
                    # Filter candidates to those on 4-way junction roads
                    junction_candidates = [sp for sp in candidates if sp.get('road_id') in four_way_roads]
                    
                    if junction_candidates:
                        self.logger.info(f"Preferring spawns near 4-way junctions (roads: {list(four_way_roads)[:5]})")
                        candidates = junction_candidates
                    else:
                        self.logger.warning(f"No spawns found near 4-way junctions, using all intersection spawns")
        
        # If we need actors ahead/behind in same lane, prefer roads with good spawn density
        elif same_lane_actors and (needs_ahead or needs_behind):
            # Group spawns by road/lane to find those with good density
            road_lane_counts = {}
            for sp in spawn_points:
                if sp.get('lane_type') == 'Driving':  # Focus on driving lanes
                    key = (sp.get('road_id'), sp.get('lane_id'))
                    if key not in road_lane_counts:
                        road_lane_counts[key] = 0
                    road_lane_counts[key] += 1
            
            # Find road/lanes with at least 30 spawn points (good density)
            dense_roads = set()
            for (road_id, lane_id), count in road_lane_counts.items():
                if count >= 30:
                    dense_roads.add(road_id)
            
            if dense_roads:
                # Prefer spawns from dense roads
                dense_candidates = [sp for sp in candidates if sp.get('road_id') in dense_roads]
                if dense_candidates:
                    self.logger.info(f"Preferring roads with good spawn density: {list(dense_roads)[:5]}")
                    candidates = dense_candidates
        
        # Apply lane type filter from ego_criteria first
        if 'lane_type' in ego_criteria:
            requested_types = ego_criteria['lane_type'] if isinstance(ego_criteria['lane_type'], list) else [ego_criteria['lane_type']]
            lane_filtered = []
            for pt in candidates:
                pt_lane_type = pt.get('lane_type', '')
                if isinstance(pt_lane_type, str) and pt_lane_type.lower() in [rt.lower() for rt in requested_types]:
                    lane_filtered.append(pt)
            if lane_filtered:
                candidates = lane_filtered
                self.logger.info(f"Filtered to {len(candidates)} spawn points with lane type(s): {requested_types}")
        
        # For highway scenarios, filter for actual highway roads
        if ego_criteria.get('road_context') == 'highway':
            # Try to get road intelligence data
            road_data = self.road_intelligence.get(map_name, {})
            
            # First try to find actual highway-type roads
            highway_roads = set()
            high_speed_roads = set()
            straight_roads = set()
            curved_roads = set()
            
            if road_data and 'roads' in road_data:
                # Find the highest speed limit in this map
                max_speed = 0
                for road_info in road_data['roads'].values():
                    speed = road_info.get('speed_limit', 0)
                    if speed and speed > max_speed:
                        max_speed = speed
                
                for road_id, road_info in road_data['roads'].items():
                    # Check if it's a highway by type or speed limit
                    speed_limit = road_info.get('speed_limit')
                    road_type = road_info.get('road_type', '').lower()
                    length = road_info.get('length', 0)
                    
                    # Count the number of driving lanes
                    lanes = road_info.get('lanes', {})
                    driving_lane_count = sum(1 for lane_info in lanes.values() if lane_info.get('type') == 'driving')
                    
                    # Highway if explicitly typed as highway
                    if 'highway' in road_type or 'motorway' in road_type:
                        highway_roads.add(int(road_id))
                    # Or if it has high speed AND multiple lanes AND is long enough
                    elif speed_limit and max_speed > 0 and driving_lane_count >= 2:
                        # Highway criteria: high speed + multiple lanes + decent length
                        if speed_limit >= max_speed * 0.9 and length > 100:  # Within 10% of max speed and >100m long
                            high_speed_roads.add(int(road_id))
                            self.logger.debug(f"Road {road_id}: {driving_lane_count} lanes, {speed_limit} km/h, {length:.0f}m - likely highway")
                    
                    # Also track straight vs curved roads
                    geometry = road_info.get('geometry', [])
                    arc_count = sum(1 for g in geometry if g.get('geometry_type') == 'arc')
                    total_count = len(geometry)
                    if total_count > 0:
                        curve_ratio = arc_count / total_count
                        if curve_ratio < 0.3:  # Less than 30% curved segments
                            straight_roads.add(int(road_id))
                        elif curve_ratio > 0.7:  # More than 70% curved segments
                            curved_roads.add(int(road_id))
                
                # FIRST: Filter for actual highway roads if any exist
                if highway_roads or high_speed_roads:
                    # Try highway roads first, then high-speed roads
                    highway_candidates = [pt for pt in candidates if pt.get('road_id') in highway_roads]
                    if not highway_candidates and high_speed_roads:
                        highway_candidates = [pt for pt in candidates if pt.get('road_id') in high_speed_roads]
                        if highway_candidates:
                            self.logger.info(f"Found {len(highway_candidates)} spawn points on high-speed roads (likely highways): {list(high_speed_roads)[:10]}")
                    
                    if highway_candidates:
                        self.logger.info(f"Found {len(highway_candidates)} spawn points on highway/high-speed roads")
                        candidates = highway_candidates
                        
                        # Further filter for straight sections of the highway
                        # Prefer spawn points that are on straight roads (from our straight_roads set)
                        if straight_roads:
                            straight_highway_candidates = [pt for pt in candidates if pt.get('road_id') in straight_roads]
                            if straight_highway_candidates:
                                self.logger.info(f"Preferring {len(straight_highway_candidates)} spawn points on straight highway sections")
                                candidates = straight_highway_candidates
                    else:
                        self.logger.warning(f"Found highway/high-speed roads but no spawn points on them")
                else:
                    # Dynamically detect highway roads from XODR file
                    detected_highways = self._detect_highway_roads(map_name)
                    if detected_highways:
                        highway_candidates = [pt for pt in candidates if pt.get('road_id') in detected_highways]
                        if highway_candidates:
                            self.logger.info(f"Using dynamically detected highway roads for {map_name}: {list(detected_highways)[:5]}... ({len(highway_candidates)} candidates)")
                            candidates = highway_candidates
                            
                            # IMPORTANT: Avoid exit/entry lanes (typically outermost lanes)
                            # Keep only the main highway lanes (typically -3, -2, -1 and 1, 2, 3)
                            main_lane_candidates = [
                                pt for pt in candidates 
                                if -3 <= pt.get('lane_id', 0) <= 3 and pt.get('lane_id', 0) != 0
                            ]
                            if main_lane_candidates:
                                self.logger.info(f"Filtered to main highway lanes (avoiding exit lanes): {len(main_lane_candidates)} candidates")
                                candidates = main_lane_candidates
                
                # THEN: Prefer straight roads among the remaining candidates
                if straight_roads:
                    straight_candidates = [pt for pt in candidates if pt.get('road_id') in straight_roads]
                    if straight_candidates:
                        self.logger.info(f"Preferring straight roads for highway: {len(straight_candidates)} candidates from roads {list(straight_roads)[:5]}")
                        candidates = straight_candidates
                    elif curved_roads:
                        # Avoid heavily curved roads if we have alternatives
                        non_curved = [pt for pt in candidates if pt.get('road_id') not in curved_roads]
                        if non_curved:
                            self.logger.info(f"Avoiding heavily curved roads: {len(non_curved)} candidates")
                            candidates = non_curved
        
        # Apply basic constraints for ego spawn
        if 'lane_id' in ego_criteria:
            lane_constraint = ego_criteria['lane_id']
            if isinstance(lane_constraint, dict):
                min_lane = lane_constraint.get('min', 1)
                max_lane = lane_constraint.get('max', 10)
                candidates = [pt for pt in candidates 
                            if min_lane <= pt.get('lane_id', 0) <= max_lane]
        
        if not candidates:
            self.logger.warning("No candidates found for ego spawn criteria, using fallback")
            return self._choose_spawn(map_name, ego_criteria)
        
        # If actors need to be ahead, choose ego position from middle/back of available positions
        # If actors need to be behind, choose ego position from front of available positions
        if needs_ahead and same_lane_actors:
            # Group candidates by road/lane
            lane_groups = {}
            for candidate in candidates:
                road_id = candidate.get('road_id')
                lane_id = candidate.get('lane_id')
                key = (road_id, lane_id)
                if key not in lane_groups:
                    lane_groups[key] = []
                lane_groups[key].append(candidate)
            
            # For each lane group, if it has enough points, choose from middle/back
            best_candidate = None
            # Sort lane groups by road_id to get deterministic results, prefer lower road IDs
            sorted_groups = sorted(lane_groups.items(), key=lambda x: (x[0][0], x[0][1]))
            
            for (road_id, lane_id), lane_candidates in sorted_groups:
                if len(lane_candidates) >= 5:  # Need at least 5 points to have room ahead
                    # Sort by position to understand spatial layout
                    sorted_candidates = sorted(lane_candidates, key=lambda pt: (pt.get('x', 0), pt.get('y', 0)))
                    
                    # Choose from positions 60-80% back to leave space ahead  
                    start_idx = len(sorted_candidates) // 3  # Skip first 33%
                    end_idx = int(len(sorted_candidates) * 0.8)  # Stop at 80%
                    strategic_candidates = sorted_candidates[start_idx:end_idx]
                    
                    if strategic_candidates:
                        # Pick a good candidate from this range
                        best_candidate = strategic_candidates[len(strategic_candidates)//2]
                        self.logger.info(f"Strategic ego spawn: chose position {start_idx}-{end_idx} of {len(sorted_candidates)} on road {road_id}, lane {lane_id}")
                        break
            
            if best_candidate:
                self._last_pick = best_candidate
                return (best_candidate.get('x', 0), best_candidate.get('y', 0), 
                       best_candidate.get('z', 0) + 0.3, math.radians(best_candidate.get('yaw', 0)))
        
        # Fallback to normal selection with filtered candidates if available
        self.logger.info("Using standard ego spawn selection")
        # If we filtered candidates for highway scenarios, pass them along
        if len(candidates) < len(spawn_points):
            # We have filtered candidates, use them
            self.logger.info(f"Using filtered candidates: {len(candidates)} points from straight roads")
            return self._legacy_choose_spawn(map_name, ego_criteria, None, None, candidates)
        else:
            return self._choose_spawn(map_name, ego_criteria)
    
    def _get_enhanced_spawn_candidates(self, pts: List[Dict], road_data: Dict) -> List[Dict]:
        """Enhance spawn candidates with road intelligence metadata"""
        enhanced_candidates = []
        
        for pt in pts:
            enhanced_pt = pt.copy()
            road_id = str(pt.get('road_id', ''))
            road_info = road_data.get('roads', {}).get(road_id, {})
            
            # Add road intelligence metadata
            enhanced_pt.update({
                'road_context': self._classify_road_context(road_info),
                'junction_distance': self._calculate_junction_distance(pt, road_data),
                'speed_limit': road_info.get('speed_limit', 40) or 40,  # Handle None values
                'curvature': self._analyze_road_curvature(road_info),
                'connectivity': self._analyze_road_connectivity(road_info)
            })
            
            enhanced_candidates.append(enhanced_pt)
        
        return enhanced_candidates
    
    def _classify_road_context(self, road_info: Dict) -> str:
        """Classify road context based on type and speed limit"""
        road_type = road_info.get('road_type', 'unknown')
        speed_limit = road_info.get('speed_limit', 0) or 0  # Handle None values
        
        if speed_limit >= 60:
            return 'highway'
        elif road_type in ['town', 'city'] and speed_limit <= 50:
            return 'urban'
        elif 30 <= speed_limit <= 60:
            return 'suburban'
        elif road_type == 'service':
            return 'service'
        else:
            return 'unknown'
    
    def _calculate_junction_distance(self, pt: Dict, road_data: Dict) -> float:
        """Calculate distance to nearest junction"""
        junctions = road_data.get('junctions', {})
        if not junctions:
            return float('inf')
            
        point_x, point_y = pt.get('x', 0), pt.get('y', 0)
        min_distance = float('inf')
        
        for junction_data in junctions.values():
            junction_center = junction_data.get('center', {})
            jx, jy = junction_center.get('x', 0), junction_center.get('y', 0)
            distance = math.hypot(point_x - jx, point_y - jy)
            min_distance = min(min_distance, distance)
            
        return min_distance
    
    def _analyze_road_curvature(self, road_info: Dict) -> str:
        """Analyze road curvature from geometry"""
        geometry = road_info.get('geometry', [])
        has_curves = any(g.get('geometry_type') == 'arc' for g in geometry)
        return 'curved' if has_curves else 'straight'
    
    def _analyze_road_connectivity(self, road_info: Dict) -> str:
        """Analyze road connectivity"""
        predecessor = road_info.get('predecessor')
        successor = road_info.get('successor')
        
        if predecessor and successor:
            return 'well_connected'
        elif not predecessor and not successor:
            return 'isolated'
        else:
            return 'terminal'
    
    def _filter_by_road_context(self, candidates: List[Dict], crit: Dict[str, Any], map_name: str) -> List[Dict]:
        """Filter candidates by road context"""
        if 'road_context' not in crit:
            return candidates
            
        context = crit['road_context']
        return [c for c in candidates if c.get('road_context') == context]
    
    def _filter_by_junction_context(self, candidates: List[Dict], crit: Dict[str, Any], map_name: str) -> List[Dict]:
        """Filter candidates by junction proximity and type"""
        # Filter by junction proximity
        if 'junction_proximity' in crit:
            proximity = crit['junction_proximity']
            min_dist = proximity.get('min', 0)
            max_dist = proximity.get('max', 1000)
            candidates = [c for c in candidates 
                        if min_dist <= c.get('junction_distance', float('inf')) <= max_dist]
        
        # Filter by junction type
        if 'junction_type' in crit:
            junction_type = crit['junction_type']
            filtered = []
            for c in candidates:
                if self._matches_junction_type(c, junction_type, map_name):
                    filtered.append(c)
            candidates = filtered
            
        return candidates
    
    def _filter_by_road_relationships(self, candidates: List[Dict], crit: Dict[str, Any], 
                                    ego_lane: Optional[Tuple[int, int]], road_data: Dict) -> List[Dict]:
        """Filter candidates by road relationships using road intelligence"""
        if 'road_relationship' in crit:
            candidates = self._filter_by_road_relationship(candidates, crit, ego_lane)
            
        if 'lane_relationship' in crit:
            candidates = self._filter_by_lane_relationship(candidates, crit, ego_lane)
            
        return candidates
    
    def _filter_by_geometry(self, candidates: List[Dict], crit: Dict[str, Any], road_data: Dict) -> List[Dict]:
        """Filter candidates by geometric constraints"""
        if 'road_curvature' in crit:
            curvature_type = crit['road_curvature']
            if curvature_type != 'any':
                candidates = [c for c in candidates if c.get('curvature') == curvature_type]
                
        if 'speed_limit' in crit:
            speed_constraint = crit['speed_limit']
            min_speed = speed_constraint.get('min', 0)
            max_speed = speed_constraint.get('max', 1000)
            candidates = [c for c in candidates 
                        if min_speed <= (c.get('speed_limit', 0) or 0) <= max_speed]
                        
        return candidates
    
    def _apply_legacy_filters(self, candidates: List[Dict], crit: Dict[str, Any],
                            ego_pos: Optional[Tuple[float, float, float, float]] = None,
                            ego_lane: Optional[Tuple[int, int]] = None) -> List[Dict]:
        """Apply existing spawn criteria filters"""
        filtered = []
        for pt in candidates:
            if self._matches_spawn_criteria(pt, crit, ego_pos, ego_lane):
                filtered.append(pt)
        return filtered
    
    def _score_and_select_spawn(self, candidates: List[Dict], crit: Dict[str, Any],
                              ego_pos: Optional[Tuple[float, float, float, float]] = None,
                              ego_lane: Optional[Tuple[int, int]] = None,
                              road_data: Dict = None, all_pts: List[Dict] = None) -> Tuple[float, float, float, float]:
        """Score candidates and select the best spawn point"""
        # Special handling for perpendicular positioning at intersections
        if crit.get('relative_position') == 'perpendicular' and crit.get('is_intersection') and ego_pos:
            self.logger.info("Looking for perpendicular spawn at intersection")
            perpendicular_candidates = []
            for pt in candidates:
                rel_pos = self._get_relative_position(ego_pos, pt)
                if rel_pos == 'perpendicular':
                    dist = math.hypot(pt.get('x', 0) - ego_pos[0], pt.get('y', 0) - ego_pos[1])
                    if dist >= 5.0:  # Minimum safety distance
                        perpendicular_candidates.append(pt)
                        self.logger.debug(f"Found perpendicular candidate at ({pt.get('x'):.1f}, {pt.get('y'):.1f})")
            
            if perpendicular_candidates:
                candidates = perpendicular_candidates
                self.logger.info(f"Filtered to {len(perpendicular_candidates)} perpendicular candidates")
        
        # First, filter out candidates that are too close to ego (< 5m)
        if ego_pos and candidates:
            safe_candidates = []
            for pt in candidates:
                dist = math.hypot(pt.get('x', 0) - ego_pos[0], pt.get('y', 0) - ego_pos[1])
                if dist >= 5.0:  # Minimum 5m distance from ego
                    safe_candidates.append(pt)
                else:
                    self.logger.warning(f"Rejecting spawn at distance {dist:.1f}m from ego (too close)")
            candidates = safe_candidates
        
        if not candidates:
            # Apply fallback strategy
            if all_pts:
                candidates = self._apply_fallback_strategy([], [], all_pts, crit, ego_pos, ego_lane)
                # Filter fallback candidates too
                if ego_pos and candidates:
                    safe_candidates = []
                    rejected_close = 0
                    for pt in candidates:
                        dist = math.hypot(pt.get('x', 0) - ego_pos[0], pt.get('y', 0) - ego_pos[1])
                        if dist >= 5.0:
                            safe_candidates.append(pt)
                        else:
                            rejected_close += 1
                    
                    if rejected_close > 0:
                        self.logger.warning(f"Rejected {rejected_close} fallback candidates that were too close to ego (< 5m)")
                    candidates = safe_candidates
            
            # If still no candidates, try one more time with very relaxed constraints
            if not candidates and all_pts and ego_pos:
                self.logger.warning("All fallbacks failed, trying emergency fallback with basic distance constraints")
                emergency_candidates = []
                # Check more points and allow wider distance range
                for pt in all_pts[:500]:  # Check more points
                    dist = math.hypot(pt.get('x', 0) - ego_pos[0], pt.get('y', 0) - ego_pos[1])
                    # Use scenario-appropriate max distance
                    max_dist = 50 if 'pedestrian' in str(crit).lower() else 150
                    if 10 <= dist <= max_dist:  # At least 10m away for safety
                        emergency_candidates.append(pt)
                    if len(emergency_candidates) >= 20:  # Get more candidates
                        break
                
                if emergency_candidates:
                    # Sort by distance and pick best ones
                    emergency_candidates.sort(key=lambda p: abs(math.hypot(p.get('x', 0) - ego_pos[0], p.get('y', 0) - ego_pos[1]) - 30))
                    candidates = emergency_candidates[:10]
                    self.logger.info(f"Emergency fallback found {len(candidates)} candidates")
            
            if not candidates:
                # For highway scenarios, try one more desperate fallback before giving up
                # Check if this is a highway scenario by looking at the selected map
                is_highway = self._selected_map in ['Town04', 'Town05', 'Town03']
                if is_highway and hasattr(self, '_allow_final_fallback') and self._allow_final_fallback:
                    self.logger.warning("Highway scenario: attempting ultra-relaxed fallback for actor spawn")
                    # Try to find ANY driving lane spawn on the same road at reasonable distance
                    ultra_relaxed_crit = {
                        'lane_type': 'Driving',
                        'distance_to_ego': {'min': 20, 'max': 150}  # Very wide range
                    }
                    if ego_lane and 'road_relationship' in crit:
                        ultra_relaxed_crit['road_relationship'] = 'same_road'
                    
                    # Get all spawn points for this map
                    if all_pts:
                        candidates = self._apply_relaxed_criteria(all_pts, ultra_relaxed_crit, ego_pos, ego_lane)
                    if candidates:
                        self.logger.info(f"Ultra-relaxed fallback found {len(candidates)} candidates for highway scenario")
                    
                if not candidates:
                    # Provide detailed error message to help debug the issue
                    error_msg = f"No valid spawn points found for actor. "
                    if ego_pos:
                        error_msg += f"All candidate spawns were too close to ego (< 5m). "
                    error_msg += f"Criteria: {crit}. "
                    error_msg += "Try: 1) Increasing distance range, 2) Relaxing lane constraints, 3) Using a different map, or 4) Checking spawn data availability."
                    raise RuntimeError(error_msg)
        
        if len(candidates) == 1:
            pick = candidates[0]
        else:
            # Score candidates with enhanced scoring including road intelligence
            scored_candidates = [(self._enhanced_score_spawn_point(pt, crit, ego_pos, ego_lane, road_data), pt) 
                               for pt in candidates]
            scored_candidates.sort(reverse=True, key=lambda x: x[0])
            pick = scored_candidates[0][1]
        
        self._last_pick = pick
        self._log_enhanced_spawn_decision(pick, ego_pos, ego_lane, crit, road_data)
        
        # Apply lateral offset if this was a fallback lane type
        x, y, z, yaw = pick['x'], pick['y'], pick['z'], math.radians(pick['yaw'])
        
        # Add proper z-offset to ensure vehicles spawn above ground (prevents getting stuck)
        # Use 0.3m for safety - enough to clear ground but not so high that vehicles get damaged
        z += 0.3  # Lift vehicle 30cm above road surface
        
        if 'lateral_offset_fallback' in pick:
            offset = pick['lateral_offset_fallback']
            # Apply offset perpendicular to the heading direction
            x += offset * math.cos(yaw + math.pi/2)
            y += offset * math.sin(yaw + math.pi/2)
            self.logger.info(f"Applied lateral offset of {offset}m to position due to lane type fallback")
        
        # Only apply explicit lateral_offset if we didn't get the exact lane type requested
        # (i.e., if we're using a fallback or want fine-tuning within the same lane)
        if 'lateral_offset' in crit:
            # Check if we got the exact lane type requested
            requested_lane_type = crit.get('lane_type')
            actual_lane_type = pick.get('lane_type')
            
            # Only apply offset if it's a different lane type or explicitly a fallback
            if 'lateral_offset_fallback' in pick or (requested_lane_type and actual_lane_type and 
                                                      requested_lane_type.lower() != actual_lane_type.lower()):
                extra_offset = crit['lateral_offset']
                x += extra_offset * math.cos(yaw + math.pi/2)
                y += extra_offset * math.sin(yaw + math.pi/2)
                self.logger.info(f"Applied additional lateral offset of {extra_offset}m from criteria (lane type mismatch)")
            else:
                self.logger.info(f"Skipping lateral_offset from criteria - already on correct {actual_lane_type} lane")
        
        return x, y, z, yaw
    
    def _enhanced_score_spawn_point(self, pt: Dict, crit: Dict[str, Any],
                                  ego_pos: Optional[Tuple[float, float, float, float]] = None,
                                  ego_lane: Optional[Tuple[int, int]] = None,
                                  road_data: Dict = None) -> float:
        """Enhanced scoring that includes road intelligence factors"""
        score = self._score_spawn_point(pt, crit, ego_pos, ego_lane)  # Base score
        
        # Add road intelligence bonuses
        if 'road_context' in crit and pt.get('road_context') == crit['road_context']:
            score += 50
            
        if 'junction_type' in crit:
            # Bonus for correct junction type proximity
            map_name = None  # We need to pass this through
            # For now, skip junction type bonus in enhanced scoring
            pass
            
        if 'road_curvature' in crit and pt.get('curvature') == crit['road_curvature']:
            score += 30
            
        if 'speed_limit' in crit:
            speed_constraint = crit['speed_limit']
            actual_speed = pt.get('speed_limit', 0) or 0  # Handle None values
            target_min = speed_constraint.get('min', 0)
            target_max = speed_constraint.get('max', 1000)
            if target_min <= actual_speed <= target_max:
                score += 25
                
        return score
    
    def _log_enhanced_spawn_decision(self, selected_spawn: Dict, 
                                   ego_pos: Optional[Tuple[float, float, float, float]], 
                                   ego_lane: Optional[Tuple[int, int]], 
                                   criteria: Dict[str, Any],
                                   road_data: Dict = None):
        """Enhanced logging with road intelligence information"""
        self._log_spawn_decision(selected_spawn, ego_pos, ego_lane, criteria)  # Base logging
        
        # Add road intelligence logging
        self.logger.info(f"Road Intelligence:")
        self.logger.info(f"  Road context: {selected_spawn.get('road_context', 'unknown')}")
        
        junction_distance = selected_spawn.get('junction_distance', 'unknown')
        if isinstance(junction_distance, (int, float)):
            self.logger.info(f"  Junction distance: {junction_distance:.1f}m")
        else:
            self.logger.info(f"  Junction distance: {junction_distance}")
            
        self.logger.info(f"  Speed limit: {selected_spawn.get('speed_limit', 'unknown')} km/h")
        self.logger.info(f"  Curvature: {selected_spawn.get('curvature', 'unknown')}")
        self.logger.info(f"  Connectivity: {selected_spawn.get('connectivity', 'unknown')}")
    
    def _matches_spawn_criteria(self, pt: Dict, crit: Dict[str, Any], 
                               ego_pos: Optional[Tuple[float, float, float, float]] = None,
                               ego_lane: Optional[Tuple[int, int]] = None) -> bool:
        """Check if a spawn point matches the given criteria"""
        # Road ID matching with same_as_ego support
        if 'road_id' in crit:
            rid = crit['road_id']
            if rid == 'same_as_ego':
                if not ego_lane:
                    return True  # Skip check if ego not positioned yet
                rid = ego_lane[0]
            if isinstance(rid, list):
                if pt.get('road_id') not in rid:
                    return False
            elif rid != 'same_as_ego' and pt.get('road_id') != rid:
                return False
        
        # Lane ID matching with enhanced same_as_ego and adjacent support
        if 'lane_id' in crit:
            lid = crit['lane_id']
            if lid == 'same_as_ego':
                if not ego_lane:
                    return True
                lid = ego_lane[1]
            elif lid == 'adjacent' and ego_lane:
                # Adjacent means same road, lane_id differs by ±1
                if not self._are_lanes_adjacent(ego_lane, (pt.get('road_id'), pt.get('lane_id'))):
                    return False
            elif isinstance(lid, list):
                if pt.get('lane_id') not in lid:
                    return False
            elif isinstance(lid, dict):
                if not (lid.get('min', float('-inf')) <= pt.get('lane_id', 0) <= lid.get('max', float('inf'))):
                    return False
            elif lid not in ['same_as_ego', 'adjacent'] and pt.get('lane_id') != lid:
                return False
        
        # Lane type filtering (case-insensitive)
        if 'lane_type' in crit:
            valid_types = crit['lane_type'] if isinstance(crit['lane_type'], list) else [crit['lane_type']]
            valid_types_lower = [vt.lower() if isinstance(vt, str) else vt for vt in valid_types]
            pt_lane_type = pt.get('lane_type', '')
            if isinstance(pt_lane_type, str) and pt_lane_type.lower() not in valid_types_lower:
                return False
        
        # Lane relationship filtering (critical for cut-in scenarios)
        if 'lane_relationship' in crit and ego_lane:
            relationship = crit['lane_relationship']
            if relationship == 'same_lane':
                if pt.get('road_id') != ego_lane[0] or pt.get('lane_id') != ego_lane[1]:
                    return False
            elif relationship == 'adjacent_lane':
                # Adjacent lanes must be on same road with lane_id differing by ±1 and same direction
                if pt.get('road_id') != ego_lane[0]:
                    return False
                pt_lane_id = pt.get('lane_id', 0)
                ego_lane_id = ego_lane[1]
                if not (abs(pt_lane_id - ego_lane_id) == 1 and 
                       self._are_same_direction_lanes(ego_lane_id, pt_lane_id)):
                    return False
            elif relationship == 'different_lane':
                if pt.get('road_id') == ego_lane[0] and pt.get('lane_id') == ego_lane[1]:
                    return False
            # 'any_lane' has no filtering
        
        # Road relationship filtering
        if 'road_relationship' in crit and ego_lane:
            road_rel = crit['road_relationship']
            if road_rel == 'same_road':
                if pt.get('road_id') != ego_lane[0]:
                    return False
            elif road_rel == 'different_road':
                if pt.get('road_id') == ego_lane[0]:
                    return False
        
        # Intersection filtering with default to avoid intersections
        if 'is_intersection' in crit:
            intersection_filter = crit['is_intersection']
            pt_is_intersection = pt.get('is_intersection', False)  # Default spawn to non-intersection if not specified
            if pt_is_intersection != intersection_filter:
                return False
        
        # Heading tolerance
        if 'heading_tol' in crit and ego_pos:
            pt_yaw = pt.get('yaw', 0)
            dyaw = abs((pt_yaw - math.degrees(ego_pos[3]) + 180) % 360 - 180)
            if dyaw > crit['heading_tol']:
                return False
        
        # Relative position (ahead/behind/perpendicular with improved accuracy)
        if 'relative_position' in crit and ego_pos:
            rel_pos = self._get_relative_position(ego_pos, pt)
            expected_pos = crit['relative_position']
            if expected_pos == 'adjacent':
                # For adjacent, check lateral displacement
                if not self._is_laterally_adjacent(ego_pos, pt):
                    return False
            elif expected_pos == 'perpendicular':
                # For perpendicular, be less strict in initial filtering
                # We'll do finer selection in _score_and_select_spawn
                pass  # Don't filter out non-perpendicular here
            elif expected_pos in ['ahead', 'behind']:
                if rel_pos != expected_pos:
                    return False
        
        # Distance to arbitrary target
        if 'distance_to' in crit:
            tgt = crit['distance_to']
            d = math.hypot(pt.get('x', 0) - tgt.get('x', 0), pt.get('y', 0) - tgt.get('y', 0))
            if d > tgt.get('max', float('inf')):
                return False
        
        # Additional topology constraints using road intelligence
        if hasattr(self, '_selected_map') and self._selected_map:
            road_data = self.road_intelligence.get(self._selected_map, {})
            if road_data:
                # Speed zone compatibility
                if 'avoid_highways' in crit and crit['avoid_highways']:
                    road_info = road_data.get('roads', {}).get(str(pt.get('road_id', '')), {})
                    speed_limit = road_info.get('speed_limit', 0) or 0
                    if speed_limit >= 60:  # Highway speed
                        return False
                
                # Service road filtering
                if 'avoid_service_roads' in crit and crit['avoid_service_roads']:
                    road_info = road_data.get('roads', {}).get(str(pt.get('road_id', '')), {})
                    road_type = road_info.get('road_type', 'unknown')
                    if road_type == 'service':
                        return False
        
        return True
    
    def _are_lanes_adjacent(self, ego_lane: Tuple[int, int], candidate_lane: Tuple[int, int]) -> bool:
        """Check if two lanes are adjacent (same road, lane_id differs by ±1)"""
        if not ego_lane or not candidate_lane:
            return False
        road_id_ego, lane_id_ego = ego_lane
        road_id_candidate, lane_id_candidate = candidate_lane
        
        return (road_id_ego == road_id_candidate and 
                abs(lane_id_ego - lane_id_candidate) == 1)
    
    def _are_same_direction_lanes(self, ego_lane_id: int, candidate_lane_id: int) -> bool:
        """Check if two lane IDs represent lanes with same traffic direction"""
        # In OpenDRIVE, negative lane IDs are typically right-hand traffic direction
        # Positive lane IDs are typically left-hand traffic direction
        # Same direction means same sign (both positive or both negative)
        if ego_lane_id == 0 or candidate_lane_id == 0:
            return True  # Center lane (reference line) is compatible with both directions
        return (ego_lane_id > 0) == (candidate_lane_id > 0)
    
    def _get_relative_position(self, ego_pos: Tuple[float, float, float, float], pt: Dict) -> str:
        """Get relative position (ahead/behind/perpendicular) with improved accuracy"""
        dx = pt.get('x', 0) - ego_pos[0]
        dy = pt.get('y', 0) - ego_pos[1]
        
        # Use spawn point's yaw if available to determine lane direction
        pt_yaw = pt.get('yaw', 0)  # In degrees
        ego_yaw = math.degrees(ego_pos[3])  # Convert to degrees
        
        # Check angle between ego heading and vector to point
        angle_to_point = math.atan2(dy, dx)
        ego_heading_rad = ego_pos[3]
        
        # Debug logging for perpendicular detection
        if hasattr(self, 'logger'):
            self.logger.debug(f"Relative position calc: ego=({ego_pos[0]:.1f},{ego_pos[1]:.1f}) pt=({pt.get('x',0):.1f},{pt.get('y',0):.1f}) "
                            f"ego_heading={math.degrees(ego_heading_rad):.1f}° angle_to_pt={math.degrees(angle_to_point):.1f}°")
        
        # Calculate angle difference (normalized to -pi to pi)
        angle_diff = angle_to_point - ego_heading_rad
        while angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        while angle_diff < -math.pi:
            angle_diff += 2 * math.pi
        
        # Check if perpendicular (roughly 90 degrees to either side)
        angle_diff_deg = abs(math.degrees(angle_diff))
        if 60 <= angle_diff_deg <= 120:  # Within 30 degrees of perpendicular
            self.logger.debug(f"Detected perpendicular: angle_diff={angle_diff_deg:.1f}°")
            return 'perpendicular'
        
        # Check if vehicles are facing similar directions (within 90 degrees)
        yaw_diff = abs((pt_yaw - ego_yaw + 180) % 360 - 180)
        same_direction = yaw_diff < 90
        
        # Project along ego's heading direction for ahead/behind
        proj = math.cos(ego_pos[3]) * dx + math.sin(ego_pos[3]) * dy
        
        if same_direction:
            # Same direction lanes: ahead means positive projection
            return 'ahead' if proj > 0 else 'behind'
        else:
            # Opposite direction lanes: ahead means negative projection
            return 'ahead' if proj < 0 else 'behind'
    
    def _is_laterally_adjacent(self, ego_pos: Tuple[float, float, float, float], pt: Dict) -> bool:
        """Check if point is laterally adjacent (perpendicular to ego heading)"""
        dx = pt.get('x', 0) - ego_pos[0]
        dy = pt.get('y', 0) - ego_pos[1]
        # Project perpendicular to ego's heading
        lateral_proj = abs(-math.sin(ego_pos[3]) * dx + math.cos(ego_pos[3]) * dy)
        longitudinal_proj = abs(math.cos(ego_pos[3]) * dx + math.sin(ego_pos[3]) * dy)
        # Adjacent if lateral displacement is significant but longitudinal is small
        return lateral_proj > 3.0 and longitudinal_proj < 10.0
    
    def _score_spawn_point(self, pt: Dict, crit: Dict[str, Any], 
                          ego_pos: Optional[Tuple[float, float, float, float]] = None,
                          ego_lane: Optional[Tuple[int, int]] = None) -> float:
        """Score a spawn point based on how well it matches criteria (higher = better)"""
        score = 0.0
        
        # Distance accuracy scoring
        if 'distance_to_ego' in crit and ego_pos:
            actual_distance = math.hypot(pt.get('x', 0) - ego_pos[0], pt.get('y', 0) - ego_pos[1])
            target_min = crit['distance_to_ego'].get('min', 0)
            target_max = crit['distance_to_ego'].get('max', 1e9)
            target_center = (target_min + target_max) / 2
            
            # Perfect score if at target center, decreases with distance from center
            distance_error = abs(actual_distance - target_center)
            max_error = (target_max - target_min) / 2
            if max_error > 0:
                distance_score = max(0, 100 - (distance_error / max_error) * 100)
                score += distance_score
        
        # Lane relationship scoring
        if ego_lane and pt.get('road_id') is not None:
            # Check if we want different road (for perpendicular/crossing scenarios)
            if crit.get('road_relationship') == 'different_road':
                if pt.get('road_id') != ego_lane[0]:
                    score += 50  # Different road bonus for crossing scenarios
            elif pt.get('road_id') == ego_lane[0]:
                score += 50  # Same road bonus
                if pt.get('lane_id') == ego_lane[1]:
                    score += 25  # Same lane bonus
                elif abs(pt.get('lane_id', 0) - ego_lane[1]) == 1:
                    score += 15  # Adjacent lane bonus
        
        # Relative position accuracy scoring
        if 'relative_position' in crit and ego_pos:
            actual_rel_pos = self._get_relative_position(ego_pos, pt)
            expected_rel_pos = crit['relative_position']
            if actual_rel_pos == expected_rel_pos:
                score += 50  # Higher score for exact match
            elif expected_rel_pos == 'perpendicular' and actual_rel_pos in ['ahead', 'behind']:
                # Partial credit if looking for perpendicular but found ahead/behind
                score += 10
            elif expected_rel_pos == 'adjacent':
                score += 30
        
        # Intersection preference scoring
        if 'is_intersection' in crit:
            if pt.get('is_intersection') == crit['is_intersection']:
                score += 20
        
        # Lane type preference scoring
        if 'lane_type' in crit:
            valid_types = crit['lane_type'] if isinstance(crit['lane_type'], list) else [crit['lane_type']]
            if pt.get('lane_type') in valid_types:
                score += 10
        
        return score
    
    def _apply_fallback_strategy(self, filtered_candidates: List[Dict], 
                               candidates: List[Dict], 
                               all_points: List[Dict],
                               crit: Dict[str, Any],
                               ego_pos: Optional[Tuple[float, float, float, float]] = None,
                               ego_lane: Optional[Tuple[int, int]] = None) -> List[Dict]:
        """Apply progressive fallback strategy with explicit road/lane relationship relaxation"""
        if filtered_candidates:
            return filtered_candidates
        
        self.logger.warning(f"No perfect matches found, applying fallbacks for criteria: {crit}")
        
        # Fallback 1: Relax lane_relationship (highest priority after road)
        if 'lane_relationship' in crit and crit['lane_relationship'] == 'same_lane':
            relaxed_crit = crit.copy()
            relaxed_crit['lane_relationship'] = 'adjacent_lane'
            
            fallback_candidates = self._apply_relaxed_criteria(all_points, relaxed_crit, ego_pos, ego_lane)
            if fallback_candidates:
                self.logger.info(f"Fallback 1 (same_lane -> adjacent_lane): found {len(fallback_candidates)} candidates")
                return fallback_candidates
        
        # Fallback 2: For adjacent_lane, try relaxing distance FIRST before changing lanes
        if 'lane_relationship' in crit and crit['lane_relationship'] == 'adjacent_lane' and 'distance_to_ego' in crit and ego_pos:
            relaxed_crit = crit.copy()
            # Keep adjacent_lane but dramatically relax distance
            original_min = crit['distance_to_ego'].get('min', 0)
            original_max = crit['distance_to_ego'].get('max', 1000)
            
            # Try progressively larger distance ranges
            distance_expansions = [
                (0.5, 1.5),   # 50% reduction, 50% expansion
                (0.25, 2.0),  # 75% reduction, 100% expansion
                (0.1, 3.0),   # 90% reduction, 200% expansion
            ]
            
            for min_factor, max_factor in distance_expansions:
                relaxed_crit['distance_to_ego'] = {
                    'min': max(5, original_min * min_factor),
                    'max': min(200, original_max * max_factor)  # Cap at 200m
                }
                
                fallback_candidates = self._apply_relaxed_criteria(all_points, relaxed_crit, ego_pos, ego_lane)
                if fallback_candidates:
                    # Sort by distance to prefer closer to original range
                    def distance_score(pt):
                        d = math.hypot(pt.get('x', 0) - ego_pos[0], pt.get('y', 0) - ego_pos[1])
                        if original_min <= d <= original_max:
                            return 0  # Perfect
                        else:
                            # Distance from the original range
                            if d < original_min:
                                return (original_min - d) / original_min
                            else:
                                return (d - original_max) / original_max
                    
                    fallback_candidates.sort(key=distance_score)
                    actual_dist = math.hypot(fallback_candidates[0].get('x', 0) - ego_pos[0], 
                                           fallback_candidates[0].get('y', 0) - ego_pos[1])
                    self.logger.info(f"Fallback 2 (adjacent_lane with relaxed distance {relaxed_crit['distance_to_ego']['min']:.0f}-{relaxed_crit['distance_to_ego']['max']:.0f}m): "
                                   f"found {len(fallback_candidates)} candidates, best at {actual_dist:.1f}m")
                    return fallback_candidates[:5]  # Return top 5 candidates
            
        # Fallback 2b: Relax lane_relationship further (only if not adjacent_lane or distance relaxation failed)
        if 'lane_relationship' in crit and crit['lane_relationship'] in ['same_lane', 'adjacent_lane']:
            relaxed_crit = crit.copy()
            relaxed_crit['lane_relationship'] = 'any_lane'
            
            fallback_candidates = self._apply_relaxed_criteria(all_points, relaxed_crit, ego_pos, ego_lane)
            if fallback_candidates:
                self.logger.info(f"Fallback 2b (lane_relationship -> any_lane): found {len(fallback_candidates)} candidates")
                return fallback_candidates
        
        # Skip relaxing road_relationship - it's critical for spawn safety
        # Instead, try relaxing other non-critical constraints first
        
        # Fallback 3: Find closest spawn that meets other criteria, prioritizing original distance
        if 'distance_to_ego' in crit and ego_pos:
            relaxed_crit = crit.copy()
            distance_constraint = relaxed_crit['distance_to_ego'].copy()
            
            current_min = distance_constraint.get('min', 0)
            current_max = distance_constraint.get('max', 1000)
            
            # First try modest expansion (25%)
            range_expansion = (current_max - current_min) * 0.25
            distance_constraint['min'] = max(5, current_min - range_expansion)
            distance_constraint['max'] = current_max + range_expansion
            relaxed_crit['distance_to_ego'] = distance_constraint
            
            fallback_candidates = self._apply_relaxed_criteria(all_points, relaxed_crit, ego_pos, ego_lane)
            if fallback_candidates:
                # Sort by how close they are to the original desired range
                def distance_score(pt):
                    d = math.hypot(pt.get('x', 0) - ego_pos[0], pt.get('y', 0) - ego_pos[1])
                    if current_min <= d <= current_max:
                        return 0  # Perfect
                    elif d < current_min:
                        return current_min - d  # Penalty for being too close
                    else:
                        return d - current_max  # Penalty for being too far
                
                fallback_candidates.sort(key=distance_score)
                self.logger.info(f"Fallback 3 (expanded distance {current_min}-{current_max} -> {distance_constraint['min']:.1f}-{distance_constraint['max']:.1f}): found {len(fallback_candidates)} candidates")
                return fallback_candidates
            
            # If still no candidates, try larger expansion (50%) but warn
            range_expansion = (current_max - current_min) * 0.5
            distance_constraint['min'] = max(5, current_min - range_expansion)
            distance_constraint['max'] = current_max + range_expansion * 2  # Allow more expansion on the far side
            relaxed_crit['distance_to_ego'] = distance_constraint
            
            fallback_candidates = self._apply_relaxed_criteria(all_points, relaxed_crit, ego_pos, ego_lane)
            if fallback_candidates:
                # Sort to prefer spawns closest to original range
                def distance_score(pt):
                    d = math.hypot(pt.get('x', 0) - ego_pos[0], pt.get('y', 0) - ego_pos[1])
                    if current_min <= d <= current_max:
                        return 0
                    elif d < current_min:
                        return (current_min - d) * 2  # Higher penalty for too close
                    else:
                        return d - current_max
                
                fallback_candidates.sort(key=distance_score)
                self.logger.warning(f"Fallback 3b (large distance expansion {current_min}-{current_max} -> {distance_constraint['min']:.1f}-{distance_constraint['max']:.1f}): found {len(fallback_candidates)} candidates")
                return fallback_candidates[:10]  # Limit to best 10 to avoid very bad spawns
        
        # Fallback 4: Ignore intersection requirements
        if 'is_intersection' in crit:
            relaxed_crit = crit.copy()
            del relaxed_crit['is_intersection']
            
            fallback_candidates = self._apply_relaxed_criteria(all_points, relaxed_crit, ego_pos, ego_lane)
            if fallback_candidates:
                self.logger.info(f"Fallback 4 (relaxed intersection): found {len(fallback_candidates)} candidates")
                return fallback_candidates
        
        # Fallback 5: For Shoulder lanes with same_road, try relaxing road constraint first
        # (Shoulder lanes are rare and might not exist on the same road)
        if 'lane_type' in crit and 'Shoulder' in str(crit['lane_type']) and crit.get('road_relationship') == 'same_road':
            relaxed_crit = crit.copy()
            # Remove the same_road constraint for Shoulder lanes
            if 'road_relationship' in relaxed_crit:
                del relaxed_crit['road_relationship']
            
            fallback_candidates = self._apply_relaxed_criteria(all_points, relaxed_crit, ego_pos, ego_lane)
            if fallback_candidates:
                self.logger.info(f"Fallback 5 (Shoulder lane without road constraint): found {len(fallback_candidates)} candidates")
                return fallback_candidates
        
        # Fallback 6: Only as last resort, relax road relationship for other cases
        if 'road_relationship' in crit and crit['road_relationship'] in ['same_road', 'different_road']:
            relaxed_crit = crit.copy()
            relaxed_crit['road_relationship'] = 'any_road'
            
            fallback_candidates = self._apply_relaxed_criteria(all_points, relaxed_crit, ego_pos, ego_lane)
            if fallback_candidates:
                self.logger.warning(f"Fallback 6 (LAST RESORT - road_relationship -> any_road): found {len(fallback_candidates)} candidates")
                return fallback_candidates
        
        # NO FINAL FALLBACK - Instead, raise error to try next map
        # This ensures we try other maps before compromising constraints
        if hasattr(self, '_allow_final_fallback') and self._allow_final_fallback:
            # Only use final fallback if explicitly allowed (last map attempt)
            if all_points and ego_pos:
                self.logger.warning("Using final fallback: any valid spawn point with distance constraints")
                # Apply at least a basic distance filter for safety
                safe_fallback = []
                
                # Try to respect original distance constraints if present
                min_dist = crit.get('distance_to_ego', {}).get('min', 5)
                max_dist = crit.get('distance_to_ego', {}).get('max', 100)
                
                # For final fallback, be more generous with distance
                max_dist = max_dist * 2  # Double the max distance as last resort
                
                for pt in all_points[:500]:  # Check more points for better matches
                    d = math.hypot(pt.get('x', 0) - ego_pos[0], pt.get('y', 0) - ego_pos[1])
                    if min_dist <= d <= max_dist:
                        safe_fallback.append(pt)
                    if len(safe_fallback) >= 30:  # Get more candidates for better selection
                        break
                
                if safe_fallback:
                    self.logger.info(f"Final fallback found {len(safe_fallback)} candidates")
                    return safe_fallback
            elif all_points:
                return all_points[:30]  # No ego position, return first 30
        
        # Don't use final fallback - let it fail so we can try next map
        return []
    
    def _apply_relaxed_criteria(self, all_points: List[Dict], relaxed_crit: Dict[str, Any],
                               ego_pos: Optional[Tuple[float, float, float, float]] = None,
                               ego_lane: Optional[Tuple[int, int]] = None) -> List[Dict]:
        """Apply relaxed criteria with the new priority system"""
        candidates = all_points
        
        # Apply filters in priority order
        if 'road_relationship' in relaxed_crit:
            candidates = self._filter_by_road_relationship(candidates, relaxed_crit, ego_lane)
        
        if 'lane_relationship' in relaxed_crit:
            candidates = self._filter_by_lane_relationship(candidates, relaxed_crit, ego_lane)
        
        if 'lane_type' in relaxed_crit:
            # Use intelligent lane type filtering with fallbacks for relaxed criteria too
            road_context = self._get_road_context_from_criteria(relaxed_crit, ego_lane, 'unknown')
            candidates = self._filter_by_lane_type_with_fallbacks(candidates, relaxed_crit, road_context)
        
        if 'distance_to_ego' in relaxed_crit and ego_pos:
            distance_filtered = []
            for pt in candidates:
                d = math.hypot(pt.get('x', 0) - ego_pos[0], pt.get('y', 0) - ego_pos[1])
                low = relaxed_crit['distance_to_ego'].get('min', 0)
                hi = relaxed_crit['distance_to_ego'].get('max', 1000)
                if low <= d <= hi:
                    distance_filtered.append(pt)
            candidates = distance_filtered
        
        # Apply remaining criteria
        final_candidates = []
        for pt in candidates:
            if self._matches_spawn_criteria(pt, relaxed_crit, ego_pos, ego_lane):
                final_candidates.append(pt)
        
        return final_candidates
    
    def _filter_by_road_relationship(self, candidates: List[Dict], crit: Dict[str, Any], ego_lane: Optional[Tuple[int, int]]) -> List[Dict]:
        """Filter spawn points based on road relationship to ego vehicle"""
        relationship = crit['road_relationship']
        ego_road_id = ego_lane[0] if ego_lane else None
        
        if relationship == 'same_road' and ego_road_id is not None:
            result = [pt for pt in candidates if pt.get('road_id') == ego_road_id]
            self.logger.debug(f"Road relationship 'same_road': filtering to road_id={ego_road_id}")
            return result
        elif relationship == 'different_road' and ego_road_id is not None:
            result = [pt for pt in candidates if pt.get('road_id') != ego_road_id]
            self.logger.debug(f"Road relationship 'different_road': excluding road_id={ego_road_id}")
            return result
        else:  # 'any_road' or ego not positioned yet
            self.logger.debug(f"Road relationship '{relationship}': no filtering")
            return candidates
    
    def _filter_by_lane_relationship(self, candidates: List[Dict], crit: Dict[str, Any], ego_lane: Optional[Tuple[int, int]]) -> List[Dict]:
        """Filter spawn points based on lane relationship to ego vehicle with direction awareness"""
        relationship = crit['lane_relationship'] 
        ego_road_id, ego_lane_id = ego_lane if ego_lane else (None, None)
        
        if relationship == 'same_lane' and ego_lane:
            result = [pt for pt in candidates 
                    if pt.get('road_id') == ego_road_id and pt.get('lane_id') == ego_lane_id]
            self.logger.debug(f"Lane relationship 'same_lane': filtering to road_id={ego_road_id}, lane_id={ego_lane_id}")
            return result
        elif relationship == 'adjacent_lane' and ego_lane:
            # For adjacent lanes, ensure same direction by default (same sign of lane_id)
            adjacent_candidates = []
            
            # Check if this is a highway scenario (to avoid exit lanes)
            # We check both the stored scenario type and if the current road is a detected highway
            is_highway = (hasattr(self, '_current_scenario_type') and self._current_scenario_type == 'highway')
            
            # Also check if we're on a dynamically detected highway road
            if not is_highway and hasattr(self, '_selected_map') and self._selected_map:
                detected_highways = self._detect_highway_roads(self._selected_map)
                if ego_road_id in detected_highways:
                    is_highway = True
                    
            if is_highway:
                self.logger.info(f"Highway road detected (road {ego_road_id}) - will filter exit lanes for adjacent lane selection")
            
            # First try to find lanes with delta of ±1
            for pt in candidates:
                if pt.get('road_id') == ego_road_id:
                    pt_lane_id = pt.get('lane_id', 0)
                    
                    # For highways, avoid exit lanes (typically -4, 4 or beyond)
                    if is_highway and abs(pt_lane_id) > 3:
                        self.logger.debug(f"Skipping exit lane {pt_lane_id} for highway scenario")
                        continue
                    
                    # Adjacent means distance of 1 AND same direction (same sign)
                    if (abs(pt_lane_id - ego_lane_id) == 1 and 
                        self._are_same_direction_lanes(ego_lane_id, pt_lane_id)):
                        adjacent_candidates.append(pt)
            
            # If no lanes found with ±1, try ±2 as fallback
            if not adjacent_candidates:
                self.logger.warning(f"No adjacent lanes with ±1 delta found, trying ±2 delta for road_id={ego_road_id}, lane_id={ego_lane_id}")
                for pt in candidates:
                    if pt.get('road_id') == ego_road_id:
                        pt_lane_id = pt.get('lane_id', 0)
                        
                        # For highways, still avoid exit lanes in fallback
                        if is_highway and abs(pt_lane_id) > 3:
                            continue
                        
                        # Try distance of 2 with same direction
                        if (abs(pt_lane_id - ego_lane_id) == 2 and 
                            self._are_same_direction_lanes(ego_lane_id, pt_lane_id)):
                            adjacent_candidates.append(pt)
            
            # If still no lanes found, allow same lane as last resort
            if not adjacent_candidates:
                self.logger.warning(f"No adjacent lanes found with ±1 or ±2 delta, falling back to same lane for road_id={ego_road_id}, lane_id={ego_lane_id}")
                for pt in candidates:
                    if pt.get('road_id') == ego_road_id and pt.get('lane_id') == ego_lane_id:
                        adjacent_candidates.append(pt)
            
            self.logger.debug(f"Lane relationship 'adjacent_lane': found {len(adjacent_candidates)} candidates for road_id={ego_road_id}, lanes adjacent to {ego_lane_id}")
            return adjacent_candidates
        elif relationship == 'any_lane' and ego_lane:
            # For any_lane, still respect direction unless explicitly overridden
            # Filter to same road and same direction lanes only
            direction_filtered = []
            for pt in candidates:
                if pt.get('road_id') == ego_road_id:
                    pt_lane_id = pt.get('lane_id', 0)
                    # Only accept same direction lanes
                    if self._are_same_direction_lanes(ego_lane_id, pt_lane_id):
                        direction_filtered.append(pt)
            
            self.logger.debug(f"Lane relationship 'any_lane': filtered to {len(direction_filtered)} same-direction candidates for road_id={ego_road_id}")
            return direction_filtered if direction_filtered else candidates  # Fallback to all if none found
        else:  # ego not positioned yet
            self.logger.debug(f"Lane relationship '{relationship}': no filtering (ego not positioned)")
            return candidates
    
    def _infer_road_lane_from_position(self, x: float, y: float, map_name: str) -> Optional[Tuple[int, int]]:
        """Infer road and lane IDs from world coordinates by finding closest spawn point"""
        spawn_points = self._get_spawn_points_for_map(map_name)
        if not spawn_points:
            self.logger.warning(f"No spawn points available for {map_name} to infer road/lane")
            return None
        
        # Find closest spawn point
        closest_point = None
        min_distance = float('inf')
        
        for pt in spawn_points:
            pt_x, pt_y = pt.get('x', 0), pt.get('y', 0)
            distance = math.hypot(x - pt_x, y - pt_y)
            if distance < min_distance:
                min_distance = distance
                closest_point = pt
        
        if closest_point and min_distance < 50.0:  # Within 50m threshold
            road_id = closest_point.get('road_id')
            lane_id = closest_point.get('lane_id')
            if road_id is not None and lane_id is not None:
                self.logger.info(f"Inferred ego position: road_id={road_id}, lane_id={lane_id} (distance: {min_distance:.1f}m)")
                return (road_id, lane_id)
            else:
                self.logger.warning(f"Closest spawn point missing road/lane info: {closest_point}")
        else:
            self.logger.warning(f"No nearby spawn point found for coordinates ({x:.1f}, {y:.1f}), min_distance={min_distance:.1f}m")
        
        return None
    
    def _auto_compute_heading_from_position(self, x: float, y: float, map_name: str) -> float:
        """Auto-compute heading based on road direction at given position"""
        # Find nearby spawn points to get road heading
        spawn_points = self._get_spawn_points_for_map(map_name)
        if not spawn_points:
            return 0.0
        
        # Find closest driving lane spawn point
        closest_point = None
        min_distance = float('inf')
        
        for pt in spawn_points:
            if pt.get('lane_type') != 'Driving':
                continue
            pt_x, pt_y = pt.get('x', 0), pt.get('y', 0)
            distance = math.hypot(x - pt_x, y - pt_y)
            if distance < min_distance:
                min_distance = distance
                closest_point = pt
        
        if closest_point and min_distance < 20.0:  # Within 20m for heading inference
            heading = math.radians(closest_point.get('yaw', 0))
            self.logger.info(f"Auto-computed heading: {math.degrees(heading):.1f}° from nearby spawn point")
            return heading
        
        self.logger.warning(f"Could not auto-compute heading for position ({x:.1f}, {y:.1f})")
        return 0.0
    
    def _log_spawn_decision(self, selected_spawn: Dict, ego_pos: Optional[Tuple[float, float, float, float]], ego_lane: Optional[Tuple[int, int]], criteria: Dict[str, Any]):
        """Log comprehensive spawn decision information"""
        actor_id = "ego" if ego_pos is None else "actor"
        self.logger.info(f"=== Spawning {actor_id} ===")
        
        if ego_lane:
            self.logger.info(f"Ego: road_id={ego_lane[0]}, lane_id={ego_lane[1]}")
        else:
            self.logger.info("Ego: not positioned yet")
            
        self.logger.info(f"Actor: road_id={selected_spawn.get('road_id')}, lane_id={selected_spawn.get('lane_id')}")
        
        if ego_pos:
            distance = math.hypot(selected_spawn.get('x', 0) - ego_pos[0], selected_spawn.get('y', 0) - ego_pos[1])
            self.logger.info(f"Distance: {distance:.1f}m")
        
        # Log constraint validation
        constraints_satisfied = []
        if 'road_relationship' in criteria:
            rel = criteria['road_relationship']
            if rel == 'same_road' and ego_lane:
                satisfied = selected_spawn.get('road_id') == ego_lane[0]
                constraints_satisfied.append(f"road_relationship({rel}): {'✓' if satisfied else '✗'}")
            elif rel == 'different_road' and ego_lane:
                satisfied = selected_spawn.get('road_id') != ego_lane[0]
                constraints_satisfied.append(f"road_relationship({rel}): {'✓' if satisfied else '✗'}")
            else:
                constraints_satisfied.append(f"road_relationship({rel}): ✓")
                
        if 'lane_relationship' in criteria:
            rel = criteria['lane_relationship']
            if rel == 'same_lane' and ego_lane:
                satisfied = (selected_spawn.get('road_id') == ego_lane[0] and 
                           selected_spawn.get('lane_id') == ego_lane[1])
                constraints_satisfied.append(f"lane_relationship({rel}): {'✓' if satisfied else '✗'}")
            elif rel == 'adjacent_lane' and ego_lane:
                satisfied = (selected_spawn.get('road_id') == ego_lane[0] and 
                           abs(selected_spawn.get('lane_id', 0) - ego_lane[1]) == 1)
                constraints_satisfied.append(f"lane_relationship({rel}): {'✓' if satisfied else '✗'}")
            else:
                constraints_satisfied.append(f"lane_relationship({rel}): ✓")
                
        if constraints_satisfied:
            self.logger.info(f"Constraints: {', '.join(constraints_satisfied)}")
        
        self.logger.info("="*40)


    
    def convert(self, json_data: Dict[str, Any]) -> str:
        """Convert JSON to OpenSCENARIO XML string"""
        # Validate first
        self.validate_json(json_data)
        
        # If map is explicitly specified, use it directly
        if 'map_name' in json_data:
            return self._convert_with_map(json_data, json_data['map_name'])
        
        # Otherwise, try maps in order of suitability until one works
        maps_to_try = self._get_maps_by_priority(json_data)
        
        last_error = None
        for i, map_name in enumerate(maps_to_try):
            try:
                # For highway scenarios, allow fallback on highway-suitable maps (first 3 attempts)
                # For other scenarios, only allow fallback on the last map
                scenario_type = self._detect_scenario_type(json_data)
                if scenario_type == 'highway':
                    # Allow relaxed spawning for the first 3 highway-suitable maps
                    self._allow_final_fallback = (i < 3) or (i == len(maps_to_try) - 1)
                else:
                    # Original behavior for non-highway scenarios
                    self._allow_final_fallback = (i == len(maps_to_try) - 1)
                
                self.logger.info(f"Attempting conversion with map {map_name} (scenario_type={scenario_type}, allow_final_fallback={self._allow_final_fallback})...")
                self._selected_map = map_name
                result = self._convert_with_map(json_data, map_name)
                self.logger.info(f"✓ Successfully converted with map {map_name}")
                return result
            except RuntimeError as e:
                if "No valid spawn points found" in str(e):
                    if i < len(maps_to_try) - 1:
                        self.logger.info(f"✗ Map {map_name} couldn't satisfy spawn constraints, trying next map...")
                    else:
                        self.logger.warning(f"✗ Map {map_name} (last option) couldn't satisfy spawn constraints")
                    last_error = e
                    continue
                else:
                    raise  # Re-raise non-spawn related errors
        
        # If no map worked, raise the last error
        if last_error:
            raise RuntimeError(f"No map could satisfy all spawn constraints. Last error: {last_error}")
        
        # Fallback (shouldn't reach here)
        return self._convert_with_map(json_data, 'Town01')
    
    def _get_maps_by_priority(self, data: Dict[str, Any]) -> List[str]:
        """Get list of maps sorted by priority for this scenario"""
        scenario_type = self._detect_scenario_type(data)
        
        # Collect spawn criteria
        spawn_criteria = []
        if 'ego_spawn' in data:
            spawn_criteria.append(data['ego_spawn'].get('criteria', {}))
        for actor in data.get('actors', []):
            if 'spawn' in actor:
                spawn_criteria.append(actor['spawn'].get('criteria', {}))
        
        # Score available maps
        available_maps = list(set(self.spawn_meta.keys()) | set(self.waypoint_meta.keys()))
        map_scores = {}
        for map_name in available_maps:
            score = self._calculate_map_suitability_score(map_name, scenario_type, spawn_criteria)
            map_scores[map_name] = score
        
        # Sort by score
        sorted_maps = sorted(map_scores.items(), key=lambda x: x[1], reverse=True)
        return [map_name for map_name, score in sorted_maps if score > 0]
    
    def _convert_with_map(self, json_data: Dict[str, Any], map_name: str) -> str:
        """Convert with a specific map"""
        # Create root element
        root = ET.Element('OpenSCENARIO')
        
        # Add main sections
        root.append(self.create_file_header())
        ET.SubElement(root, 'ParameterDeclarations')
        ET.SubElement(root, 'CatalogLocations')
        
        # RoadNetwork
        road_network = ET.SubElement(root, 'RoadNetwork')
        logic_file = ET.SubElement(road_network, 'LogicFile')
        logic_file.set('filepath', map_name)
        ET.SubElement(road_network, 'SceneGraphFile').set('filepath', '')
        
        # Entities
        root.append(self.create_entities(json_data))
        
        # Storyboard (this is where spawn selection happens and may fail)
        root.append(self.create_storyboard(json_data))
        
        # Pretty print
        return self.prettify_xml(root)
    
    def prettify_xml(self, elem: ET.Element) -> str:
        """Return a pretty-printed XML string"""
        rough_string = ET.tostring(elem, 'unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Convert JSON to OpenSCENARIO')
    parser.add_argument('input', help='Input JSON file')
    parser.add_argument('-o', '--output', help='Output XOSC file (default: input.xosc)')
    parser.add_argument('-s', '--schema', help='JSON schema file for validation')
    parser.add_argument('-v', '--validate-only', action='store_true', 
                       help='Only validate, do not convert')
    parser.add_argument('--log-level', default='INFO', 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Set logging level')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load JSON
    try:
        with open(args.input, 'r') as f:
            json_data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        sys.exit(1)
    
    # Create converter
    converter = JsonToXoscConverter(args.schema)
    
    # Validate only mode
    if args.validate_only:
        try:
            converter.validate_json(json_data)
            print("Validation successful!")
            sys.exit(0)
        except ValidationError as e:
            print(f"Validation failed: {e}")
            sys.exit(1)
    
    # Convert
    try:
        xosc_content = converter.convert(json_data)
        
        # Determine output file
        output_file = args.output
        if not output_file:
            base_name = os.path.splitext(args.input)[0]
            output_file = f"{base_name}.xosc"
        
        # Write output
        with open(output_file, 'w') as f:
            f.write(xosc_content)
        
        print(f"Successfully converted to {output_file}")
        
    except ValidationError as e:
        print(f"Validation error: {e}")
        sys.exit(1)
    """except Exception as e:
        print(f"Conversion error: {e}")
        sys.exit(1)"""


if __name__ == '__main__':
    main()