import carla, json

def enhanced_spawn_dump():
    client = carla.Client("localhost", 2000)
    towns = ['Town01', 'Town02', 'Town03', 'Town04', 'Town05']
    
    for town in towns:
        print(f"\n=== Processing {town} ===")
        world = client.load_world(town)
        mp = world.get_map()
        
        all_waypoints = {}
        
        # Get ALL waypoints (not just spawn points)
        waypoint_list = mp.generate_waypoints(2.0)
        
        # Also sample for non-driving waypoints that generate_waypoints misses
        additional_waypoints = []
        for x in range(-300, 300, 10):
            for y in range(-300, 300, 10):
                try:
                    loc = carla.Location(x, y, 0.5)
                    wp = mp.get_waypoint(loc, project_to_road=False, lane_type=carla.LaneType.Any)
                    if wp and wp.lane_type.name != "Driving":
                        additional_waypoints.append(wp)
                except:
                    continue
        
        # Combine all waypoints
        all_waypoints_combined = waypoint_list + additional_waypoints
        
        # Group by lane type with FULL metadata
        by_lane_type = {}
        for wp in all_waypoints_combined:
            lane_type = wp.lane_type.name
            
            waypoint_data = {
                "x": round(wp.transform.location.x, 3),
                "y": round(wp.transform.location.y, 3), 
                "z": round(wp.transform.location.z, 3),
                "yaw": round(wp.transform.rotation.yaw, 3),
                "lane_type": lane_type,
                "road_id": wp.road_id,
                "lane_id": wp.lane_id,
                "is_intersection": wp.is_junction,
                "lane_width": round(wp.lane_width, 2)  # Bonus: useful for clearance
            }
            
            if lane_type not in by_lane_type:
                by_lane_type[lane_type] = []
            by_lane_type[lane_type].append(waypoint_data)
        
        # Save with rich metadata
        data = {f"Carla/Maps/{town}": by_lane_type}
        with open(f"enhanced_{town}.json", "w") as f:
            json.dump(data, f, indent=2)
            
        print(f"Lane types found:")
        for lt, points in by_lane_type.items():
            print(f"  {lt}: {len(points)} waypoints")

if __name__ == "__main__":
    enhanced_spawn_dump()