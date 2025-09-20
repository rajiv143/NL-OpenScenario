#!/usr/bin/env python3
"""
Comprehensive manual validation of all CARLA scenarios
Provides detailed categorical breakdown and validation status
"""

import json
import os
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple

class ComprehensiveValidator:
    def __init__(self, dataset_path: str):
        self.dataset_path = Path(dataset_path)
        self.validation_results = []
        
        # Primary categories
        self.categories = {
            'following': [],
            'cut_in_lane_change': [],
            'intersection': [],
            'pedestrian': [],
            'multi_actor': [],  # 3+ actors
            'emergency': [],
            'construction': [],
            'weather_specific': []
        }
        
        # Context distribution
        self.contexts = defaultdict(list)
        
        # Complexity distribution
        self.actor_counts = {
            'single': [],
            'two': [],
            'three_plus': []
        }
        self.max_actors = 0
        
        # Weather distribution
        self.weather = {
            'clear': [],
            'rain_wet': [],
            'fog': [],
            'night_sunset': []
        }
        
        # Validation status
        self.valid_scenarios = []
        self.error_scenarios = []
        self.warning_scenarios = []
        
    def validate_all(self):
        """Validate all scenarios and generate comprehensive report"""
        scenario_files = sorted(self.dataset_path.glob("scenario_*.json"))
        scenario_files = [f for f in scenario_files if 'backup' not in str(f)]
        
        print(f"Found {len(scenario_files)} scenarios to validate\n")
        
        for json_file in scenario_files:
            self.validate_scenario(json_file)
        
        return self.generate_report()
    
    def validate_scenario(self, json_file: Path):
        """Manually validate a single scenario"""
        scenario_num = json_file.stem.split('_')[1]
        txt_file = json_file.with_suffix('.txt')
        
        try:
            with open(json_file, 'r') as f:
                json_data = json.load(f)
            
            if txt_file.exists():
                with open(txt_file, 'r') as f:
                    txt_content = f.read().lower()
            else:
                txt_content = ""
                
        except Exception as e:
            print(f"Error reading scenario {scenario_num}: {e}")
            self.error_scenarios.append(scenario_num)
            return
        
        # Categorize the scenario
        self.categorize_scenario(scenario_num, json_data, txt_content)
        
        # Validate lane relationships and other rules
        validation_status = self.validate_rules(scenario_num, json_data, txt_content)
        
        if validation_status == "VALID":
            self.valid_scenarios.append(scenario_num)
        elif validation_status == "ERROR":
            self.error_scenarios.append(scenario_num)
        else:
            self.warning_scenarios.append(scenario_num)
            
        # Track max actors
        num_actors = len(json_data.get('actors', []))
        if num_actors > self.max_actors:
            self.max_actors = num_actors
    
    def categorize_scenario(self, scenario_num: str, json_data: Dict, txt_content: str):
        """Categorize scenario into primary and secondary categories"""
        
        actors = json_data.get('actors', [])
        num_actors = len(actors)
        
        # Check for pedestrians
        has_pedestrian = any('pedestrian' in actor.get('type', '') for actor in actors)
        if has_pedestrian:
            self.categories['pedestrian'].append(scenario_num)
        
        # Check for emergency vehicles
        has_emergency = any(
            'emergency' in str(actor.get('special_type', '')) or
            'ambulance' in actor.get('model', '') or
            'firetruck' in actor.get('model', '') or
            'police' in actor.get('model', '')
            for actor in actors
        )
        if has_emergency or 'emergency' in txt_content:
            self.categories['emergency'].append(scenario_num)
        
        # Check for construction
        if 'construction' in txt_content or any('construction' in str(actor.get('special_type', '')) for actor in actors):
            self.categories['construction'].append(scenario_num)
        
        # Check for intersection scenarios
        is_intersection = json_data.get('ego_spawn', {}).get('criteria', {}).get('is_intersection', False)
        has_perpendicular = any(
            actor.get('spawn', {}).get('criteria', {}).get('relative_position') == 'perpendicular'
            for actor in actors
        )
        if is_intersection or has_perpendicular or 'intersection' in txt_content:
            self.categories['intersection'].append(scenario_num)
        
        # Check for cut-in/lane change scenarios
        has_lane_change = any(
            action.get('action_type') == 'lane_change'
            for action in json_data.get('actions', [])
        )
        has_adjacent_lane = any(
            actor.get('spawn', {}).get('criteria', {}).get('lane_relationship') == 'adjacent_lane'
            for actor in actors
        )
        if has_lane_change or ('cut' in txt_content or 'merge' in txt_content or 'overtake' in txt_content):
            self.categories['cut_in_lane_change'].append(scenario_num)
        
        # Check for following scenarios
        has_same_lane_ahead = any(
            actor.get('spawn', {}).get('criteria', {}).get('lane_relationship') == 'same_lane' and
            actor.get('spawn', {}).get('criteria', {}).get('relative_position') == 'ahead'
            for actor in actors
        )
        if has_same_lane_ahead and not has_lane_change:
            self.categories['following'].append(scenario_num)
        elif 'follow' in txt_content and not has_lane_change:
            self.categories['following'].append(scenario_num)
        
        # Multi-actor scenarios (3+ actors)
        if num_actors >= 3:
            self.categories['multi_actor'].append(scenario_num)
        
        # Weather-specific scenarios
        weather = json_data.get('weather', '').lower()
        if any(w in weather for w in ['rain', 'wet', 'fog', 'snow', 'storm']):
            self.categories['weather_specific'].append(scenario_num)
        
        # Context distribution
        context = json_data.get('ego_spawn', {}).get('criteria', {}).get('road_context', 'unspecified')
        self.contexts[context].append(scenario_num)
        
        # Actor count distribution
        if num_actors == 1:
            self.actor_counts['single'].append(scenario_num)
        elif num_actors == 2:
            self.actor_counts['two'].append(scenario_num)
        else:
            self.actor_counts['three_plus'].append(scenario_num)
        
        # Weather distribution
        if 'clear' in weather or weather in ['', 'default']:
            self.weather['clear'].append(scenario_num)
        if any(w in weather for w in ['rain', 'wet']):
            self.weather['rain_wet'].append(scenario_num)
        if 'fog' in weather:
            self.weather['fog'].append(scenario_num)
        if any(w in weather for w in ['night', 'sunset', 'dusk', 'dawn']):
            self.weather['night_sunset'].append(scenario_num)
    
    def validate_rules(self, scenario_num: str, json_data: Dict, txt_content: str) -> str:
        """Validate scenario against critical rules"""
        errors = []
        warnings = []
        
        for actor in json_data.get('actors', []):
            spawn_criteria = actor.get('spawn', {}).get('criteria', {})
            lane_rel = spawn_criteria.get('lane_relationship')
            road_rel = spawn_criteria.get('road_relationship')
            rel_pos = spawn_criteria.get('relative_position')
            
            # Rule 1: Following scenarios should have same_lane
            if 'follow' in txt_content and rel_pos == 'ahead':
                if lane_rel == 'adjacent_lane':
                    # Check if there's a lane change action
                    has_lane_change = any(
                        action.get('actor_id') == actor.get('id') and 
                        action.get('action_type') == 'lane_change'
                        for action in json_data.get('actions', [])
                    )
                    if not has_lane_change:
                        errors.append(f"Following scenario but {actor.get('id')} in adjacent_lane without lane change")
            
            # Rule 2: Cut-in scenarios should start in adjacent_lane
            if any(action.get('actor_id') == actor.get('id') and 
                   action.get('action_type') == 'lane_change'
                   for action in json_data.get('actions', [])):
                if lane_rel != 'adjacent_lane' and road_rel == 'same_road':
                    warnings.append(f"Lane change action but {actor.get('id')} not in adjacent_lane")
            
            # Rule 3: Intersection scenarios with perpendicular traffic
            if rel_pos == 'perpendicular':
                if road_rel != 'different_road':
                    errors.append(f"Perpendicular traffic but not different_road")
        
        # Rule 4: Check action completeness
        for action in json_data.get('actions', []):
            action_type = action.get('action_type')
            
            if action_type == 'brake':
                if 'brake_force' not in action:
                    errors.append(f"Brake action missing brake_force")
                elif not (0.1 <= action.get('brake_force', 0) <= 1.0):
                    errors.append(f"Brake force out of range")
            
            if action_type == 'speed':
                if 'speed_value' not in action:
                    errors.append(f"Speed action missing speed_value")
            
            if action_type == 'lane_change':
                if 'target_lane' not in action:
                    errors.append(f"Lane change missing target_lane")
        
        if errors:
            return "ERROR"
        elif warnings:
            return "WARNING"
        else:
            return "VALID"
    
    def generate_report(self) -> Dict:
        """Generate comprehensive validation report"""
        total_scenarios = len(self.valid_scenarios) + len(self.error_scenarios) + len(self.warning_scenarios)
        
        print("\n" + "="*80)
        print("COMPREHENSIVE VALIDATION REPORT")
        print("="*80)
        
        print(f"\nTotal Scenarios Validated: {total_scenarios}")
        print(f"✅ Valid: {len(self.valid_scenarios)} ({len(self.valid_scenarios)/total_scenarios*100:.1f}%)")
        print(f"⚠️  Warnings: {len(self.warning_scenarios)} ({len(self.warning_scenarios)/total_scenarios*100:.1f}%)")
        print(f"❌ Errors: {len(self.error_scenarios)} ({len(self.error_scenarios)/total_scenarios*100:.1f}%)")
        
        print("\n" + "-"*40)
        print("PRIMARY CATEGORIES:")
        print("-"*40)
        for category, scenarios in self.categories.items():
            percentage = len(scenarios) / total_scenarios * 100
            print(f"{category.replace('_', ' ').title()}: {len(scenarios)} count ({percentage:.1f}%)")
        
        print("\n" + "-"*40)
        print("CONTEXT DISTRIBUTION:")
        print("-"*40)
        for context, scenarios in sorted(self.contexts.items()):
            print(f"{context.title()} contexts: {len(scenarios)} scenarios")
        
        print("\n" + "-"*40)
        print("COMPLEXITY DISTRIBUTION:")
        print("-"*40)
        print(f"Single actor: {len(self.actor_counts['single'])} scenarios")
        print(f"Two actors: {len(self.actor_counts['two'])} scenarios")
        print(f"Three+ actors: {len(self.actor_counts['three_plus'])} scenarios")
        print(f"Maximum actors in one scenario: {self.max_actors}")
        
        print("\n" + "-"*40)
        print("WEATHER DISTRIBUTION:")
        print("-"*40)
        print(f"Clear weather: {len(self.weather['clear'])} scenarios")
        print(f"Wet/rain conditions: {len(self.weather['rain_wet'])} scenarios")
        print(f"Fog conditions: {len(self.weather['fog'])} scenarios")
        print(f"Night/sunset conditions: {len(self.weather['night_sunset'])} scenarios")
        
        # Save detailed results
        results = {
            'total_scenarios': total_scenarios,
            'valid_count': len(self.valid_scenarios),
            'warning_count': len(self.warning_scenarios),
            'error_count': len(self.error_scenarios),
            'categories': {k: len(v) for k, v in self.categories.items()},
            'contexts': {k: len(v) for k, v in self.contexts.items()},
            'actor_distribution': {k: len(v) for k, v in self.actor_counts.items()},
            'weather_distribution': {k: len(v) for k, v in self.weather.items()},
            'max_actors': self.max_actors
        }
        
        with open('/home/user/Desktop/Rajiv/comprehensive_validation_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        return results

def main():
    validator = ComprehensiveValidator('/home/user/Desktop/Rajiv/dataset1908')
    results = validator.validate_all()
    
    print("\n" + "="*80)
    print("Validation complete! Results saved to comprehensive_validation_results.json")
    print("="*80)
    
    return results

if __name__ == "__main__":
    main()