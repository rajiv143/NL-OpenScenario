#!/usr/bin/env python3
"""
Improved CARLA scenario preparation with start tokens and validation
Fixes truncation issues and ensures valid CARLA models
"""

import json
import os
from pathlib import Path
from sklearn.model_selection import train_test_split
import random
import re

# Valid CARLA vehicle models (add more as needed)
VALID_CARLA_VEHICLES = {
    # Sedans/Coupes
    'vehicle.audi.a2', 'vehicle.audi.etron', 'vehicle.audi.tt',
    'vehicle.bmw.grandtourer', 'vehicle.mercedes.coupe', 'vehicle.mercedes.coupe_2020',
    'vehicle.tesla.model3', 'vehicle.tesla.cybertruck',
    
    # SUVs/Trucks
    'vehicle.chevrolet.impala', 'vehicle.dodge.charger_2020', 'vehicle.dodge.charger_police',
    'vehicle.ford.crown', 'vehicle.ford.mustang', 'vehicle.jeep.wrangler_rubicon',
    'vehicle.lincoln.mkz_2017', 'vehicle.lincoln.mkz_2020',
    'vehicle.nissan.patrol', 'vehicle.nissan.patrol_2021', 'vehicle.nissan.micra',
    
    # Vans/Buses
    'vehicle.volkswagen.t2', 'vehicle.volkswagen.t2_2021',
    'vehicle.mercedes.sprinter', 'vehicle.mitsubishi.fusorosa',
    'vehicle.carlamotors.european_hgv',
    
    # Compact/City cars
    'vehicle.citroen.c3', 'vehicle.seat.leon', 'vehicle.toyota.prius',
    'vehicle.mini.cooper_s_2021', 'vehicle.micro.microlino',
    
    # Emergency/Special
    'vehicle.ford.ambulance', 'vehicle.carlamotors.firetruck',
    'vehicle.dodge.charger_police_2020',
    
    # Motorcycles/Bikes
    'vehicle.harley-davidson.low_rider', 'vehicle.kawasaki.ninja',
    'vehicle.vespa.zx125', 'vehicle.yamaha.yzf',
    'vehicle.bh.crossbike', 'vehicle.diamondback.century',
    'vehicle.gazelle.omafiets'
}

VALID_WALKER_MODELS = {f'walker.pedestrian.{i:04d}' for i in range(1, 50)}

def validate_and_fix_vehicle_model(model: str) -> str:
    """Validate and fix vehicle model names"""
    if model in VALID_CARLA_VEHICLES:
        return model
    
    # Try to fix common issues
    model_lower = model.lower()
    
    # Remove extra prefixes
    model_lower = model_lower.replace('vehicle.car.', 'vehicle.')
    model_lower = model_lower.replace('vehicle.carlamotors.', 'vehicle.')
    
    # Find closest match
    for valid_model in VALID_CARLA_VEHICLES:
        if valid_model.lower() == model_lower:
            return valid_model
        # Partial match on brand/model
        if model_lower.split('.')[-1] in valid_model:
            return valid_model
    
    # Default fallback
    return 'vehicle.audi.a2'

def standardize_spawn_criteria(spawn_data: dict) -> dict:
    """Standardize spawn criteria structure"""
    standardized = {}
    
    # Handle different field names
    if 'spawn_criteria' in spawn_data:
        criteria = spawn_data['spawn_criteria']
    elif 'criteria' in spawn_data:
        criteria = spawn_data['criteria']
    else:
        criteria = spawn_data
    
    # Always use 'criteria' as the key
    standardized['criteria'] = {}
    
    # Standardize common fields
    if 'lane_type' in criteria:
        standardized['criteria']['lane_type'] = criteria['lane_type']
    
    if 'distance_to_ego' in criteria:
        distance = criteria['distance_to_ego']
        # Ensure it's in the correct format
        if isinstance(distance, dict) and 'min' in distance and 'max' in distance:
            standardized['criteria']['distance_to_ego'] = distance
        elif isinstance(distance, (int, float)):
            standardized['criteria']['distance_to_ego'] = {
                'min': distance - 10,
                'max': distance + 10
            }
    
    # Copy other standard fields
    for field in ['relative_position', 'road_relationship', 'lane_relationship', 
                  'road_context', 'is_intersection', 'lateral_offset']:
        if field in criteria:
            standardized['criteria'][field] = criteria[field]
    
    return standardized

