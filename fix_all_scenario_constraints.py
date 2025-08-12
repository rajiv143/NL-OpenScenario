#!/usr/bin/env python3
"""
Comprehensive Scenario Constraint Fixer

This script fixes ALL scenario JSON files by:
1. Removing hardcoded map names to enable intelligent map selection
2. Adding appropriate road/lane relationship constraints based on scenario patterns
3. Updating success conditions and timeouts
4. Validating and fixing constraint patterns

The script determines appropriate constraints based on scenario name patterns:
- Following scenarios -> same_road, same_lane
- Cut-in scenarios -> same_road, adjacent_lane  
- Intersection scenarios -> different_road, is_intersection: true
- Pedestrian scenarios -> lane_type: Sidewalk
- etc.
"""

import json
import os
import glob
import shutil
from typing import Dict, List, Any, Optional
from pathlib import Path
import re
from datetime import datetime

class ScenarioConstraintFixer:
    def __init__(self, base_dir: str = ".", create_backup: bool = True):
        self.base_dir = Path(base_dir)
        self.create_backup = create_backup
        self.backup_dir = self.base_dir / "scenario_backups" / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.fixes_applied = {
            'hardcoded_maps_removed': 0,
            'constraints_added': 0,
            'success_conditions_updated': 0,
            'files_processed': 0,
            'files_fixed': 0
        }
        self.scenario_patterns = {
            # Following scenarios - same road, same lane
            'following': {
                'patterns': ['following', 'slow_lead', 'lead_vehicle', 'stop_and_go'],
                'constraints': {
                    'road_relationship': 'same_road',
                    'lane_relationship': 'same_lane',
                    'relative_position': 'ahead'
                }
            },
            
            # Cut-in and lane change scenarios - same road, adjacent lane
            'cut_in': {
                'patterns': ['cut_in', 'lane_change', 'aggressive_merge'],
                'constraints': {
                    'road_relationship': 'same_road',
                    'lane_relationship': 'adjacent_lane',
                    'relative_position': 'ahead'
                }
            },
            
            # Merge scenarios - same road, adjacent lane
            'merge': {
                'patterns': ['merge_from_ramp', 'merge_gap_closing', 'highway_merge'],
                'constraints': {
                    'road_relationship': 'same_road',
                    'lane_relationship': 'adjacent_lane',
                    'relative_position': 'behind'
                }
            },
            
            # Overtaking scenarios - same road, adjacent lane
            'overtake': {
                'patterns': ['overtake', 'slow_vehicle_overtake'],
                'constraints': {
                    'road_relationship': 'same_road',
                    'lane_relationship': 'adjacent_lane',
                    'relative_position': 'behind'
                }
            },
            
            # Intersection scenarios - different road
            'intersection': {
                'patterns': ['intersection', 'cross_traffic', 'chaos'],
                'constraints': {
                    'road_relationship': 'different_road',
                    'lane_relationship': 'any',
                    'is_intersection': True
                }
            },
            
            # Stationary/obstacle scenarios - same road
            'stationary': {
                'patterns': ['parked', 'obstacle', 'broken_down', 'construction', 'accident_scene'],
                'constraints': {
                    'road_relationship': 'same_road',
                    'lane_relationship': 'same_lane',
                    'relative_position': 'ahead'
                }
            },
            
            # Emergency scenarios - flexible constraints
            'emergency': {
                'patterns': ['emergency', 'ambulance', 'fire_truck', 'police'],
                'constraints': {
                    'road_relationship': 'same_road',
                    'lane_relationship': 'any'
                }
            },
            
            # Pedestrian scenarios - sidewalk
            'pedestrian': {
                'patterns': ['pedestrian', 'crossing', 'child', 'elderly', 'jogger', 'wheelchair', 'blind'],
                'constraints': {
                    'road_relationship': 'same_road',
                    'lane_type': 'Sidewalk'
                }
            },
            
            # Vulnerable users - cyclists
            'cyclist': {
                'patterns': ['cyclist', 'bike'],
                'constraints': {
                    'road_relationship': 'same_road',
                    'lane_relationship': 'adjacent_lane',
                    'lane_type': 'Driving'
                }
            }
        }
        
        # Success condition templates by scenario complexity
        self.success_templates = {
            'simple': {'success_distance': 100, 'timeout': 60},
            'medium': {'success_distance': 150, 'timeout': 90},
            'complex': {'success_distance': 200, 'timeout': 120},
            'multi_actor': {'success_distance': 250, 'timeout': 150}
        }
    
    def find_scenario_files(self) -> List[Path]:
        """Find all scenario JSON files"""
        scenario_files = []
        
        search_dirs = [
            'demo_scenarios',
            'test_scenarios', 
            'generated_scenarios',
            'gpt_jsons',
            'handcrafted_jsons',
            'exported_json'
        ]
        
        for search_dir in search_dirs:
            pattern = str(self.base_dir / search_dir / "*.json")
            scenario_files.extend([Path(f) for f in glob.glob(pattern)])
            
        # Filter out non-scenario files from root
        root_pattern = str(self.base_dir / "*.json")
        root_files = glob.glob(root_pattern)
        scenario_files.extend([
            Path(f) for f in root_files 
            if not any(exclude in f.lower() for exclude in [
                'road_intelligence', 'spawn', 'network_analysis', 
                'enhanced_town', 'carla-scenarios-dataset', 'audit', 'report'
            ])
        ])
        
        return list(set(scenario_files))
    
    def classify_scenario(self, scenario_name: str, description: str = "") -> str:
        """Classify scenario type based on name patterns"""
        name_lower = scenario_name.lower()
        desc_lower = description.lower()
        combined = f"{name_lower} {desc_lower}"
        
        # Check each pattern type
        for scenario_type, config in self.scenario_patterns.items():
            for pattern in config['patterns']:
                if pattern in combined:
                    return scenario_type
        
        return 'unknown'
    
    def get_success_complexity(self, scenario_data: Dict) -> str:
        """Determine success condition complexity"""
        actors = scenario_data.get('actors', [])
        actions = scenario_data.get('actions', [])
        
        if len(actors) >= 3:
            return 'multi_actor'
        elif len(actions) >= 4:
            return 'complex'
        elif len(actions) >= 2:
            return 'medium'
        else:
            return 'simple'
    
    def backup_file(self, file_path: Path) -> bool:
        """Create backup of original file"""
        if not self.create_backup:
            return True
            
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = self.backup_dir / file_path.name
            shutil.copy2(file_path, backup_path)
            return True
        except Exception as e:
            print(f"⚠️  Warning: Could not backup {file_path}: {e}")
            return False
    
    def fix_scenario_file(self, file_path: Path) -> Dict[str, Any]:
        """Fix a single scenario file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            return {'error': f"Failed to load {file_path}: {e}"}
        
        # Create backup
        if not self.backup_file(file_path):
            return {'error': f"Failed to backup {file_path}"}
        
        changes_made = []
        scenario_name = data.get('scenario_name', 'unknown')
        description = data.get('description', '')
        scenario_type = self.classify_scenario(scenario_name, description)
        
        # 1. Remove hardcoded map names
        if 'map_name' in data:
            old_map = data.pop('map_name')
            changes_made.append(f"Removed hardcoded map: {old_map}")
            self.fixes_applied['hardcoded_maps_removed'] += 1
        
        # 2. Fix actor constraints
        actors = data.get('actors', [])
        for i, actor in enumerate(actors):
            actor_changes = self.fix_actor_constraints(actor, scenario_type, i)
            changes_made.extend(actor_changes)
        
        # 3. Update success conditions
        success_changes = self.fix_success_conditions(data, scenario_type)
        changes_made.extend(success_changes)
        
        # 4. Save fixed file
        if changes_made:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                self.fixes_applied['files_fixed'] += 1
            except Exception as e:
                return {'error': f"Failed to save {file_path}: {e}"}
        
        self.fixes_applied['files_processed'] += 1
        
        return {
            'file': str(file_path.relative_to(self.base_dir)),
            'scenario_type': scenario_type,
            'changes': changes_made
        }
    
    def fix_actor_constraints(self, actor: Dict, scenario_type: str, actor_index: int) -> List[str]:
        """Fix constraints for a single actor"""
        changes = []
        
        if 'spawn' not in actor:
            actor['spawn'] = {'criteria': {}}
        if 'criteria' not in actor['spawn']:
            actor['spawn']['criteria'] = {}
        
        criteria = actor['spawn']['criteria']
        actor_type = actor.get('type', 'vehicle')
        actor_id = actor.get('id', f'actor_{actor_index}')
        
        # Get expected constraints for this scenario type
        if scenario_type in self.scenario_patterns:
            expected_constraints = self.scenario_patterns[scenario_type]['constraints'].copy()
            
            # Adjust for actor type
            if actor_type == 'pedestrian':
                expected_constraints['lane_type'] = 'Sidewalk'
                # Remove vehicle-specific constraints for pedestrians
                expected_constraints.pop('lane_relationship', None)
            elif actor_type == 'vehicle' and 'lane_type' not in expected_constraints:
                expected_constraints['lane_type'] = 'Driving'
            
            # Apply missing critical constraints
            critical_constraints = ['road_relationship']
            if actor_type == 'vehicle':
                critical_constraints.append('lane_relationship')
            
            for constraint_key, expected_value in expected_constraints.items():
                if constraint_key not in criteria:
                    criteria[constraint_key] = expected_value
                    changes.append(f"Added {constraint_key}: {expected_value} to {actor_id}")
                    self.fixes_applied['constraints_added'] += 1
        
        # Fix deprecated constraints
        if 'road_id' in criteria and criteria['road_id'] == 'same_as_ego':
            criteria.pop('road_id')
            criteria['road_relationship'] = 'same_road'
            changes.append(f"Updated deprecated road_id constraint for {actor_id}")
            self.fixes_applied['constraints_added'] += 1
        
        # Ensure distance constraints exist
        if 'distance_to_ego' not in criteria:
            # Set reasonable defaults based on scenario type
            if scenario_type == 'following':
                criteria['distance_to_ego'] = {'min': 30, 'max': 60}
            elif scenario_type in ['cut_in', 'merge', 'overtake']:
                criteria['distance_to_ego'] = {'min': 30, 'max': 50}
            elif scenario_type == 'intersection':
                criteria['distance_to_ego'] = {'min': 40, 'max': 80}
            elif scenario_type == 'pedestrian':
                criteria['distance_to_ego'] = {'min': 20, 'max': 40}
            else:
                criteria['distance_to_ego'] = {'min': 30, 'max': 60}
            changes.append(f"Added distance_to_ego constraint for {actor_id}")
            self.fixes_applied['constraints_added'] += 1
        
        return changes
    
    def fix_success_conditions(self, data: Dict, scenario_type: str) -> List[str]:
        """Fix success conditions and timeout"""
        changes = []
        complexity = self.get_success_complexity(data)
        template = self.success_templates[complexity]
        
        # Update success_distance if missing or too low
        current_success = data.get('success_distance', 0)
        if current_success < template['success_distance']:
            data['success_distance'] = template['success_distance']
            changes.append(f"Updated success_distance to {template['success_distance']}")
            self.fixes_applied['success_conditions_updated'] += 1
        
        # Update timeout if missing or too low
        current_timeout = data.get('timeout', 0)
        if current_timeout < template['timeout']:
            data['timeout'] = template['timeout']
            changes.append(f"Updated timeout to {template['timeout']}")
            self.fixes_applied['success_conditions_updated'] += 1
        
        # Ensure collision_allowed is set
        if 'collision_allowed' not in data:
            data['collision_allowed'] = False
            changes.append("Added collision_allowed: false")
        
        return changes
    
    def run_fixes(self) -> Dict[str, Any]:
        """Run fixes on all scenario files"""
        print("🔧 Starting comprehensive scenario constraint fixes...")
        
        scenario_files = self.find_scenario_files()
        print(f"Found {len(scenario_files)} scenario files to process")
        
        if self.create_backup:
            print(f"📁 Backups will be saved to: {self.backup_dir}")
        
        results = []
        errors = []
        
        for i, file_path in enumerate(scenario_files, 1):
            print(f"  [{i:3d}/{len(scenario_files)}] Processing: {file_path.name}")
            
            result = self.fix_scenario_file(file_path)
            
            if 'error' in result:
                errors.append(result)
                print(f"    ❌ Error: {result['error']}")
            else:
                results.append(result)
                if result['changes']:
                    print(f"    ✅ Applied {len(result['changes'])} fixes")
                else:
                    print(f"    ⏭️  No fixes needed")
        
        return {
            'summary': self.fixes_applied,
            'results': results,
            'errors': errors,
            'backup_location': str(self.backup_dir) if self.create_backup else None
        }
    
    def generate_report(self, results: Dict[str, Any], output_file: str = "scenario_fixes_report.json"):
        """Generate fix report"""
        # Save detailed JSON report
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        # Generate summary report
        summary_file = output_file.replace('.json', '_summary.txt')
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            summary = results['summary']
            
            f.write("=" * 60 + "\n")
            f.write("CARLA SCENARIO CONSTRAINT FIX REPORT\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"📊 SUMMARY:\n")
            f.write(f"  Files processed: {summary['files_processed']}\n")
            f.write(f"  Files fixed: {summary['files_fixed']}\n")
            f.write(f"  Hardcoded maps removed: {summary['hardcoded_maps_removed']}\n")
            f.write(f"  Constraints added: {summary['constraints_added']}\n")
            f.write(f"  Success conditions updated: {summary['success_conditions_updated']}\n\n")
            
            if results['backup_location']:
                f.write(f"📁 Backup location: {results['backup_location']}\n\n")
            
            if results['errors']:
                f.write(f"❌ ERRORS ({len(results['errors'])}):\n")
                for error in results['errors']:
                    f.write(f"  - {error.get('error', 'Unknown error')}\n")
                f.write("\n")
            
            f.write("✅ CHANGES APPLIED:\n")
            f.write("-" * 40 + "\n")
            
            for result in results['results']:
                if result.get('changes'):
                    f.write(f"\n📁 {result['file']} ({result['scenario_type']})\n")
                    for change in result['changes']:
                        f.write(f"  • {change}\n")
        
        print(f"\n✅ Fix process complete!")
        print(f"📄 Detailed report: {output_file}")
        print(f"📋 Summary report: {summary_file}")
        
        return results

def main():
    # Ask user for confirmation
    print("🚨 This will modify ALL scenario files in the project.")
    print("📁 Backups will be created automatically.")
    response = input("Continue? (y/N): ").strip().lower()
    
    if response != 'y':
        print("Operation cancelled.")
        return
    
    fixer = ScenarioConstraintFixer(create_backup=True)
    results = fixer.run_fixes()
    fixer.generate_report(results)
    
    # Print summary
    summary = results['summary']
    print(f"\n🎯 Summary:")
    print(f"   Files processed: {summary['files_processed']}")
    print(f"   Files fixed: {summary['files_fixed']}")
    print(f"   Hardcoded maps removed: {summary['hardcoded_maps_removed']}")
    print(f"   Constraints added: {summary['constraints_added']}")
    print(f"   Success conditions updated: {summary['success_conditions_updated']}")
    
    if results['errors']:
        print(f"   Errors encountered: {len(results['errors'])}")

if __name__ == "__main__":
    main()