#!/usr/bin/env python3
"""
Fix existing training data to have proper color mapping
"""

import json
import re

def fix_color_in_training_data(input_file, output_file):
    """Fix existing training data to have proper color mapping"""
    
    color_map = {
        "blue": "0,0,255",
        "red": "255,0,0",
        "green": "0,255,0",
        "yellow": "255,255,0",
        "orange": "255,165,0",
        "purple": "128,0,128",
        "white": "255,255,255",
        "black": "0,0,0",
        "gray": "128,128,128",
        "grey": "128,128,128",  # Alternative spelling
        "silver": "192,192,192",
        "brown": "139,69,19",
        "pink": "255,192,203"
    }
    
    try:
        with open(input_file, 'r') as f:
            training_data = json.load(f)
    except FileNotFoundError:
        print(f"File {input_file} not found")
        return 0
    
    fixed_data = []
    color_fixes = 0
    
    for example in training_data:
        input_text = example.get('input', '').lower()
        
        # Find all color words in input
        found_colors = []
        for color_name in color_map.keys():
            # Use word boundaries to match whole words only
            if re.search(r'\b' + color_name + r'\b', input_text):
                found_colors.append(color_name)
        
        if found_colors:
            # Parse and fix the JSON output
            try:
                scenario = json.loads(example['output'])
                
                # If there's only one color mentioned, apply it to all actors
                if len(found_colors) == 1:
                    for actor in scenario.get('actors', []):
                        if actor.get('type') == 'vehicle':
                            actor['color'] = color_map[found_colors[0]]
                            color_fixes += 1
                
                # If multiple colors, try to match them to actors by order or context
                elif len(found_colors) > 1:
                    actors = [a for a in scenario.get('actors', []) if a.get('type') == 'vehicle']
                    for i, actor in enumerate(actors):
                        if i < len(found_colors):
                            actor['color'] = color_map[found_colors[i]]
                            color_fixes += 1
                
                # Update the output
                example['output'] = json.dumps(scenario, indent=2)
                
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Skipping invalid JSON in training example: {str(e)[:50]}")
        
        fixed_data.append(example)
    
    # Save fixed data
    with open(output_file, 'w') as f:
        json.dump(fixed_data, f, indent=2)
    
    print(f"Fixed {color_fixes} color mappings in {len(fixed_data)} training examples")
    print(f"Saved to {output_file}")
    return color_fixes

def validate_color_fixes(file_path):
    """Validate that colors are properly mapped in the dataset"""
    
    color_map = {
        "blue": "0,0,255",
        "red": "255,0,0",
        "green": "0,255,0",
        "yellow": "255,255,0",
        "orange": "255,165,0",
        "purple": "128,0,128",
        "white": "255,255,255",
        "black": "0,0,0",
        "gray": "128,128,128",
        "grey": "128,128,128",
        "silver": "192,192,192",
        "brown": "139,69,19",
        "pink": "255,192,203"
    }
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    mismatches = 0
    correct_matches = 0
    
    for example in data:
        input_text = example.get('input', '').lower()
        
        # Find color in input
        found_color = None
        for color_name in color_map.keys():
            if re.search(r'\b' + color_name + r'\b', input_text):
                found_color = color_name
                break
        
        if found_color:
            try:
                scenario = json.loads(example['output'])
                expected_rgb = color_map[found_color]
                
                for actor in scenario.get('actors', []):
                    if actor.get('type') == 'vehicle':
                        actual_color = actor.get('color', '')
                        if actual_color == expected_rgb:
                            correct_matches += 1
                        else:
                            mismatches += 1
                            print(f"Mismatch: Expected {found_color}({expected_rgb}) but got {actual_color}")
                            
            except json.JSONDecodeError:
                pass
    
    print(f"\nValidation Results:")
    print(f"  Correct color mappings: {correct_matches}")
    print(f"  Incorrect mappings: {mismatches}")
    print(f"  Accuracy: {correct_matches/(correct_matches+mismatches)*100:.1f}%" if (correct_matches+mismatches) > 0 else "N/A")
    
    return correct_matches, mismatches

if __name__ == "__main__":
    # Fix training data
    print("Fixing training dataset...")
    train_fixes = fix_color_in_training_data("train_dataset.json", "train_dataset_fixed.json")
    
    print("\nFixing validation dataset...")
    val_fixes = fix_color_in_training_data("val_dataset.json", "val_dataset_fixed.json")
    
    print("\nFixing test dataset...")
    test_fixes = fix_color_in_training_data("test_dataset.json", "test_dataset_fixed.json")
    
    # Validate the fixes
    if train_fixes > 0:
        print("\n" + "="*50)
        print("Validating fixed training data...")
        validate_color_fixes("train_dataset_fixed.json")
    
    if val_fixes > 0:
        print("\nValidating fixed validation data...")
        validate_color_fixes("val_dataset_fixed.json")
    
    print("\n" + "="*50)
    print(f"Total color mappings fixed: {train_fixes + val_fixes + test_fixes}")