def add_start_token_to_json(scenario_json: dict) -> str:
    """Add explicit start token and ensure complete JSON"""
    # Ensure all required top-level fields are present and in order
    complete_scenario = {
        "scenario_name": scenario_json.get("scenario_name", "generated_scenario"),
        "description": scenario_json.get("description", "CARLA scenario"),
        "weather": scenario_json.get("weather", "clear"),
        "ego_vehicle_model": validate_and_fix_vehicle_model(
            scenario_json.get("ego_vehicle_model", "vehicle.audi.a2")
        ),
        "ego_spawn": scenario_json.get("ego_spawn", {
            "criteria": {"lane_type": "Driving", "is_intersection": False}
        }),
        "ego_start_speed": scenario_json.get("ego_start_speed", 10),
        "actors": scenario_json.get("actors", []),
        "actions": scenario_json.get("actions", []),
        "success_distance": scenario_json.get("success_distance", 100),
        "timeout": scenario_json.get("timeout", 60),
        "collision_allowed": scenario_json.get("collision_allowed", False)
    }
    
    # Fix vehicle models in actors
    for actor in complete_scenario.get("actors", []):
        if 'model' in actor:
            if actor['type'] == 'vehicle':
                actor['model'] = validate_and_fix_vehicle_model(actor['model'])
            elif actor['type'] in ['pedestrian', 'walker']:
                if not actor['model'].startswith('walker.'):
                    actor['model'] = 'walker.pedestrian.0010'
        
        # Standardize spawn criteria
        if 'spawn' in actor:
            actor['spawn'] = standardize_spawn_criteria(actor['spawn'])
    
    # Fix action fields
    for action in complete_scenario.get("actions", []):
        # Ensure speed_value not speed
        if 'speed' in action and 'speed_value' not in action:
            action['speed_value'] = action.pop('speed')
        
        # Fix trigger types
        if action.get('trigger_type') == 'after_previous_action':
            action['trigger_type'] = 'after_previous'
    
    # Add explicit start token in the JSON string
    json_str = json.dumps(complete_scenario, indent=2)
    
    # Add a comment at the start (will be part of the training)
    return "<<<JSON_START>>>\n" + json_str + "\n<<<JSON_END>>>"

