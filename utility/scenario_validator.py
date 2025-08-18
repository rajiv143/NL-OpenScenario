#!/usr/bin/env python3
"""
Enhanced Scenario Validator and Fixer
Validates and fixes comprehensive issues in generated scenarios
"""
import json
import os
import glob
import logging
import re

class ScenarioValidator:
    VALID_RELATIVE_POSITIONS = {'ahead', 'behind'}
    VALID_LANE_TYPES = {'Driving', 'Sidewalk', 'Shoulder', 'Parking', 'Stop', 'Border'}
    VALID_ROAD_RELATIONSHIPS = {'same_road', 'different_road', 'any_road'}
    VALID_LANE_RELATIONSHIPS = {'same_lane', 'adjacent_lane', 'any_lane'}
    VALID_MAPS = {'Town01', 'Town02', 'Town03', 'Town04', 'Town05', 'Town06', 'Town07', 'Town10HD'}
    
    # Minimum distance requirements by scenario type
    MIN_DISTANCES = {
        'cut_in': 25,
        'following': 20,
        'gradual_slowdown': 20,
        'sudden_brake': 20,
        'parked_vehicle': 15,
        'pedestrian': 10,
        'intersection': 30,
        'general': 10
    }
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.scenario_names = set()
        
    def _detect_scenario_type(self, scenario_name: str) -> str:
        """Detect the scenario type from the name"""
        name_lower = scenario_name.lower()
        if 'cut_in' in name_lower or 'cut-in' in name_lower or 'lane_change' in name_lower:
            return 'cut_in'
        elif 'following' in name_lower or 'follow' in name_lower:
            return 'following'
        elif 'brake' in name_lower and 'sudden' in name_lower:
            return 'sudden_brake'
        elif 'slowdown' in name_lower or 'gradual' in name_lower:
            return 'gradual_slowdown'
        elif 'parked' in name_lower:
            return 'parked_vehicle'
        elif 'pedestrian' in name_lower or 'crossing' in name_lower:
            return 'pedestrian'
        elif 'intersection' in name_lower or 'junction' in name_lower:
            return 'intersection'
        else:
            return 'general'
        
    def validate_scenario(self, scenario_path: str) -> list:
        """Validate a scenario and return list of issues found"""
        issues = []
        
        try:
            with open(scenario_path, 'r') as f:
                data = json.load(f)
        except Exception as e:
            issues.append(f"Could not load JSON: {e}")
            return issues
        
        # Basic structure validation
        scenario_name = data.get('scenario_name', '')
        if not scenario_name:
            issues.append("Missing scenario_name")
        elif scenario_name in self.scenario_names:
            issues.append(f"Duplicate scenario_name '{scenario_name}'")
        else:
            self.scenario_names.add(scenario_name)
        
        # Map specification check
        if 'map_name' not in data:
            issues.append("Missing explicit map_name specification")
        elif data['map_name'] not in self.VALID_MAPS:
            issues.append(f"Invalid map_name '{data['map_name']}', must be one of {self.VALID_MAPS}")
        
        # Validate actors
        for actor in data.get('actors', []):
            actor_issues = self._validate_actor(actor, scenario_name)
            issues.extend(actor_issues)
        
        # Check for intersection scenarios missing proper constraints
        if 'intersection' in scenario_name.lower() or 'chaos' in scenario_name.lower():
            intersection_issues = self._validate_intersection_scenario(data)
            issues.extend(intersection_issues)
        
        # Success condition validation
        if 'success_distance' not in data and 'timeout' not in data:
            issues.append("Missing success conditions - scenario needs success_distance or timeout to prevent premature termination")
        elif 'success_distance' in data and data['success_distance'] < 50:
            issues.append(f"Success distance {data['success_distance']}m is very short, may cause premature termination")
        elif 'timeout' in data and data['timeout'] < 60:
            issues.append(f"Timeout {data['timeout']}s is very short, may cause premature termination")
            
        return issues
    
    def _validate_actor(self, actor: dict, scenario_name: str) -> list:
        """Validate individual actor constraints"""
        issues = []
        actor_id = actor.get('id', 'unknown_actor')
        actor_type = actor.get('type')
        spawn_criteria = actor.get('spawn', {}).get('criteria', {})
        
        # Lane type validation by actor type
        lane_type = spawn_criteria.get('lane_type')
        if actor_type == 'pedestrian':
            if lane_type == 'Driving':
                issues.append(f"Pedestrian '{actor_id}' has lane_type 'Driving', should be 'Sidewalk'")
            elif lane_type is None:
                issues.append(f"Pedestrian '{actor_id}' missing lane_type criteria")
        elif actor_type in ['vehicle', 'cyclist'] and lane_type not in ['Driving', None]:
            if lane_type not in self.VALID_LANE_TYPES:
                issues.append(f"Actor '{actor_id}' has invalid lane_type '{lane_type}'")
        
        # Invalid relative position values
        rel_pos = spawn_criteria.get('relative_position')
        if rel_pos and rel_pos not in self.VALID_RELATIVE_POSITIONS:
            if rel_pos == 'adjacent':
                issues.append(f"Actor '{actor_id}' has invalid relative_position 'adjacent' - use 'ahead'/'behind' with lane_relationship='adjacent_lane'")
            else:
                issues.append(f"Actor '{actor_id}' has invalid relative_position '{rel_pos}', must be one of {self.VALID_RELATIVE_POSITIONS}")
        
        # Road/lane relationship validation
        road_rel = spawn_criteria.get('road_relationship')
        if road_rel and road_rel not in self.VALID_ROAD_RELATIONSHIPS:
            issues.append(f"Actor '{actor_id}' has invalid road_relationship '{road_rel}'")
        
        lane_rel = spawn_criteria.get('lane_relationship')
        if lane_rel and lane_rel not in self.VALID_LANE_RELATIONSHIPS:
            issues.append(f"Actor '{actor_id}' has invalid lane_relationship '{lane_rel}'")
        
        # Distance range validation with scenario-specific minimums
        distance_constraint = spawn_criteria.get('distance_to_ego')
        scenario_type = self._detect_scenario_type(scenario_name)
        required_min = self.MIN_DISTANCES.get(scenario_type, 10)
        
        if actor_type == 'pedestrian':
            required_min = max(required_min, 10)  # At least 10m for pedestrians
        
        if isinstance(distance_constraint, dict):
            min_dist = distance_constraint.get('min', 0)
            max_dist = distance_constraint.get('max', float('inf'))
            
            # Check minimum distance requirements
            if min_dist < required_min:
                issues.append(f"Actor '{actor_id}' has minimum distance {min_dist}m, should be at least {required_min}m for {scenario_type} scenario")
            
            # Check range width
            if max_dist - min_dist < 20:
                issues.append(f"Actor '{actor_id}' has narrow distance range ({min_dist}-{max_dist}m), should be at least 20m range")
            
            # Check absolute minimum for safety
            if min_dist < 5:
                issues.append(f"Actor '{actor_id}' has very small minimum distance ({min_dist}m), may cause collision")
            
            # Check pedestrian max distance
            if actor_type == 'pedestrian' and max_dist > 50:
                issues.append(f"Pedestrian '{actor_id}' has excessive max distance {max_dist}m, should be capped at 50m")
        elif not distance_constraint:
            issues.append(f"Actor '{actor_id}' missing distance_to_ego constraint for {scenario_type} scenario")
        
        # Scenario-specific validations
        if 'overtake' in scenario_name.lower() and actor_type in ['vehicle', 'cyclist']:
            if 'lane_relationship' not in spawn_criteria:
                issues.append(f"Overtake scenario missing lane_relationship for actor '{actor_id}'")
        
        if 'cross' in scenario_name.lower() or 'intersection' in scenario_name.lower():
            if actor_type in ['vehicle', 'cyclist'] and road_rel != 'different_road':
                issues.append(f"Cross-traffic actor '{actor_id}' should have road_relationship='different_road'")
        
        # Following scenario validations
        if any(keyword in scenario_name.lower() for keyword in ['following', 'brake', 'slowdown', 'stop_and_go']):
            if actor_type in ['vehicle', 'cyclist'] and lane_rel != 'same_lane':
                issues.append(f"Following scenario actor '{actor_id}' should have lane_relationship='same_lane' to prevent opposite-side spawns")
        
        # Cut-in/merge scenario validations  
        if any(keyword in scenario_name.lower() for keyword in ['cut_in', 'merge', 'gap_closing']):
            if actor_type in ['vehicle', 'cyclist'] and lane_rel != 'adjacent_lane':
                issues.append(f"Cut-in/merge scenario actor '{actor_id}' should have lane_relationship='adjacent_lane'")
        
        return issues
    
    def _validate_intersection_scenario(self, data: dict) -> list:
        """Special validation for intersection scenarios"""
        issues = []
        
        cross_traffic_actors = []
        for actor in data.get('actors', []):
            spawn_criteria = actor.get('spawn', {}).get('criteria', {})
            if spawn_criteria.get('road_relationship') == 'different_road':
                cross_traffic_actors.append(actor['id'])
        
        if not cross_traffic_actors:
            issues.append("Intersection scenario missing cross-traffic actors with road_relationship='different_road'")
        
        # Check if intersection spawning is enabled
        intersection_spawns = []
        for actor in data.get('actors', []):
            spawn_criteria = actor.get('spawn', {}).get('criteria', {})
            if spawn_criteria.get('is_intersection') is True:
                intersection_spawns.append(actor['id'])
        
        if cross_traffic_actors and not intersection_spawns:
            issues.append("Cross-traffic actors should have is_intersection=true for proper intersection spawning")
        
        return issues
    
    def fix_scenario(self, scenario_path: str, issues: list) -> bool:
        """Fix common scenario issues"""
        if not issues:
            return False
            
        try:
            with open(scenario_path, 'r') as f:
                data = json.load(f)
        except:
            return False
            
        modified = False
        scenario_name = data.get('scenario_name', '')
        
        # Add missing map_name
        if 'map_name' not in data:
            # Default to Town04 which has good intersection coverage
            data['map_name'] = 'Town04'
            self.logger.info(f"Added default map_name 'Town04' to {scenario_path}")
            modified = True
        
        # Fix actors
        for actor in data.get('actors', []):
            actor_id = actor.get('id', 'unknown')
            actor_type = actor.get('type')
            spawn_criteria = actor.get('spawn', {}).get('criteria', {})
            
            # Fix pedestrian lane types
            if actor_type == 'pedestrian':
                if spawn_criteria.get('lane_type') == 'Driving':
                    spawn_criteria['lane_type'] = 'Sidewalk'
                    self.logger.info(f"Fixed pedestrian lane_type for {actor_id} in {scenario_path}")
                    modified = True
                elif 'lane_type' not in spawn_criteria:
                    spawn_criteria['lane_type'] = 'Sidewalk'
                    self.logger.info(f"Added missing lane_type for pedestrian {actor_id} in {scenario_path}")
                    modified = True
            
            # Fix invalid relative_position "adjacent"
            if spawn_criteria.get('relative_position') == 'adjacent':
                spawn_criteria['relative_position'] = 'ahead'
                if 'lane_relationship' not in spawn_criteria:
                    spawn_criteria['lane_relationship'] = 'adjacent_lane'
                self.logger.info(f"Fixed relative_position 'adjacent' -> 'ahead' + lane_relationship for {actor_id} in {scenario_path}")
                modified = True
            
            # Fix missing lane relationships for specific scenarios
            if ('overtake' in scenario_name.lower() and actor_type in ['vehicle', 'cyclist'] 
                and 'lane_relationship' not in spawn_criteria):
                spawn_criteria['lane_relationship'] = 'adjacent_lane'
                self.logger.info(f"Added lane_relationship for overtake actor {actor_id} in {scenario_path}")
                modified = True
            
            # Fix following scenarios
            if any(keyword in scenario_name.lower() for keyword in ['following', 'brake', 'slowdown', 'stop_and_go']):
                if actor_type in ['vehicle', 'cyclist'] and spawn_criteria.get('lane_relationship') != 'same_lane':
                    spawn_criteria['lane_relationship'] = 'same_lane'
                    spawn_criteria['road_relationship'] = 'same_road'
                    spawn_criteria['relative_position'] = 'ahead'
                    self.logger.info(f"Fixed following scenario constraints for {actor_id} in {scenario_path}")
                    modified = True
            
            # Fix cut-in scenarios
            if any(keyword in scenario_name.lower() for keyword in ['cut_in', 'cut-in', 'merge', 'gap_closing']):
                if actor_type in ['vehicle', 'cyclist'] and spawn_criteria.get('lane_relationship') != 'adjacent_lane':
                    spawn_criteria['lane_relationship'] = 'adjacent_lane'
                    spawn_criteria['relative_position'] = 'ahead'
                    self.logger.info(f"Fixed cut-in scenario constraints for {actor_id} in {scenario_path}")
                    modified = True
            
            # Fix intersection scenarios
            if ('intersection' in scenario_name.lower() or 'chaos' in scenario_name.lower()):
                if actor_type in ['vehicle', 'cyclist']:
                    # Add road_relationship for cross-traffic
                    if 'road_relationship' not in spawn_criteria:
                        spawn_criteria['road_relationship'] = 'different_road'
                        self.logger.info(f"Added road_relationship='different_road' for intersection actor {actor_id} in {scenario_path}")
                        modified = True
                    
                    # Enable intersection spawning
                    if 'is_intersection' not in spawn_criteria:
                        spawn_criteria['is_intersection'] = True
                        self.logger.info(f"Added is_intersection=true for actor {actor_id} in {scenario_path}")
                        modified = True
            
            # Fix distance constraints based on scenario type
            scenario_type = self._detect_scenario_type(scenario_name)
            required_min = self.MIN_DISTANCES.get(scenario_type, 10)
            
            if actor_type == 'pedestrian':
                required_min = max(required_min, 10)
            
            if 'spawn' not in actor:
                actor['spawn'] = {'criteria': {}}
            if 'criteria' not in actor['spawn']:
                actor['spawn']['criteria'] = {}
            spawn_criteria = actor['spawn']['criteria']
            
            # Ensure distance_to_ego exists
            if 'distance_to_ego' not in spawn_criteria:
                spawn_criteria['distance_to_ego'] = {'min': required_min, 'max': required_min * 3}
                self.logger.info(f"Added missing distance_to_ego for {actor_id}: {required_min}-{required_min*3}m in {scenario_path}")
                modified = True
            else:
                distance_constraint = spawn_criteria['distance_to_ego']
                if isinstance(distance_constraint, dict):
                    min_dist = distance_constraint.get('min', 0)
                    max_dist = distance_constraint.get('max', float('inf'))
                    
                    # Enforce minimum distance
                    if min_dist < required_min:
                        distance_constraint['min'] = required_min
                        self.logger.info(f"Increased minimum distance for {actor_id} from {min_dist}m to {required_min}m in {scenario_path}")
                        modified = True
                    
                    # Ensure absolute minimum of 5m
                    if distance_constraint['min'] < 5:
                        distance_constraint['min'] = 5
                        modified = True
                    
                    # Widen narrow ranges
                    if max_dist - distance_constraint['min'] < 20:
                        distance_constraint['max'] = distance_constraint['min'] + 30
                        self.logger.info(f"Widened distance range for {actor_id} to {distance_constraint['min']}-{distance_constraint['max']}m in {scenario_path}")
                        modified = True
                    
                    # Cap pedestrian max distance
                    if actor_type == 'pedestrian' and max_dist > 50:
                        distance_constraint['max'] = 50
                        self.logger.info(f"Capped pedestrian max distance for {actor_id} to 50m in {scenario_path}")
                        modified = True
        
        if modified:
            # Write back to file
            with open(scenario_path, 'w') as f:
                json.dump(data, f, indent=2)
            return True
            
        return False

