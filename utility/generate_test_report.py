#!/usr/bin/env python3
"""
Test Report Generator - Run scenarios and generate detailed spawn reports
"""

import json
import subprocess
import sys
import re
import os
from typing import Dict, List, Any, Optional
import math

class ScenarioTestReporter:
    def __init__(self):
        self.test_results = []
    
    def parse_spawn_output(self, output: str) -> Dict[str, Any]:
        """Parse spawn summary from xosc_json.py output"""
        spawn_data = {
            'ego': {},
            'actors': [],
            'issues': []
        }
        
        # Look for spawn summary section
        if "=== SPAWN SUMMARY ===" in output:
            lines = output.split('\n')
            current_actor = None
            parsing_ego = False
            parsing_actor = False
            
            for line in lines:
                line = line.strip()
                
                if line == "=== SPAWN SUMMARY ===":
                    continue
                elif line.startswith("EGO Position:"):
                    parsing_ego = True
                    current_actor = 'ego'
                elif line.endswith(" Position:") and "EGO" not in line:
                    parsing_ego = False
                    parsing_actor = True
                    current_actor = line.replace(" Position:", "")
                    spawn_data['actors'].append({
                        'name': current_actor,
                        'spawn': {},
                        'issues': []
                    })
                elif line.startswith("Issues:"):
                    issues = line.replace("Issues:", "").strip()
                    if current_actor == 'ego':
                        spawn_data['issues'].extend(issues.split(', '))
                    else:
                        for actor in spawn_data['actors']:
                            if actor['name'] == current_actor:
                                actor['issues'].extend(issues.split(', '))
                elif line.startswith("Road:"):
                    match = re.search(r"Road: (\w+), Lane: (\w+)", line)
                    if match:
                        road_id, lane_id = match.groups()
                        if parsing_ego:
                            spawn_data['ego']['road_id'] = road_id
                            spawn_data['ego']['lane_id'] = lane_id
                        elif parsing_actor:
                            for actor in spawn_data['actors']:
                                if actor['name'] == current_actor:
                                    actor['spawn']['road_id'] = road_id
                                    actor['spawn']['lane_id'] = lane_id
                elif line.startswith("Coordinates:"):
                    match = re.search(r"x=([-\d.]+), y=([-\d.]+)", line)
                    if match:
                        x, y = match.groups()
                        if parsing_ego:
                            spawn_data['ego']['x'] = float(x)
                            spawn_data['ego']['y'] = float(y)
                        elif parsing_actor:
                            for actor in spawn_data['actors']:
                                if actor['name'] == current_actor:
                                    actor['spawn']['x'] = float(x)
                                    actor['spawn']['y'] = float(y)
                elif line.startswith("Distance from ego:"):
                    match = re.search(r"Distance from ego: ([\d.]+)m", line)
                    if match and parsing_actor:
                        distance = float(match.group(1))
                        for actor in spawn_data['actors']:
                            if actor['name'] == current_actor:
                                actor['distance_from_ego'] = distance
                elif line.startswith("Relative position:"):
                    rel_pos = line.replace("Relative position:", "").strip()
                    if parsing_actor:
                        for actor in spawn_data['actors']:
                            if actor['name'] == current_actor:
                                actor['relative_position'] = rel_pos
        
        return spawn_data
    
    def test_scenario_and_report(self, scenario_file: str) -> Dict[str, Any]:
        """Run scenario and generate detailed report"""
        print(f"\nTesting scenario: {os.path.basename(scenario_file)}")
        
        try:
            # Convert to XOSC with debug logging
            result = subprocess.run([
                'python', 'xosc_json.py', scenario_file,
                '-o', 'temp_test.xosc', '--log-level', 'INFO'
            ], capture_output=True, text=True)
            
            # Parse spawn information
            spawn_data = self.parse_spawn_output(result.stdout)
            
            # Load original scenario for analysis
            with open(scenario_file, 'r') as f:
                scenario_json = json.load(f)
            
            report = {
                'scenario': os.path.basename(scenario_file),
                'scenario_type': self._detect_scenario_type(scenario_json),
                'success': result.returncode == 0,
                'ego_spawn': spawn_data.get('ego', {}),
                'actor_spawns': spawn_data.get('actors', []),
                'spawn_issues': [],
                'conversion_output': result.stdout,
                'errors': result.stderr
            }
            
            # Analyze spawn issues
            report['spawn_issues'] = self._analyze_spawn_issues(report, scenario_json)
            
            return report
            
        except Exception as e:
            return {
                'scenario': os.path.basename(scenario_file),
                'success': False,
                'error': str(e),
                'spawn_issues': [f"Failed to run scenario: {e}"]
            }
    
    def _detect_scenario_type(self, scenario_json: Dict) -> str:
        """Detect scenario type from JSON"""
        name = scenario_json.get('scenario_name', '').lower()
        desc = scenario_json.get('description', '').lower()
        
        if 'cut_in' in name or 'lane_change' in name:
            return 'cut_in'
        elif 'intersection' in name or 'chaos' in name:
            return 'intersection'
        elif 'pedestrian' in name or 'crossing' in name:
            return 'pedestrian'
        elif 'following' in name or 'brake' in name:
            return 'following'
        else:
            return 'general'
    
    def _analyze_spawn_issues(self, report: Dict, scenario_json: Dict) -> List[str]:
        """Analyze spawn data for issues"""
        issues = []
        scenario_type = report['scenario_type']
        ego_spawn = report['ego_spawn']
        actor_spawns = report['actor_spawns']
        
        # Check for common issues based on scenario type
        if scenario_type == 'cut_in':
            for actor in actor_spawns:
                # Cut-in actors should be in adjacent lane, not same lane
                if (actor['spawn'].get('road_id') == ego_spawn.get('road_id') and 
                    actor['spawn'].get('lane_id') == ego_spawn.get('lane_id')):
                    issues.append(f"[ERROR] Cut-in actor {actor['name']} in same lane as ego")
                
                # Cut-in actors should be ahead, not behind or alongside
                if actor.get('distance_from_ego', 0) < 10:
                    issues.append(f"[ERROR] Cut-in actor {actor['name']} too close ({actor.get('distance_from_ego', 0):.1f}m)")
                
                if actor.get('relative_position') != 'ahead':
                    issues.append(f"[WARNING] Cut-in actor {actor['name']} not ahead (position: {actor.get('relative_position', 'unknown')})")
        
        elif scenario_type == 'pedestrian':
            for actor in actor_spawns:
                if actor.get('distance_from_ego', 0) > 100:
                    issues.append(f"[ERROR] Pedestrian {actor['name']} too far ({actor.get('distance_from_ego', 0):.1f}m)")
        
        # General distance checks
        for actor in actor_spawns:
            distance = actor.get('distance_from_ego', 0)
            if distance < 3:
                issues.append(f"[ERROR] Actor {actor['name']} dangerously close ({distance:.1f}m)")
            elif distance > 300:
                issues.append(f"[ERROR] Actor {actor['name']} extremely far ({distance:.1f}m)")
        
        return issues
    
    def generate_summary_report(self, test_results: List[Dict]) -> str:
        """Generate a summary report of all test results"""
        total_tests = len(test_results)
        successful_tests = len([r for r in test_results if r['success']])
        failed_tests = total_tests - successful_tests
        
        # Count issues by type
        error_count = 0
        warning_count = 0
        
        for result in test_results:
            for issue in result.get('spawn_issues', []):
                if '[ERROR]' in issue:
                    error_count += 1
                elif '[WARNING]' in issue:
                    warning_count += 1
        
        report = f"""
=== SCENARIO TEST SUMMARY REPORT ===

Total scenarios tested: {total_tests}
Successful conversions: {successful_tests}
Failed conversions: {failed_tests}

Spawn Issues Found:
- Errors: {error_count}
- Warnings: {warning_count}

=== DETAILED RESULTS ===

"""
        
        for result in test_results:
            scenario = result['scenario']
            scenario_type = result.get('scenario_type', 'unknown')
            success_status = "✅ SUCCESS" if result['success'] else "❌ FAILED"
            
            report += f"\nScenario: {scenario} ({scenario_type})\n"
            report += f"Status: {success_status}\n"
            
            if result['success']:
                ego = result['ego_spawn']
                report += f"EGO: Road {ego.get('road_id', '?')}, Lane {ego.get('lane_id', '?')}, "
                report += f"({ego.get('x', 0):.2f}, {ego.get('y', 0):.2f})\n"
                
                for actor in result['actor_spawns']:
                    spawn = actor['spawn']
                    distance = actor.get('distance_from_ego', 0)
                    status_icon = "✓" if distance >= 5 else "✗"
                    report += f"Actor {actor['name']}: Road {spawn.get('road_id', '?')}, Lane {spawn.get('lane_id', '?')}, "
                    report += f"({spawn.get('x', 0):.2f}, {spawn.get('y', 0):.2f}) - {distance:.1f}m {actor.get('relative_position', '?')} {status_icon}\n"
            
            # Show issues
            issues = result.get('spawn_issues', [])
            if issues:
                report += "Issues:\n"
                for issue in issues:
                    report += f"  {issue}\n"
            else:
                report += "Issues: None\n"
        
        return report

