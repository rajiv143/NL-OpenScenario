#!/usr/bin/env python3
"""
Fix Following Scenarios - Wrong Lane Spawns and Early Termination
Fixes critical issues in CARLA scenario JSON files for following scenarios
"""
import json
import os
import glob
import logging
from typing import Dict, List, Any

class FollowingScenarioFixer:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.fixes_applied = {
            'lane_relationships_added': 0,
            'success_conditions_updated': 0,
            'scenarios_processed': 0,
            'errors': []
        }
        
        # Success conditions by scenario type
        self.success_templates = {
            'gradual_slowdown': {'success_distance': 150, 'timeout': 180},
            'sudden_brake': {'success_distance': 100, 'timeout': 120},
            'emergency_stop': {'success_distance': 80, 'timeout': 90},
            'stop_and_go': {'success_distance': 120, 'timeout': 150},
            'following_slow': {'success_distance': 130, 'timeout': 160},
            'merge_gap': {'success_distance': 110, 'timeout': 140},
            'default': {'success_distance': 100, 'timeout': 120}
        }
        
        # Lane relationships by scenario type
        self.lane_relationships = {
            'following': 'same_lane',
            'cut_in': 'adjacent_lane',
            'overtake': 'adjacent_lane',
            'merge': 'adjacent_lane',
            'cross_traffic': 'any_lane'  # Uses road_relationship instead
        }
    
    def fix_all_following_scenarios(self, scenario_dir: str = "generated_scenarios"):
        """Fix all basic_following scenarios in the directory"""
        pattern = os.path.join(scenario_dir, "basic_following_*.json")
        scenario_files = glob.glob(pattern)
        
        self.logger.info(f"Found {len(scenario_files)} following scenarios to fix")
        
        for scenario_file in scenario_files:
            self.logger.info(f"Processing: {os.path.basename(scenario_file)}")
            self._fix_single_scenario(scenario_file)
        
        self._generate_fix_report()
    
    def _fix_single_scenario(self, scenario_path: str):
        """Fix a single following scenario"""
        try:
            with open(scenario_path, 'r') as f:
                data = json.load(f)
        except Exception as e:
            self.fixes_applied['errors'].append(f"Could not load {scenario_path}: {e}")
            return
        
        self.fixes_applied['scenarios_processed'] += 1
        scenario_name = data.get('scenario_name', '')
        modified = False
        
        # Fix 1: Add lane relationships to actors
        for actor in data.get('actors', []):
            if actor.get('type') in ['vehicle', 'cyclist']:
                spawn_criteria = actor.get('spawn', {}).get('criteria', {})
                
                # Add lane_relationship if missing
                if 'lane_relationship' not in spawn_criteria:
                    # Determine appropriate lane relationship
                    lane_rel = self._determine_lane_relationship(scenario_name, actor)
                    spawn_criteria['lane_relationship'] = lane_rel
                    
                    self.logger.info(f"Added lane_relationship='{lane_rel}' to actor '{actor['id']}' in {scenario_name}")
                    self.fixes_applied['lane_relationships_added'] += 1
                    modified = True
        
        # Fix 2: Add/update success conditions
        success_conditions = self._get_success_conditions(scenario_name)
        
        for key, value in success_conditions.items():
            if key not in data or data[key] != value:
                old_value = data.get(key, 'missing')
                data[key] = value
                self.logger.info(f"Updated {key}: {old_value} -> {value} in {scenario_name}")
                self.fixes_applied['success_conditions_updated'] += 1
                modified = True
        
        # Save if modified
        if modified:
            try:
                with open(scenario_path, 'w') as f:
                    json.dump(data, f, indent=2)
                self.logger.info(f"✅ Fixed and saved: {scenario_path}")
            except Exception as e:
                self.fixes_applied['errors'].append(f"Could not save {scenario_path}: {e}")
    
    def _determine_lane_relationship(self, scenario_name: str, actor: Dict) -> str:
        """Determine appropriate lane relationship based on scenario type and actor"""
        scenario_lower = scenario_name.lower()
        actor_id = actor.get('id', '').lower()
        
        # Following scenarios: same lane
        if any(keyword in scenario_lower for keyword in ['following', 'slowdown', 'brake', 'stop_and_go']):
            return 'same_lane'
        
        # Cut-in/merge scenarios: adjacent lane initially
        if any(keyword in scenario_lower for keyword in ['cut_in', 'merge', 'gap_closing']):
            return 'adjacent_lane'
        
        # Overtaking scenarios: adjacent lane
        if 'overtake' in scenario_lower or 'overtake' in actor_id:
            return 'adjacent_lane'
        
        # Default for following scenarios
        return 'same_lane'
    
    def _get_success_conditions(self, scenario_name: str) -> Dict[str, int]:
        """Get appropriate success conditions based on scenario type"""
        scenario_lower = scenario_name.lower()
        
        for scenario_type, conditions in self.success_templates.items():
            if scenario_type.replace('_', ' ') in scenario_lower:
                return conditions
        
        return self.success_templates['default']
    
    def fix_related_scenarios(self, scenario_dir: str = "generated_scenarios"):
        """Fix related scenario types (cut-in, overtake, etc.)"""
        patterns = [
            "lane_change_*cut_in*.json",
            "lane_change_*overtake*.json", 
            "lane_change_*merge*.json"
        ]
        
        for pattern in patterns:
            scenario_files = glob.glob(os.path.join(scenario_dir, pattern))
            self.logger.info(f"Fixing {len(scenario_files)} scenarios matching {pattern}")
            
            for scenario_file in scenario_files:
                self._fix_lane_change_scenario(scenario_file)
    
    def _fix_lane_change_scenario(self, scenario_path: str):
        """Fix lane change scenarios with appropriate relationships"""
        try:
            with open(scenario_path, 'r') as f:
                data = json.load(f)
        except Exception as e:
            self.fixes_applied['errors'].append(f"Could not load {scenario_path}: {e}")
            return
        
        scenario_name = data.get('scenario_name', '')
        modified = False
        
        for actor in data.get('actors', []):
            if actor.get('type') in ['vehicle', 'cyclist']:
                spawn_criteria = actor.get('spawn', {}).get('criteria', {})
                
                # Determine lane relationship for lane change scenarios
                if 'cut_in' in scenario_name.lower():
                    expected_rel = 'adjacent_lane'
                elif 'overtake' in scenario_name.lower():
                    expected_rel = 'adjacent_lane'
                elif 'merge' in scenario_name.lower():
                    expected_rel = 'adjacent_lane'
                else:
                    expected_rel = 'same_lane'
                
                current_rel = spawn_criteria.get('lane_relationship')
                if current_rel != expected_rel:
                    spawn_criteria['lane_relationship'] = expected_rel
                    self.logger.info(f"Updated lane_relationship to '{expected_rel}' for {actor['id']} in {scenario_name}")
                    modified = True
        
        if modified:
            try:
                with open(scenario_path, 'w') as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                self.fixes_applied['errors'].append(f"Could not save {scenario_path}: {e}")
    
    def _generate_fix_report(self):
        """Generate comprehensive fix report"""
        fixes = self.fixes_applied
        
        print(f"\n{'='*60}")
        print(f"FOLLOWING SCENARIOS FIX REPORT")
        print(f"{'='*60}")
        
        print(f"Scenarios Processed: {fixes['scenarios_processed']}")
        print(f"Lane Relationships Added: {fixes['lane_relationships_added']}")
        print(f"Success Conditions Updated: {fixes['success_conditions_updated']}")
        
        if fixes['errors']:
            print(f"\nErrors Encountered: {len(fixes['errors'])}")
            for error in fixes['errors']:
                print(f"  ❌ {error}")
        
        success_rate = (fixes['scenarios_processed'] - len(fixes['errors'])) / max(fixes['scenarios_processed'], 1) * 100
        print(f"\nSuccess Rate: {success_rate:.1f}%")
        
        if success_rate >= 95:
            print("✅ EXCELLENT: Following scenarios successfully fixed!")
        elif success_rate >= 80:
            print("✅ GOOD: Most scenarios fixed, minor issues remain")
        else:
            print("⚠️  WARNING: Some scenarios could not be fixed")

