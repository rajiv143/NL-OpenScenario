#!/usr/bin/env python3
"""
Convert all lane_direction to target_lane with proper numeric values:
- 0 = same lane as ego (for cut-in scenarios)
- 1 = one lane to the right of ego
- -1 = one lane to the left of ego
"""

import json
import os
from pathlib import Path

def convert_to_target_lane(dataset_path: str):
    """Convert all scenarios to use target_lane"""
    dataset_path = Path(dataset_path)
    converted_count = 0
    
    for json_file in sorted(dataset_path.glob("scenario_*.json")):
        if 'backup' in str(json_file):
            continue
        
        # Read the txt file to understand context
        txt_file = json_file.with_suffix('.txt')
        context = ""
        if txt_file.exists():
            with open(txt_file, 'r') as f:
                context = f.read().lower()
        
        modified = False
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        scenario_name = data.get('scenario_name', '').lower()
        description = data.get('description', '').lower()
        
        # Process each action
        for action in data.get('actions', []):
            if action.get('action_type') == 'lane_change':
                # Get actor info to understand the scenario
                actor_id = action.get('actor_id')
                actor_info = None
                for actor in data.get('actors', []):
                    if actor.get('id') == actor_id:
                        actor_info = actor
                        break
                
                # Determine the correct target_lane value
                if 'lane_direction' in action:
                    direction = action['lane_direction']
                    
                    # Check if this is a cut-in scenario
                    is_cutin = any(term in scenario_name or term in description or term in context 
                                  for term in ['cut', 'cutin', 'cut-in', 'cut_in', 'merge'])
                    
                    # Check actor's spawn position
                    lane_rel = None
                    if actor_info:
                        lane_rel = actor_info.get('spawn', {}).get('criteria', {}).get('lane_relationship')
                    
                    # For cut-in scenarios where actor is in adjacent lane
                    if is_cutin and lane_rel == 'adjacent_lane':
                        # Actor needs to move into ego's lane
                        action['target_lane'] = 0
                    # For overtaking scenarios
                    elif 'overtake' in scenario_name or 'overtake' in description or 'overtaking' in context:
                        # Overtaking typically goes left (in right-hand traffic)
                        if direction == 'left':
                            action['target_lane'] = -1
                        elif direction == 'right':
                            # Returning after overtake
                            action['target_lane'] = 1
                        else:
                            action['target_lane'] = -1  # Default overtake left
                    # For general lane changes
                    else:
                        if direction == 'left':
                            action['target_lane'] = -1
                        elif direction == 'right':
                            action['target_lane'] = 1
                        elif direction in ['ego_lane', 'same']:
                            action['target_lane'] = 0
                        else:
                            # Default based on context
                            if is_cutin:
                                action['target_lane'] = 0
                            else:
                                action['target_lane'] = 1
                    
                    # Remove lane_direction
                    del action['lane_direction']
                    modified = True
                    
                elif 'target_lane' not in action:
                    # No lane specification, add based on context
                    is_cutin = any(term in scenario_name or term in description or term in context 
                                  for term in ['cut', 'cutin', 'cut-in', 'cut_in', 'merge'])
                    
                    if is_cutin:
                        action['target_lane'] = 0  # Move to ego's lane
                    elif 'overtake' in scenario_name or 'overtake' in description:
                        action['target_lane'] = -1  # Overtake to the left
                    else:
                        action['target_lane'] = 1  # Default to right
                    
                    modified = True
        
        if modified:
            with open(json_file, 'w') as f:
                json.dump(data, f, indent=2)
            converted_count += 1
            print(f"Converted {json_file.name}")
    
    print(f"\n✅ Converted {converted_count} scenario files to use target_lane")
    return converted_count

if __name__ == "__main__":
    convert_to_target_lane('/home/user/Desktop/Rajiv/dataset1908')