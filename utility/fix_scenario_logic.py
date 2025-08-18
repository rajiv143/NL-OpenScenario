#!/usr/bin/env python3
"""
Comprehensive logic fixer for scenario JSON files.
Fixes critical issues: spawn vs trigger distances, lane changes, unreachable goals.
"""

import json
import os
import glob
import logging
from typing import Dict, List, Any, Tuple

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class ScenarioLogicFixer:
    def __init__(self):
        self.fixes_applied = {
            'spawn_trigger_conflicts': 0,
            'lane_change_directions': 0,
            'unreachable_success': 0,
            'fractional_distances': 0,
            'timeout_adjustments': 0
        }

    def fix_spawn_trigger_conflicts(self, scenario: Dict) -> List[str]:
        """Fix spawn vs trigger distance conflicts"""
        fixes = []
        
        for actor in scenario.get('actors', []):
            actor_id = actor['id']
            spawn_criteria = actor.get('spawn', {}).get('criteria', {})
            
            if 'distance_to_ego' not in spawn_criteria:
                continue
                
            spawn_dist = spawn_criteria['distance_to_ego']
            current_min = spawn_dist.get('min', 0)
            current_max = spawn_dist.get('max', 100)
            
            # Find all distance triggers for this actor
            distance_triggers = []
            for action in scenario.get('actions', []):
                if (action.get('actor_id') == actor_id and 
                    action.get('trigger_type') == 'distance_to_ego'):
                    trigger_value = action.get('trigger_value', 0)
                    trigger_comparison = action.get('trigger_comparison', '<')
                    distance_triggers.append((trigger_value, trigger_comparison))
            
            if distance_triggers:
                # Find the most restrictive trigger (closest distance)
                min_trigger = min(t[0] for t in distance_triggers)
                
                # Calculate safe spawn distance with buffer
                buffer = 15  # 15m buffer
                safe_min = min_trigger + buffer
                
                if current_min < safe_min:
                    new_min = safe_min
                    new_max = max(new_min + 30, current_max)  # Ensure reasonable range
                    
                    spawn_dist['min'] = new_min
                    spawn_dist['max'] = new_max
                    
                    fix_msg = f"{actor_id}: spawn {current_min}m → {new_min}m (trigger at {min_trigger}m)"
                    fixes.append(fix_msg)
                    self.fixes_applied['spawn_trigger_conflicts'] += 1
        
        return fixes

    def fix_lane_change_directions(self, scenario: Dict) -> List[str]:
        """Fix lane change direction issues"""
        fixes = []
        scenario_name = scenario.get('scenario_name', '').lower()
        
        if 'cut_in' in scenario_name or 'lane_change' in scenario_name:
            for action in scenario.get('actions', []):
                if action.get('action_type') == 'lane_change':
                    actor_id = action['actor_id']
                    current_direction = action.get('lane_direction')
                    
                    # Find the actor to understand spawn relationship
                    actor = next((a for a in scenario['actors'] if a['id'] == actor_id), None)
                    if not actor:
                        continue
                    
                    lane_rel = actor.get('spawn', {}).get('criteria', {}).get('lane_relationship')
                    
                    # For cut-in scenarios, the direction should be toward ego
                    # Since we can't determine exact positions, use safer defaults
                    if 'cut_in' in scenario_name:
                        # For cut-in, typically changing from left lane to ego's lane
                        safe_direction = 'right'  # Most common pattern
                    else:
                        # For general lane changes, keep existing or use right as default
                        safe_direction = current_direction or 'right'
                    
                    if current_direction != safe_direction:
                        action['lane_direction'] = safe_direction
                        fix_msg = f"{actor_id}: lane change direction → {safe_direction}"
                        fixes.append(fix_msg)
                        self.fixes_applied['lane_change_directions'] += 1
        
        return fixes

    def fix_success_distances(self, scenario: Dict) -> List[str]:
        """Fix unreachable success distances"""
        fixes = []
        current_success = scenario.get('success_distance', 100)
        
        # Calculate reasonable success distance based on scenario type
        scenario_name = scenario.get('scenario_name', '').lower()
        
        if any(word in scenario_name for word in ['following', 'brake', 'stop']):
            # Following scenarios need less distance
            ideal_success = 60
        elif any(word in scenario_name for word in ['merge', 'lane_change', 'cut_in']):
            # Lane changes need moderate distance
            ideal_success = 80
        elif any(word in scenario_name for word in ['intersection', 'multi_actor']):
            # Complex scenarios need more distance
            ideal_success = 100
        elif any(word in scenario_name for word in ['pedestrian', 'crossing']):
            # Pedestrian scenarios are quick
            ideal_success = 50
        else:
            # Default
            ideal_success = 70
        
        if current_success > ideal_success + 20:  # Only fix if significantly off
            scenario['success_distance'] = ideal_success
            fix_msg = f"success_distance: {current_success}m → {ideal_success}m"
            fixes.append(fix_msg)
            self.fixes_applied['unreachable_success'] += 1
        
        return fixes

    def fix_fractional_distances(self, scenario: Dict) -> List[str]:
        """Round fractional distances to integers"""
        fixes = []
        
        for actor in scenario.get('actors', []):
            spawn_criteria = actor.get('spawn', {}).get('criteria', {})
            
            if 'distance_to_ego' in spawn_criteria:
                dist = spawn_criteria['distance_to_ego']
                
                for key in ['min', 'max']:
                    if key in dist:
                        original = dist[key]
                        rounded = int(round(original))
                        
                        if original != rounded:
                            dist[key] = rounded
                            fix_msg = f"{actor['id']}: {key} distance {original} → {rounded}"
                            fixes.append(fix_msg)
                            self.fixes_applied['fractional_distances'] += 1
        
        # Fix trigger distances too
        for action in scenario.get('actions', []):
            if 'trigger_value' in action:
                original = action['trigger_value']
                if isinstance(original, float) and original != int(original):
                    rounded = int(round(original))
                    action['trigger_value'] = rounded
                    fix_msg = f"{action.get('actor_id', 'unknown')}: trigger {original} → {rounded}"
                    fixes.append(fix_msg)
                    self.fixes_applied['fractional_distances'] += 1
        
        return fixes

    def fix_timeout_values(self, scenario: Dict) -> List[str]:
        """Ensure timeouts are reasonable for success distance"""
        fixes = []
        
        success_distance = scenario.get('success_distance', 70)
        current_timeout = scenario.get('timeout', 90)
        
        # Calculate reasonable timeout: time to travel success distance at ~30 km/h + buffer
        travel_time = (success_distance / 1000) / (30 / 3600)  # seconds
        ideal_timeout = max(60, int(travel_time + 30))  # 30s buffer
        
        if current_timeout < ideal_timeout or current_timeout > ideal_timeout + 60:
            scenario['timeout'] = ideal_timeout
            fix_msg = f"timeout: {current_timeout}s → {ideal_timeout}s"
            fixes.append(fix_msg)
            self.fixes_applied['timeout_adjustments'] += 1
        
        return fixes

    def validate_scenario_logic(self, scenario: Dict) -> List[str]:
        """Check for remaining logical issues"""
        issues = []
        
        # Check spawn vs trigger distances
        for actor in scenario.get('actors', []):
            actor_id = actor['id']
            spawn_criteria = actor.get('spawn', {}).get('criteria', {})
            spawn_min = spawn_criteria.get('distance_to_ego', {}).get('min', 0)
            
            for action in scenario.get('actions', []):
                if (action.get('actor_id') == actor_id and 
                    action.get('trigger_type') == 'distance_to_ego'):
                    trigger_dist = action.get('trigger_value', 0)
                    if spawn_min <= trigger_dist + 10:  # Less than 10m buffer
                        issues.append(f"{actor_id}: spawns at {spawn_min}m, triggers at {trigger_dist}m (too close)")
        
        # Check success distance achievability
        success_dist = scenario.get('success_distance', 0)
        timeout = scenario.get('timeout', 0)
        if success_dist > 120:
            issues.append(f"Success distance {success_dist}m may be unreachable")
        
        # Check for invalid lane directions
        for action in scenario.get('actions', []):
            if action.get('action_type') == 'lane_change':
                direction = action.get('lane_direction')
                if direction not in ['left', 'right']:
                    issues.append(f"Invalid lane direction: {direction}")
        
        return issues

    def fix_scenario_file(self, filepath: str) -> bool:
        """Fix logical issues in a single scenario file"""
        try:
            with open(filepath, 'r') as f:
                scenario = json.load(f)
            
            filename = os.path.basename(filepath)
            original_json = json.dumps(scenario, sort_keys=True)
            
            print(f"\nProcessing {filename}:")
            
            # Apply all fixes
            all_fixes = []
            all_fixes.extend(self.fix_spawn_trigger_conflicts(scenario))
            all_fixes.extend(self.fix_lane_change_directions(scenario))
            all_fixes.extend(self.fix_success_distances(scenario))
            all_fixes.extend(self.fix_fractional_distances(scenario))
            all_fixes.extend(self.fix_timeout_values(scenario))
            
            # Show fixes applied
            if all_fixes:
                for fix in all_fixes:
                    print(f"  ✓ {fix}")
            else:
                print(f"  - No fixes needed")
            
            # Check for remaining issues
            issues = self.validate_scenario_logic(scenario)
            if issues:
                print(f"  ⚠️  Remaining issues:")
                for issue in issues:
                    print(f"    - {issue}")
            
            # Save if changed
            new_json = json.dumps(scenario, sort_keys=True)
            if original_json != new_json:
                with open(filepath, 'w') as f:
                    json.dump(scenario, f, indent=2)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to process {filepath}: {e}")
            return False

    def process_all_scenarios(self, directory: str):
        """Process all scenario files in directory"""
        pattern = os.path.join(directory, "*.json")
        files = glob.glob(pattern)
        
        if not files:
            logger.warning(f"No JSON files found in {directory}")
            return
        
        logger.info(f"Found {len(files)} scenario files to fix")
        
        fixed_count = 0
        
        for filepath in sorted(files):
            if self.fix_scenario_file(filepath):
                fixed_count += 1
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"LOGIC FIX SUMMARY")
        print(f"{'='*60}")
        print(f"Total scenarios processed: {len(files)}")
        print(f"Files modified: {fixed_count}")
        print(f"\nFixes applied:")
        for fix_type, count in self.fixes_applied.items():
            if count > 0:
                print(f"  - {fix_type.replace('_', ' ').title()}: {count}")
        
        # Generate validation report
        self.generate_validation_report(directory)

    def generate_validation_report(self, directory: str):
        """Generate validation report for all fixed scenarios"""
        report_path = os.path.join(directory, "../logic_validation_report.txt")
        
        pattern = os.path.join(directory, "*.json")
        files = glob.glob(pattern)
        
        total_issues = 0
        
        with open(report_path, 'w') as f:
            f.write("Scenario Logic Validation Report\n")
            f.write("=" * 50 + "\n\n")
            
            for filepath in sorted(files):
                try:
                    with open(filepath, 'r') as json_file:
                        scenario = json.load(json_file)
                    
                    filename = os.path.basename(filepath)
                    issues = self.validate_scenario_logic(scenario)
                    
                    if issues:
                        f.write(f"\n{filename}:\n")
                        for issue in issues:
                            f.write(f"  - {issue}\n")
                        total_issues += len(issues)
                    
                except Exception as e:
                    f.write(f"\n{filename}: ERROR - {e}\n")
                    total_issues += 1
            
            f.write(f"\n\nSummary:\n")
            f.write(f"Total files checked: {len(files)}\n")
            f.write(f"Remaining issues: {total_issues}\n")
            
            if total_issues == 0:
                f.write("✅ All scenarios pass logic validation!\n")
            else:
                f.write(f"⚠️  {total_issues} issues still need attention\n")
        
        logger.info(f"Validation report saved to: {report_path}")

    def test_specific_scenarios(self, directory: str):
        """Test specific problematic scenarios mentioned in the prompt"""
        test_scenarios = [
            'lane_change_065_cut_in_ahead_15.json',
            'basic_following_010_gradual_slowdown_10.json',
            'pedestrian_crossing_027_child_dart_out_02.json'
        ]
        
        print(f"\n{'='*60}")
        print(f"TESTING SPECIFIC PROBLEM SCENARIOS")
        print(f"{'='*60}")
        
        for filename in test_scenarios:
            filepath = os.path.join(directory, filename)
            if os.path.exists(filepath):
                print(f"\n📋 Testing {filename}:")
                
                try:
                    with open(filepath, 'r') as f:
                        scenario = json.load(f)
                    
                    # Show key metrics
                    print(f"  Success distance: {scenario.get('success_distance', 'N/A')}m")
                    print(f"  Timeout: {scenario.get('timeout', 'N/A')}s")
                    
                    for actor in scenario.get('actors', []):
                        spawn_dist = actor.get('spawn', {}).get('criteria', {}).get('distance_to_ego', {})
                        spawn_min = spawn_dist.get('min', 'N/A')
                        spawn_max = spawn_dist.get('max', 'N/A')
                        print(f"  {actor['id']}: spawn {spawn_min}-{spawn_max}m")
                        
                        # Check triggers
                        for action in scenario.get('actions', []):
                            if (action.get('actor_id') == actor['id'] and 
                                action.get('trigger_type') == 'distance_to_ego'):
                                trigger = action.get('trigger_value', 'N/A')
                                print(f"    → triggers at {trigger}m")
                    
                    # Validate
                    issues = self.validate_scenario_logic(scenario)
                    if issues:
                        print(f"  ⚠️  Issues found:")
                        for issue in issues:
                            print(f"    - {issue}")
                    else:
                        print(f"  ✅ Passes validation")
                
                except Exception as e:
                    print(f"  ❌ Error reading file: {e}")
            else:
                print(f"\n❌ File not found: {filename}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix logical issues in all scenarios")
    parser.add_argument(
        '--dir',
        default='generated_scenarios',
        help='Directory containing scenario JSON files'
    )
    parser.add_argument(
        '--test-only',
        action='store_true',
        help='Only run validation tests, do not fix files'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    fixer = ScenarioLogicFixer()
    
    if args.test_only:
        print("Running validation tests only...")
        fixer.generate_validation_report(args.dir)
        fixer.test_specific_scenarios(args.dir)
    else:
        print("Fixing all scenario logic issues...")
        fixer.process_all_scenarios(args.dir)
        fixer.test_specific_scenarios(args.dir)


if __name__ == "__main__":
    main()