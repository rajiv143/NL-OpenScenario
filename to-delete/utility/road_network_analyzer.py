import json
import math
import networkx as nx
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass
import numpy as np


@dataclass
class RoadConnection:
    from_road: int
    to_road: int
    connection_type: str  # "direct", "junction", "roundabout"
    junction_id: Optional[int] = None
    distance: float = 0.0


@dataclass
class IntersectionAnalysis:
    junction_id: int
    intersection_type: str  # "signalized", "stop_sign", "yield", "uncontrolled", "roundabout"
    approach_roads: List[int]
    conflict_points: List[Tuple[float, float]]
    traffic_complexity: float  # 0-1 scale


@dataclass
class RoadSegment:
    road_id: int
    segment_type: str  # "straight", "curve", "merge", "diverge", "intersection_approach"
    start_s: float
    end_s: float
    curvature: float
    speed_context: str  # "highway", "arterial", "residential", "service"


class RoadNetworkAnalyzer:
    def __init__(self, road_intelligence_db: Dict):
        self.db = road_intelligence_db
        self.graph = nx.DiGraph()
        self.road_connections: List[RoadConnection] = []
        self.intersection_analyses: Dict[int, IntersectionAnalysis] = {}
        self.road_segments: Dict[int, List[RoadSegment]] = {}
        self.traffic_zones = {}
        
    def build_road_network_graph(self):
        """Build a NetworkX graph representing the road network topology"""
        print("Building road network graph...")
        
        # Add roads as nodes
        for road_id, road_data in self.db['roads'].items():
            road_id = int(road_id)
            self.graph.add_node(road_id, **{
                'road_type': road_data['road_type'],
                'length': road_data['length'],
                'speed_limit': road_data['speed_limit'],
                'junction_id': road_data['junction_id'],
                'lane_count': len([l for l in road_data['lanes'].values() if l['lane_type'] == 'driving'])
            })
        
        # Add connections as edges
        for road_id, road_data in self.db['roads'].items():
            road_id = int(road_id)
            
            # Direct predecessor/successor connections
            if road_data['predecessor'] and road_data['predecessor']['elementType'] == 'road':
                pred_id = road_data['predecessor']['elementId']
                if pred_id in self.graph.nodes:
                    distance = self.calculate_road_distance(pred_id, road_id)
                    self.graph.add_edge(pred_id, road_id, 
                                      connection_type='direct', 
                                      distance=distance)
                    
                    self.road_connections.append(RoadConnection(
                        from_road=pred_id,
                        to_road=road_id,
                        connection_type='direct',
                        distance=distance
                    ))
            
            if road_data['successor'] and road_data['successor']['elementType'] == 'road':
                succ_id = road_data['successor']['elementId']
                if succ_id in self.graph.nodes:
                    distance = self.calculate_road_distance(road_id, succ_id)
                    self.graph.add_edge(road_id, succ_id, 
                                      connection_type='direct', 
                                      distance=distance)
                    
                    self.road_connections.append(RoadConnection(
                        from_road=road_id,
                        to_road=succ_id,
                        connection_type='direct',
                        distance=distance
                    ))
        
        # Add junction connections
        for junction_id, junction_data in self.db['junctions'].items():
            junction_id = int(junction_id)
            
            for connection in junction_data['connections']:
                incoming_road = connection['incomingRoad']
                connecting_road = connection['connectingRoad']
                
                # Find outgoing road from connecting road
                if str(connecting_road) in self.db['roads']:
                    conn_road_data = self.db['roads'][str(connecting_road)]
                    if (conn_road_data['successor'] and 
                        conn_road_data['successor']['elementType'] == 'road'):
                        outgoing_road = conn_road_data['successor']['elementId']
                        
                        if (incoming_road in self.graph.nodes and 
                            outgoing_road in self.graph.nodes):
                            
                            distance = self.calculate_junction_distance(
                                incoming_road, outgoing_road, junction_id
                            )
                            
                            connection_type = 'roundabout' if any(
                                r['junction_id'] == junction_id for r in self.db['roundabouts']
                            ) else 'junction'
                            
                            self.graph.add_edge(incoming_road, outgoing_road,
                                              connection_type=connection_type,
                                              junction_id=junction_id,
                                              distance=distance)
                            
                            self.road_connections.append(RoadConnection(
                                from_road=incoming_road,
                                to_road=outgoing_road,
                                connection_type=connection_type,
                                junction_id=junction_id,
                                distance=distance
                            ))
        
        print(f"Network graph built: {len(self.graph.nodes)} roads, {len(self.graph.edges)} connections")
    
    def calculate_road_distance(self, road1_id: int, road2_id: int) -> float:
        """Calculate distance between two connected roads"""
        road1 = self.db['roads'][str(road1_id)]
        road2 = self.db['roads'][str(road2_id)]
        
        # Use last geometry point of road1 and first geometry point of road2
        if road1['geometry'] and road2['geometry']:
            p1 = road1['geometry'][-1]
            p2 = road2['geometry'][0]
            return math.sqrt((p1['x'] - p2['x'])**2 + (p1['y'] - p2['y'])**2)
        
        return 0.0
    
    def calculate_junction_distance(self, incoming_road: int, outgoing_road: int, junction_id: int) -> float:
        """Calculate distance through a junction"""
        junction = self.db['junctions'][str(junction_id)]
        bbox = junction['bounding_box']
        
        # Approximate junction size
        width = bbox['max_x'] - bbox['min_x']
        height = bbox['max_y'] - bbox['min_y']
        
        return math.sqrt(width**2 + height**2) / 2  # Rough estimate
    
    def analyze_intersections(self):
        """Analyze intersection characteristics and complexity"""
        print("Analyzing intersections...")
        
        for junction_id, junction_data in self.db['junctions'].items():
            junction_id = int(junction_id)
            
            # Determine intersection type
            intersection_type = self.classify_intersection_type(junction_data)
            
            # Find approach roads
            approach_roads = []
            for connection in junction_data['connections']:
                incoming_road = connection['incomingRoad']
                if incoming_road not in approach_roads:
                    approach_roads.append(incoming_road)
            
            # Calculate conflict points (simplified)
            conflict_points = self.calculate_conflict_points(junction_data)
            
            # Calculate traffic complexity score
            traffic_complexity = self.calculate_traffic_complexity(
                junction_data, approach_roads, len(conflict_points)
            )
            
            analysis = IntersectionAnalysis(
                junction_id=junction_id,
                intersection_type=intersection_type,
                approach_roads=approach_roads,
                conflict_points=conflict_points,
                traffic_complexity=traffic_complexity
            )
            
            self.intersection_analyses[junction_id] = analysis
        
        print(f"Analyzed {len(self.intersection_analyses)} intersections")
    
    def classify_intersection_type(self, junction_data: Dict) -> str:
        """Classify intersection type based on structure"""
        num_connections = len(junction_data['connections'])
        connecting_roads = junction_data['connecting_roads']
        
        # Check if it's a roundabout
        junction_id = int(next(iter([k for k, v in self.db['junctions'].items() if v == junction_data])))
        if any(r['junction_id'] == junction_id for r in self.db['roundabouts']):
            return 'roundabout'
        
        # Simple classification based on number of connections
        if num_connections == 2:
            return 'uncontrolled'
        elif num_connections == 3:
            return 'yield'  # T-intersection typically yield
        elif num_connections == 4:
            return 'stop_sign'  # 4-way intersection typically stop sign
        else:
            return 'signalized'  # Complex intersections typically signalized
    
    def calculate_conflict_points(self, junction_data: Dict) -> List[Tuple[float, float]]:
        """Calculate potential conflict points in intersection"""
        conflict_points = []
        bbox = junction_data['bounding_box']
        
        center_x = (bbox['min_x'] + bbox['max_x']) / 2
        center_y = (bbox['min_y'] + bbox['max_y']) / 2
        
        # Simplified: add conflict points based on number of approaches
        num_approaches = len(set(conn['incomingRoad'] for conn in junction_data['connections']))
        
        if num_approaches >= 3:
            # Add center point as main conflict area
            conflict_points.append((center_x, center_y))
            
            # Add additional conflict points for complex intersections
            if num_approaches >= 4:
                offset = min(bbox['max_x'] - bbox['min_x'], bbox['max_y'] - bbox['min_y']) / 4
                conflict_points.extend([
                    (center_x + offset, center_y),
                    (center_x - offset, center_y),
                    (center_x, center_y + offset),
                    (center_x, center_y - offset)
                ])
        
        return conflict_points
    
    def calculate_traffic_complexity(self, junction_data: Dict, approach_roads: List[int], num_conflicts: int) -> float:
        """Calculate traffic complexity score (0-1)"""
        complexity = 0.0
        
        # Factor 1: Number of approaches (normalized to 0-1)
        num_approaches = len(approach_roads)
        approach_factor = min(num_approaches / 6, 1.0)  # Max complexity at 6+ approaches
        
        # Factor 2: Number of connections (turning movements)
        num_connections = len(junction_data['connections'])
        connection_factor = min(num_connections / 12, 1.0)  # Max complexity at 12+ connections
        
        # Factor 3: Lane complexity (sum of lanes from approach roads)
        total_lanes = 0
        for road_id in approach_roads:
            if str(road_id) in self.db['roads']:
                road_data = self.db['roads'][str(road_id)]
                driving_lanes = [l for l in road_data['lanes'].values() if l['lane_type'] == 'driving']
                total_lanes += len(driving_lanes)
        
        lane_factor = min(total_lanes / 16, 1.0)  # Max complexity at 16+ total lanes
        
        # Factor 4: Conflict points
        conflict_factor = min(num_conflicts / 8, 1.0)  # Max complexity at 8+ conflict points
        
        # Weighted average
        complexity = (
            approach_factor * 0.3 +
            connection_factor * 0.3 +
            lane_factor * 0.2 +
            conflict_factor * 0.2
        )
        
        return complexity
    
    def segment_roads_by_characteristics(self):
        """Segment roads based on geometric and traffic characteristics"""
        print("Segmenting roads by characteristics...")
        
        for road_id, road_data in self.db['roads'].items():
            road_id = int(road_id)
            segments = []
            
            geometry = road_data['geometry']
            if not geometry:
                continue
            
            current_segment_start = 0.0
            current_segment_type = None
            
            for i, geom_point in enumerate(geometry):
                # Determine segment type at this point
                segment_type = self.classify_road_segment_type(
                    road_data, geom_point, i, geometry
                )
                
                # Determine speed context
                speed_context = self.get_speed_context(road_data)
                
                # If segment type changes, finalize previous segment
                if current_segment_type is not None and segment_type != current_segment_type:
                    segments.append(RoadSegment(
                        road_id=road_id,
                        segment_type=current_segment_type,
                        start_s=current_segment_start,
                        end_s=geom_point['s'],
                        curvature=self.calculate_segment_curvature(
                            geometry, current_segment_start, geom_point['s']
                        ),
                        speed_context=speed_context
                    ))
                    current_segment_start = geom_point['s']
                
                current_segment_type = segment_type
            
            # Add final segment
            if current_segment_type is not None and geometry:
                segments.append(RoadSegment(
                    road_id=road_id,
                    segment_type=current_segment_type,
                    start_s=current_segment_start,
                    end_s=geometry[-1]['s'] + geometry[-1]['length'],
                    curvature=self.calculate_segment_curvature(
                        geometry, current_segment_start, geometry[-1]['s'] + geometry[-1]['length']
                    ),
                    speed_context=self.get_speed_context(road_data)
                ))
            
            self.road_segments[road_id] = segments
        
        total_segments = sum(len(segments) for segments in self.road_segments.values())
        print(f"Created {total_segments} road segments across {len(self.road_segments)} roads")
    
    def classify_road_segment_type(self, road_data: Dict, geom_point: Dict, index: int, geometry: List) -> str:
        """Classify the type of road segment at a given point"""
        # Check if near intersection
        if road_data['junction_id'] != -1:
            return 'intersection_approach'
        
        # Check geometry type
        if geom_point['geometry_type'] == 'line':
            return 'straight'
        elif geom_point['geometry_type'] in ['arc', 'spiral']:
            return 'curve'
        
        # Check for merge/diverge based on lane changes (simplified)
        if index > 0 and index < len(geometry) - 1:
            # This would require more detailed lane analysis
            pass
        
        return 'straight'  # Default
    
    def get_speed_context(self, road_data: Dict) -> str:
        """Get speed context classification for road"""
        road_type = road_data['road_type']
        speed_limit = road_data['speed_limit']
        
        if road_type in ['motorway', 'trunk']:
            return 'highway'
        elif road_type in ['primary', 'secondary']:
            return 'arterial'
        elif road_type == 'residential':
            return 'residential'
        elif road_type == 'service':
            return 'service'
        elif speed_limit:
            if speed_limit >= 45:  # mph
                return 'highway'
            elif speed_limit >= 30:
                return 'arterial'
            else:
                return 'residential'
        
        return 'arterial'  # Default
    
    def calculate_segment_curvature(self, geometry: List, start_s: float, end_s: float) -> float:
        """Calculate average curvature for a road segment"""
        relevant_geom = [g for g in geometry if start_s <= g['s'] <= end_s]
        
        if len(relevant_geom) < 2:
            return 0.0
        
        total_angle_change = 0.0
        total_distance = 0.0
        
        for i in range(1, len(relevant_geom)):
            prev_geom = relevant_geom[i-1]
            curr_geom = relevant_geom[i]
            
            angle_diff = abs(curr_geom['hdg'] - prev_geom['hdg'])
            if angle_diff > math.pi:
                angle_diff = 2 * math.pi - angle_diff
            
            distance = math.sqrt(
                (curr_geom['x'] - prev_geom['x'])**2 + 
                (curr_geom['y'] - prev_geom['y'])**2
            )
            
            total_angle_change += angle_diff
            total_distance += distance
        
        return total_angle_change / total_distance if total_distance > 0 else 0.0
    
    def identify_traffic_zones(self):
        """Identify and classify traffic zones (highway, urban, suburban, etc.)"""
        print("Identifying traffic zones...")
        
        zones = {
            'highway_zones': [],
            'urban_zones': [],
            'suburban_zones': [],
            'service_zones': []
        }
        
        # Group roads by proximity and characteristics
        processed_roads = set()
        
        for road_id, road_data in self.db['roads'].items():
            road_id = int(road_id)
            
            if road_id in processed_roads:
                continue
            
            # Find connected roads with similar characteristics
            zone_roads = self.find_similar_connected_roads(road_id, processed_roads)
            processed_roads.update(zone_roads)
            
            # Classify zone type
            zone_type = self.classify_zone_type(zone_roads)
            
            zone_info = {
                'roads': list(zone_roads),
                'center': self.calculate_zone_center(zone_roads),
                'characteristics': self.get_zone_characteristics(zone_roads)
            }
            
            zones[f'{zone_type}_zones'].append(zone_info)
        
        self.traffic_zones = zones
        
        for zone_type, zone_list in zones.items():
            print(f"Identified {len(zone_list)} {zone_type}")
    
    def find_similar_connected_roads(self, start_road_id: int, processed_roads: Set[int]) -> Set[int]:
        """Find roads connected to start_road with similar characteristics"""
        zone_roads = {start_road_id}
        queue = [start_road_id]
        start_road_data = self.db['roads'][str(start_road_id)]
        
        while queue:
            current_road_id = queue.pop(0)
            
            # Find connected roads
            for edge in self.graph.edges(current_road_id, data=True):
                connected_road_id = edge[1]
                
                if (connected_road_id not in processed_roads and 
                    connected_road_id not in zone_roads):
                    
                    connected_road_data = self.db['roads'][str(connected_road_id)]
                    
                    # Check if similar characteristics
                    if self.roads_have_similar_characteristics(start_road_data, connected_road_data):
                        zone_roads.add(connected_road_id)
                        queue.append(connected_road_id)
        
        return zone_roads
    
    def roads_have_similar_characteristics(self, road1: Dict, road2: Dict) -> bool:
        """Check if two roads have similar characteristics for zoning"""
        # Same road type
        if road1['road_type'] != road2['road_type']:
            return False
        
        # Similar speed limits (within 10 mph)
        if road1['speed_limit'] and road2['speed_limit']:
            if abs(road1['speed_limit'] - road2['speed_limit']) > 10:
                return False
        
        return True
    
    def classify_zone_type(self, zone_roads: Set[int]) -> str:
        """Classify the type of traffic zone"""
        road_types = []
        speed_limits = []
        
        for road_id in zone_roads:
            road_data = self.db['roads'][str(road_id)]
            road_types.append(road_data['road_type'])
            if road_data['speed_limit']:
                speed_limits.append(road_data['speed_limit'])
        
        # Determine zone type based on predominant characteristics
        if any(rt in ['motorway', 'trunk'] for rt in road_types):
            return 'highway'
        elif any(rt in ['primary', 'secondary'] for rt in road_types):
            return 'urban'
        elif road_types.count('residential') > len(road_types) / 2:
            return 'suburban'
        else:
            return 'service'
    
    def calculate_zone_center(self, zone_roads: Set[int]) -> Tuple[float, float]:
        """Calculate the geometric center of a zone"""
        all_x, all_y = [], []
        
        for road_id in zone_roads:
            road_data = self.db['roads'][str(road_id)]
            for geom_point in road_data['geometry']:
                all_x.append(geom_point['x'])
                all_y.append(geom_point['y'])
        
        if all_x and all_y:
            return (sum(all_x) / len(all_x), sum(all_y) / len(all_y))
        
        return (0.0, 0.0)
    
    def get_zone_characteristics(self, zone_roads: Set[int]) -> Dict:
        """Get characteristics summary for a zone"""
        total_length = 0.0
        speed_limits = []
        road_types = []
        
        for road_id in zone_roads:
            road_data = self.db['roads'][str(road_id)]
            total_length += road_data['length']
            road_types.append(road_data['road_type'])
            if road_data['speed_limit']:
                speed_limits.append(road_data['speed_limit'])
        
        return {
            'total_length': total_length,
            'avg_speed_limit': sum(speed_limits) / len(speed_limits) if speed_limits else None,
            'predominant_road_type': max(set(road_types), key=road_types.count),
            'road_count': len(zone_roads)
        }
    
    def generate_network_statistics(self) -> Dict:
        """Generate comprehensive network statistics"""
        stats = {
            'network_topology': {
                'total_roads': len(self.graph.nodes),
                'total_connections': len(self.graph.edges),
                'average_connections_per_road': len(self.graph.edges) / len(self.graph.nodes) if self.graph.nodes else 0,
                'network_density': nx.density(self.graph),
                'strongly_connected_components': len(list(nx.strongly_connected_components(self.graph))),
                'weakly_connected_components': len(list(nx.weakly_connected_components(self.graph)))
            },
            'road_characteristics': {
                'by_type': {},
                'by_speed_limit': {},
                'total_network_length': 0.0
            },
            'intersection_analysis': {
                'total_intersections': len(self.intersection_analyses),
                'by_type': {},
                'avg_complexity': 0.0,
                'high_complexity_intersections': []
            },
            'traffic_zones': {
                zone_type: len(zones) for zone_type, zones in self.traffic_zones.items()
            }
        }
        
        # Road characteristics
        for road_id, road_data in self.db['roads'].items():
            road_type = road_data['road_type']
            speed_limit = road_data['speed_limit']
            length = road_data['length']
            
            stats['road_characteristics']['total_network_length'] += length
            
            if road_type not in stats['road_characteristics']['by_type']:
                stats['road_characteristics']['by_type'][road_type] = {'count': 0, 'total_length': 0.0}
            stats['road_characteristics']['by_type'][road_type]['count'] += 1
            stats['road_characteristics']['by_type'][road_type]['total_length'] += length
            
            if speed_limit:
                speed_range = f"{int(speed_limit//10)*10}-{int(speed_limit//10)*10+9} mph"
                if speed_range not in stats['road_characteristics']['by_speed_limit']:
                    stats['road_characteristics']['by_speed_limit'][speed_range] = {'count': 0, 'total_length': 0.0}
                stats['road_characteristics']['by_speed_limit'][speed_range]['count'] += 1
                stats['road_characteristics']['by_speed_limit'][speed_range]['total_length'] += length
        
        # Intersection analysis
        if self.intersection_analyses:
            complexities = [analysis.traffic_complexity for analysis in self.intersection_analyses.values()]
            stats['intersection_analysis']['avg_complexity'] = sum(complexities) / len(complexities)
            
            # High complexity intersections (top 20%)
            high_complexity_threshold = np.percentile(complexities, 80)
            stats['intersection_analysis']['high_complexity_intersections'] = [
                {'junction_id': analysis.junction_id, 'complexity': analysis.traffic_complexity}
                for analysis in self.intersection_analyses.values()
                if analysis.traffic_complexity >= high_complexity_threshold
            ]
            
            # By intersection type
            for analysis in self.intersection_analyses.values():
                int_type = analysis.intersection_type
                if int_type not in stats['intersection_analysis']['by_type']:
                    stats['intersection_analysis']['by_type'][int_type] = 0
                stats['intersection_analysis']['by_type'][int_type] += 1
        
        return stats
    
    def analyze_full_network(self) -> Dict:
        """Perform complete network analysis"""
        print("Starting comprehensive road network analysis...")
        
        self.build_road_network_graph()
        self.analyze_intersections()
        self.segment_roads_by_characteristics()
        self.identify_traffic_zones()
        
        # Generate final analysis report
        analysis_report = {
            'network_graph': {
                'nodes': len(self.graph.nodes),
                'edges': len(self.graph.edges),
                'adjacency_list': dict(self.graph.adjacency())
            },
            'road_connections': [
                {
                    'from_road': conn.from_road,
                    'to_road': conn.to_road,
                    'connection_type': conn.connection_type,
                    'junction_id': conn.junction_id,
                    'distance': conn.distance
                }
                for conn in self.road_connections
            ],
            'intersection_analyses': {
                str(junction_id): {
                    'intersection_type': analysis.intersection_type,
                    'approach_roads': analysis.approach_roads,
                    'conflict_points': analysis.conflict_points,
                    'traffic_complexity': analysis.traffic_complexity
                }
                for junction_id, analysis in self.intersection_analyses.items()
            },
            'road_segments': {
                str(road_id): [
                    {
                        'segment_type': segment.segment_type,
                        'start_s': segment.start_s,
                        'end_s': segment.end_s,
                        'curvature': segment.curvature,
                        'speed_context': segment.speed_context
                    }
                    for segment in segments
                ]
                for road_id, segments in self.road_segments.items()
            },
            'traffic_zones': self.traffic_zones,
            'network_statistics': self.generate_network_statistics()
        }
        
        print("Network analysis complete!")
        return analysis_report


def analyze_network_from_database(database_file: str, output_file: str = None):
    """Analyze road network from existing road intelligence database"""
    with open(database_file, 'r') as f:
        road_db = json.load(f)
    
    analyzer = RoadNetworkAnalyzer(road_db)
    analysis = analyzer.analyze_full_network()
    
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        print(f"Network analysis saved to: {output_file}")
    
    return analysis


if __name__ == "__main__":
    # Example usage
    database_file = "Town01_road_intelligence.json"
    analysis = analyze_network_from_database(database_file, "Town01_network_analysis.json")
    
    print("\nNetwork Analysis Summary:")
    stats = analysis['network_statistics']
    print(f"Roads: {stats['network_topology']['total_roads']}")
    print(f"Connections: {stats['network_topology']['total_connections']}")
    print(f"Intersections: {stats['intersection_analysis']['total_intersections']}")
    print(f"Network Length: {stats['road_characteristics']['total_network_length']:.1f}m")