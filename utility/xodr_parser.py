import xml.etree.ElementTree as ET
import json
import math
from typing import Dict, List, Tuple, Optional
import numpy as np
from dataclasses import dataclass, asdict


@dataclass
class GeometryPoint:
    s: float
    x: float
    y: float
    hdg: float
    length: float
    geometry_type: str


@dataclass
class LaneInfo:
    lane_id: int
    lane_type: str
    width: float
    direction: str
    level: bool


@dataclass
class RoadData:
    road_id: int
    name: str
    length: float
    road_type: str
    speed_limit: Optional[float]
    junction_id: int
    predecessor: Optional[Dict]
    successor: Optional[Dict]
    geometry: List[GeometryPoint]
    lanes: Dict[int, LaneInfo]


@dataclass
class JunctionData:
    junction_id: int
    name: str
    connections: List[Dict]
    connecting_roads: List[int]
    bounding_box: Dict[str, float]


@dataclass
class RoundaboutInfo:
    junction_id: int
    center: Dict[str, float]
    radius: float
    entry_roads: List[int]
    exit_roads: List[int]
    lanes_count: int


class XODRAnalyzer:
    def __init__(self, xodr_file_path: str):
        self.xodr_file_path = xodr_file_path
        self.tree = ET.parse(xodr_file_path)
        self.root = self.tree.getroot()
        self.roads: Dict[int, RoadData] = {}
        self.junctions: Dict[int, JunctionData] = {}
        self.roundabouts: List[RoundaboutInfo] = []
        self.road_network = {}
        
    def parse_full_network(self) -> Dict:
        """Main method to parse the entire XODR network"""
        print(f"Parsing XODR file: {self.xodr_file_path}")
        
        self.extract_roads()
        self.extract_junctions()
        self.analyze_road_types()
        self.detect_special_features()
        self.generate_enhanced_waypoints()
        
        return self.create_network_database()
    
    def extract_roads(self):
        """Extract all road information from XODR"""
        for road_elem in self.root.findall('road'):
            road_id = int(road_elem.get('id'))
            road_name = road_elem.get('name', f'Road {road_id}')
            road_length = float(road_elem.get('length'))
            junction_id = int(road_elem.get('junction', -1))
            
            # Extract road type and speed limit
            road_type = "unknown"
            speed_limit = None
            type_elem = road_elem.find('type')
            if type_elem is not None:
                road_type = type_elem.get('type', 'unknown')
                speed_elem = type_elem.find('speed')
                if speed_elem is not None:
                    speed_limit = float(speed_elem.get('max'))
            
            # Extract link information
            predecessor = None
            successor = None
            link_elem = road_elem.find('link')
            if link_elem is not None:
                pred_elem = link_elem.find('predecessor')
                if pred_elem is not None:
                    predecessor = {
                        'elementType': pred_elem.get('elementType'),
                        'elementId': int(pred_elem.get('elementId')),
                        'contactPoint': pred_elem.get('contactPoint')
                    }
                
                succ_elem = link_elem.find('successor')
                if succ_elem is not None:
                    successor = {
                        'elementType': succ_elem.get('elementType'),
                        'elementId': int(succ_elem.get('elementId')),
                        'contactPoint': succ_elem.get('contactPoint')
                    }
            
            # Extract geometry
            geometry = self.extract_road_geometry(road_elem)
            
            # Extract lanes
            lanes = self.extract_lane_info(road_elem)
            
            road_data = RoadData(
                road_id=road_id,
                name=road_name,
                length=road_length,
                road_type=road_type,
                speed_limit=speed_limit,
                junction_id=junction_id,
                predecessor=predecessor,
                successor=successor,
                geometry=geometry,
                lanes=lanes
            )
            
            self.roads[road_id] = road_data
            print(f"Extracted road {road_id}: {road_name} ({road_type})")
    
    def extract_road_geometry(self, road_elem) -> List[GeometryPoint]:
        """Extract planView geometry from road element"""
        geometry_points = []
        plan_view = road_elem.find('planView')
        
        if plan_view is not None:
            for geom_elem in plan_view.findall('geometry'):
                s = float(geom_elem.get('s'))
                x = float(geom_elem.get('x'))
                y = float(geom_elem.get('y'))
                hdg = float(geom_elem.get('hdg'))
                length = float(geom_elem.get('length'))
                
                # Determine geometry type
                geom_type = "unknown"
                if geom_elem.find('line') is not None:
                    geom_type = "line"
                elif geom_elem.find('arc') is not None:
                    geom_type = "arc"
                elif geom_elem.find('spiral') is not None:
                    geom_type = "spiral"
                elif geom_elem.find('poly3') is not None:
                    geom_type = "poly3"
                
                geometry_points.append(GeometryPoint(
                    s=s, x=x, y=y, hdg=hdg, length=length, geometry_type=geom_type
                ))
        
        return geometry_points
    
    def extract_lane_info(self, road_elem) -> Dict[int, LaneInfo]:
        """Extract lane information from road element"""
        lanes_info = {}
        lanes_elem = road_elem.find('lanes')
        
        if lanes_elem is not None:
            for lane_section in lanes_elem.findall('laneSection'):
                # Process left, center, and right lanes
                for side in ['left', 'center', 'right']:
                    side_elem = lane_section.find(side)
                    if side_elem is not None:
                        for lane_elem in side_elem.findall('lane'):
                            lane_id = int(lane_elem.get('id'))
                            lane_type = lane_elem.get('type', 'unknown')
                            level = lane_elem.get('level', 'false') == 'true'
                            
                            # Extract width (use first width element)
                            width = 0.0
                            width_elem = lane_elem.find('width')
                            if width_elem is not None:
                                width = float(width_elem.get('a', 0.0))
                            
                            # Determine direction from userData if available
                            direction = "unknown"
                            user_data = lane_elem.find('userData')
                            if user_data is not None:
                                vector_lane = user_data.find('vectorLane')
                                if vector_lane is not None:
                                    direction = vector_lane.get('travelDir', 'unknown')
                            
                            lanes_info[lane_id] = LaneInfo(
                                lane_id=lane_id,
                                lane_type=lane_type,
                                width=width,
                                direction=direction,
                                level=level
                            )
        
        return lanes_info
    
    def extract_junctions(self):
        """Extract junction information from XODR"""
        for junction_elem in self.root.findall('junction'):
            junction_id = int(junction_elem.get('id'))
            junction_name = junction_elem.get('name', f'Junction {junction_id}')
            
            connections = []
            connecting_roads = []
            
            for connection_elem in junction_elem.findall('connection'):
                connection_data = {
                    'id': int(connection_elem.get('id')),
                    'incomingRoad': int(connection_elem.get('incomingRoad')),
                    'connectingRoad': int(connection_elem.get('connectingRoad')),
                    'contactPoint': connection_elem.get('contactPoint')
                }
                
                # Extract lane links
                lane_links = []
                for lane_link in connection_elem.findall('laneLink'):
                    lane_links.append({
                        'from': int(lane_link.get('from')),
                        'to': int(lane_link.get('to'))
                    })
                connection_data['laneLinks'] = lane_links
                
                connections.append(connection_data)
                connecting_roads.append(connection_data['connectingRoad'])
            
            # Calculate bounding box from connected roads
            bounding_box = self.calculate_junction_bounding_box(junction_id, connecting_roads)
            
            junction_data = JunctionData(
                junction_id=junction_id,
                name=junction_name,
                connections=connections,
                connecting_roads=connecting_roads,
                bounding_box=bounding_box
            )
            
            self.junctions[junction_id] = junction_data
            print(f"Extracted junction {junction_id}: {junction_name}")
    
    def calculate_junction_bounding_box(self, junction_id: int, connecting_roads: List[int]) -> Dict[str, float]:
        """Calculate bounding box for junction based on connected roads"""
        min_x, max_x = float('inf'), float('-inf')
        min_y, max_y = float('inf'), float('-inf')
        
        for road_id in connecting_roads:
            if road_id in self.roads:
                for geom_point in self.roads[road_id].geometry:
                    min_x = min(min_x, geom_point.x)
                    max_x = max(max_x, geom_point.x)
                    min_y = min(min_y, geom_point.y)
                    max_y = max(max_y, geom_point.y)
        
        return {
            'min_x': min_x if min_x != float('inf') else 0.0,
            'max_x': max_x if max_x != float('-inf') else 0.0,
            'min_y': min_y if min_y != float('inf') else 0.0,
            'max_y': max_y if max_y != float('-inf') else 0.0
        }
    
    def analyze_road_types(self):
        """Analyze and classify road types based on OpenDRIVE data"""
        road_classifications = {}
        
        for road_id, road_data in self.roads.items():
            classification = {
                'is_highway': False,
                'is_arterial': False,
                'is_residential': False,
                'is_service': False,
                'has_multiple_lanes': False,
                'is_one_way': False
            }
            
            # Classify based on road type
            if road_data.road_type in ['motorway', 'trunk']:
                classification['is_highway'] = True
            elif road_data.road_type in ['primary', 'secondary']:
                classification['is_arterial'] = True
            elif road_data.road_type == 'residential':
                classification['is_residential'] = True
            elif road_data.road_type == 'service':
                classification['is_service'] = True
            
            # Check for multiple driving lanes
            driving_lanes = [lane for lane in road_data.lanes.values() 
                           if lane.lane_type == 'driving']
            if len(driving_lanes) > 2:
                classification['has_multiple_lanes'] = True
            
            # Check if one-way (simplified check)
            forward_lanes = [lane for lane in driving_lanes if lane.direction == 'forward']
            backward_lanes = [lane for lane in driving_lanes if lane.direction == 'backward']
            
            if len(forward_lanes) > 0 and len(backward_lanes) == 0:
                classification['is_one_way'] = True
            elif len(backward_lanes) > 0 and len(forward_lanes) == 0:
                classification['is_one_way'] = True
            
            road_classifications[road_id] = classification
        
        self.road_classifications = road_classifications
    
    def detect_special_features(self):
        """Detect roundabouts, highway features, and other special road features"""
        self.detect_roundabouts()
        self.detect_highway_features()
        self.detect_parking_areas()
    
    def detect_roundabouts(self):
        """Detect roundabouts by analyzing junction patterns and geometry"""
        for junction_id, junction_data in self.junctions.items():
            # Simple roundabout detection: look for circular patterns
            if len(junction_data.connecting_roads) >= 3:
                # Get geometry points from connecting roads
                all_points = []
                for road_id in junction_data.connecting_roads:
                    if road_id in self.roads:
                        for geom in self.roads[road_id].geometry:
                            all_points.append((geom.x, geom.y))
                
                if len(all_points) >= 3:
                    # Calculate potential circle center and radius
                    center_x = sum(p[0] for p in all_points) / len(all_points)
                    center_y = sum(p[1] for p in all_points) / len(all_points)
                    
                    # Calculate average distance from center (potential radius)
                    distances = [math.sqrt((p[0] - center_x)**2 + (p[1] - center_y)**2) 
                               for p in all_points]
                    avg_radius = sum(distances) / len(distances)
                    
                    # Check if points form a roughly circular pattern
                    radius_variance = sum((d - avg_radius)**2 for d in distances) / len(distances)
                    
                    # If variance is low, likely a roundabout
                    if radius_variance < (avg_radius * 0.3)**2 and avg_radius > 5.0:
                        # Identify entry and exit roads
                        entry_roads = []
                        exit_roads = []
                        
                        for connection in junction_data.connections:
                            incoming_road = connection['incomingRoad']
                            if incoming_road not in junction_data.connecting_roads:
                                entry_roads.append(incoming_road)
                        
                        # For simplicity, assume same roads can be entry/exit
                        exit_roads = entry_roads.copy()
                        
                        roundabout = RoundaboutInfo(
                            junction_id=junction_id,
                            center={'x': center_x, 'y': center_y},
                            radius=avg_radius,
                            entry_roads=entry_roads,
                            exit_roads=exit_roads,
                            lanes_count=len(junction_data.connecting_roads)
                        )
                        
                        self.roundabouts.append(roundabout)
                        print(f"Detected roundabout at junction {junction_id}")
    
    def detect_highway_features(self):
        """Detect highway-specific features like on/off ramps"""
        highway_features = {}
        
        for road_id, road_data in self.roads.items():
            if hasattr(self, 'road_classifications') and self.road_classifications.get(road_id, {}).get('is_highway'):
                features = {
                    'on_ramps': [],
                    'off_ramps': [],
                    'weaving_sections': []
                }
                
                # Look for ramp connections
                if road_data.predecessor and road_data.predecessor['elementType'] == 'road':
                    pred_road_id = road_data.predecessor['elementId']
                    if pred_road_id in self.roads:
                        pred_road = self.roads[pred_road_id]
                        if pred_road.road_type == 'service':
                            features['on_ramps'].append(pred_road_id)
                
                if road_data.successor and road_data.successor['elementType'] == 'road':
                    succ_road_id = road_data.successor['elementId']
                    if succ_road_id in self.roads:
                        succ_road = self.roads[succ_road_id]
                        if succ_road.road_type == 'service':
                            features['off_ramps'].append(succ_road_id)
                
                highway_features[road_id] = features
        
        self.highway_features = highway_features
    
    def detect_parking_areas(self):
        """Detect parking lots and service areas"""
        parking_areas = []
        
        for road_id, road_data in self.roads.items():
            if road_data.road_type == 'service':
                # Look for parking-type lanes
                parking_lanes = [lane for lane in road_data.lanes.values() 
                               if lane.lane_type == 'parking']
                
                if parking_lanes:
                    parking_areas.append({
                        'road_id': road_id,
                        'type': 'parking_lot',
                        'access_points': [(geom.x, geom.y) for geom in road_data.geometry[:2]]
                    })
        
        self.parking_areas = parking_areas
    
    def generate_enhanced_waypoints(self):
        """Generate waypoints with enhanced road context"""
        enhanced_waypoints = {}
        
        for road_id, road_data in self.roads.items():
            waypoints = []
            
            for i, geom in enumerate(road_data.geometry):
                # Calculate distance to nearest junction
                dist_to_junction = float('inf')
                nearest_junction_type = None
                
                for junction_id, junction_data in self.junctions.items():
                    if road_id in junction_data.connecting_roads:
                        # Calculate distance to junction center
                        center_x = (junction_data.bounding_box['min_x'] + junction_data.bounding_box['max_x']) / 2
                        center_y = (junction_data.bounding_box['min_y'] + junction_data.bounding_box['max_y']) / 2
                        
                        dist = math.sqrt((geom.x - center_x)**2 + (geom.y - center_y)**2)
                        if dist < dist_to_junction:
                            dist_to_junction = dist
                            # Check if it's a roundabout
                            nearest_junction_type = "roundabout" if any(r.junction_id == junction_id for r in self.roundabouts) else "intersection"
                
                # Calculate curvature (simplified)
                curvature = 0.0
                if i > 0 and i < len(road_data.geometry) - 1:
                    prev_geom = road_data.geometry[i-1]
                    next_geom = road_data.geometry[i+1]
                    
                    angle_diff = abs(next_geom.hdg - prev_geom.hdg)
                    if angle_diff > math.pi:
                        angle_diff = 2 * math.pi - angle_diff
                    
                    distance = math.sqrt((next_geom.x - prev_geom.x)**2 + (next_geom.y - prev_geom.y)**2)
                    if distance > 0:
                        curvature = angle_diff / distance
                
                # Get road context
                road_context = {
                    'road_type': road_data.road_type,
                    'curvature': curvature,
                    'speed_limit': road_data.speed_limit,
                    'connected_roads': self.get_connected_roads(road_id),
                    'distance_to_junction': dist_to_junction if dist_to_junction != float('inf') else None,
                    'junction_type': nearest_junction_type,
                    'is_intersection': road_data.junction_id != -1
                }
                
                # Generate waypoint for each driving lane
                for lane_id, lane_info in road_data.lanes.items():
                    if lane_info.lane_type == 'driving':
                        # Calculate lane offset from road center
                        lane_offset = lane_id * lane_info.width
                        
                        # Calculate perpendicular offset
                        offset_x = -lane_offset * math.sin(geom.hdg)
                        offset_y = lane_offset * math.cos(geom.hdg)
                        
                        waypoint = {
                            'x': geom.x + offset_x,
                            'y': geom.y + offset_y,
                            'z': 0.0,  # Simplified - would need elevation profile
                            'yaw': geom.hdg,
                            'lane_type': lane_info.lane_type,
                            'lane_id': lane_id,
                            'road_context': road_context
                        }
                        
                        waypoints.append(waypoint)
            
            enhanced_waypoints[road_id] = waypoints
        
        self.enhanced_waypoints = enhanced_waypoints
    
    def get_connected_roads(self, road_id: int) -> List[int]:
        """Get list of roads connected to the given road"""
        connected = []
        road_data = self.roads[road_id]
        
        if road_data.predecessor and road_data.predecessor['elementType'] == 'road':
            connected.append(road_data.predecessor['elementId'])
        
        if road_data.successor and road_data.successor['elementType'] == 'road':
            connected.append(road_data.successor['elementId'])
        
        # Also check junction connections
        if road_data.junction_id != -1 and road_data.junction_id in self.junctions:
            junction = self.junctions[road_data.junction_id]
            for conn_road in junction.connecting_roads:
                if conn_road != road_id and conn_road not in connected:
                    connected.append(conn_road)
        
        return connected
    
    def create_network_database(self) -> Dict:
        """Create the final road intelligence database"""
        # Convert dataclasses to dictionaries for JSON serialization
        roads_dict = {road_id: asdict(road_data) for road_id, road_data in self.roads.items()}
        junctions_dict = {junction_id: asdict(junction_data) for junction_id, junction_data in self.junctions.items()}
        roundabouts_list = [asdict(roundabout) for roundabout in self.roundabouts]
        
        database = {
            'header': {
                'source_file': self.xodr_file_path,
                'total_roads': len(self.roads),
                'total_junctions': len(self.junctions),
                'total_roundabouts': len(self.roundabouts)
            },
            'roads': roads_dict,
            'junctions': junctions_dict,
            'roundabouts': roundabouts_list,
            'highway_features': getattr(self, 'highway_features', {}),
            'parking_areas': getattr(self, 'parking_areas', []),
            'enhanced_waypoints': getattr(self, 'enhanced_waypoints', {}),
            'road_classifications': getattr(self, 'road_classifications', {})
        }
        
        return database
    
    def save_database(self, output_file: str):
        """Save the road intelligence database to JSON file"""
        database = self.create_network_database()
        
        with open(output_file, 'w') as f:
            json.dump(database, f, indent=2, default=str)
        
        print(f"Road intelligence database saved to: {output_file}")
        return database