def prepare_training_data(scenarios_dir="dataset1908", output_dir="training_data"):
    """Convert scenario files into LLM training format with improvements"""
    training_data = []
    
    base_dir = Path(scenarios_dir)
    
    if not base_dir.exists():
        print(f"Error: {scenarios_dir} directory not found!")
        return None, None
    
    print(f"Processing {base_dir.name} with improvements...")
    
    # Find all JSON files
    json_files = sorted(list(base_dir.glob("*.json")))
    
    fixed_count = 0
    for json_file in json_files:
        txt_file = json_file.with_suffix('.txt')
        
        if txt_file.exists():
            try:
                # Read natural language description
                with open(txt_file, 'r') as f:
                    description = f.read().strip()
                
                # Read JSON scenario
                with open(json_file, 'r') as f:
                    scenario_json = json.load(f)
                
                # Apply fixes and add start token
                fixed_json_str = add_start_token_to_json(scenario_json)
                fixed_count += 1
                
                # Extract scenario number
                scenario_num = json_file.stem.split('_')[-1] if '_' in json_file.stem else "unknown"
                
                # Format 1: Direct instruction with emphasis on complete generation
                training_example = {
                    "instruction": "Generate a COMPLETE CARLA scenario JSON. Start with <<<JSON_START>>> and end with <<<JSON_END>>>. Include ALL fields in order: scenario_name, description, weather, ego_vehicle_model, ego_spawn, ego_start_speed, actors, actions, success_distance, timeout, collision_allowed.",
                    "input": description,
                    "output": fixed_json_str,
                    "scenario_id": json_file.stem,
                    "scenario_number": scenario_num
                }
                training_data.append(training_example)
                
                # Format 2: With context (25% of examples)
                if random.random() < 0.25:
                    context_example = {
                        "instruction": "Create a CARLA autonomous vehicle testing scenario in JSON format. IMPORTANT: Start your response with <<<JSON_START>>> and include all required fields.",
                        "input": f"Scenario description: {description}",
                        "output": fixed_json_str,
                        "scenario_id": json_file.stem,
                        "scenario_number": scenario_num
                    }
                    training_data.append(context_example)
                
                # Format 3: Specific request variation (25% of examples)
                if random.random() < 0.25:
                    request_variations = [
                        "Convert this into a COMPLETE CARLA scenario JSON (start with <<<JSON_START>>>):",
                        "Generate a full JSON configuration for CARLA (include <<<JSON_START>>> token):",
                        "Create a complete structured CARLA scenario (begin with <<<JSON_START>>>):",
                        "Design a CARLA test scenario JSON with all fields (start: <<<JSON_START>>>):",
                        "Build a complete scenario JSON (<<<JSON_START>>> to <<<JSON_END>>>):"
                    ]
                    varied_example = {
                        "instruction": random.choice(request_variations),
                        "input": description,
                        "output": fixed_json_str,
                        "scenario_id": json_file.stem,
                        "scenario_number": scenario_num
                    }
                    training_data.append(varied_example)
                    
            except Exception as e:
                print(f"Error processing {json_file}: {e}")
                continue
        else:
            print(f"Warning: No matching .txt file found for {json_file}")
    
    print(f"\nCreated {len(training_data)} training examples from {len(json_files)} scenario files")
    print(f"Fixed {fixed_count} scenarios (vehicle models, spawn criteria, start tokens)")
    
    if not training_data:
        print("No training data created!")
        return None, None
    
    # Shuffle data
    random.shuffle(training_data)
    
    # Split into train/validation/test (70/15/15)
    train_data, temp_data = train_test_split(training_data, test_size=0.3, random_state=42)
    val_data, test_data = train_test_split(temp_data, test_size=0.5, random_state=42)
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Save datasets
    with open(output_path / 'train_dataset.json', 'w') as f:
        json.dump(train_data, f, indent=2)
    
    with open(output_path / 'val_dataset.json', 'w') as f:
        json.dump(val_data, f, indent=2)
    
    with open(output_path / 'test_dataset.json', 'w') as f:
        json.dump(test_data, f, indent=2)
    
    # Create a validation report
    validation_report = {
        "total_examples": len(training_data),
        "train_examples": len(train_data),
        "val_examples": len(val_data),
        "test_examples": len(test_data),
        "improvements_applied": {
            "start_tokens_added": True,
            "vehicle_models_validated": True,
            "spawn_criteria_standardized": True,
            "action_fields_fixed": True
        },
        "example_with_tokens": training_data[0]["output"][:200] if training_data else None
    }
    
    with open(output_path / 'validation_report.json', 'w') as f:
        json.dump(validation_report, f, indent=2)
    
    print(f"\nDataset Statistics:")
    print(f"  Training examples: {len(train_data)}")
    print(f"  Validation examples: {len(val_data)}")
    print(f"  Test examples: {len(test_data)}")
    print(f"\nImprovements Applied:")
    print(f"  ✓ Start/end tokens added to all examples")
    print(f"  ✓ Vehicle models validated and fixed")
    print(f"  ✓ Spawn criteria standardized")
    print(f"  ✓ Action fields corrected")
    
    print(f"\nDatasets saved to {output_path}/")
    
    return train_data, val_data

if __name__ == "__main__":
    print("Preparing improved dataset for LLM training...")
    print("This version includes:")
    print("  - Explicit start/end tokens to prevent truncation")
    print("  - Valid CARLA vehicle model names")
    print("  - Standardized spawn criteria structure")
    print("  - Fixed action field names\n")
    
    # Prepare training data with improvements
    train_data, val_data = prepare_training_data()
    
    if train_data is not None:
        print("\n✓ Data preparation complete with improvements!")
        print("\nNext steps:")
        print("1. Retrain your model with this improved dataset")
        print("2. The model should now generate complete JSON starting with <<<JSON_START>>>")
        print("3. Update your inference script to handle/remove these tokens")
        
        # Show example of improved output
        if train_data:
            print("\nExample of improved training format:")
            print(train_data[0]["output"][:300] + "...")
    else:
        print("\n✗ Data preparation failed!")