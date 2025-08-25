#!/usr/bin/env python3
"""
Extract accurate shoulder lane spawn points directly from CARLA
This ensures we get the correct lane types and positions
"""

import carla
import json
import time
import argparse
import os
from typing import Dict, List, Tuple

def get_lane_type_string(lane_type):
    """Convert CARLA lane type to string"""
    lane_type_map = {
        carla.LaneType.NONE: 'None',
        carla.LaneType.Driving: 'Driving',
        carla.LaneType.Stop: 'Stop',
        carla.LaneType.Shoulder: 'Shoulder',
        carla.LaneType.Biking: 'Biking',
        carla.LaneType.Sidewalk: 'Sidewalk',
        carla.LaneType.Border: 'Border',
        carla.LaneType.Restricted: 'Restricted',
        carla.LaneType.Parking: 'Parking',
        carla.LaneType.Bidirectional: 'Bidirectional',
        carla.LaneType.Median: 'Median',
        carla.LaneType.Special1: 'Special1',
        carla.LaneType.Special2: 'Special2',
        carla.LaneType.Special3: 'Special3',
        carla.LaneType.RoadWorks: 'RoadWorks',
        carla.LaneType.Tram: 'Tram',
        carla.LaneType.Rail: 'Rail',
        carla.LaneType.Entry: 'Entry',
        carla.LaneType.Exit: 'Exit',
        carla.LaneType.OffRamp: 'OffRamp',
        carla.LaneType.OnRamp: 'OnRamp',
        carla.LaneType.Any: 'Any'
    }
    return lane_type_map.get(lane_type, 'Unknown')

def extract_lane_spawns(client, map_name: str, sample_distance: float = 10.0) -> Dict:
    """Extract spawn points for all lane types from CARLA"""
    
    print(f"Loading map {map_name}...")
    world = client.load_world(map_name)
    time.sleep(5)  # Wait for map to load fully
    
    carla_map = world.get_map()
    spawn_points = []
    
    # Track processed segments to avoid duplicates
    processed = set()
    
    # Get all waypoints including non-drivable lanes
    print(f"Extracting all lane types with {sample_distance}m spacing...")
    
    # Generate waypoints for ALL lane types, not just driving
    all_waypoints = []
    
    # Method 1: Generate waypoints at regular intervals and check all lanes
    x_min, y_min = -500, -500  # Adjust based on map size
    x_max, y_max = 500, 500
    
    # Use a grid approach to find all lanes
    for x in range(int(x_min), int(x_max), int(sample_distance * 2)):
        for y in range(int(y_min), int(y_max), int(sample_distance * 2)):
            location = carla.Location(x=x, y=y, z=0)
            
            # Get the closest waypoint (driving lane)
            wp = carla_map.get_waypoint(location, project_to_road=True, 
                                       lane_type=carla.LaneType.Any)
            
            if wp:
                # Get all lanes at this road section
                road_id = wp.road_id
                section_id = wp.section_id
                
                # Try to get waypoints for all lane IDs (positive and negative)
                for lane_id in range(-10, 11):  # Check lane IDs from -10 to 10
                    try:
                        # Try to get waypoint at this specific lane
                        test_wp = carla_map.get_waypoint_xodr(road_id, lane_id, wp.s)
                        
                        if test_wp and test_wp.lane_type != carla.LaneType.NONE:
                            wp_id = (test_wp.road_id, test_wp.section_id, test_wp.lane_id,
                                   round(test_wp.transform.location.x / sample_distance),
                                   round(test_wp.transform.location.y / sample_distance))
                            
                            if wp_id not in processed:
                                processed.add(wp_id)
                                
                                lane_type = get_lane_type_string(test_wp.lane_type)
                                
                                spawn = {
                                    'x': test_wp.transform.location.x,
                                    'y': test_wp.transform.location.y,
                                    'z': test_wp.transform.location.z,
                                    'yaw': test_wp.transform.rotation.yaw,
                                    'road_id': test_wp.road_id,
                                    'section_id': test_wp.section_id,
                                    'lane_id': test_wp.lane_id,
                                    'lane_type': lane_type,
                                    'lane_width': test_wp.lane_width,
                                    'is_junction': test_wp.is_junction
                                }
                                
                                spawn_points.append(spawn)
                    except:
                        continue
    
    # Method 2: Also use generate_waypoints for driving lanes
    print("Adding driving lane waypoints...")
    driving_waypoints = carla_map.generate_waypoints(sample_distance)
    
    for wp in driving_waypoints:
        wp_id = (wp.road_id, wp.section_id, wp.lane_id,
                round(wp.transform.location.x / sample_distance),
                round(wp.transform.location.y / sample_distance))
        
        if wp_id not in processed:
            processed.add(wp_id)
            
            lane_type = get_lane_type_string(wp.lane_type)
            
            spawn = {
                'x': wp.transform.location.x,
                'y': wp.transform.location.y,
                'z': wp.transform.location.z,
                'yaw': wp.transform.rotation.yaw,
                'road_id': wp.road_id,
                'section_id': wp.section_id,
                'lane_id': wp.lane_id,
                'lane_type': lane_type,
                'lane_width': wp.lane_width,
                'is_junction': wp.is_junction
            }
            
            spawn_points.append(spawn)
    
    # Count by type
    type_counts = {}
    for sp in spawn_points:
        lt = sp['lane_type']
        type_counts[lt] = type_counts.get(lt, 0) + 1
    
    print(f"\nExtracted {len(spawn_points)} spawn points:")
    for lt, count in sorted(type_counts.items()):
        print(f"  {lt}: {count}")
    
    # Separate shoulder spawns
    shoulder_spawns = [sp for sp in spawn_points if sp['lane_type'] == 'Shoulder']
    print(f"\nFound {len(shoulder_spawns)} shoulder lane spawns")
    
    return {
        'map_name': map_name,
        'total_spawns': len(spawn_points),
        'spawn_points': spawn_points,
        'type_counts': type_counts,
        'shoulder_spawns': shoulder_spawns
    }

