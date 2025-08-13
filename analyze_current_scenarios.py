#!/usr/bin/env python3
"""Analyze current scenarios to understand what needs to be rebuilt"""

import os
import json
import glob
from collections import defaultdict

def analyze_scenarios():
    """Analyze all JSON scenarios to understand patterns and issues"""
    
    json_files = glob.glob("generated_scenarios/*.json")
    
    # Analysis data
    scenario_types = defaultdict(int)
    actor_counts = defaultdict(int)
    vehicle_models = defaultdict(int)
    issues = defaultdict(int)
    
    print(f"Analyzing {len(json_files)} scenarios...")
    
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            # Extract scenario type from filename
            filename = os.path.basename(json_file)
            scenario_category = filename.split('_')[0]
            scenario_types[scenario_category] += 1
            
            # Count actors
            actor_count = len(data.get('actors', []))
            actor_counts[actor_count] += 1
            
            # Check for issues
            for actor in data.get('actors', []):
                model = actor.get('model', '')
                vehicle_models[model] += 1
                
                # Check for problematic models
                if any(bike in model.lower() for bike in ['crossbike', 'bicycle', 'ninja', 'harley', 'vespa']):
                    issues['bicycle_in_vehicle_scenario'] += 1
                
                # Check spawn criteria
                if 'spawn' in actor:
                    criteria = actor['spawn'].get('criteria', {})
                    
                    # Check distance constraints
                    if 'distance_to_ego' in criteria:
                        dist = criteria['distance_to_ego']
                        if isinstance(dist, dict):
                            min_dist = dist.get('min', 0)
                            max_dist = dist.get('max', 100)
                            if min_dist < 10:
                                issues['too_close_spawn'] += 1
                            if max_dist > 200:
                                issues['too_far_spawn'] += 1
            
            # Check actions
            for action in data.get('actions', []):
                if action.get('action_type') == 'lane_change':
                    # Check if actor doing lane change is appropriate
                    actor_id = action.get('actor_id')
                    actor = next((a for a in data.get('actors', []) if a['id'] == actor_id), None)
                    if actor and any(bike in actor.get('model', '').lower() for bike in ['crossbike', 'bicycle']):
                        issues['bicycle_lane_change'] += 1
        
        except Exception as e:
            issues['json_parse_error'] += 1
    
    # Print analysis results
    print("\n" + "="*60)
    print("SCENARIO ANALYSIS RESULTS")
    print("="*60)
    
    print(f"\n📊 Scenario Categories:")
    for category, count in sorted(scenario_types.items()):
        print(f"  {category}: {count}")
    
    print(f"\n👥 Actor Counts:")
    for count, scenarios in sorted(actor_counts.items()):
        print(f"  {count} actors: {scenarios} scenarios")
    
    print(f"\n🚗 Most Common Vehicle Models:")
    top_models = sorted(vehicle_models.items(), key=lambda x: x[1], reverse=True)[:10]
    for model, count in top_models:
        print(f"  {model}: {count}")
    
    print(f"\n⚠️  Issues Found:")
    for issue, count in sorted(issues.items()):
        print(f"  {issue}: {count}")
    
    print(f"\n📈 Summary:")
    print(f"  Total scenarios: {len(json_files)}")
    print(f"  Categories: {len(scenario_types)}")
    print(f"  Total issues: {sum(issues.values())}")
    print(f"  Issue rate: {sum(issues.values())/len(json_files)*100:.1f}%")
    
    return {
        'scenario_types': dict(scenario_types),
        'actor_counts': dict(actor_counts),
        'vehicle_models': dict(vehicle_models),
        'issues': dict(issues),
        'total_scenarios': len(json_files)
    }

if __name__ == '__main__':
    analysis = analyze_scenarios()