def test_specific_scenarios():
    """Test the two specific problematic scenarios"""
    test_scenarios = [
        "generated_scenarios/basic_following_010_gradual_slowdown_10.json",
        "generated_scenarios/basic_following_024_sudden_brake_ahead_24.json"
    ]
    
    print(f"\n🧪 TESTING SPECIFIC PROBLEMATIC SCENARIOS")
    
    for scenario_path in test_scenarios:
        if not os.path.exists(scenario_path):
            print(f"❌ {scenario_path} not found")
            continue
            
        print(f"\nTesting: {os.path.basename(scenario_path)}")
        
        # Show before state
        with open(scenario_path, 'r') as f:
            data = json.load(f)
        
        actors = data.get('actors', [])
        has_lane_rel = any(
            'lane_relationship' in actor.get('spawn', {}).get('criteria', {})
            for actor in actors if actor.get('type') == 'vehicle'
        )
        
        success_distance = data.get('success_distance', 'missing')
        timeout = data.get('timeout', 'missing')
        
        print(f"  Before - Lane relationships: {'✅' if has_lane_rel else '❌'}")
        print(f"  Before - Success distance: {success_distance}")
        print(f"  Before - Timeout: {timeout}")
        
        # Apply fixes
        fixer = FollowingScenarioFixer()
        fixer._fix_single_scenario(scenario_path)
        
        # Show after state
        with open(scenario_path, 'r') as f:
            data = json.load(f)
        
        actors = data.get('actors', [])
        lane_rels = []
        for actor in actors:
            if actor.get('type') == 'vehicle':
                lane_rel = actor.get('spawn', {}).get('criteria', {}).get('lane_relationship')
                lane_rels.append(f"{actor['id']}:{lane_rel}")
        
        print(f"  After - Lane relationships: {', '.join(lane_rels) if lane_rels else 'none'}")
        print(f"  After - Success distance: {data.get('success_distance')}")
        print(f"  After - Timeout: {data.get('timeout')}")

def main():
    """Main fix routine"""
    logging.basicConfig(level=logging.INFO)
    
    # Test specific problematic scenarios first
    test_specific_scenarios()
    
    # Fix all following scenarios
    fixer = FollowingScenarioFixer()
    fixer.fix_all_following_scenarios()
    
    # Fix related scenario types
    fixer.fix_related_scenarios()
    
    print(f"\n✅ All fixes completed! Run scenario validator to verify results.")

if __name__ == '__main__':
    main()