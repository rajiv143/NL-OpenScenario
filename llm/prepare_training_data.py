import json
import os
from pathlib import Path
from sklearn.model_selection import train_test_split

def prepare_training_data():
    """Convert scenario files into LLM training format"""
    training_data = []
    
    base_dir = Path("claude_scenarios")
    
    # Process all subdirectories
    for subdir in base_dir.iterdir():
        if subdir.is_dir():
            print(f"Processing {subdir.name}...")
            
            # Find all JSON files
            json_files = list(subdir.glob("*.json"))
            
            for json_file in json_files:
                # Get corresponding description file
                desc_file = json_file.with_name(f"{json_file.stem}_description.txt")
                
                if desc_file.exists():
                    # Read natural language description
                    with open(desc_file, 'r') as f:
                        description = f.read().strip()
                    
                    # Read JSON scenario
                    with open(json_file, 'r') as f:
                        scenario_json = json.load(f)
                    
                    # Create training example
                    training_example = {
                        "instruction": "Generate a CARLA scenario JSON based on this description:",
                        "input": description,
                        "output": json.dumps(scenario_json, indent=2)
                    }
                    
                    training_data.append(training_example)
    
    print(f"Created {len(training_data)} training examples")
    
    # Split into train/validation (80/20)
    train_data, val_data = train_test_split(training_data, test_size=0.2, random_state=42)
    
    # Save datasets
    with open('train_dataset.json', 'w') as f:
        json.dump(train_data, f, indent=2)
    
    with open('val_dataset.json', 'w') as f:
        json.dump(val_data, f, indent=2)
    
    print(f"Training examples: {len(train_data)}")
    print(f"Validation examples: {len(val_data)}")
    
    return train_data, val_data

# Run data preparation
train_data, val_data = prepare_training_data()