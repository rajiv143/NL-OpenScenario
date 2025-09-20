#!/usr/bin/env python3
"""
Fix lane direction issues in scenarios
"""

import json
import os
from pathlib import Path

def fix_lane_directions(dataset_path: str):
    """Fix all lane direction issues"""
    dataset_path = Path(dataset_path)
    fixed_count = 0
    
    for json_file in sorted(dataset_path.glob("scenario_*.json")):
        if 'backup' in str(json_file):
            continue
            
        modified = False
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        # Check and fix actions
        for action in data.get('actions', []):
            if action.get('action_type') == 'lane_change':
                # Remove target_lane if it exists alongside lane_direction
                if 'target_lane' in action and 'lane_direction' in action:
                    del action['target_lane']
                    modified = True
                    print(f"Removed duplicate target_lane from {json_file.name}")
                
                # If only target_lane exists, convert to lane_direction
                elif 'target_lane' in action and 'lane_direction' not in action:
                    target = action['target_lane']
                    
                    # Handle special case where target_lane is "same_as_ego"
                    if target == 'same_as_ego':
                        # This means move to ego's lane - for cut-in scenarios
                        # We need to determine which side the actor is on
                        # Check if actor spawns in adjacent lane
                        actor_id = action.get('actor_id')
                        for actor in data.get('actors', []):
                            if actor.get('id') == actor_id:
                                lane_rel = actor.get('spawn', {}).get('criteria', {}).get('lane_relationship')
                                if lane_rel == 'adjacent_lane':
                                    # For cut-ins from adjacent lane, default to moving right
                                    # (this is a simplification - in reality we'd need to know which side)
                                    action['lane_direction'] = 'right'
                                    break
                        else:
                            action['lane_direction'] = 'right'  # Default
                    else:
                        # Convert numeric target_lane
                        try:
                            target = float(target) if isinstance(target, str) else target
                            action['lane_direction'] = 'right' if target > 0 else 'left'
                        except (ValueError, TypeError):
                            # If conversion fails, default to right
                            action['lane_direction'] = 'right'
                    
                    del action['target_lane']
                    modified = True
                    print(f"Converted target_lane to lane_direction in {json_file.name}")
                
                # If neither exists, add lane_direction with a default
                elif 'target_lane' not in action and 'lane_direction' not in action:
                    # Check context to determine likely direction
                    scenario_name = data.get('scenario_name', '')
                    description = data.get('description', '').lower()
                    
                    # Default to right for cut-ins (most common case)
                    if 'cut' in scenario_name or 'cut' in description:
                        action['lane_direction'] = 'right'
                    elif 'overtake' in description or 'pass' in description:
                        action['lane_direction'] = 'left'
                    else:
                        action['lane_direction'] = 'right'  # Default
                    
                    modified = True
                    print(f"Added missing lane_direction to {json_file.name}")
        
        if modified:
            with open(json_file, 'w') as f:
                json.dump(data, f, indent=2)
            fixed_count += 1
    
    print(f"\nFixed {fixed_count} scenario files")
    return fixed_count

if __name__ == "__main__":
    fix_lane_directions('/home/user/Desktop/Rajiv/dataset1908')