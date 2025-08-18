#!/usr/bin/env python3
"""
Quick Fix for Spawn Constraint Issues

Applies immediate fixes to scenario constraints based on the diagnostic findings:
1. Relaxes overly strict adjacent_lane constraints where no adjacent lanes exist
2. Widens distance constraints for better spawn point coverage
3. Adds fallback constraint strategies
4. Updates scenarios to use highway roads when adjacent lanes are needed
"""

import json
import shutil
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import glob

class QuickConstraintFixer:
    def __init__(self, create_backup: bool = True):
        self.create_backup = create_backup
        self.backup_dir = Path("constraint_fix_backups") / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.fixes_applied = {
            'files_processed': 0,
            'constraints_relaxed': 0,
            'distances_widened': 0,
            'fallbacks_added': 0
        }
        
        # Highway roads with good lane coverage (from our analysis)
        self.preferred_roads_for_adjacent_lanes = [45, 35, 38, 40, 41, 50]
        
        # Roads with no adjacent lanes (simple bidirectional)
        self.problematic_roads = [27, 26, 24, 18, 14, 16, 17, 19, 20, 21]
    
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
        """Apply constraint fixes to a single scenario file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            return {'error': f"Failed to load {file_path}: {e}"}
        
        if not self.backup_file(file_path):
            return {'error': f"Failed to backup {file_path}"}
        
        changes_made = []
        scenario_name = data.get('scenario_name', 'unknown')
        
        # Classify scenario type
        scenario_type = self.classify_scenario(scenario_name)
        
        # Fix actor constraints
        actors = data.get('actors', [])
        for i, actor in enumerate(actors):
            actor_changes = self.fix_actor_constraints(actor, scenario_type, i)
            changes_made.extend(actor_changes)
        
        # Add fallback spawn strategies
        if scenario_type in ['cut_in', 'lane_change', 'overtake']:
            fallback_changes = self.add_fallback_strategies(data, scenario_type)
            changes_made.extend(fallback_changes)
        
        # Save fixed file if changes were made
        if changes_made:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                return {'error': f"Failed to save {file_path}: {e}"}
        
        self.fixes_applied['files_processed'] += 1
        
        return {
            'file': str(file_path),
            'scenario_type': scenario_type,
            'changes': changes_made
        }
    
    def classify_scenario(self, scenario_name: str) -> str:
        """Classify scenario type from name"""
        name_lower = scenario_name.lower()
        
        if any(pattern in name_lower for pattern in ['following', 'slow_lead']):
            return 'following'
        elif any(pattern in name_lower for pattern in ['cut_in', 'lane_change']):
            return 'cut_in'
        elif any(pattern in name_lower for pattern in ['overtake']):
            return 'overtake'
        elif any(pattern in name_lower for pattern in ['intersection', 'cross_traffic', 'chaos']):
            return 'intersection'
        elif any(pattern in name_lower for pattern in ['merge']):
            return 'merge'
        elif any(pattern in name_lower for pattern in ['pedestrian', 'crossing']):
            return 'pedestrian'
        else:
            return 'unknown'
    
    def fix_actor_constraints(self, actor: Dict, scenario_type: str, actor_index: int) -> List[str]:
        """Fix constraints for a single actor"""
        changes = []
        
        if 'spawn' not in actor or 'criteria' not in actor['spawn']:
            return changes
        
        criteria = actor['spawn']['criteria']
        actor_id = actor.get('id', f'actor_{actor_index}')
        
        # Fix adjacent_lane constraints for problematic scenarios
        if criteria.get('lane_relationship') == 'adjacent_lane':
            if scenario_type in ['cut_in', 'lane_change', 'overtake']:
                # Add relaxed constraints
                original_lane_rel = criteria['lane_relationship']
                
                # Strategy 1: Allow same-direction lanes within 2 lane distances
                criteria['lane_relationship_fallback'] = 'same_direction_nearby'
                criteria['max_lane_distance'] = 2
                
                changes.append(f"Added fallback for adjacent_lane constraint on {actor_id}")
                self.fixes_applied['constraints_relaxed'] += 1
        
        # Widen distance constraints if they're too restrictive
        if 'distance_to_ego' in criteria:
            dist_constraint = criteria['distance_to_ego']
            min_dist = dist_constraint.get('min', 20)
            max_dist = dist_constraint.get('max', 60)
            
            # If range is too narrow (< 30m), widen it
            if max_dist - min_dist < 30:
                new_min = max(min_dist * 0.7, 15)  # Reduce min by 30%, but not below 15m
                new_max = min_dist + 50  # Ensure at least 50m range
                
                criteria['distance_to_ego'] = {
                    'min': new_min,
                    'max': new_max
                }
                
                changes.append(f"Widened distance constraint for {actor_id}: {min_dist:.0f}-{max_dist:.0f}m → {new_min:.0f}-{new_max:.0f}m")
                self.fixes_applied['distances_widened'] += 1
        
        # Add heading tolerance for direction-sensitive scenarios
        if scenario_type in ['following', 'cut_in', 'overtake'] and 'heading_tol' not in criteria:
            criteria['heading_tol'] = 45  # Allow 45 degree heading difference
            changes.append(f"Added heading tolerance for {actor_id}")
        
        # For pedestrian actors, ensure lane_type is Sidewalk but add fallbacks
        if actor.get('type') == 'pedestrian':
            if criteria.get('lane_type') == 'Sidewalk':
                # Add fallback to allow spawning on driving lanes if no sidewalks available
                criteria['lane_type_fallback'] = 'Driving'
                criteria['lateral_offset'] = 3.0  # Spawn 3m to the side of driving lane
                changes.append(f"Added lane_type fallback for pedestrian {actor_id}")
        
        return changes
    
    def add_fallback_strategies(self, data: Dict, scenario_type: str) -> List[str]:
        """Add fallback strategies at the scenario level"""
        changes = []
        
        # Add spawn strategy hints for the converter
        if 'spawn_strategy' not in data:
            if scenario_type in ['cut_in', 'lane_change', 'overtake']:
                data['spawn_strategy'] = {
                    'prefer_highways': True,
                    'preferred_roads': self.preferred_roads_for_adjacent_lanes,
                    'avoid_roads': self.problematic_roads,
                    'constraint_relaxation': 'enabled'
                }
                changes.append("Added intelligent spawn strategy hints")
                self.fixes_applied['fallbacks_added'] += 1
            
            elif scenario_type == 'intersection':
                data['spawn_strategy'] = {
                    'require_intersections': True,
                    'constraint_relaxation': 'enabled'
                }
                changes.append("Added intersection spawn strategy hints")
                self.fixes_applied['fallbacks_added'] += 1
        
        return changes
    
    def process_all_scenarios(self, scenario_dirs: List[str] = None) -> Dict[str, Any]:
        """Process all scenario files"""
        if scenario_dirs is None:
            scenario_dirs = [
                'demo_scenarios',
                'test_scenarios',
                'generated_scenarios', 
                'gpt_jsons',
                'handcrafted_jsons'
            ]
        
        print("🔧 Applying quick fixes to scenario constraints...")
        
        all_results = []
        errors = []
        
        for scenario_dir in scenario_dirs:
            if not Path(scenario_dir).exists():
                continue
                
            scenario_files = list(Path(scenario_dir).glob("*.json"))
            print(f"  Processing {len(scenario_files)} files in {scenario_dir}/")
            
            for file_path in scenario_files:
                result = self.fix_scenario_file(file_path)
                
                if 'error' in result:
                    errors.append(result)
                else:
                    all_results.append(result)
                    if result['changes']:
                        print(f"    ✅ {file_path.name}: {len(result['changes'])} fixes applied")
        
        return {
            'summary': self.fixes_applied,
            'results': all_results,
            'errors': errors,
            'backup_location': str(self.backup_dir) if self.create_backup else None
        }
    
    def generate_fix_report(self, results: Dict[str, Any], output_file: str = "constraint_fixes_report.json"):
        """Generate report of fixes applied"""
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Generate summary report
        summary_file = output_file.replace('.json', '_summary.txt')
        
        with open(summary_file, 'w') as f:
            summary = results['summary']
            
            f.write("=" * 60 + "\n")
            f.write("SPAWN CONSTRAINT QUICK FIXES REPORT\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"📊 SUMMARY:\n")
            f.write(f"  Files processed: {summary['files_processed']}\n")
            f.write(f"  Constraints relaxed: {summary['constraints_relaxed']}\n")
            f.write(f"  Distances widened: {summary['distances_widened']}\n")
            f.write(f"  Fallback strategies added: {summary['fallbacks_added']}\n\n")
            
            if results['backup_location']:
                f.write(f"📁 Backup location: {results['backup_location']}\n\n")
            
            f.write("🔧 FIXES BY SCENARIO TYPE:\n")
            f.write("-" * 40 + "\n")
            
            # Group by scenario type
            by_type = {}
            for result in results['results']:
                scenario_type = result['scenario_type']
                if scenario_type not in by_type:
                    by_type[scenario_type] = []
                by_type[scenario_type].append(result)
            
            for scenario_type, type_results in by_type.items():
                files_with_fixes = [r for r in type_results if r['changes']]
                f.write(f"\n{scenario_type.upper()}:\n")
                f.write(f"  Files: {len(type_results)}\n")
                f.write(f"  Files with fixes: {len(files_with_fixes)}\n")
                
                if files_with_fixes:
                    f.write(f"  Common fixes:\n")
                    all_changes = []
                    for result in files_with_fixes:
                        all_changes.extend(result['changes'])
                    
                    # Count change types
                    change_counts = {}
                    for change in all_changes:
                        if 'fallback' in change.lower():
                            change_counts['Fallback strategies'] = change_counts.get('Fallback strategies', 0) + 1
                        elif 'distance' in change.lower():
                            change_counts['Distance widening'] = change_counts.get('Distance widening', 0) + 1
                        elif 'constraint' in change.lower():
                            change_counts['Constraint relaxation'] = change_counts.get('Constraint relaxation', 0) + 1
                        else:
                            change_counts['Other fixes'] = change_counts.get('Other fixes', 0) + 1
                    
                    for change_type, count in change_counts.items():
                        f.write(f"    • {change_type}: {count}\n")
        
        print(f"\n📄 Fix report saved: {output_file}")
        print(f"📋 Summary report: {summary_file}")

def main():
    print("🚨 This will apply quick fixes to scenario constraint issues.")
    print("📁 Backups will be created automatically.")
    response = input("Continue? (y/N): ").strip().lower()
    
    if response != 'y':
        print("Operation cancelled.")
        return
    
    fixer = QuickConstraintFixer(create_backup=True)
    results = fixer.process_all_scenarios()
    fixer.generate_fix_report(results)
    
    # Print summary
    summary = results['summary']
    print(f"\n🎯 Quick Fix Summary:")
    print(f"   Files processed: {summary['files_processed']}")
    print(f"   Constraints relaxed: {summary['constraints_relaxed']}")
    print(f"   Distances widened: {summary['distances_widened']}")
    print(f"   Fallback strategies added: {summary['fallbacks_added']}")
    
    if results['errors']:
        print(f"   Errors encountered: {len(results['errors'])}")
    
    print(f"\n💡 Next Steps:")
    print(f"   1. Test scenarios with: python xosc_json.py <scenario_file>")
    print(f"   2. Update xosc_json.py to implement smart constraint relaxation")
    print(f"   3. Prefer highway roads for scenarios requiring adjacent lanes")

if __name__ == "__main__":
    main()