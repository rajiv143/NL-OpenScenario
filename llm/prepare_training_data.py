#!/usr/bin/env python3
"""
Prepare CARLA scenarios for Llama model training
Converts scenario files into LLM training format
"""

import json
import os
from pathlib import Path
from sklearn.model_selection import train_test_split
import random

def prepare_training_data(scenarios_dir="claude_scenarios", output_dir="."):
    """Convert scenario files into LLM training format"""
    training_data = []
    
    base_dir = Path(scenarios_dir)
    
    if not base_dir.exists():
        print(f"Error: {scenarios_dir} directory not found!")
        return None, None
    
    # Process all subdirectories
    for subdir in sorted(base_dir.iterdir()):
        if subdir.is_dir():
            print(f"Processing {subdir.name}...")
            
            # Find all JSON files
            json_files = sorted(list(subdir.glob("*.json")))
            
            for json_file in json_files:
                # Skip description files
                if "_description" in json_file.name:
                    continue
                
                # Get corresponding description file
                desc_file = json_file.with_name(f"{json_file.stem}_description.txt")
                
                if desc_file.exists():
                    try:
                        # Read natural language description
                        with open(desc_file, 'r') as f:
                            description = f.read().strip()
                        
                        # Read JSON scenario
                        with open(json_file, 'r') as f:
                            scenario_json = json.load(f)
                        
                        # Create training example with multiple formats
                        # Format 1: Direct instruction
                        training_example = {
                            "instruction": "Generate a CARLA scenario JSON based on this description:",
                            "input": description,
                            "output": json.dumps(scenario_json, indent=2),
                            "complexity_level": subdir.name.split("_")[0]  # 01, 02, etc.
                        }
                        training_data.append(training_example)
                        
                        # Format 2: With context (25% of examples)
                        if random.random() < 0.25:
                            context_example = {
                                "instruction": "Create a CARLA autonomous vehicle testing scenario in JSON format. The scenario should include spawn criteria, actors, and actions.",
                                "input": f"Scenario description: {description}",
                                "output": json.dumps(scenario_json, indent=2),
                                "complexity_level": subdir.name.split("_")[0]
                            }
                            training_data.append(context_example)
                        
                        # Format 3: Specific request variation (25% of examples)
                        if random.random() < 0.25:
                            request_variations = [
                                "Convert this natural language description into a CARLA scenario JSON:",
                                "Generate a JSON configuration for CARLA simulator with the following scenario:",
                                "Create a structured CARLA scenario from this description:",
                                "Design a CARLA test scenario in JSON format based on:"
                            ]
                            varied_example = {
                                "instruction": random.choice(request_variations),
                                "input": description,
                                "output": json.dumps(scenario_json, indent=2),
                                "complexity_level": subdir.name.split("_")[0]
                            }
                            training_data.append(varied_example)
                            
                    except Exception as e:
                        print(f"Error processing {json_file}: {e}")
                        continue
    
    print(f"\nCreated {len(training_data)} training examples")
    
    if not training_data:
        print("No training data created!")
        return None, None
    
    # Shuffle data
    random.shuffle(training_data)
    
    # Split into train/validation/test (70/15/15)
    train_data, temp_data = train_test_split(training_data, test_size=0.3, random_state=42)
    val_data, test_data = train_test_split(temp_data, test_size=0.5, random_state=42)
    
    # Save datasets
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    with open(output_path / 'train_dataset.json', 'w') as f:
        json.dump(train_data, f, indent=2)
    
    with open(output_path / 'val_dataset.json', 'w') as f:
        json.dump(val_data, f, indent=2)
    
    with open(output_path / 'test_dataset.json', 'w') as f:
        json.dump(test_data, f, indent=2)
    
    # Save dataset statistics
    stats = {
        "total_examples": len(training_data),
        "train_examples": len(train_data),
        "val_examples": len(val_data),
        "test_examples": len(test_data),
        "complexity_distribution": {}
    }
    
    # Count examples per complexity level
    for data in training_data:
        level = data.get("complexity_level", "unknown")
        stats["complexity_distribution"][level] = stats["complexity_distribution"].get(level, 0) + 1
    
    with open(output_path / 'dataset_stats.json', 'w') as f:
        json.dump(stats, f, indent=2)
    
    print(f"\nDataset Statistics:")
    print(f"  Training examples: {len(train_data)}")
    print(f"  Validation examples: {len(val_data)}")
    print(f"  Test examples: {len(test_data)}")
    print(f"\nComplexity Distribution:")
    for level, count in sorted(stats["complexity_distribution"].items()):
        print(f"  Level {level}: {count} examples")
    
    print(f"\nDatasets saved to {output_path}")
    
    return train_data, val_data

