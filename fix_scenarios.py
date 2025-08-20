#!/usr/bin/env python3
"""
Fix script to automatically correct common errors in CARLA scenarios
Based on validation report findings
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List

class ScenarioFixer:
    def __init__(self, dataset_path: str):
        self.dataset_path = Path(dataset_path)
        self.fixes_applied = {
            'lane_relationship': 0,
            'missing_fields': 0,
            'weather': 0,
            'colors': 0
        }
        
    def fix_all_scenarios(self):
        """Fix all scenarios in the dataset"""
        scenario_files = sorted(self.dataset_path.glob("scenario_*.json"))
        scenario_files = [f for f in scenario_files if 'backup' not in str(f)]
        
        for json_file in scenario_files:
            txt_file = json_file.with_suffix('.txt')
            
            if not txt_file.exists():
                continue
                
            self.fix_scenario(json_file, txt_file)
        
        print(f"Fixes Applied:")
        for fix_type, count in self.fixes_applied.items():
            print(f"  - {fix_type}: {count} fixes")
    
    def fix_scenario(self, json_file: Path, txt_file: Path):
        """Fix a single scenario"""
        try:
            with open(json_file, 'r') as f:
                json_data = json.load(f)
            with open(txt_file, 'r') as f:
                txt_content = f.read().lower()
            
            original_data = json.dumps(json_data)
            
            # Apply fixes
            json_data = self.fix_lane_relationships(json_data, txt_content)
            json_data = self.fix_missing_action_fields(json_data)
            json_data = self.fix_weather_alignment(json_data, txt_content)
            json_data = self.add_missing_colors(json_data, txt_content)
            
            # Save if modified
            if json.dumps(json_data) != original_data:
                with open(json_file, 'w') as f:
                    json.dump(json_data, f, indent=2)
                    
        except Exception as e:
            print(f"Error fixing {json_file}: {e}")
    
    def fix_lane_relationships(self, json_data: Dict, txt_content: str) -> Dict:
        """Fix lane relationship based on scenario type"""
        
        # Following scenario patterns
        following_patterns = ['following', 'ahead in same lane', 'behind in same lane', 
                            'lead vehicle', 'in front', 'same lane', 'maintains distance']
        cut_in_patterns = ['cuts in', 'cut-in', 'merges', 'changes lanes into', 
                          'from adjacent', 'overtakes', 'switches lanes']
        
        # Check if this is a following scenario
        is_following = any(pattern in txt_content for pattern in following_patterns)
        is_cutin = any(pattern in txt_content for pattern in cut_in_patterns)
        
        for actor in json_data.get('actors', []):
            spawn_criteria = actor.get('spawn', {}).get('criteria', {})
            
            # Fix following scenarios
            if is_following and not is_cutin:
                if spawn_criteria.get('lane_relationship') == 'adjacent_lane':
                    # Check if actor is described as being in same lane
                    if 'ahead' in txt_content or 'behind' in txt_content:
                        spawn_criteria['lane_relationship'] = 'same_lane'
                        self.fixes_applied['lane_relationship'] += 1
            
            # Fix cut-in scenarios - actors should start in adjacent lane if performing lane change
            elif is_cutin:
                # Check if there's a lane change action for this actor
                has_lane_change = any(
                    action.get('actor_id') == actor.get('id') and 
                    action.get('action_type') == 'lane_change'
                    for action in json_data.get('actions', [])
                )
                
                if has_lane_change and spawn_criteria.get('lane_relationship') == 'same_lane':
                    spawn_criteria['lane_relationship'] = 'adjacent_lane'
                    self.fixes_applied['lane_relationship'] += 1
        
        return json_data
    
    def fix_missing_action_fields(self, json_data: Dict) -> Dict:
        """Add missing required fields to actions"""
        
        default_fields = {
            'speed': {
                'dynamics_dimension': 'time',
                'dynamics_shape': 'linear',
                'dynamics_value': 2.0
            },
            'brake': {
                'dynamics_dimension': 'time',
                'dynamics_shape': 'linear',
                'dynamics_value': 1.5
            },
            'lane_change': {
                'dynamics_dimension': 'time',
                'dynamics_shape': 'sinusoidal',
                'dynamics_value': 2.5
            },
            'wait': {
                'dynamics_dimension': 'time',
                'dynamics_value': 1.0
            }
        }
        
        for action in json_data.get('actions', []):
            action_type = action.get('action_type')
            
            if action_type in default_fields:
                for field, value in default_fields[action_type].items():
                    if field not in action:
                        action[field] = value
                        self.fixes_applied['missing_fields'] += 1
                
                # Fix brake force if out of range
                if action_type == 'brake':
                    brake_force = action.get('brake_force', 0)
                    if brake_force < 0.1:
                        action['brake_force'] = 0.1
                        self.fixes_applied['missing_fields'] += 1
                    elif brake_force > 1.0:
                        action['brake_force'] = 1.0
                        self.fixes_applied['missing_fields'] += 1
        
        return json_data
    
    def fix_weather_alignment(self, json_data: Dict, txt_content: str) -> Dict:
        """Fix weather to match description"""
        
        weather_mappings = {
            'heavy rain': 'hard_rain',
            'hard rain': 'hard_rain',
            'light rain': 'soft_rain',
            'soft rain': 'soft_rain',
            'moderate rain': 'mid_rain',
            'rain': 'mid_rain',
            'wet': 'wet_cloudy',
            'rainy': 'mid_rain',
            'fog': 'fog',
            'foggy': 'fog',
            'night': 'clear_night',
            'evening': 'clear_sunset',
            'sunset': 'clear_sunset',
            'cloudy': 'cloudy',
            'overcast': 'cloudy',
            'clear day': 'clear_noon',
            'sunny': 'clear_noon'
        }
        
        current_weather = json_data.get('weather', '').lower()
        
        for weather_phrase, correct_weather in weather_mappings.items():
            if weather_phrase in txt_content:
                if current_weather != correct_weather:
                    json_data['weather'] = correct_weather
                    self.fixes_applied['weather'] += 1
                break
        
        return json_data
    
    def add_missing_colors(self, json_data: Dict, txt_content: str) -> Dict:
        """Add colors mentioned in description"""
        
        color_mappings = {
            'red': '255,0,0',
            'blue': '0,0,255',
            'green': '0,255,0',
            'white': '255,255,255',
            'black': '0,0,0',
            'yellow': '255,255,0',
            'gray': '128,128,128',
            'grey': '128,128,128',
            'orange': '255,165,0',
            'purple': '128,0,128',
            'brown': '139,69,19',
            'pink': '255,192,203',
            'cyan': '0,255,255'
        }
        
        for color_name, rgb_value in color_mappings.items():
            if color_name in txt_content:
                # Try to identify which actor should have this color
                for actor in json_data.get('actors', []):
                    actor_id = actor.get('id', '').lower()
                    actor_model = actor.get('model', '').lower()
                    
                    # Check if color is associated with this actor in description
                    if (color_name + ' ' in txt_content and 
                        (actor_id in txt_content or 
                         any(part in txt_content for part in actor_model.split('.')))):
                        
                        if 'color' not in actor:
                            actor['color'] = rgb_value
                            self.fixes_applied['colors'] += 1
                            break
        
        return json_data

def main():
    fixer = ScenarioFixer('/home/user/Desktop/Rajiv/dataset1908')
    fixer.fix_all_scenarios()

if __name__ == "__main__":
    main()