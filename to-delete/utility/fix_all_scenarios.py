#!/usr/bin/env python3
"""
Comprehensive scenario fixer that simplifies and corrects all generated scenarios
to work properly with the intelligent xosc_json.py converter.

Key improvements:
1. Removes unnecessary spawn_strategy fields
2. Simplifies spawn constraints based on scenario type
3. Ensures logical consistency in constraints
4. Lets the converter handle intelligent map selection
"""

import json
import os
import glob
import re
from typing import Dict, List, Any, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class ScenarioFixer:
    def __init__(self):
        # Define scenario type patterns and their implicit constraints
        self.scenario_patterns = {
            'following': {
                'keywords': ['following', 'stop_and_go', 'gradual_slowdown', 'sudden_brake'],
                'implicit_constraints': {
                    'road_relationship': 'same_road',
                    'lane_relationship': 'same_lane',
                    'relative_position': 'ahead'
                }
            },
            'cut_in': {
                'keywords': ['cut_in', 'aggressive_merge'],
                'implicit_constraints': {
                    'road_relationship': 'same_road',
                    'lane_relationship': 'adjacent_lane',
                    'relative_position': 'ahead'
                }
            },
            'lane_change': {
                'keywords': ['lane_change', 'double_lane', 'slow_vehicle_overtake'],
                'implicit_constraints': {
                    'road_relationship': 'same_road',
                    'lane_relationship': 'adjacent_lane'
                }
            },
            'merge': {
                'keywords': ['merge_from_ramp', 'merge_gap'],
                'implicit_constraints': {
                    'road_relationship': 'same_road',
                    'lane_relationship': 'adjacent_lane',
                    'relative_position': 'ahead'
                }
            },
            'intersection': {
                'keywords': ['intersection', 'cross_traffic'],
                'implicit_constraints': {
                    'road_relationship': 'different_road',
                    'is_intersection': True
                }
            },
            'pedestrian': {
                'keywords': ['pedestrian', 'child_dart', 'elderly_crossing', 'jogger', 'crosswalk'],
                'implicit_constraints': {
                    'lane_type': 'Sidewalk'
                }
            },
            'emergency': {
                'keywords': ['ambulance', 'fire_truck', 'police', 'emergency'],
                'implicit_constraints': {
                    'road_relationship': 'same_road'
                }
            },
            'static_obstacle': {
                'keywords': ['broken_down', 'parked_car', 'construction', 'accident_scene', 'delivery_truck_stopped'],
                'implicit_constraints': {
                    'road_relationship': 'same_road',
                    'lane_relationship': 'same_lane',
                    'relative_position': 'ahead'
                }
            },
            'multi_actor': {
                'keywords': ['multi_actor', 'market_street', 'bus_stop', 'school', 'parking_lot', 'highway_merge'],
                'implicit_constraints': {}  # Multi-actor scenarios vary too much for defaults
            },
            'vulnerable': {
                'keywords': ['cyclist', 'wheelchair', 'blind_pedestrian', 'school_zone'],
                'implicit_constraints': {}
            },
            'weather': {
                'keywords': ['rain_following', 'wet_braking', 'glare', 'visibility'],
                'implicit_constraints': {
                    'road_relationship': 'same_road'
                }
            }
        }
        
        # Fields to remove from all scenarios
        self.fields_to_remove = [
            'spawn_strategy',
            'map_name',
            'lane_relationship_fallback',
            'lane_type_fallback',
            'max_lane_distance',
            'heading_tol',
            'constraint_relaxation'
        ]
        
        # Fields to remove from spawn criteria
        self.spawn_fields_to_remove = [
            'lane_relationship_fallback',
            'lane_type_fallback', 
            'max_lane_distance',
            'heading_tol'
        ]

    def detect_scenario_type(self, scenario_name: str, description: str) -> str:
        """Detect scenario type from name and description"""
        name_lower = scenario_name.lower()
        desc_lower = description.lower() if description else ""
        
        for scenario_type, config in self.scenario_patterns.items():
            for keyword in config['keywords']:
                if keyword in name_lower or keyword in desc_lower:
                    return scenario_type
        
        return 'general'

    def simplify_ego_spawn(self, ego_spawn: Dict) -> Dict:
        """Simplify ego spawn constraints"""
        # Start with minimal constraints
        simplified = {
            'criteria': {
                'lane_type': 'Driving'
            }
        }
        
        # Only keep essential criteria
        if 'criteria' in ego_spawn:
            criteria = ego_spawn['criteria']
            
            # Keep is_intersection if explicitly false (for non-intersection scenarios)
            if criteria.get('is_intersection') is False:
                simplified['criteria']['is_intersection'] = False
            
            # Keep lane_id if it has reasonable bounds
            if 'lane_id' in criteria:
                lane_id = criteria['lane_id']
                if isinstance(lane_id, dict) and 'min' in lane_id and 'max' in lane_id:
                    # Simplify to reasonable range
                    simplified['criteria']['lane_id'] = {
                        'min': max(1, lane_id.get('min', 1)),
                        'max': min(4, lane_id.get('max', 4))  # Most roads have 1-4 lanes
                    }
        
        return simplified

    def simplify_actor_spawn(self, actor: Dict, scenario_type: str) -> Dict:
        """Simplify actor spawn constraints based on scenario type"""
        if 'spawn' not in actor:
            return actor
        
        simplified_actor = actor.copy()
        spawn = actor['spawn']
        
        if 'criteria' not in spawn:
            return simplified_actor
        
        old_criteria = spawn['criteria']
        new_criteria = {}
        
        # Get implicit constraints for this scenario type
        implicit = self.scenario_patterns.get(scenario_type, {}).get('implicit_constraints', {})
        
        # Apply implicit constraints first
        new_criteria.update(implicit)
        
        # Handle distance constraint - always keep if present
        if 'distance_to_ego' in old_criteria:
            dist = old_criteria['distance_to_ego']
            if isinstance(dist, dict):
                # Ensure reasonable bounds
                min_dist = dist.get('min', 10)
                max_dist = dist.get('max', 100)
                
                # Fix inverted ranges
                if min_dist > max_dist:
                    min_dist, max_dist = max_dist, min_dist
                
                # Ensure minimum separation
                if max_dist - min_dist < 10:
                    max_dist = min_dist + 30
                
                new_criteria['distance_to_ego'] = {
                    'min': max(5, min_dist),
                    'max': min(150, max_dist)
                }
        
        # Handle relative position - keep if present and not conflicting
        if 'relative_position' in old_criteria and 'relative_position' not in implicit:
            new_criteria['relative_position'] = old_criteria['relative_position']
        
        # Special handling for pedestrians
        if actor.get('type') == 'pedestrian':
            new_criteria['lane_type'] = 'Sidewalk'
            # Remove vehicle-specific constraints
            new_criteria.pop('lane_relationship', None)
            new_criteria.pop('road_relationship', None)
            
            # Add lateral offset for sidewalk fallback
            if 'lateral_offset' not in new_criteria:
                new_criteria['lateral_offset'] = 3.0
        
        # Special handling for intersection scenarios
        if scenario_type == 'intersection' or old_criteria.get('is_intersection'):
            new_criteria['is_intersection'] = True
            # Different road implies intersection
            if 'road_relationship' not in new_criteria:
                new_criteria['road_relationship'] = 'different_road'
        
        # Remove problematic fields
        for field in self.spawn_fields_to_remove:
            new_criteria.pop(field, None)
        
        simplified_actor['spawn'] = {'criteria': new_criteria}
        return simplified_actor

    def fix_scenario(self, scenario: Dict) -> Dict:
        """Fix a single scenario by simplifying and correcting it"""
        fixed = scenario.copy()
        
        # Detect scenario type
        scenario_type = self.detect_scenario_type(
            scenario.get('scenario_name', ''),
            scenario.get('description', '')
        )
        
        # Remove unnecessary top-level fields
        for field in self.fields_to_remove:
            fixed.pop(field, None)
        
        # Simplify ego spawn
        if 'ego_spawn' in fixed:
            fixed['ego_spawn'] = self.simplify_ego_spawn(fixed['ego_spawn'])
        else:
            # Add minimal ego spawn if missing
            fixed['ego_spawn'] = {
                'criteria': {
                    'lane_type': 'Driving'
                }
            }
        
        # Fix actors
        if 'actors' in fixed:
            fixed_actors = []
            for actor in fixed['actors']:
                fixed_actor = self.simplify_actor_spawn(actor, scenario_type)
                fixed_actors.append(fixed_actor)
            fixed['actors'] = fixed_actors
        
        # Ensure essential fields are present
        if 'ego_start_speed' not in fixed:
            fixed['ego_start_speed'] = 0
        
        if 'success_distance' not in fixed:
            fixed['success_distance'] = 150
        
        if 'timeout' not in fixed:
            fixed['timeout'] = 90
        
        if 'collision_allowed' not in fixed:
            fixed['collision_allowed'] = False
        
        # Fix weather if needed
        if 'weather' in fixed:
            valid_weather = ['clear', 'cloudy', 'wet', 'wet_cloudy', 'soft_rain', 
                           'mid_rain', 'hard_rain', 'clear_noon', 'clear_sunset']
            if fixed['weather'] not in valid_weather:
                fixed['weather'] = 'clear'
        
        return fixed

    def process_file(self, filepath: str) -> bool:
        """Process a single scenario file"""
        try:
            with open(filepath, 'r') as f:
                scenario = json.load(f)
            
            # Fix the scenario
            fixed = self.fix_scenario(scenario)
            
            # Write back the fixed scenario
            with open(filepath, 'w') as f:
                json.dump(fixed, f, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to process {filepath}: {e}")
            return False

    def process_all_scenarios(self, directory: str):
        """Process all scenario files in a directory"""
        pattern = os.path.join(directory, "*.json")
        files = glob.glob(pattern)
        
        if not files:
            logger.warning(f"No JSON files found in {directory}")
            return
        
        logger.info(f"Found {len(files)} scenario files to process")
        
        success_count = 0
        failure_count = 0
        
        for filepath in sorted(files):
            filename = os.path.basename(filepath)
            logger.info(f"Processing {filename}...")
            
            if self.process_file(filepath):
                success_count += 1
            else:
                failure_count += 1
        
        logger.info(f"\nProcessing complete:")
        logger.info(f"  Successfully fixed: {success_count}")
        logger.info(f"  Failed: {failure_count}")
        
        # Generate summary report
        self.generate_report(directory, success_count, failure_count)

    def generate_report(self, directory: str, success: int, failed: int):
        """Generate a summary report of the fixes"""
        report_path = os.path.join(directory, "../scenario_fix_report.txt")
        
        with open(report_path, 'w') as f:
            f.write("Scenario Fix Report\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Total scenarios processed: {success + failed}\n")
            f.write(f"Successfully fixed: {success}\n")
            f.write(f"Failed to fix: {failed}\n\n")
            
            f.write("Key improvements made:\n")
            f.write("- Removed unnecessary spawn_strategy fields\n")
            f.write("- Simplified spawn constraints based on scenario type\n")
            f.write("- Applied implicit constraints for each scenario category\n")
            f.write("- Fixed inverted or illogical distance ranges\n")
            f.write("- Removed contradictory lane/road relationships\n")
            f.write("- Ensured pedestrians spawn on sidewalks\n")
            f.write("- Added missing essential fields\n")
            
        logger.info(f"\nReport saved to: {report_path}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix all generated scenarios")
    parser.add_argument(
        '--dir',
        default='generated_scenarios',
        help='Directory containing scenario JSON files'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create fixer and process all scenarios
    fixer = ScenarioFixer()
    fixer.process_all_scenarios(args.dir)


if __name__ == "__main__":
    main()