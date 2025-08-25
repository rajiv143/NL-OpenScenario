#!/usr/bin/env python3
"""
Prepare CARLA scenarios from dataset1908 for Llama model training
Converts scenario files into LLM training format
"""

import json
import os
from pathlib import Path
from sklearn.model_selection import train_test_split
import random

def prepare_training_data(scenarios_dir="dataset1908", output_dir="training_data"):
    """Convert scenario files into LLM training format"""
    training_data = []
    
    base_dir = Path(scenarios_dir)
    
    if not base_dir.exists():
        print(f"Error: {scenarios_dir} directory not found!")
        return None, None
    
    # Process all files directly in dataset1908 directory
    print(f"Processing {base_dir.name}...")
    
    # Find all JSON files
    json_files = sorted(list(base_dir.glob("*.json")))
    
    for json_file in json_files:
        # Get corresponding .txt file (same name, different extension)
        txt_file = json_file.with_suffix('.txt')
        
        if txt_file.exists():
            try:
                # Read natural language description
                with open(txt_file, 'r') as f:
                    description = f.read().strip()
                
                # Read JSON scenario
                with open(json_file, 'r') as f:
                    scenario_json = json.load(f)
                
                # Extract scenario number for complexity tracking
                scenario_num = json_file.stem.split('_')[-1] if '_' in json_file.stem else "unknown"
                
                # Create training example with multiple formats
                # Format 1: Direct instruction
                training_example = {
                    "instruction": "Generate a CARLA scenario JSON based on this description:",
                    "input": description,
                    "output": json.dumps(scenario_json, indent=2),
                    "scenario_id": json_file.stem,
                    "scenario_number": scenario_num
                }
                training_data.append(training_example)
                
                # Format 2: With context (25% of examples)
                if random.random() < 0.25:
                    context_example = {
                        "instruction": "Create a CARLA autonomous vehicle testing scenario in JSON format. The scenario should include spawn criteria, actors, and actions.",
                        "input": f"Scenario description: {description}",
                        "output": json.dumps(scenario_json, indent=2),
                        "scenario_id": json_file.stem,
                        "scenario_number": scenario_num
                    }
                    training_data.append(context_example)
                
                # Format 3: Specific request variation (25% of examples)
                if random.random() < 0.25:
                    request_variations = [
                        "Convert this natural language description into a CARLA scenario JSON:",
                        "Generate a JSON configuration for CARLA simulator with the following scenario:",
                        "Create a structured CARLA scenario from this description:",
                        "Design a CARLA test scenario in JSON format based on:",
                        "Build an OpenSCENARIO-compatible JSON from this description:"
                    ]
                    varied_example = {
                        "instruction": random.choice(request_variations),
                        "input": description,
                        "output": json.dumps(scenario_json, indent=2),
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
    
    # Save dataset statistics
    stats = {
        "total_examples": len(training_data),
        "train_examples": len(train_data),
        "val_examples": len(val_data),
        "test_examples": len(test_data),
        "unique_scenarios": len(json_files),
        "scenario_distribution": {}
    }
    
    # Count examples per scenario batch (if numbered)
    for data in training_data:
        scenario_num = data.get("scenario_number", "unknown")
        if scenario_num != "unknown":
            # Group by ranges (001-050, 051-100, etc.)
            try:
                num = int(scenario_num)
                batch = f"{((num-1)//50)*50+1:03d}-{((num-1)//50+1)*50:03d}"
                stats["scenario_distribution"][batch] = stats["scenario_distribution"].get(batch, 0) + 1
            except ValueError:
                stats["scenario_distribution"]["other"] = stats["scenario_distribution"].get("other", 0) + 1
        else:
            stats["scenario_distribution"]["unknown"] = stats["scenario_distribution"].get("unknown", 0) + 1
    
    with open(output_path / 'dataset_stats.json', 'w') as f:
        json.dump(stats, f, indent=2)
    
    print(f"\nDataset Statistics:")
    print(f"  Unique scenarios processed: {len(json_files)}")
    print(f"  Training examples: {len(train_data)}")
    print(f"  Validation examples: {len(val_data)}")
    print(f"  Test examples: {len(test_data)}")
    print(f"\nScenario Distribution:")
    for batch, count in sorted(stats["scenario_distribution"].items()):
        print(f"  Batch {batch}: {count} examples")
    
    print(f"\nDatasets saved to {output_path}/")
    
    return train_data, val_data

def create_few_shot_examples(output_dir="training_data"):
    """Create a small set of few-shot examples for testing"""
    few_shot_examples = [
        {
            "description": "Create a scenario where a vehicle ahead suddenly brakes when I approach within 30 meters.",
            "scenario": {
                "scenario_name": "example_emergency_brake",
                "description": "Emergency braking scenario",
                "weather": "clear",
                "ego_vehicle_model": "vehicle.audi.a2",
                "ego_spawn": {
                    "criteria": {
                        "lane_type": "Driving",
                        "is_intersection": False
                    }
                },
                "ego_start_speed": 15,
                "actors": [
                    {
                        "id": "braking_vehicle",
                        "type": "vehicle",
                        "model": "vehicle.toyota.prius",
                        "spawn": {
                            "criteria": {
                                "lane_type": "Driving",
                                "distance_to_ego": {"min": 40, "max": 60},
                                "relative_position": "ahead",
                                "road_relationship": "same_road",
                                "lane_relationship": "same_lane"
                            }
                        }
                    }
                ],
                "actions": [
                    {
                        "actor_id": "braking_vehicle",
                        "action_type": "brake",
                        "trigger_type": "distance_to_ego",
                        "trigger_value": 30,
                        "trigger_comparison": "<",
                        "brake_force": 0.8,
                        "dynamics_dimension": "time",
                        "dynamics_shape": "step",
                        "dynamics_value": 0.5
                    }
                ],
                "success_distance": 100,
                "timeout": 60,
                "collision_allowed": False
            }
        },
        {
            "description": "I need a scenario with a pedestrian crossing the road ahead of me in wet weather conditions.",
            "scenario": {
                "scenario_name": "example_wet_pedestrian",
                "description": "Pedestrian crossing in wet conditions",
                "weather": "wet",
                "ego_vehicle_model": "vehicle.audi.a2",
                "ego_spawn": {
                    "criteria": {
                        "lane_type": "Driving",
                        "is_intersection": False
                    }
                },
                "ego_start_speed": 10,
                "actors": [
                    {
                        "id": "crossing_pedestrian",
                        "type": "pedestrian",
                        "model": "walker.pedestrian.0010",
                        "spawn": {
                            "criteria": {
                                "lane_type": "Sidewalk",
                                "distance_to_ego": {"min": 25, "max": 40},
                                "relative_position": "ahead"
                            }
                        }
                    }
                ],
                "actions": [
                    {
                        "actor_id": "crossing_pedestrian",
                        "action_type": "speed",
                        "trigger_type": "time",
                        "trigger_value": 3.0,
                        "speed_value": 1.5,
                        "dynamics_dimension": "time",
                        "dynamics_shape": "linear",
                        "dynamics_value": 1.0
                    }
                ],
                "success_distance": 75,
                "timeout": 45,
                "collision_allowed": False
            }
        }
    ]
    
    output_path = Path(output_dir)
    with open(output_path / 'few_shot_examples.json', 'w') as f:
        json.dump(few_shot_examples, f, indent=2)
    
    print(f"Created {len(few_shot_examples)} few-shot examples")

def analyze_dataset_quality(scenarios_dir="dataset1908"):
    """Analyze the quality and coverage of the dataset"""
    base_dir = Path(scenarios_dir)
    json_files = list(base_dir.glob("*.json"))
    txt_files = list(base_dir.glob("*.txt"))
    
    print(f"\nDataset Quality Analysis:")
    print(f"  JSON files: {len(json_files)}")
    print(f"  TXT files: {len(txt_files)}")
    
    # Check for matching pairs
    matched_pairs = 0
    orphaned_json = []
    orphaned_txt = []
    
    for json_file in json_files:
        txt_file = json_file.with_suffix('.txt')
        if txt_file.exists():
            matched_pairs += 1
        else:
            orphaned_json.append(json_file.name)
    
    for txt_file in txt_files:
        json_file = txt_file.with_suffix('.json')
        if not json_file.exists():
            orphaned_txt.append(txt_file.name)
    
    print(f"  Matched JSON+TXT pairs: {matched_pairs}")
    if orphaned_json:
        print(f"  JSON files without TXT: {len(orphaned_json)}")
        for file in orphaned_json[:5]:  # Show first 5
            print(f"    - {file}")
        if len(orphaned_json) > 5:
            print(f"    ... and {len(orphaned_json) - 5} more")
    
    if orphaned_txt:
        print(f"  TXT files without JSON: {len(orphaned_txt)}")
        for file in orphaned_txt[:5]:  # Show first 5
            print(f"    - {file}")
        if len(orphaned_txt) > 5:
            print(f"    ... and {len(orphaned_txt) - 5} more")
    
    return matched_pairs

if __name__ == "__main__":
    print("Preparing dataset1908 for LLM training...")
    
    # Analyze dataset quality first
    matched_pairs = analyze_dataset_quality()
    
    if matched_pairs == 0:
        print("\nError: No matched JSON+TXT pairs found!")
        print("Please ensure your dataset1908 directory contains matching .json and .txt files")
        exit(1)
    
    # Prepare main training data
    train_data, val_data = prepare_training_data()
    
    if train_data is not None:
        # Create few-shot examples
        create_few_shot_examples()
        
        print("\n✓ Data preparation complete!")
        print("Files created in training_data/:")
        print("  - train_dataset.json")
        print("  - val_dataset.json") 
        print("  - test_dataset.json")
        print("  - dataset_stats.json")
        print("  - few_shot_examples.json")
        
        print(f"\nReady for LLM training with {len(train_data)} training examples!")
    else:
        print("\n✗ Data preparation failed!")