#!/usr/bin/env python3
"""
Spawn Point Availability Analyzer

Analyzes spawn point distribution across all maps to identify:
- Spawn point density per lane
- Adjacent lane availability
- Direction-specific spawn coverage
- Distance distributions
- Missing spawn point gaps

This helps diagnose why constraint matching is failing.
"""

import json
import numpy as np
from pathlib import Path
from collections import defaultdict, Counter
import matplotlib.pyplot as plt
from typing import Dict, List, Any, Tuple
import pandas as pd

class SpawnPointAnalyzer:
    def __init__(self, spawns_dir: str = "spawns"):
        self.spawns_dir = Path(spawns_dir)
        self.maps_data = {}
        self.analysis_results = {}
        
    def load_spawn_data(self):
        """Load all enhanced spawn point files"""
        spawn_files = list(self.spawns_dir.glob("enhanced_*.json"))
        
        for spawn_file in spawn_files:
            map_name = spawn_file.stem.replace("enhanced_", "")
            try:
                with open(spawn_file, 'r') as f:
                    data = json.load(f)
                    
                    # Handle different data structures
                    spawn_points = []
                    if isinstance(data, dict):
                        for map_key, map_data in data.items():
                            if isinstance(map_data, dict):
                                for lane_type, points in map_data.items():
                                    if isinstance(points, list):
                                        spawn_points.extend(points)
                    
                    self.maps_data[map_name] = {'spawn_points': spawn_points}
                    print(f"✅ Loaded {len(spawn_points)} spawn points for {map_name}")
            except Exception as e:
                print(f"❌ Failed to load {spawn_file}: {e}")
    
    def analyze_map_spawn_distribution(self, map_name: str) -> Dict[str, Any]:
        """Analyze spawn point distribution for a single map"""
        if map_name not in self.maps_data:
            return {"error": f"Map {map_name} not loaded"}
        
        spawn_points = self.maps_data[map_name].get('spawn_points', [])
        
        analysis = {
            'map_name': map_name,
            'total_spawn_points': len(spawn_points),
            'roads': defaultdict(lambda: {
                'lanes': defaultdict(list),
                'lane_types': defaultdict(int),
                'total_points': 0
            }),
            'lane_type_distribution': defaultdict(int),
            'direction_distribution': {'positive_lanes': 0, 'negative_lanes': 0},
            'critical_issues': []
        }
        
        # Group spawn points by road and lane
        for i, spawn in enumerate(spawn_points):
            road_id = spawn.get('road_id')
            lane_id = spawn.get('lane_id')
            lane_type = spawn.get('lane_type', 'Unknown')
            
            if road_id is None or lane_id is None:
                continue
                
            analysis['roads'][road_id]['lanes'][lane_id].append({
                'index': i,
                'x': spawn.get('x', 0),
                'y': spawn.get('y', 0), 
                'z': spawn.get('z', 0),
                'yaw': spawn.get('yaw', 0),
                'lane_type': lane_type
            })
            
            analysis['roads'][road_id]['lane_types'][lane_type] += 1
            analysis['roads'][road_id]['total_points'] += 1
            analysis['lane_type_distribution'][lane_type] += 1
            
            # Track lane direction (positive vs negative lane IDs)
            if lane_id > 0:
                analysis['direction_distribution']['positive_lanes'] += 1
            else:
                analysis['direction_distribution']['negative_lanes'] += 1
        
        # Analyze each road for issues
        for road_id, road_data in analysis['roads'].items():
            road_analysis = self._analyze_road_spawn_coverage(road_id, road_data)
            analysis['roads'][road_id].update(road_analysis)
            
            # Collect critical issues
            if road_analysis.get('issues'):
                analysis['critical_issues'].extend([
                    f"Road {road_id}: {issue}" for issue in road_analysis['issues']
                ])
        
        return analysis
    
    def _analyze_road_spawn_coverage(self, road_id: int, road_data: Dict) -> Dict[str, Any]:
        """Analyze spawn coverage for a single road"""
        lanes = road_data['lanes']
        analysis = {
            'lane_count': len(lanes),
            'has_positive_lanes': any(lid > 0 for lid in lanes.keys()),
            'has_negative_lanes': any(lid < 0 for lid in lanes.keys()),
            'adjacent_lanes_available': False,
            'same_direction_options': {},
            'opposite_direction_options': {},
            'issues': [],
            'lane_details': {}
        }
        
        # Check for adjacent lanes and direction options
        sorted_lanes = sorted(lanes.keys())
        
        for i, lane_id in enumerate(sorted_lanes):
            lane_spawns = lanes[lane_id]
            lane_detail = {
                'spawn_count': len(lane_spawns),
                'lane_type': lane_spawns[0]['lane_type'] if lane_spawns else 'Unknown',
                'has_adjacent_left': i > 0,
                'has_adjacent_right': i < len(sorted_lanes) - 1,
                'adjacent_lanes': []
            }
            
            # Check for truly adjacent lanes (consecutive lane IDs)
            if i > 0:
                left_lane = sorted_lanes[i-1]
                if abs(lane_id - left_lane) == 1:
                    lane_detail['adjacent_lanes'].append(left_lane)
                    analysis['adjacent_lanes_available'] = True
                    
            if i < len(sorted_lanes) - 1:
                right_lane = sorted_lanes[i+1]
                if abs(lane_id - right_lane) == 1:
                    lane_detail['adjacent_lanes'].append(right_lane)
                    analysis['adjacent_lanes_available'] = True
            
            # Group by direction
            if lane_id > 0:
                analysis['same_direction_options'][lane_id] = len(lane_spawns)
            else:
                analysis['opposite_direction_options'][lane_id] = len(lane_spawns)
            
            analysis['lane_details'][lane_id] = lane_detail
            
            # Check for issues
            if len(lane_spawns) == 0:
                analysis['issues'].append(f"Lane {lane_id} has no spawn points")
            elif len(lane_spawns) < 3:
                analysis['issues'].append(f"Lane {lane_id} has very few spawn points ({len(lane_spawns)})")
        
        # Check for common constraint matching issues
        if not analysis['adjacent_lanes_available']:
            analysis['issues'].append("No adjacent lanes available for lane_change scenarios")
            
        if len(analysis['same_direction_options']) <= 1:
            analysis['issues'].append("Limited same-direction lane options")
            
        return analysis
    
    def find_constraint_violations(self, map_name: str) -> Dict[str, List[str]]:
        """Find common scenarios that would fail constraint matching"""
        if map_name not in self.analysis_results:
            return {"error": "Map not analyzed"}
        
        analysis = self.analysis_results[map_name]
        violations = {
            'same_lane_impossible': [],
            'adjacent_lane_impossible': [],
            'insufficient_spawn_density': [],
            'lane_type_mismatches': []
        }
        
        for road_id, road_data in analysis['roads'].items():
            for lane_id, lane_detail in road_data.get('lane_details', {}).items():
                # Check same_lane constraint feasibility
                if lane_detail['spawn_count'] < 2:
                    violations['same_lane_impossible'].append(f"Road {road_id}, Lane {lane_id}")
                
                # Check adjacent_lane constraint feasibility
                if not lane_detail['adjacent_lanes']:
                    violations['adjacent_lane_impossible'].append(f"Road {road_id}, Lane {lane_id}")
                
                # Check spawn density
                if lane_detail['spawn_count'] < 5 and lane_detail['lane_type'] == 'Driving':
                    violations['insufficient_spawn_density'].append(
                        f"Road {road_id}, Lane {lane_id} ({lane_detail['spawn_count']} points)"
                    )
        
        return violations
    
    def calculate_spawn_distances(self, map_name: str, road_id: int, lane_id: int) -> Dict[str, Any]:
        """Calculate distances between spawn points on a specific lane"""
        if map_name not in self.maps_data:
            return {"error": "Map not loaded"}
        
        spawn_points = self.maps_data[map_name]['spawn_points']
        lane_spawns = []
        
        for spawn in spawn_points:
            if spawn.get('road_id') == road_id and spawn.get('lane_id') == lane_id:
                lane_spawns.append(spawn)
        
        if len(lane_spawns) < 2:
            return {"error": f"Not enough spawn points on road {road_id}, lane {lane_id}"}
        
        # Sort by position along the road
        lane_spawns.sort(key=lambda s: (s.get('x', 0)**2 + s.get('y', 0)**2)**0.5)
        
        distances = []
        for i in range(len(lane_spawns) - 1):
            p1 = lane_spawns[i]
            p2 = lane_spawns[i + 1]
            
            dist = ((p2['x'] - p1['x'])**2 + (p2['y'] - p1['y'])**2)**0.5
            distances.append(dist)
        
        return {
            'spawn_count': len(lane_spawns),
            'distances': distances,
            'min_distance': min(distances) if distances else 0,
            'max_distance': max(distances) if distances else 0,
            'avg_distance': np.mean(distances) if distances else 0,
            'gaps_over_50m': len([d for d in distances if d > 50])
        }
    
    def diagnose_scenario_constraint_failures(self, scenario_patterns: Dict[str, Dict]) -> Dict[str, Any]:
        """Diagnose why common scenario constraint patterns fail"""
        diagnosis = {}
        
        for scenario_type, constraints in scenario_patterns.items():
            diagnosis[scenario_type] = {
                'constraint_set': constraints,
                'failing_maps': [],
                'failure_reasons': [],
                'success_probability': 0
            }
            
            total_maps = 0
            successful_maps = 0
            
            for map_name, analysis in self.analysis_results.items():
                total_maps += 1
                can_satisfy = True
                reasons = []
                
                # Check if constraints can be satisfied
                if constraints.get('lane_relationship') == 'same_lane':
                    # Check if any road has multiple spawn points in same lane
                    same_lane_possible = False
                    for road_data in analysis['roads'].values():
                        for lane_detail in road_data.get('lane_details', {}).values():
                            if lane_detail['spawn_count'] >= 2:
                                same_lane_possible = True
                                break
                        if same_lane_possible:
                            break
                    
                    if not same_lane_possible:
                        can_satisfy = False
                        reasons.append("No lanes with multiple spawn points for same_lane constraint")
                
                elif constraints.get('lane_relationship') == 'adjacent_lane':
                    # Check if any road has adjacent lanes
                    adjacent_possible = False
                    for road_data in analysis['roads'].values():
                        if road_data.get('adjacent_lanes_available'):
                            adjacent_possible = True
                            break
                    
                    if not adjacent_possible:
                        can_satisfy = False
                        reasons.append("No adjacent lanes available for adjacent_lane constraint")
                
                if constraints.get('road_relationship') == 'different_road':
                    # Check if map has multiple roads
                    if len(analysis['roads']) < 2:
                        can_satisfy = False
                        reasons.append("Map has insufficient roads for different_road constraint")
                
                if can_satisfy:
                    successful_maps += 1
                else:
                    diagnosis[scenario_type]['failing_maps'].append(map_name)
                    diagnosis[scenario_type]['failure_reasons'].extend(reasons)
            
            diagnosis[scenario_type]['success_probability'] = successful_maps / total_maps if total_maps > 0 else 0
        
        return diagnosis
    
    def generate_detailed_report(self, output_file: str = "spawn_analysis_report.json"):
        """Generate comprehensive analysis report"""
        report = {
            'analysis_summary': {
                'maps_analyzed': len(self.analysis_results),
                'total_spawn_points': sum(r['total_spawn_points'] for r in self.analysis_results.values()),
                'critical_issues_count': sum(len(r['critical_issues']) for r in self.analysis_results.values())
            },
            'map_analyses': self.analysis_results,
            'constraint_violations': {},
            'scenario_diagnosis': {},
            'recommendations': []
        }
        
        # Analyze constraint violations for each map
        for map_name in self.analysis_results:
            report['constraint_violations'][map_name] = self.find_constraint_violations(map_name)
        
        # Diagnose common scenario patterns
        common_patterns = {
            'following': {
                'road_relationship': 'same_road',
                'lane_relationship': 'same_lane'
            },
            'cut_in': {
                'road_relationship': 'same_road', 
                'lane_relationship': 'adjacent_lane'
            },
            'intersection': {
                'road_relationship': 'different_road',
                'is_intersection': True
            }
        }
        
        report['scenario_diagnosis'] = self.diagnose_scenario_constraint_failures(common_patterns)
        
        # Generate recommendations
        recommendations = []
        
        for map_name, violations in report['constraint_violations'].items():
            if violations.get('same_lane_impossible'):
                recommendations.append(f"Add more spawn points to lanes in {map_name} for same_lane scenarios")
            
            if violations.get('adjacent_lane_impossible'):
                recommendations.append(f"Add adjacent lane spawn points in {map_name} for lane_change scenarios")
            
            if violations.get('insufficient_spawn_density'):
                recommendations.append(f"Increase spawn point density on driving lanes in {map_name}")
        
        report['recommendations'] = list(set(recommendations))
        
        # Save report
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Generate human-readable summary
        summary_file = output_file.replace('.json', '_summary.txt')
        self._generate_summary_report(report, summary_file)
        
        return report
    
    def _generate_summary_report(self, report: Dict, output_file: str):
        """Generate human-readable summary"""
        with open(output_file, 'w') as f:
            f.write("="*60 + "\n")
            f.write("SPAWN POINT AVAILABILITY ANALYSIS REPORT\n") 
            f.write("="*60 + "\n\n")
            
            summary = report['analysis_summary']
            f.write(f"📊 OVERVIEW:\n")
            f.write(f"  Maps analyzed: {summary['maps_analyzed']}\n")
            f.write(f"  Total spawn points: {summary['total_spawn_points']:,}\n")
            f.write(f"  Critical issues found: {summary['critical_issues_count']}\n\n")
            
            # Map-by-map analysis
            f.write("🗺️  MAP ANALYSIS:\n")
            f.write("-" * 40 + "\n")
            
            for map_name, analysis in report['map_analyses'].items():
                f.write(f"\n{map_name.upper()}:\n")
                f.write(f"  Spawn points: {analysis['total_spawn_points']:,}\n")
                f.write(f"  Roads: {len(analysis['roads'])}\n")
                f.write(f"  Lane types: {dict(analysis['lane_type_distribution'])}\n")
                
                if analysis['critical_issues']:
                    f.write(f"  ⚠️  Critical issues:\n")
                    for issue in analysis['critical_issues'][:5]:  # Show top 5
                        f.write(f"    • {issue}\n")
                    if len(analysis['critical_issues']) > 5:
                        f.write(f"    • ... and {len(analysis['critical_issues']) - 5} more\n")
            
            # Scenario diagnosis
            f.write(f"\n🎯 SCENARIO CONSTRAINT DIAGNOSIS:\n")
            f.write("-" * 40 + "\n")
            
            for scenario_type, diagnosis in report['scenario_diagnosis'].items():
                success_rate = diagnosis['success_probability'] * 100
                f.write(f"\n{scenario_type.upper()} scenarios:\n")
                f.write(f"  Success probability: {success_rate:.1f}%\n")
                f.write(f"  Constraints: {diagnosis['constraint_set']}\n")
                
                if diagnosis['failing_maps']:
                    f.write(f"  Failing on: {', '.join(diagnosis['failing_maps'])}\n")
                
                if diagnosis['failure_reasons']:
                    f.write(f"  Common failures:\n")
                    for reason in list(set(diagnosis['failure_reasons']))[:3]:
                        f.write(f"    • {reason}\n")
            
            # Recommendations
            f.write(f"\n💡 RECOMMENDATIONS:\n")
            f.write("-" * 40 + "\n")
            
            for i, rec in enumerate(report['recommendations'], 1):
                f.write(f"{i}. {rec}\n")
            
        print(f"📄 Analysis report saved: {output_file}")
    
    def run_complete_analysis(self):
        """Run complete spawn point analysis"""
        print("🔍 Starting comprehensive spawn point analysis...")
        
        # Load all spawn data
        self.load_spawn_data()
        
        # Analyze each map
        for map_name in self.maps_data:
            print(f"  Analyzing {map_name}...")
            self.analysis_results[map_name] = self.analyze_map_spawn_distribution(map_name)
        
        # Generate comprehensive report
        report = self.generate_detailed_report()
        
        print(f"\n✅ Analysis complete!")
        print(f"📊 Found {report['analysis_summary']['critical_issues_count']} critical issues")
        print(f"💾 Reports saved: spawn_analysis_report.json and _summary.txt")
        
        return report

def main():
    analyzer = SpawnPointAnalyzer()
    report = analyzer.run_complete_analysis()
    
    # Print quick summary
    print(f"\n🎯 Quick Summary:")
    for scenario_type, diagnosis in report['scenario_diagnosis'].items():
        success_rate = diagnosis['success_probability'] * 100
        print(f"  {scenario_type}: {success_rate:.1f}% success rate")

if __name__ == "__main__":
    main()