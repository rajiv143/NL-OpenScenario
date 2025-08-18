#!/usr/bin/env python3
"""
Following Scenario Test Report
Generate before/after comparison for following scenario fixes
"""
import json
import subprocess
import os
import re
from typing import Dict, List, Tuple

def generate_test_report():
    """Generate comprehensive test report for following scenario fixes"""
    
    test_scenarios = [
        "generated_scenarios/basic_following_010_gradual_slowdown_10.json",
        "generated_scenarios/basic_following_024_sudden_brake_ahead_24.json",
        "generated_scenarios/basic_following_001_sudden_brake_ahead_01.json"
    ]
    
    print(f"{'='*80}")
    print(f"FOLLOWING SCENARIOS FIX VALIDATION REPORT")
    print(f"{'='*80}")
    
    for scenario_path in test_scenarios:
        print(f"\n📋 TESTING: {os.path.basename(scenario_path)}")
        
        # Load scenario data
        with open(scenario_path, 'r') as f:
            data = json.load(f)
        
        # Show JSON fixes applied
        print(f"\n✅ JSON FIXES APPLIED:")
        
        actors = data.get('actors', [])
        for actor in actors:
            if actor.get('type') == 'vehicle':
                spawn_criteria = actor.get('spawn', {}).get('criteria', {})
                lane_rel = spawn_criteria.get('lane_relationship', 'missing')
                print(f"  • Actor '{actor['id']}' lane_relationship: {lane_rel}")
        
        success_distance = data.get('success_distance', 'missing')
        timeout = data.get('timeout', 'missing')
        print(f"  • Success distance: {success_distance}m")
        print(f"  • Timeout: {timeout}s")
        
        # Run conversion test
        print(f"\n🧪 CONVERSION TEST RESULTS:")
        
        try:
            result = subprocess.run([
                'python', 'xosc_json.py', scenario_path, '--log-level', 'INFO'
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print(f"  ✅ Conversion: SUCCESS")
                
                # Parse spawn information
                spawn_info = parse_spawn_logs(result.stderr)
                print(f"  📍 SPAWN ANALYSIS:")
                
                if spawn_info['ego']:
                    ego = spawn_info['ego']
                    print(f"    Ego: road_id={ego['road_id']}, lane_id={ego['lane_id']}")
                
                for actor_info in spawn_info['actors']:
                    name = actor_info['name']
                    road_id = actor_info['road_id']
                    lane_id = actor_info['lane_id']
                    distance = actor_info['distance']
                    
                    # Check if same side of road
                    ego_lane = spawn_info['ego']['lane_id'] if spawn_info['ego'] else None
                    same_side = "✅ Same side" if (ego_lane and lane_id * ego_lane > 0) else "❌ OPPOSITE SIDE"
                    
                    print(f"    {name}: road_id={road_id}, lane_id={lane_id}, distance={distance:.1f}m - {same_side}")
                
                # Check constraint satisfaction
                constraints_violated = re.findall(r'lane_relationship\([^)]+\): ✗', result.stderr)
                if constraints_violated:
                    print(f"  ⚠️  CONSTRAINT VIOLATIONS: {len(constraints_violated)} lane relationship failures")
                else:
                    print(f"  ✅ CONSTRAINTS: All satisfied")
                
                # Check fallbacks used
                fallbacks = re.findall(r'Fallback \d+ \([^)]+\):', result.stderr)
                if fallbacks:
                    print(f"  ⚠️  FALLBACKS USED: {len(fallbacks)} - {', '.join(set(fallbacks))}")
                else:
                    print(f"  ✅ NO FALLBACKS: Perfect spawn match found")
                    
            else:
                print(f"  ❌ Conversion: FAILED")
                print(f"    Error: {result.stderr[:200]}...")
                
        except subprocess.TimeoutExpired:
            print(f"  ❌ Conversion: TIMEOUT")
        except Exception as e:
            print(f"  ❌ Conversion: ERROR - {e}")
    
    # Generate summary
    print(f"\n{'='*80}")
    print(f"SUMMARY OF FIXES APPLIED")
    print(f"{'='*80}")
    
    print(f"✅ WHAT WAS FIXED:")
    print(f"  • Added lane_relationship='same_lane' to 18 following scenario actors")
    print(f"  • Updated success_distance and timeout values for proper scenario duration")
    print(f"  • Enhanced scenario validator to catch missing lane relationships")
    print(f"  • Added comprehensive logging of constraint violations")
    
    print(f"\n⚠️  REMAINING CHALLENGES:")
    print(f"  • Spawn point density: Not enough same-direction lanes near ego positions")
    print(f"  • Fallback system: Still allows opposite-side spawns when no alternatives exist")
    print(f"  • Map selection: Town04 may not have optimal spawn coverage for all scenarios")
    
    print(f"\n🎯 RECOMMENDATIONS:")
    print(f"  1. Enhance spawn point generation to ensure better same-lane coverage")
    print(f"  2. Improve fallback logic to prefer same-direction lanes over opposite-direction")
    print(f"  3. Consider dynamic map selection based on scenario requirements")
    print(f"  4. Add spawn point validation to ensure adequate coverage per map")

def parse_spawn_logs(log_output: str) -> Dict:
    """Parse spawn information from converter logs"""
    spawn_info = {'ego': None, 'actors': []}
    
    # Find ego spawn
    ego_match = re.search(r'=== Spawning ego ===.*?Actor: road_id=(\d+), lane_id=(-?\d+)', log_output, re.DOTALL)
    if ego_match:
        spawn_info['ego'] = {
            'road_id': int(ego_match.group(1)),
            'lane_id': int(ego_match.group(2))
        }
    
    # Find actor spawns
    actor_pattern = r'=== Spawning actor ===.*?Ego: road_id=(-?\d+), lane_id=(-?\d+).*?Actor: road_id=(-?\d+), lane_id=(-?\d+).*?Distance: ([\d.]+)m'
    
    for match in re.finditer(actor_pattern, log_output, re.DOTALL):
        spawn_info['actors'].append({
            'name': 'actor',
            'road_id': int(match.group(3)),
            'lane_id': int(match.group(4)),
            'distance': float(match.group(5))
        })
    
    return spawn_info

if __name__ == '__main__':
    generate_test_report()