#!/usr/bin/env python3
"""
Comprehensive validation script for CARLA scenario dataset
Validates 350+ scenarios against critical rules
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

class ScenarioValidator:
    def __init__(self, dataset_path: str):
        self.dataset_path = Path(dataset_path)
        self.errors = defaultdict(list)
        self.warnings = defaultdict(list)
        self.correct = defaultdict(list)
        self.stats = defaultdict(int)
        
        # Categories tracking
        self.categories = {
            'following': [],
            'cut_in': [],
            'intersection': [],
            'pedestrian': [],
            'multi_actor': [],
            'emergency': [],
            'construction': [],
            'weather_specific': []
        }
        
        # Context tracking
        self.contexts = defaultdict(list)
        self.weather_types = defaultdict(list)
        self.actor_counts = defaultdict(list)
        
    def validate_all_scenarios(self) -> Dict:
        """Validate all scenarios in the dataset"""
        scenario_files = sorted(self.dataset_path.glob("scenario_*.json"))
        scenario_files = [f for f in scenario_files if 'backup' not in str(f)]
        
        results = []
        for json_file in scenario_files:
            txt_file = json_file.with_suffix('.txt')
            
            if not txt_file.exists():
                self.warnings['missing_txt'].append(str(json_file))
                continue
                
            result = self.validate_scenario(json_file, txt_file)
            results.append(result)
            
        return self.generate_report(results)
    
    def validate_scenario(self, json_file: Path, txt_file: Path) -> Dict:
        """Validate a single scenario"""
        scenario_num = json_file.stem.split('_')[1]
        
        try:
            with open(json_file, 'r') as f:
                json_data = json.load(f)
            with open(txt_file, 'r') as f:
                txt_content = f.read().lower()
        except Exception as e:
            return {
                'scenario': scenario_num,
                'name': json_file.stem,
                'status': 'ERROR',
                'errors': [f"Failed to read files: {e}"]
            }
        
        scenario_name = json_data.get('scenario_name', '')
        errors = []
        warnings = []
        correct = []
        
        # Categorize scenario
        self.categorize_scenario(scenario_num, json_data, txt_content)
        
        # Rule 1: Lane Relationship Logic
        lane_errors = self.check_lane_relationship(json_data, txt_content, scenario_num)
        errors.extend(lane_errors)
        
        # Rule 2: Weather Alignment
        weather_errors = self.check_weather_alignment(json_data, txt_content, scenario_num)
        errors.extend(weather_errors)
        
        # Rule 3: Color Specification
        color_warnings = self.check_color_specification(json_data, txt_content, scenario_num)
        warnings.extend(color_warnings)
        
        # Rule 4: Action Completeness
        action_errors = self.check_action_completeness(json_data, scenario_num)
        errors.extend(action_errors)
        
        # Track statistics
        if 'road_context' in json_data.get('ego_spawn', {}).get('criteria', {}):
            self.contexts[json_data['ego_spawn']['criteria']['road_context']].append(scenario_num)
        
        self.weather_types[json_data.get('weather', 'unknown')].append(scenario_num)
        self.actor_counts[len(json_data.get('actors', []))].append(scenario_num)
        
        # Determine status
        if errors:
            status = 'ERRORS'
            self.stats['errors'] += 1
        elif warnings:
            status = 'WARNINGS'
            self.stats['warnings'] += 1
        else:
            status = 'VALID'
            self.stats['valid'] += 1
            correct.append(f"All validation rules passed for scenario {scenario_num}")
        
        return {
            'scenario': scenario_num,
            'name': scenario_name,
            'status': status,
            'errors': errors,
            'warnings': warnings,
            'correct': correct
        }
    
    def check_lane_relationship(self, json_data: Dict, txt_content: str, scenario_num: str) -> List[str]:
        """Check lane relationship logic"""
        errors = []
        
        # Following scenario patterns
        following_patterns = ['following', 'ahead', 'behind', 'lead vehicle', 'in front', 
                            'same lane', 'maintains distance', 'follows']
        cut_in_patterns = ['cuts in', 'cut-in', 'merges', 'changes lanes', 'from adjacent', 
                          'overtakes', 'lane change', 'switches lanes']
        intersection_patterns = ['intersection', 'cross-traffic', 'perpendicular', 'cross traffic',
                               'different road', 'crossing']
        
        for actor in json_data.get('actors', []):
            spawn_criteria = actor.get('spawn', {}).get('criteria', {})
            lane_rel = spawn_criteria.get('lane_relationship')
            road_rel = spawn_criteria.get('road_relationship')
            
            # Check following scenarios
            if any(pattern in txt_content for pattern in following_patterns):
                if lane_rel == 'adjacent_lane':
                    errors.append(f"Scenario {scenario_num}: Following scenario but actor '{actor.get('id')}' has lane_relationship='adjacent_lane' (should be 'same_lane')")
                elif lane_rel == 'same_lane':
                    self.correct['lane_logic'].append(f"Scenario {scenario_num}: Correct same_lane for following")
            
            # Check cut-in scenarios
            if any(pattern in txt_content for pattern in cut_in_patterns):
                # Cut-in actors typically start in adjacent lane
                if 'spawn' in actor and lane_rel == 'same_lane' and 'lane_change' in str(json_data.get('actions', [])):
                    errors.append(f"Scenario {scenario_num}: Cut-in scenario but actor '{actor.get('id')}' starts in same_lane (should start in adjacent_lane)")
            
            # Check intersection scenarios
            if any(pattern in txt_content for pattern in intersection_patterns):
                if road_rel != 'different_road' and 'perpendicular' in txt_content:
                    errors.append(f"Scenario {scenario_num}: Intersection scenario but actor '{actor.get('id')}' missing road_relationship='different_road'")
        
        return errors
    
    def check_weather_alignment(self, json_data: Dict, txt_content: str, scenario_num: str) -> List[str]:
        """Check weather alignment between description and JSON"""
        errors = []
        json_weather = json_data.get('weather', '').lower()
        
        weather_mappings = {
            'rain': ['wet', 'soft_rain', 'mid_rain', 'hard_rain', 'wet_cloudy'],
            'wet': ['wet', 'soft_rain', 'mid_rain', 'hard_rain', 'wet_cloudy'],
            'rainy': ['wet', 'soft_rain', 'mid_rain', 'hard_rain', 'wet_cloudy'],
            'fog': ['fog'],
            'foggy': ['fog'],
            'night': ['clear_night', 'wet_night'],
            'evening': ['clear_sunset'],
            'sunset': ['clear_sunset'],
            'sunny': ['clear', 'clear_noon'],
            'clear': ['clear', 'clear_noon', 'clear_sunset', 'clear_night']
        }
        
        for weather_word, valid_values in weather_mappings.items():
            if weather_word in txt_content:
                if json_weather not in valid_values:
                    errors.append(f"Scenario {scenario_num}: Description mentions '{weather_word}' but JSON has weather='{json_weather}'")
                else:
                    self.correct['weather'].append(f"Scenario {scenario_num}: Weather correctly aligned")
                break
        
        return errors
    
    def check_color_specification(self, json_data: Dict, txt_content: str, scenario_num: str) -> List[str]:
        """Check if colors mentioned in description are in JSON"""
        warnings = []
        
        color_mappings = {
            'red': '255,0,0',
            'blue': '0,0,255',
            'green': '0,255,0',
            'white': '255,255,255',
            'black': '0,0,0',
            'yellow': '255,255,0',
            'gray': '128,128,128',
            'grey': '128,128,128'
        }
        
        for color_name, rgb_value in color_mappings.items():
            if color_name in txt_content:
                # Check if any actor has this color
                color_found = False
                for actor in json_data.get('actors', []):
                    if 'color' in actor:
                        color_found = True
                        break
                
                if not color_found:
                    warnings.append(f"Scenario {scenario_num}: Description mentions '{color_name}' but no actor has color field")
        
        return warnings
    
    def check_action_completeness(self, json_data: Dict, scenario_num: str) -> List[str]:
        """Check if all actions have required fields"""
        errors = []
        
        required_fields = {
            'speed': ['speed_value', 'dynamics_dimension', 'dynamics_shape', 'dynamics_value'],
            'brake': ['brake_force', 'dynamics_dimension', 'dynamics_shape', 'dynamics_value'],
            'lane_change': ['target_lane', 'dynamics_dimension', 'dynamics_shape', 'dynamics_value'],
            'wait': ['wait_duration', 'dynamics_dimension', 'dynamics_value']
        }
        
        for i, action in enumerate(json_data.get('actions', [])):
            action_type = action.get('action_type')
            if action_type in required_fields:
                for field in required_fields[action_type]:
                    if field not in action:
                        errors.append(f"Scenario {scenario_num}: Action {i} (type={action_type}) missing required field '{field}'")
                
                # Check brake force range
                if action_type == 'brake':
                    brake_force = action.get('brake_force', 0)
                    if not (0.1 <= brake_force <= 1.0):
                        errors.append(f"Scenario {scenario_num}: Action {i} brake_force={brake_force} outside valid range [0.1, 1.0]")
        
        return errors
    
    def categorize_scenario(self, scenario_num: str, json_data: Dict, txt_content: str):
        """Categorize the scenario type"""
        # Following
        if 'following' in txt_content or 'follow' in txt_content:
            self.categories['following'].append(scenario_num)
        
        # Cut-in
        if 'cut' in txt_content or 'merge' in txt_content:
            self.categories['cut_in'].append(scenario_num)
        
        # Intersection
        if 'intersection' in txt_content:
            self.categories['intersection'].append(scenario_num)
        
        # Pedestrian
        if 'pedestrian' in txt_content or any('pedestrian' in a.get('type', '') for a in json_data.get('actors', [])):
            self.categories['pedestrian'].append(scenario_num)
        
        # Multi-actor
        if len(json_data.get('actors', [])) >= 2:
            self.categories['multi_actor'].append(scenario_num)
        
        # Emergency
        if 'emergency' in txt_content or 'ambulance' in txt_content or 'fire' in txt_content:
            self.categories['emergency'].append(scenario_num)
        
        # Construction
        if 'construction' in txt_content:
            self.categories['construction'].append(scenario_num)
    
    def generate_report(self, results: List[Dict]) -> Dict:
        """Generate comprehensive validation report"""
        total = len(results)
        
        # Count errors by type
        error_types = defaultdict(int)
        for result in results:
            for error in result.get('errors', []):
                if 'lane_relationship' in error:
                    error_types['lane_relationship'] += 1
                elif 'weather' in error.lower():
                    error_types['weather'] += 1
                elif 'missing required field' in error:
                    error_types['missing_field'] += 1
                elif 'brake_force' in error:
                    error_types['brake_force_range'] += 1
        
        report = {
            'total_scenarios': total,
            'valid_scenarios': self.stats['valid'],
            'scenarios_with_errors': self.stats['errors'],
            'scenarios_with_warnings': self.stats['warnings'],
            'error_breakdown': dict(error_types),
            'categories': {k: len(v) for k, v in self.categories.items()},
            'contexts': {k: len(v) for k, v in self.contexts.items()},
            'weather_distribution': {k: len(v) for k, v in self.weather_types.items()},
            'actor_complexity': {k: len(v) for k, v in self.actor_counts.items()},
            'detailed_results': results
        }
        
        return report

def main():
    validator = ScenarioValidator('/home/user/Desktop/Rajiv/dataset1908')
    report = validator.validate_all_scenarios()
    
    # Save detailed report
    with open('/home/user/Desktop/Rajiv/validation_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    print(f"VALIDATION COMPLETE - {report['total_scenarios']} Scenarios Processed")
    print(f"\nCRITICAL ERRORS FOUND: {report['scenarios_with_errors']} scenarios")
    print(f"QUALITY WARNINGS: {report['scenarios_with_warnings']} scenarios")
    print(f"PERFECT SCENARIOS: {report['valid_scenarios']} scenarios ({report['valid_scenarios']/report['total_scenarios']*100:.1f}%)")
    
    print("\nERROR BREAKDOWN:")
    for error_type, count in report['error_breakdown'].items():
        print(f"  - {error_type}: {count} scenarios")
    
    print("\nCATEGORICAL BREAKDOWN:")
    for category, count in report['categories'].items():
        print(f"  - {category}: {count} scenarios")
    
    print("\nCONTEXT DISTRIBUTION:")
    for context, count in report['contexts'].items():
        print(f"  - {context}: {count} scenarios")
    
    return report

if __name__ == "__main__":
    main()