def analyze_all_towns(maps_directory: str = "maps/", output_directory: str = "road_intelligence/"):
    """Analyze all CARLA town XODR files"""
    import os
    
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
    
    xodr_files = [f for f in os.listdir(maps_directory) if f.endswith('.xodr') and not f.endswith('_Opt.xodr')]
    
    all_databases = {}
    
    for xodr_file in xodr_files:
        print(f"\n=== Analyzing {xodr_file} ===")
        
        file_path = os.path.join(maps_directory, xodr_file)
        analyzer = XODRAnalyzer(file_path)
        
        try:
            database = analyzer.parse_full_network()
            town_name = xodr_file.replace('.xodr', '')
            
            # Save individual town database
            output_file = os.path.join(output_directory, f"{town_name}_road_intelligence.json")
            analyzer.save_database(output_file)
            
            all_databases[town_name] = database
            
        except Exception as e:
            print(f"Error analyzing {xodr_file}: {e}")
    
    # Save combined database
    combined_output = os.path.join(output_directory, "all_towns_road_intelligence.json")
    with open(combined_output, 'w') as f:
        json.dump(all_databases, f, indent=2, default=str)
    
    print(f"\nCombined road intelligence database saved to: {combined_output}")
    return all_databases


if __name__ == "__main__":
    # Example usage
    analyzer = XODRAnalyzer("maps/Town01.xodr")
    database = analyzer.parse_full_network()
    analyzer.save_database("Town01_road_intelligence.json")
    
    print("\nSample road data:")
    for road_id, road_data in list(analyzer.roads.items())[:3]:
        print(f"Road {road_id}: {road_data.name} ({road_data.road_type})")
        print(f"  Length: {road_data.length:.2f}m")
        print(f"  Lanes: {len(road_data.lanes)}")
        print(f"  Geometry points: {len(road_data.geometry)}")
        print()
    
    print(f"Detected {len(analyzer.roundabouts)} roundabouts")
    print(f"Detected {len(analyzer.junctions)} junctions")