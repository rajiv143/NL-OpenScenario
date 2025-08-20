#!/usr/bin/env python3
"""
Identify specific issues in scenarios and fix them
"""

import json
import os
from pathlib import Path
from typing import Dict, List

class IssueIdentifierFixer:
    def __init__(self, dataset_path: str):
        self.dataset_path = Path(dataset_path)
        self.issues_found = []
        self.fixes_applied = []
        
    def identify_and_fix_all(self):
        """Identify issues in all scenarios and fix them"""
        scenario_files = sorted(self.dataset_path.glob("scenario_*.json"))
        scenario_files = [f for f in scenario_files if 'backup' not in str(f)]
        
        print("="*80)
        print("IDENTIFYING AND FIXING ISSUES")
        print("="*80)
        
        for json_file in scenario_files:
            self.check_and_fix_scenario(json_file)
        
        # Print summary
        print("\n" + "="*80)
        print(f"ISSUES FOUND: {len(self.issues_found)}")
        print(f"FIXES APPLIED: {len(self.fixes_applied)}")
        print("="*80)
        
        # Save detailed report
        with open('/home/user/Desktop/Rajiv/issues_and_fixes.json', 'w') as f:
            json.dump({
                'issues': self.issues_found,
                'fixes': self.fixes_applied
            }, f, indent=2)
    
    def check_and_fix_scenario(self, json_file: Path):
        """Check a single scenario for issues and fix them"""
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
            self.issues_found.append({
                'scenario': scenario_num,
                'file': str(json_file.name),
                'issue': f"Cannot read file: {e}",
                'severity': 'ERROR'
            })
            return
        
        original_data = json.dumps(json_data, sort_keys=True)
        issues_in_scenario = []
        
        # Check for missing required fields in actions
        for i, action in enumerate(json_data.get('actions', [])):
            action_type = action.get('action_type')
            
            # Check brake actions
            if action_type == 'brake':
                if 'brake_force' not in action:
                    issues_in_scenario.append(f"Action {i}: Missing brake_force")
                    action['brake_force'] = 0.5  # Default moderate braking
                    
                if 'dynamics_dimension' not in action:
                    issues_in_scenario.append(f"Action {i}: Missing dynamics_dimension")
                    action['dynamics_dimension'] = 'time'
                    
                if 'dynamics_shape' not in action:
                    issues_in_scenario.append(f"Action {i}: Missing dynamics_shape")
                    action['dynamics_shape'] = 'linear'
                    
                if 'dynamics_value' not in action:
                    issues_in_scenario.append(f"Action {i}: Missing dynamics_value")
                    action['dynamics_value'] = 2.0
                    
                # Check brake force range
                brake_force = action.get('brake_force', 0)
                if brake_force < 0.1 or brake_force > 1.0:
                    issues_in_scenario.append(f"Action {i}: brake_force {brake_force} out of range")
                    action['brake_force'] = max(0.1, min(1.0, brake_force))
            
            # Check speed actions
            elif action_type == 'speed':
                if 'speed_value' not in action:
                    issues_in_scenario.append(f"Action {i}: Missing speed_value")
                    action['speed_value'] = 10.0  # Default speed
                    
                if 'dynamics_dimension' not in action:
                    issues_in_scenario.append(f"Action {i}: Missing dynamics_dimension")
                    action['dynamics_dimension'] = 'time'
                    
                if 'dynamics_shape' not in action:
                    issues_in_scenario.append(f"Action {i}: Missing dynamics_shape")
                    action['dynamics_shape'] = 'linear'
                    
                if 'dynamics_value' not in action:
                    issues_in_scenario.append(f"Action {i}: Missing dynamics_value")
                    action['dynamics_value'] = 2.0
            
            # Check lane_change actions
            elif action_type == 'lane_change':
                if 'target_lane' not in action:
                    issues_in_scenario.append(f"Action {i}: Missing target_lane")
                    action['target_lane'] = 1  # Default to right lane
                    
                if 'dynamics_dimension' not in action:
                    issues_in_scenario.append(f"Action {i}: Missing dynamics_dimension")
                    action['dynamics_dimension'] = 'time'
                    
                if 'dynamics_shape' not in action:
                    issues_in_scenario.append(f"Action {i}: Missing dynamics_shape")
                    action['dynamics_shape'] = 'sinusoidal'
                    
                if 'dynamics_value' not in action:
                    issues_in_scenario.append(f"Action {i}: Missing dynamics_value")
                    action['dynamics_value'] = 2.5
            
            # Check wait actions
            elif action_type == 'wait':
                if 'wait_duration' not in action:
                    issues_in_scenario.append(f"Action {i}: Missing wait_duration")
                    action['wait_duration'] = 2.0
                    
                if 'dynamics_dimension' not in action:
                    issues_in_scenario.append(f"Action {i}: Missing dynamics_dimension")
                    action['dynamics_dimension'] = 'time'
                    
                if 'dynamics_value' not in action:
                    issues_in_scenario.append(f"Action {i}: Missing dynamics_value")
                    action['dynamics_value'] = 1.0
        
        # Check for lane relationship issues
        for actor in json_data.get('actors', []):
            spawn_criteria = actor.get('spawn', {}).get('criteria', {})
            lane_rel = spawn_criteria.get('lane_relationship')
            rel_pos = spawn_criteria.get('relative_position')
            actor_id = actor.get('id')
            
            # Check if this is a following scenario with wrong lane relationship
            if 'follow' in txt_content and rel_pos == 'ahead':
                # Check if there's a lane change for this actor
                has_lane_change = any(
                    a.get('actor_id') == actor_id and a.get('action_type') == 'lane_change'
                    for a in json_data.get('actions', [])
                )
                
                if lane_rel == 'adjacent_lane' and not has_lane_change:
                    issues_in_scenario.append(f"Actor {actor_id}: Following scenario but in adjacent_lane without lane change")
                    spawn_criteria['lane_relationship'] = 'same_lane'
            
            # Check perpendicular traffic at intersections
            if rel_pos == 'perpendicular':
                road_rel = spawn_criteria.get('road_relationship')
                if road_rel != 'different_road':
                    issues_in_scenario.append(f"Actor {actor_id}: Perpendicular but not different_road")
                    spawn_criteria['road_relationship'] = 'different_road'
                    # Remove lane_relationship for different road
                    if 'lane_relationship' in spawn_criteria:
                        del spawn_criteria['lane_relationship']
        
        # Check if we made any changes
        modified_data = json.dumps(json_data, sort_keys=True)
        if modified_data != original_data and issues_in_scenario:
            # Save the fixed version
            with open(json_file, 'w') as f:
                json.dump(json_data, f, indent=2)
            
            self.fixes_applied.append({
                'scenario': scenario_num,
                'file': str(json_file.name),
                'fixes': issues_in_scenario
            })
            
            print(f"\n✅ FIXED Scenario {scenario_num}:")
            for issue in issues_in_scenario:
                print(f"   - {issue}")
        
        elif issues_in_scenario:
            # Record issues that couldn't be fixed
            self.issues_found.append({
                'scenario': scenario_num,
                'file': str(json_file.name),
                'issues': issues_in_scenario,
                'severity': 'ERROR'
            })
            
            print(f"\n❌ ISSUES in Scenario {scenario_num} (couldn't auto-fix):")
            for issue in issues_in_scenario:
                print(f"   - {issue}")

def main():
    fixer = IssueIdentifierFixer('/home/user/Desktop/Rajiv/dataset1908')
    fixer.identify_and_fix_all()
    
    # Re-run validation to confirm fixes
    print("\n" + "="*80)
    print("RE-VALIDATING AFTER FIXES...")
    print("="*80)
    
    import subprocess
    result = subprocess.run(['python', 'comprehensive_validation.py'], 
                          capture_output=True, text=True)
    
    # Show just the summary
    lines = result.stdout.split('\n')
    summary_start = False
    for line in lines:
        if 'COMPREHENSIVE VALIDATION REPORT' in line:
            summary_start = True
        if summary_start and 'Total Scenarios Validated' in line:
            print('\n'.join(lines[lines.index(line):lines.index(line)+5]))
            break

if __name__ == "__main__":
    main()