def main():
    """Main validation and fixing routine"""
    logging.basicConfig(level=logging.INFO)
    validator = ScenarioValidator()
    
    scenario_dir = "generated_scenarios"
    if not os.path.exists(scenario_dir):
        print(f"Directory {scenario_dir} not found")
        return
        
    scenario_files = glob.glob(os.path.join(scenario_dir, "*.json"))
    total_issues = 0
    fixed_files = 0
    issue_categories = {
        'invalid_relative_position': 0,
        'missing_map_name': 0,
        'invalid_lane_type': 0,
        'narrow_distance_range': 0,
        'missing_lane_relationship': 0,
        'intersection_issues': 0,
        'other': 0
    }
    
    print(f"Validating {len(scenario_files)} scenario files...")
    
    for scenario_file in scenario_files:
        issues = validator.validate_scenario(scenario_file)
        if issues:
            total_issues += len(issues)
            print(f"\n{os.path.basename(scenario_file)}:")
            for issue in issues:
                print(f"  - {issue}")
                
                # Categorize issues
                if 'relative_position' in issue and 'adjacent' in issue:
                    issue_categories['invalid_relative_position'] += 1
                elif 'map_name' in issue:
                    issue_categories['missing_map_name'] += 1
                elif 'lane_type' in issue and ('Driving' in issue or 'missing' in issue):
                    issue_categories['invalid_lane_type'] += 1
                elif 'narrow distance range' in issue:
                    issue_categories['narrow_distance_range'] += 1
                elif 'lane_relationship' in issue:
                    issue_categories['missing_lane_relationship'] += 1
                elif 'intersection' in issue.lower() or 'cross-traffic' in issue:
                    issue_categories['intersection_issues'] += 1
                else:
                    issue_categories['other'] += 1
                
            # Try to fix
            if validator.fix_scenario(scenario_file, issues):
                fixed_files += 1
                print(f"  ✓ Fixed issues in {scenario_file}")
    
    print(f"\n{'='*60}")
    print(f"VALIDATION SUMMARY")
    print(f"{'='*60}")
    print(f"Total scenarios processed: {len(scenario_files)}")
    print(f"Total issues found: {total_issues}")
    print(f"Files with issues: {len([f for f in scenario_files if validator.validate_scenario(f)])}")
    print(f"Files fixed: {fixed_files}")
    
    print(f"\nISSUE BREAKDOWN:")
    for category, count in issue_categories.items():
        if count > 0:
            print(f"  {category.replace('_', ' ').title()}: {count}")
    
    if fixed_files > 0:
        print(f"\n✅ Run the validator again to verify all fixes were applied correctly.")
    else:
        print(f"\n✅ All scenarios passed validation!")

if __name__ == '__main__':
    main()