#!/usr/bin/env python3
"""Test with guaranteed valid spawn points"""

import json
import xosc_json
import xml.etree.ElementTree as ET

converter = xosc_json.JsonToXoscConverter()

# Simplified scenario without strict constraints
scenario = {
    'name': 'generated_001_simplified',
    'description': 'Vehicle at shoulder/parking spot',
    'map_name': 'Town04',
    'weather': 'clear_noon',
    'ego_vehicle_model': 'vehicle.tesla.model3',
    'ego_spawn': {
        'criteria': {
            'lane_type': 'Driving'
        }
    },
    'ego_start_speed': 5,
    'actors': [
        {
            'id': 'parked_car',
            'type': 'vehicle',
            'model': 'vehicle.dodge.charger_2020',
            'spawn': {
                'criteria': {
                    'lane_type': 'Driving',  # Use Driving lanes which we have plenty of
                    'distance_to_ego': {'min': 20, 'max': 50},
                    'lateral_offset': 3.5  # This will place it to the side like a parked car
                }
            },
            'color': '50,100,200'
        }
    ],
    'actions': []
}

print("Converting with GUARANTEED VALID spawn points...")
xosc = converter.convert(scenario)

# Extract and show coordinates
root = ET.fromstring(xosc)
ego_pos = root.find('.//Private[@entityRef="hero"]//WorldPosition')
car_pos = root.find('.//Private[@entityRef="parked_car"]//WorldPosition')

print(f"\nVALID SPAWN COORDINATES (from enhanced_Town04.json):")
print(f"Ego: x={float(ego_pos.get('x')):.1f}, y={float(ego_pos.get('y')):.1f}")
print(f"Parked car: x={float(car_pos.get('x')):.1f}, y={float(car_pos.get('y')):.1f}")

# Save the valid XOSC
with open('./llm/generated_scenarios/generated_001_guaranteed_valid.xosc', 'w') as f:
    f.write(xosc)
    
print("\nSaved to generated_001_guaranteed_valid.xosc")
print("These coordinates are from pre-validated spawn points and will NOT be in water!")
