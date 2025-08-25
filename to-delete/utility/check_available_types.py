import carla

def check_available_lane_types(world):
    mp = world.get_map()
    
    print(f"Checking {mp.name}")
    
    # Method 1: Check all possible lane types
    lane_types_found = set()
    waypoints = mp.generate_waypoints(5.0)  # Sparse sampling
    
    for wp in waypoints:
        lane_types_found.add(wp.lane_type.name)
    
    print(f"Lane types from generate_waypoints(): {sorted(lane_types_found)}")
    
    # Method 2: Try to find specific lane types
    test_locations = [
        carla.Location(100, 100, 0),
        carla.Location(200, 200, 0), 
        carla.Location(0, 0, 0),
        carla.Location(-100, -100, 0)
    ]
    
    found_types = set()
    for loc in test_locations:
        try:
            # project_to_road=False to get non-driving areas
            wp = mp.get_waypoint(loc, project_to_road=False, 
                                lane_type=carla.LaneType.Any)
            if wp:
                found_types.add(wp.lane_type.name)
        except:
            continue
    
    print(f"Lane types from get_waypoint(): {sorted(found_types)}")
    
    # Method 3: Check all available LaneType enum values
    print("\nAll possible LaneType values:")
    for attr in dir(carla.LaneType):
        if not attr.startswith('_'):
            print(f"  {attr}")

if __name__ == "__main__":
    client = carla.Client("localhost", 2000)
    for world_x in ["Town01", "Town02", "Town03", "Town04", "Town05"]:
        world = client.load_world(world_x)
        client.set_timeout(10.0)
        check_available_lane_types(world)