def get_available_maps():
    """Get list of available maps from maps/ directory"""
    import os
    import glob
    
    xodr_files = glob.glob('maps/*.xodr')
    map_names = []
    for xodr in xodr_files:
        basename = os.path.basename(xodr)
        map_name = basename.replace('.xodr', '')
        map_names.append(map_name)
    
    return sorted(map_names)

def main():
    parser = argparse.ArgumentParser(description='Extract accurate lane spawns from CARLA')
    parser.add_argument('--map', help='Specific map name (if not provided, processes all maps)')
    parser.add_argument('--host', default='127.0.0.1', help='CARLA host')
    parser.add_argument('--port', type=int, default=2000, help='CARLA port')
    parser.add_argument('--sample-distance', type=float, default=2.0, 
                       help='Distance between spawn points (default: 2m)')
    parser.add_argument('-o', '--output', help='Output directory')
    
    args = parser.parse_args()
    
    # Connect to CARLA
    print(f"Connecting to CARLA at {args.host}:{args.port}...")
    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    
    # Test connection
    try:
        version = client.get_server_version()
        print(f"Connected to CARLA {version}")
    except Exception as e:
        print(f"Failed to connect to CARLA: {e}")
        return
    
    # Get maps to process
    if args.map:
        maps_to_process = [args.map]
    else:
        maps_to_process = get_available_maps()
        print(f"Found {len(maps_to_process)} maps to process: {', '.join(maps_to_process)}")
    
    # Process each map
    all_results = {}
    
    for map_name in maps_to_process:
        print(f"\n{'='*60}")
        print(f"Processing {map_name}...")
        print(f"{'='*60}")
        
        try:
            # Extract spawns
            result = extract_lane_spawns(client, map_name, args.sample_distance)
            all_results[map_name] = result
            
            # Save individual map results
            output_dir = args.output or 'carla_accurate_spawns'
            os.makedirs(output_dir, exist_ok=True)
            
            output_file = os.path.join(output_dir, f"{map_name}_spawns.json")
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            print(f"Saved to {output_file}")
            
        except Exception as e:
            print(f"Error processing {map_name}: {e}")
            continue
    
    # Save combined results
    if all_results:
        combined_file = os.path.join(output_dir, 'all_maps_spawns.json')
        with open(combined_file, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f"\nSaved combined results to {combined_file}")
        
        # Print summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        for map_name, result in all_results.items():
            print(f"\n{map_name}:")
            for lt, count in sorted(result['type_counts'].items()):
                print(f"  {lt}: {count}")

if __name__ == '__main__':
    main()