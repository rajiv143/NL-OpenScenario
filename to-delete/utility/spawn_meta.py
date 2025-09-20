# spawn_dump.py
# This script connects to a CARLA server, retrieves spawn points from the map,
# and saves them in a JSON file. Each spawn point includes its coordinates, yaw,
# lane type, road ID, lane ID, and whether it is an intersection.
# It is useful for understanding the layout of the map and for debugging purposes.
import carla, json

def dump_spawn_points(out="spawn_meta.json"):
    client = carla.Client("localhost", 2000)
    client.set_timeout(10.0)
    world = client.get_world()
    mp    = world.get_map()
    data  = {}
    pts   = []
    for t in mp.get_spawn_points():
        wp = mp.get_waypoint(t.location)
        pts.append({
            "x": round(t.location.x,3),
            "y": round(t.location.y,3),
            "z": round(t.location.z,3),
            "yaw": round(t.rotation.yaw,3),
            "lane_type":     wp.lane_type.name,
            "road_id":       wp.road_id,
            "lane_id":       wp.lane_id,
            "is_intersection": wp.is_intersection
        })
    data[mp.name] = pts
    print(f"Outputted to spawns/{mp.name.split('/')[-1]}.json")
    with open(f"spawns/{mp.name.split('/')[-1]}.json","w") as f:
        json.dump(data, f, indent=2)

if __name__=="__main__":
    dump_spawn_points()