def main():
    """Test specific problematic scenarios"""
    reporter = ScenarioTestReporter()
    
    # Test scenarios mentioned in the prompt
    test_scenarios = [
        'generated_scenarios/lane_change_071_cut_in_ahead_21.json',  # Cut-in issue
        'generated_scenarios/multi_actor_166_intersection_chaos_01.json',  # Intersection constraint issue
        'generated_scenarios/multi_actor_176_intersection_chaos_11.json',  # Actor reference issue
        'generated_scenarios/pedestrian_crossing_027_sudden_crossing_02.json',  # Pedestrian distance issue
        'generated_scenarios/lane_change_070_cut_in_ahead_20.json'  # Another cut-in test
    ]
    
    results = []
    
    for scenario_file in test_scenarios:
        if os.path.exists(scenario_file):
            result = reporter.test_scenario_and_report(scenario_file)
            results.append(result)
        else:
            print(f"Scenario file not found: {scenario_file}")
    
    # Generate and save report
    summary_report = reporter.generate_summary_report(results)
    
    with open('spawn_test_report.txt', 'w') as f:
        f.write(summary_report)
    
    print("\n" + summary_report)
    print(f"\nDetailed report saved to spawn_test_report.txt")
    
    # Clean up temp file
    if os.path.exists('temp_test.xosc'):
        os.remove('temp_test.xosc')

if __name__ == "__main__":
    main()