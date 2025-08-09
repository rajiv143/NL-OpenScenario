#!/usr/bin/env python3
"""
JSON to OpenSCENARIO (XOSC) Converter for CARLA
Converts flat, LLM-friendly JSON to valid OpenSCENARIO XML files
"""

import json
import sys
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
import xml.etree.ElementTree as ET
from xml.dom import minidom
import jsonschema
import os
import math
import argparse
import copy
import carla
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
        
        self._ego_pos: Optional[Tuple[float, float, float, float]] = None
        self._ego_lane: Optional[Tuple[int, int]] = None # road_id, lane_id)
        self._selected_map: Optional[str] = None
        self._last_pick: Optional[Dict] = None
    def _load_map_data(self):
        """Load spawn and waypoint data for all available maps"""
        base_dir = os.path.dirname(__file__)
        
        # Load spawn data - ONLY use enhanced_TownX.json files
        spawns_dir = os.path.join(base_dir, "spawns")
        for path in glob.glob(os.path.join(spawns_dir, "enhanced_Town*.json")):
            # Extract town name from enhanced_TownX.json -> TownX
            filename = os.path.basename(path)
            town = filename.replace("enhanced_", "").replace(".json", "")
            
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
        
        # Load road intelligence files (*_road_intelligence.json)
        for path in glob.glob(os.path.join(base_dir, "*_road_intelligence.json")):
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
    
    def _detect_best_map(self, data: Dict[str, Any]) -> str:
        """Auto-detect the best map based on spawn constraints"""
        # If map is explicitly specified, validate and use it
        if 'map_name' in data:
            map_name = data['map_name']
            if map_name in self.spawn_meta or map_name in self.waypoint_meta:
                self.logger.info(f"Using explicitly specified map: {map_name}")
                return map_name
            else:
                self.logger.warning(f"Specified map {map_name} not found, attempting auto-detection")
        
        # Collect all spawn criteria
        spawn_criteria = []
        if 'ego_spawn' in data:
            spawn_criteria.append(data['ego_spawn'].get('criteria', {}))
        
        for actor in data.get('actors', []):
            if 'spawn' in actor:
                spawn_criteria.append(actor['spawn'].get('criteria', {}))
        
        if not spawn_criteria:
            # No criteria specified, use default map
            default_map = 'Town01'
            self.logger.info(f"No spawn criteria found, using default map: {default_map}")
            return default_map
        
        # Test each available map
        available_maps = set(self.spawn_meta.keys()) | set(self.waypoint_meta.keys())
        compatible_maps = []
        
        for map_name in available_maps:
            try:
                # Try to satisfy all spawn criteria for this map
                all_satisfied = True
                for criteria in spawn_criteria:
                    spawn_points = self._get_spawn_points_for_map(map_name)
                    if not any(self._matches_criteria(pt, criteria, map_name) for pt in spawn_points):
                        all_satisfied = False
                        break
                
                if all_satisfied:
                    compatible_maps.append(map_name)
                    self.logger.debug(f"Map {map_name} satisfies all spawn criteria")
            except Exception as e:
                self.logger.debug(f"Map {map_name} failed compatibility check: {e}")
        
        if compatible_maps:
            # Prefer maps with more spawn points (more flexibility)
            best_map = max(compatible_maps, key=lambda m: len(self._get_spawn_points_for_map(m)))
            self.logger.info(f"Auto-detected best map: {best_map} (from {len(compatible_maps)} compatible maps)")
            return best_map
        else:
            # Fall back to default with warning
            default_map = 'Town01'
            self.logger.warning(f"No maps satisfy all spawn criteria, falling back to: {default_map}")
            return default_map
    
    def _get_spawn_points_for_map(self, map_name: str) -> List[Dict]:
        """Get spawn points for a given map from enhanced spawn files only"""
        points = []
        
        # Only use enhanced spawn data
        if map_name in self.spawn_meta:
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
        
        # Auto-detect and validate map
        detected_map = self._detect_best_map(data)
        self._selected_map = detected_map
        
        # Update data with selected map if not explicitly set
        if 'map_name' not in data:
            data['map_name'] = detected_map
        
        # Validate selected map exists
        if detected_map not in CARLA_MAPS:
            self.logger.warning(f"Selected map {detected_map} not in CARLA_MAPS list, proceeding anyway")
        
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
    
    def parse_position(self, pos_str: str) -> Tuple[float, float, float, float]:
        """Parse position string 'x,y,z,yaw' with defaults"""
        parts = pos_str.split(',')
        x = float(parts[0])
        y = float(parts[1])
        z = float(parts[2]) if len(parts) > 2 else 0.5
        yaw = float(parts[3]) if len(parts) > 3 else 0.0
        # Convert yaw from degrees to radians
        yaw_rad = math.radians(yaw)
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
                vehicle.set('name', actor['model'])
                vehicle.set('vehicleCategory', 'bicycle' if actor['type'] == 'cyclist' else 'car')
                
                # Copy standard vehicle elements
                ET.SubElement(vehicle, 'ParameterDeclarations')
                vehicle.append(copy.deepcopy(perf))
                vehicle.append(copy.deepcopy(bbox))
                vehicle.append(copy.deepcopy(axles))
                
                props = ET.SubElement(vehicle, 'Properties')
                prop = ET.SubElement(props, 'Property')
                prop.set('name', 'type')
                prop.set('value', 'simulation')
                
                if 'color' in actor:
                    color_prop = ET.SubElement(props, 'Property')
                    color_prop.set('name', 'color')
                    color_prop.set('value', actor['color'])
                    
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
    
    def create_init(self, data: Dict[str, Any]) -> ET.Element:
        """Create Init section with positions and environment"""
        init = ET.Element('Init')
        actions = ET.SubElement(init, 'Actions')
        
        # Global actions (environment)
        global_action = ET.SubElement(actions, 'GlobalAction')
        env_action = ET.SubElement(global_action, 'EnvironmentAction')
        env_action.append(self.create_environment(data.get('weather', 'clear')))
        
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
            crit = data['ego_spawn'].get('criteria', {})
            x,y,z,yaw = self._choose_spawn(map_name, crit)
            meta = self._last_pick
            if meta:
                self._ego_lane = (meta.get('road_id'), meta.get('lane_id'))
            self._ego_pos = (x, y, z, yaw)
        else:
            x,y,z,yaw = self.parse_position(data['ego_start_position'])
            self._ego_pos  = (x, y, z, yaw)
            self._ego_lane = None   
        
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
        
        # Other actors positions
        for actor in data.get('actors', []):
            private = ET.SubElement(actions, 'Private')
            private.set('entityRef', actor['id'])
            
            action = ET.SubElement(private, 'PrivateAction')
            teleport = ET.SubElement(action, 'TeleportAction')
            position = ET.SubElement(teleport, 'Position')
            world_pos = ET.SubElement(position, 'WorldPosition')
    
            if 'spawn' in actor:
                crit = actor['spawn'].get('criteria', {})
                ax, ay, az, ayaw = self._choose_spawn(
                    map_name, crit,
                    ego_pos=self._ego_pos,
                    ego_lane=self._ego_lane
                )
            else:
                ax, ay, az, ayaw = self.parse_position(actor['start_position'])
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
                ev_name = f"{actor_id}Event{i}"
                ac_name = f"{actor_id}Action{i}"

                ev = ET.SubElement(man, 'Event', {
                    'name':     ev_name,
                    'priority': 'overwrite'
                })
                ac = ET.SubElement(ev, 'Action', {'name': ac_name})
                pa = ET.SubElement(ac, 'PrivateAction')

                # --- build the PrivateAction body ---
                atype = action['action_type']
                if atype == 'wait':
                    la = ET.SubElement(pa, 'LongitudinalAction')
                    sa = ET.SubElement(la, 'SpeedAction')
                    ET.SubElement(sa, 'SpeedActionDynamics', {
                        'dynamicsDimension': action.get('dynamics_dimension','time'),
                        'dynamicsShape':     action.get('dynamics_shape','step'),
                        'value':             str(action.get('wait_duration',0))
                    })
                    tgt = ET.SubElement(sa, 'SpeedActionTarget')
                    ET.SubElement(tgt, 'AbsoluteTargetSpeed', {'value':'0'})

                elif atype in ('speed','stop'):
                    la = ET.SubElement(pa, 'LongitudinalAction')
                    sa = ET.SubElement(la, 'SpeedAction')
                    speed_val = 0 if atype=='stop' else action.get('speed_value',0)
                    ET.SubElement(sa, 'SpeedActionDynamics', {
                        'dynamicsDimension': action.get('dynamics_dimension','time'),
                        'dynamicsShape':     action.get('dynamics_shape','step'),
                        'value':             str(action.get('dynamics_value',0))
                    })
                    tgt = ET.SubElement(sa, 'SpeedActionTarget')
                    ET.SubElement(tgt, 'AbsoluteTargetSpeed', {'value': str(speed_val)})

                elif atype == 'lane_change':
                    la = ET.SubElement(pa, 'LateralAction')
                    lc = ET.SubElement(la, 'LaneChangeAction')
                    ET.SubElement(lc, 'LaneChangeActionDynamics', {
                        'dynamicsDimension':'distance',
                        'dynamicsShape':    'linear',
                        'value':            str(action.get('dynamics_value',1))
                    })
                    tgt = ET.SubElement(lc, 'LaneChangeTarget')
                    ET.SubElement(tgt, 'RelativeTargetLane', {
                        'entityRef': 'hero' if actor_id=='ego' else actor_id,
                        'value':     '-1' if action.get('lane_direction')=='left' else '1'
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
                    # chain on previous action completion
                    prev_ref = f"{actor_id}Action{i-1}"
                    bv = ET.SubElement(cond, 'ByValueCondition')
                    ET.SubElement(bv, 'StoryboardElementStateCondition', {
                        'storyboardElementType': 'action',
                        'storyboardElementRef':  prev_ref,
                        'state':                 'completeState'
                    })

        # --- Act-level StartTrigger ---
        ast = ET.SubElement(act, 'StartTrigger')
        acg = ET.SubElement(ast, 'ConditionGroup')
        aco = ET.SubElement(acg, 'Condition', {
            'name':'OverallStartCondition','delay':'0','conditionEdge':'rising'
        })
        bv = ET.SubElement(aco, 'ByValueCondition')
        ET.SubElement(bv, 'SimulationTimeCondition', {
            'value':'0','rule':'greaterThan'
        })

        # --- Act-level StopTrigger: only driven distance ---
        astp = ET.SubElement(act, 'StopTrigger')
        scg  = ET.SubElement(astp, 'ConditionGroup')
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

        criteria = ['RunningStopTest', 'RunningRedLightTest', 'WrongLaneTest', 
                   'OnSidewalkTest', 'KeepLaneTest', 'CollisionTest', 'DrivenDistanceTest']
        
        for criterion in criteria:
            crit_cond = ET.SubElement(scg2, 'Condition')
            crit_cond.set('name', f'criteria_{criterion}')
            crit_cond.set('delay', '0')
            crit_cond.set('conditionEdge', 'rising')
            crit_by_value = ET.SubElement(crit_cond, 'ByValueCondition')
            param_cond = ET.SubElement(crit_by_value, 'ParameterCondition')
            
            if criterion == 'DrivenDistanceTest':
                param_cond.set('parameterRef', 'distance_success')
                param_cond.set('value', str(data.get('success_distance', 100)))
            else:
                param_cond.set('parameterRef', '')
                param_cond.set('value', '')
            param_cond.set('rule', 'lessThan')

        return sb


    def _choose_spawn(self, map_name: str, crit: Dict[str, Any],
                    ego_pos: Optional[Tuple[float, float, float, float]] = None,
                    ego_lane: Optional[Tuple[int, int]] = None) -> Tuple[float, float, float, float]:
        """Return a spawn (x,y,z,yaw) that meets the criteria using intelligent selection with road intelligence"""
        pts = self._get_spawn_points_for_map(map_name)
        if not pts:
            self.logger.error(f"No enhanced spawn data available for map {map_name}")
            raise ValidationError(f"No enhanced spawn points available for map {map_name}. Please ensure enhanced_{map_name}.json exists in spawns/ directory.")
        
        # Check if we have road intelligence data for enhanced selection
        road_data = self.road_intelligence.get(map_name, {})
        if not road_data:
            self.logger.warning(f"No road intelligence data for {map_name}, falling back to legacy spawn selection")
            return self._legacy_choose_spawn(map_name, crit, ego_pos, ego_lane, pts)
        
        # Use intelligent spawn selection with road intelligence
        return self._intelligent_choose_spawn(map_name, road_data, crit, ego_pos, ego_lane, pts)
    
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
        
        if 'lane_type' in crit:
            type_filtered = []
            valid_types = crit['lane_type'] if isinstance(crit['lane_type'], list) else [crit['lane_type']]
            for pt in candidates:
                if pt.get('lane_type') in valid_types:
                    type_filtered.append(pt)
            candidates = type_filtered
            self.logger.debug(f"Lane type filter: -> {len(candidates)} candidates")
        
        if 'distance_to_ego' in crit and ego_pos:
            distance_filtered = []
            for pt in candidates:
                d = math.hypot(pt.get('x', 0) - ego_pos[0], pt.get('y', 0) - ego_pos[1])
                low = crit['distance_to_ego'].get('min', 0)
                hi = crit['distance_to_ego'].get('max', 1000)
                if low <= d <= hi:
                    distance_filtered.append(pt)
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
        
        # Score and select best spawn point
        if not final_candidates:
            raise ValidationError(f"No spawn in {map_name} matches criteria {crit} even with fallbacks")
        
        if len(final_candidates) == 1:
            pick = final_candidates[0]
        else:
            scored_candidates = [(self._score_spawn_point(pt, crit, ego_pos, ego_lane), pt) for pt in final_candidates]
            scored_candidates.sort(reverse=True, key=lambda x: x[0])
            pick = scored_candidates[0][1]
        
        self._last_pick = pick
        self._log_spawn_decision(pick, ego_pos, ego_lane, crit)
        
        return pick['x'], pick['y'], pick['z'], math.radians(pick['yaw'])
    
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
        
        # Step 2: Apply road intelligence filters in priority order
        candidates = self._filter_by_road_context(candidates, crit, map_name)
        self.logger.debug(f"Road context filter: -> {len(candidates)} candidates")
        
        candidates = self._filter_by_junction_context(candidates, crit, map_name)
        self.logger.debug(f"Junction context filter: -> {len(candidates)} candidates")
        
        candidates = self._filter_by_road_relationships(candidates, crit, ego_lane, road_data)
        self.logger.debug(f"Road relationships filter: -> {len(candidates)} candidates")
        
        candidates = self._filter_by_geometry(candidates, crit, road_data)
        self.logger.debug(f"Geometry filter: -> {len(candidates)} candidates")
        
        # Step 3: Apply existing constraint filters
        candidates = self._apply_legacy_filters(candidates, crit, ego_pos, ego_lane)
        self.logger.debug(f"Legacy filters: -> {len(candidates)} candidates")
        
        # Step 4: Score and select best candidate
        return self._score_and_select_spawn(candidates, crit, ego_pos, ego_lane, road_data, pts)
    
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
        if not candidates:
            # Apply fallback strategy
            if all_pts:
                candidates = self._apply_fallback_strategy([], [], all_pts, crit, ego_pos, ego_lane)
            if not candidates:
                raise ValidationError(f"No valid spawn points found even with fallbacks")
        
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
        
        return pick['x'], pick['y'], pick['z'], math.radians(pick['yaw'])
    
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
        
        # Lane type filtering
        if 'lane_type' in crit:
            valid_types = crit['lane_type'] if isinstance(crit['lane_type'], list) else [crit['lane_type']]
            if pt.get('lane_type') not in valid_types:
                return False
        
        # Intersection filtering
        if 'is_intersection' in crit:
            if pt.get('is_intersection') is not crit['is_intersection']:
                return False
        
        # Heading tolerance
        if 'heading_tol' in crit and ego_pos:
            pt_yaw = pt.get('yaw', 0)
            dyaw = abs((pt_yaw - math.degrees(ego_pos[3]) + 180) % 360 - 180)
            if dyaw > crit['heading_tol']:
                return False
        
        # Relative position (ahead/behind with improved accuracy)
        if 'relative_position' in crit and ego_pos:
            rel_pos = self._get_relative_position(ego_pos, pt)
            expected_pos = crit['relative_position']
            if expected_pos == 'adjacent':
                # For adjacent, check lateral displacement
                if not self._is_laterally_adjacent(ego_pos, pt):
                    return False
            elif expected_pos in ['ahead', 'behind']:
                if rel_pos != expected_pos:
                    return False
        
        # Distance to arbitrary target
        if 'distance_to' in crit:
            tgt = crit['distance_to']
            d = math.hypot(pt.get('x', 0) - tgt.get('x', 0), pt.get('y', 0) - tgt.get('y', 0))
            if d > tgt.get('max', float('inf')):
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
    
    def _get_relative_position(self, ego_pos: Tuple[float, float, float, float], pt: Dict) -> str:
        """Get relative position (ahead/behind) with improved accuracy considering lane direction"""
        dx = pt.get('x', 0) - ego_pos[0]
        dy = pt.get('y', 0) - ego_pos[1]
        # Project along ego's heading direction
        proj = math.cos(ego_pos[3]) * dx + math.sin(ego_pos[3]) * dy
        return 'ahead' if proj > 0 else 'behind'
    
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
            if pt.get('road_id') == ego_lane[0]:
                score += 50  # Same road bonus
                if pt.get('lane_id') == ego_lane[1]:
                    score += 25  # Same lane bonus
                elif abs(pt.get('lane_id', 0) - ego_lane[1]) == 1:
                    score += 15  # Adjacent lane bonus
        
        # Relative position accuracy scoring
        if 'relative_position' in crit and ego_pos:
            actual_rel_pos = self._get_relative_position(ego_pos, pt)
            expected_rel_pos = crit['relative_position']
            if actual_rel_pos == expected_rel_pos or expected_rel_pos == 'adjacent':
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
        
        # Fallback 2: Relax lane_relationship further
        if 'lane_relationship' in crit and crit['lane_relationship'] in ['same_lane', 'adjacent_lane']:
            relaxed_crit = crit.copy()
            relaxed_crit['lane_relationship'] = 'any_lane'
            
            fallback_candidates = self._apply_relaxed_criteria(all_points, relaxed_crit, ego_pos, ego_lane)
            if fallback_candidates:
                self.logger.info(f"Fallback 2 (lane_relationship -> any_lane): found {len(fallback_candidates)} candidates")
                return fallback_candidates
        
        # Fallback 3: Relax road_relationship (last resort for relationships)
        if 'road_relationship' in crit and crit['road_relationship'] in ['same_road', 'different_road']:
            relaxed_crit = crit.copy()
            relaxed_crit['road_relationship'] = 'any_road'
            
            fallback_candidates = self._apply_relaxed_criteria(all_points, relaxed_crit, ego_pos, ego_lane)
            if fallback_candidates:
                self.logger.info(f"Fallback 3 (road_relationship -> any_road): found {len(fallback_candidates)} candidates")
                return fallback_candidates
        
        # Fallback 4: Expand distance range by 50%
        if 'distance_to_ego' in crit and ego_pos:
            relaxed_crit = crit.copy()
            distance_constraint = relaxed_crit['distance_to_ego'].copy()
            
            current_min = distance_constraint.get('min', 0)
            current_max = distance_constraint.get('max', 1000)
            range_expansion = (current_max - current_min) * 0.5
            
            distance_constraint['min'] = max(0, current_min - range_expansion)
            distance_constraint['max'] = current_max + range_expansion
            relaxed_crit['distance_to_ego'] = distance_constraint
            
            fallback_candidates = self._apply_relaxed_criteria(all_points, relaxed_crit, ego_pos, ego_lane)
            if fallback_candidates:
                self.logger.info(f"Fallback 4 (expanded distance {current_min}-{current_max} -> {distance_constraint['min']:.1f}-{distance_constraint['max']:.1f}): found {len(fallback_candidates)} candidates")
                return fallback_candidates
        
        # Fallback 5: Ignore intersection requirements
        if 'is_intersection' in crit:
            relaxed_crit = crit.copy()
            del relaxed_crit['is_intersection']
            
            fallback_candidates = self._apply_relaxed_criteria(all_points, relaxed_crit, ego_pos, ego_lane)
            if fallback_candidates:
                self.logger.info(f"Fallback 5 (relaxed intersection): found {len(fallback_candidates)} candidates")
                return fallback_candidates
        
        # Final fallback: Any valid spawn point with basic safety constraints
        if all_points:
            self.logger.warning("Using final fallback: any valid spawn point")
            return all_points[:10]  # Limit to 10 for performance
        
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
            type_filtered = []
            valid_types = relaxed_crit['lane_type'] if isinstance(relaxed_crit['lane_type'], list) else [relaxed_crit['lane_type']]
            for pt in candidates:
                if pt.get('lane_type') in valid_types:
                    type_filtered.append(pt)
            candidates = type_filtered
        
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
        """Filter spawn points based on lane relationship to ego vehicle"""
        relationship = crit['lane_relationship'] 
        ego_road_id, ego_lane_id = ego_lane if ego_lane else (None, None)
        
        if relationship == 'same_lane' and ego_lane:
            result = [pt for pt in candidates 
                    if pt.get('road_id') == ego_road_id and pt.get('lane_id') == ego_lane_id]
            self.logger.debug(f"Lane relationship 'same_lane': filtering to road_id={ego_road_id}, lane_id={ego_lane_id}")
            return result
        elif relationship == 'adjacent_lane' and ego_lane:
            result = [pt for pt in candidates 
                    if pt.get('road_id') == ego_road_id and 
                    abs(pt.get('lane_id', 0) - ego_lane_id) == 1]
            self.logger.debug(f"Lane relationship 'adjacent_lane': filtering to road_id={ego_road_id}, lane_id±1 from {ego_lane_id}")
            return result
        else:  # 'any_lane' or ego not positioned yet
            self.logger.debug(f"Lane relationship '{relationship}': no filtering")
            return candidates
    
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
        
        # Create root element
        root = ET.Element('OpenSCENARIO')
        
        # Add main sections
        root.append(self.create_file_header())
        ET.SubElement(root, 'ParameterDeclarations')
        ET.SubElement(root, 'CatalogLocations')
        
        # RoadNetwork
        road_network = ET.SubElement(root, 'RoadNetwork')
        logic_file = ET.SubElement(road_network, 'LogicFile')
        selected_map = self._selected_map or json_data.get('map_name', 'Town01')
        logic_file.set('filepath', selected_map)
        ET.SubElement(road_network, 'SceneGraphFile').set('filepath', '')
        
        # Entities
        root.append(self.create_entities(json_data))
        
        # Storyboard
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