#!/usr/bin/env python3
"""
Comprehensive Scenario Constraint Audit Script

This script scans ALL scenario JSON files and identifies missing critical constraints:
- road_relationship (same_road/different_road)
- lane_relationship (same_lane/adjacent_lane/any)
- is_intersection for junction scenarios
- lane_type appropriateness
- hardcoded map names

Generates a detailed report of what's missing per scenario and suggests
appropriate constraints based on scenario name/type patterns.
"""

import json
import os
import glob
from typing import Dict, List, Any, Set, Optional
from pathlib import Path
import re

class ConstraintAuditor:
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.audit_results = {}
        self.hardcoded_maps = []
        self.missing_constraints = {}
        self.scenario_patterns = {
            # Following scenarios - same road, same lane
            'following': ['following', 'slow_lead', 'lead_vehicle'],
            
            # Cut-in scenarios - same road, adjacent lane
            'cut_in': ['cut_in', 'lane_change', 'merge'],
            
            # Overtaking scenarios - same road, adjacent lane
            'overtake': ['overtake', 'pass'],
            
            # Intersection scenarios - different road
            'intersection': ['intersection', 'cross_traffic', 'chaos'],
            
            # Opposite traffic - same road, opposite lane
            'oncoming': ['oncoming', 'head_on', 'opposite'],
            
            # Stationary scenarios - same road, same/adjacent lane
            'stationary': ['parked', 'obstacle', 'broken_down', 'construction'],
            
            # Emergency scenarios - various relationships
            'emergency': ['emergency', 'ambulance', 'fire_truck', 'police'],
            
            # Pedestrian scenarios - sidewalk lane type
            'pedestrian': ['pedestrian', 'crossing', 'child', 'elderly', 'jogger']
        }
        
    def find_all_scenario_files(self) -> List[Path]:
        """Find all scenario JSON files in the directory structure"""
        scenario_files = []
        
        # Define directories to search
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
            
        # Also search root directory for scenario files
        root_pattern = str(self.base_dir / "*.json")
        root_files = glob.glob(root_pattern)
        
        # Filter out non-scenario files (road intelligence, spawn files, etc.)
        scenario_files.extend([
            Path(f) for f in root_files 
            if not any(exclude in f.lower() for exclude in [
                'road_intelligence', 'spawn', 'network_analysis', 
                'enhanced_town', 'carla-scenarios-dataset'
            ])
        ])
        
        return list(set(scenario_files))  # Remove duplicates
    
    def classify_scenario_type(self, scenario_name: str, description: str = "") -> List[str]:
        """Classify scenario based on name and description patterns"""
        name_lower = scenario_name.lower()
        desc_lower = description.lower()
        combined = f"{name_lower} {desc_lower}"
        
        types = []
        for scenario_type, patterns in self.scenario_patterns.items():
            if any(pattern in combined for pattern in patterns):
                types.append(scenario_type)
                
        return types if types else ['unknown']
    
    def get_expected_constraints(self, scenario_types: List[str], actor_data: Dict) -> Dict[str, Any]:
        """Get expected constraints based on scenario type"""
        constraints = {}
        
        # Handle multiple types - prioritize most specific
        primary_type = scenario_types[0] if scenario_types else 'unknown'
        
        if primary_type == 'following':
            constraints = {
                'road_relationship': 'same_road',
                'lane_relationship': 'same_lane',
                'relative_position': 'ahead'
            }
        elif primary_type == 'cut_in':
            constraints = {
                'road_relationship': 'same_road', 
                'lane_relationship': 'adjacent_lane',
                'relative_position': 'ahead'
            }
        elif primary_type == 'overtake':
            constraints = {
                'road_relationship': 'same_road',
                'lane_relationship': 'adjacent_lane',
                'relative_position': 'behind'
            }
        elif primary_type == 'intersection':
            constraints = {
                'road_relationship': 'different_road',
                'lane_relationship': 'any',
                'is_intersection': True
            }
        elif primary_type == 'oncoming':
            constraints = {
                'road_relationship': 'same_road',
                'lane_relationship': 'opposite_lane',
                'relative_position': 'ahead',
                'heading_tol': 180
            }
        elif primary_type == 'stationary':
            constraints = {
                'road_relationship': 'same_road',
                'lane_relationship': 'same_lane',  # or adjacent_lane
                'relative_position': 'ahead'
            }
        elif primary_type == 'pedestrian':
            constraints = {
                'road_relationship': 'same_road',
                'lane_type': 'Sidewalk'  # NOT Driving
            }
        elif primary_type == 'emergency':
            # Emergency vehicles can be anywhere
            constraints = {
                'road_relationship': 'any_road',
                'lane_relationship': 'any'
            }
        
        # Handle vehicle vs pedestrian actors
        if actor_data.get('type') == 'pedestrian':
            constraints['lane_type'] = 'Sidewalk'
        elif actor_data.get('type') == 'vehicle' and 'lane_type' not in constraints:
            constraints['lane_type'] = 'Driving'
            
        return constraints
    
    def audit_scenario_file(self, file_path: Path) -> Dict[str, Any]:
        """Audit a single scenario file for missing constraints"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            return {'error': f"Failed to load file: {e}"}
            
        audit = {
            'file': str(file_path.relative_to(self.base_dir)),
            'scenario_name': data.get('scenario_name', 'unknown'),
            'description': data.get('description', ''),
            'has_hardcoded_map': 'map_name' in data,
            'hardcoded_map': data.get('map_name'),
            'actors': [],
            'issues': [],
            'recommendations': []
        }
        
        # Track hardcoded maps
        if audit['has_hardcoded_map']:
            self.hardcoded_maps.append({
                'file': audit['file'],
                'map_name': audit['hardcoded_map']
            })
            audit['issues'].append(f"Hardcoded map name: {audit['hardcoded_map']}")
            audit['recommendations'].append("Remove 'map_name' field to enable intelligent map selection")
        
        # Classify scenario type
        scenario_types = self.classify_scenario_type(
            audit['scenario_name'], 
            audit['description']
        )
        audit['detected_types'] = scenario_types
        
        # Audit each actor
        actors = data.get('actors', [])
        for i, actor in enumerate(actors):
            actor_audit = self.audit_actor_constraints(actor, scenario_types, i)
            audit['actors'].append(actor_audit)
            
            # Collect issues and recommendations
            audit['issues'].extend(actor_audit['issues'])
            audit['recommendations'].extend(actor_audit['recommendations'])
        
        # Check success conditions
        if 'success_distance' not in data:
            audit['issues'].append("Missing 'success_distance' field")
            audit['recommendations'].append("Add appropriate success_distance based on scenario complexity")
            
        if 'timeout' not in data:
            audit['issues'].append("Missing 'timeout' field") 
            audit['recommendations'].append("Add reasonable timeout (60-120s based on scenario)")
            
        return audit
    
    def audit_actor_constraints(self, actor: Dict, scenario_types: List[str], actor_index: int) -> Dict[str, Any]:
        """Audit constraints for a single actor"""
        actor_audit = {
            'id': actor.get('id', f'actor_{actor_index}'),
            'type': actor.get('type', 'unknown'),
            'missing_constraints': [],
            'invalid_constraints': [],
            'issues': [],
            'recommendations': [],
            'current_constraints': {},
            'expected_constraints': {}
        }
        
        spawn_criteria = actor.get('spawn', {}).get('criteria', {})
        actor_audit['current_constraints'] = spawn_criteria.copy()
        
        # Get expected constraints for this actor type and scenario
        expected = self.get_expected_constraints(scenario_types, actor)
        actor_audit['expected_constraints'] = expected
        
        # Check for missing critical constraints
        critical_constraints = ['road_relationship', 'lane_relationship']
        
        for constraint in critical_constraints:
            if constraint not in spawn_criteria:
                if constraint in expected:
                    actor_audit['missing_constraints'].append(constraint)
                    actor_audit['issues'].append(f"Actor '{actor_audit['id']}' missing {constraint}")
                    actor_audit['recommendations'].append(
                        f"Add '{constraint}': '{expected[constraint]}' to actor '{actor_audit['id']}'"
                    )
        
        # Check lane_type appropriateness
        current_lane_type = spawn_criteria.get('lane_type')
        expected_lane_type = expected.get('lane_type')
        
        if expected_lane_type and current_lane_type != expected_lane_type:
            issue = f"Actor '{actor_audit['id']}' has lane_type '{current_lane_type}' but expected '{expected_lane_type}'"
            actor_audit['issues'].append(issue)
            actor_audit['recommendations'].append(f"Change lane_type to '{expected_lane_type}' for {actor_audit['type']} actor")
        
        # Check for intersection scenarios missing is_intersection flag
        if 'intersection' in scenario_types and 'is_intersection' not in spawn_criteria:
            if expected.get('is_intersection'):
                actor_audit['missing_constraints'].append('is_intersection')
                actor_audit['issues'].append(f"Intersection scenario missing 'is_intersection: true' for actor '{actor_audit['id']}'")
                actor_audit['recommendations'].append("Add 'is_intersection: true' to spawn criteria")
        
        # Check for old-style constraints that need updating
        old_constraints = ['road_id']
        for old_constraint in old_constraints:
            if old_constraint in spawn_criteria:
                actor_audit['issues'].append(f"Actor '{actor_audit['id']}' uses deprecated constraint '{old_constraint}'")
                if old_constraint == 'road_id' and spawn_criteria[old_constraint] == 'same_as_ego':
                    actor_audit['recommendations'].append("Replace 'road_id': 'same_as_ego' with 'road_relationship': 'same_road'")
        
        return actor_audit
    
    def run_audit(self) -> Dict[str, Any]:
        """Run the complete audit across all scenario files"""
        print("🔍 Starting comprehensive scenario constraint audit...")
        
        scenario_files = self.find_all_scenario_files()
        print(f"Found {len(scenario_files)} scenario files to audit")
        
        all_audits = []
        total_issues = 0
        files_with_hardcoded_maps = 0
        files_with_missing_constraints = 0
        
        for file_path in scenario_files:
            print(f"  Auditing: {file_path.relative_to(self.base_dir)}")
            audit = self.audit_scenario_file(file_path)
            all_audits.append(audit)
            
            if audit.get('has_hardcoded_map'):
                files_with_hardcoded_maps += 1
                
            if audit.get('issues'):
                total_issues += len(audit['issues'])
                files_with_missing_constraints += 1
        
        # Generate summary
        summary = {
            'total_files': len(scenario_files),
            'files_with_issues': files_with_missing_constraints,
            'files_with_hardcoded_maps': files_with_hardcoded_maps,
            'total_issues': total_issues,
            'hardcoded_maps': self.hardcoded_maps
        }
        
        return {
            'summary': summary,
            'audits': all_audits,
            'timestamp': str(Path(__file__).stat().st_mtime)
        }
    
    def generate_report(self, audit_results: Dict[str, Any], output_file: str = "constraint_audit_report.json"):
        """Generate and save detailed audit report"""
        
        # Save full JSON report
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(audit_results, f, indent=2, ensure_ascii=False)
        
        # Generate human-readable summary
        summary_file = output_file.replace('.json', '_summary.txt')
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            summary = audit_results['summary']
            
            f.write("=" * 60 + "\n")
            f.write("CARLA SCENARIO CONSTRAINT AUDIT REPORT\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"📊 SUMMARY:\n")
            f.write(f"  Total scenario files scanned: {summary['total_files']}\n")
            f.write(f"  Files with constraint issues: {summary['files_with_issues']}\n")
            f.write(f"  Files with hardcoded map names: {summary['files_with_hardcoded_maps']}\n")
            f.write(f"  Total issues found: {summary['total_issues']}\n\n")
            
            if summary['files_with_hardcoded_maps'] > 0:
                f.write("🗺️  HARDCODED MAP NAMES:\n")
                for item in summary['hardcoded_maps']:
                    f.write(f"  - {item['file']}: {item['map_name']}\n")
                f.write("\n")
            
            f.write("🔧 ISSUES BY SCENARIO:\n")
            f.write("-" * 40 + "\n")
            
            for audit in audit_results['audits']:
                if audit.get('issues'):
                    f.write(f"\n📁 {audit['file']}\n")
                    f.write(f"   Scenario: {audit['scenario_name']}\n")
                    f.write(f"   Types: {', '.join(audit['detected_types'])}\n")
                    
                    for issue in audit['issues']:
                        f.write(f"   ❌ {issue}\n")
                    
                    f.write("   💡 Recommendations:\n")
                    for rec in audit['recommendations']:
                        f.write(f"      • {rec}\n")
        
        print(f"\n✅ Audit complete!")
        print(f"📄 Full report: {output_file}")
        print(f"📋 Summary report: {summary_file}")
        
        return audit_results

def main():
    auditor = ConstraintAuditor()
    results = auditor.run_audit()
    auditor.generate_report(results)
    
    # Print quick summary to console
    summary = results['summary']
    print(f"\n🎯 Quick Summary:")
    print(f"   Files with hardcoded maps: {summary['files_with_hardcoded_maps']}")
    print(f"   Files needing constraint fixes: {summary['files_with_issues']}")
    print(f"   Total issues to address: {summary['total_issues']}")

if __name__ == "__main__":
    main()