def create_few_shot_examples(output_dir="."):
    """Create a small set of few-shot examples for testing"""
    few_shot_examples = [
        {
            "description": "A stationary vehicle is parked 30 meters ahead of the ego vehicle.",
            "scenario": {
                "scenario_name": "example_static",
                "description": "Static vehicle ahead",
                "weather": "clear",
                "ego_vehicle_model": "vehicle.audi.a2",
                "ego_spawn": {
                    "criteria": {
                        "lane_type": "Driving",
                        "lane_id": {"min": 1, "max": 4},
                        "is_intersection": False
                    }
                },
                "ego_start_speed": 0,
                "actors": [
                    {
                        "id": "static_vehicle",
                        "type": "vehicle",
                        "model": "vehicle.toyota.prius",
                        "spawn": {
                            "criteria": {
                                "lane_type": "Driving",
                                "distance_to_ego": {"min": 25, "max": 35},
                                "relative_position": "ahead",
                                "lane_relationship": "same_lane"
                            }
                        },
                        "color": "255,0,0"
                    }
                ],
                "actions": [],
                "success_distance": 100,
                "timeout": 60,
                "collision_allowed": False
            }
        },
        {
            "description": "A vehicle ahead starts moving at 10 m/s when ego approaches within 20 meters.",
            "scenario": {
                "scenario_name": "example_moving",
                "description": "Vehicle starts moving when ego approaches",
                "weather": "cloudy",
                "ego_vehicle_model": "vehicle.audi.a2",
                "ego_spawn": {
                    "criteria": {
                        "lane_type": "Driving",
                        "lane_id": {"min": 1, "max": 4},
                        "is_intersection": False
                    }
                },
                "ego_start_speed": 0,
                "actors": [
                    {
                        "id": "moving_vehicle",
                        "type": "vehicle",
                        "model": "vehicle.bmw.grandtourer",
                        "spawn": {
                            "criteria": {
                                "lane_type": "Driving",
                                "distance_to_ego": {"min": 30, "max": 40},
                                "relative_position": "ahead",
                                "lane_relationship": "same_lane"
                            }
                        },
                        "color": "0,255,0"
                    }
                ],
                "actions": [
                    {
                        "actor_id": "moving_vehicle",
                        "action_type": "speed",
                        "trigger_type": "distance_to_ego",
                        "trigger_value": 20,
                        "trigger_comparison": "<",
                        "speed_value": 10,
                        "dynamics_dimension": "time",
                        "dynamics_value": 2.0,
                        "dynamics_shape": "linear",
                        "delay": 0.2
                    }
                ],
                "success_distance": 100,
                "timeout": 60,
                "collision_allowed": False
            }
        }
    ]
    
    output_path = Path(output_dir)
    with open(output_path / 'few_shot_examples.json', 'w') as f:
        json.dump(few_shot_examples, f, indent=2)
    
    print(f"Created {len(few_shot_examples)} few-shot examples")

if __name__ == "__main__":
    # Prepare main training data
    train_data, val_data = prepare_training_data()
    
    # Create few-shot examples
    create_few_shot_examples()
    
    print("\n✓ Data preparation complete!")
    print("  - train_dataset.json")
    print("  - val_dataset.json")
    print("  - test_dataset.json")
    print("  - dataset_stats.json")
    print("  - few_shot_examples.json")