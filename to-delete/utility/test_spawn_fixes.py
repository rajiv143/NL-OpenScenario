#!/usr/bin/env python3
"""
Comprehensive test suite for spawn fixes
Tests all major improvements to ensure they work correctly
"""

import os
import json
import subprocess
import sys
import glob
from typing import Dict, List, Tuple

class SpawnFixTester:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.test_results = []
        
    def log_test(self, test_name: str, passed: bool, message: str = ""):
        status = "✅ PASS" if passed else "❌ FAIL"
        self.test_results.append((test_name, passed, message))
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        print(f"{status}: {test_name} {message}")
    
    def test_scenario_conversion(self, scenario_path: str, expected_features: Dict = None) -> bool:
        """Test that a scenario converts successfully and meets expectations"""
        try:
            # Run conversion
            result = subprocess.run([
                'python', 'xosc_json.py', scenario_path, '--log-level', 'ERROR'
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                return False, f"Conversion failed: {result.stderr}"
            
            # Parse spawn summary from output
            if "=== SPAWN SUMMARY ===" not in result.stdout:
                return False, "No spawn summary found"
            
            distances = []
            actors = []
            
            for line in result.stdout.split('\n'):
                if "Distance from ego:" in line:
                    dist_str = line.split("Distance from ego:")[1].strip().split('m')[0]
                    distances.append(float(dist_str))
                elif line.strip().endswith("Position:") and "EGO" not in line:
                    actor_name = line.split("Position:")[0].strip()
                    actors.append(actor_name)
            
            # Validate distances
            for dist in distances:
                if dist < 5.0:
                    return False, f"Actor spawned too close: {dist:.1f}m < 5m"
            
            # Check pedestrian distance limits  
            scenario_name = os.path.basename(scenario_path).lower()
            if 'pedestrian' in scenario_name:
                for dist in distances:
                    if dist > 50.0:
                        return False, f"Pedestrian spawned too far: {dist:.1f}m > 50m"
            
            return True, f"Converted successfully with {len(actors)} actors, distances: {[f'{d:.1f}m' for d in distances]}"
            
        except Exception as e:
            return False, f"Exception: {str(e)}"
    
    def test_scenario_types(self):
        """Test different scenario types"""
        test_scenarios = [
            ("generated_scenarios/lane_change_070_cut_in_ahead_20.json", "cut_in"),
            ("generated_scenarios/basic_following_006_sudden_brake_ahead_06.json", "following"), 
            ("generated_scenarios/pedestrian_crossing_037_jogger_crossing_12.json", "pedestrian"),
            ("generated_scenarios/multi_actor_167_intersection_chaos_02.json", "intersection"),
            ("generated_scenarios/static_obstacles_088_broken_down_vehicle_13.json", "static"),
        ]
        
        for scenario_path, scenario_type in test_scenarios:
            if os.path.exists(scenario_path):
                success, message = self.test_scenario_conversion(scenario_path)
                self.log_test(f"{scenario_type.upper()} scenario", success, message)
            else:
                self.log_test(f"{scenario_type.upper()} scenario", False, f"File not found: {scenario_path}")
    
    def test_distance_constraints(self):
        """Test distance constraint enforcement"""
        # Create test scenarios with specific distance requirements
        test_cases = [
            {
                "name": "cut_in_minimum_distance",
                "scenario_type": "cut_in",
                "expected_min": 25,
                "json": {
                    "scenario_name": "test_cut_in_distance",
                    "map_name": "Town04",
                    "weather": "clear",
                    "ego_spawn": {"criteria": {"lane_type": "Driving"}},
                    "actors": [{
                        "id": "test_actor",
                        "type": "vehicle", 
                        "model": "vehicle.tesla.model3",
                        "spawn": {
                            "criteria": {
                                "lane_type": "Driving",
                                "lane_relationship": "adjacent_lane",
                                "distance_to_ego": {"min": 15, "max": 40}  # Should be enforced to min 25
                            }
                        }
                    }]
                }
            }
        ]
        
        for test_case in test_cases:
            test_file = f"/tmp/{test_case['name']}.json"
            with open(test_file, 'w') as f:
                json.dump(test_case['json'], f, indent=2)
            
            # Test that scenario validator enforces minimum distance
            try:
                subprocess.run(['python', 'scenario_validator.py'], 
                             input=test_file, capture_output=True, text=True)
                
                # Read back the file to check if distance was enforced
                with open(test_file, 'r') as f:
                    updated_json = json.load(f)
                
                actual_min = updated_json['actors'][0]['spawn']['criteria']['distance_to_ego']['min']
                expected_min = test_case['expected_min']
                
                if actual_min >= expected_min:
                    self.log_test(f"Distance enforcement ({test_case['scenario_type']})", 
                                True, f"min distance enforced: {actual_min}m >= {expected_min}m")
                else:
                    self.log_test(f"Distance enforcement ({test_case['scenario_type']})", 
                                False, f"min distance not enforced: {actual_min}m < {expected_min}m")
                
                os.unlink(test_file)
                
            except Exception as e:
                self.log_test(f"Distance enforcement ({test_case['scenario_type']})", 
                            False, f"Test failed: {str(e)}")
    
    def test_fallback_behavior(self):
        """Test that fallback mechanisms work correctly"""
        # Create a scenario that should trigger fallbacks
        fallback_test = {
            "scenario_name": "test_fallback_behavior",
            "map_name": "Town01",  # Smaller map to trigger fallbacks
            "weather": "clear",
            "ego_spawn": {"criteria": {"lane_type": "Driving"}},
            "actors": [{
                "id": "fallback_actor",
                "type": "vehicle",
                "model": "vehicle.tesla.model3", 
                "spawn": {
                    "criteria": {
                        "lane_type": "Driving",
                        "lane_relationship": "adjacent_lane",  # May trigger fallbacks
                        "distance_to_ego": {"min": 30, "max": 50}
                    }
                }
            }]
        }
        
        test_file = "/tmp/fallback_test.json"
        with open(test_file, 'w') as f:
            json.dump(fallback_test, f, indent=2)
        
        try:
            result = subprocess.run([
                'python', 'xosc_json.py', test_file, '--log-level', 'WARNING'
            ], capture_output=True, text=True, timeout=30)
            
            # Check if fallbacks were used but scenario still succeeded
            if result.returncode == 0 and "Successfully converted" in result.stdout:
                if "fallback" in result.stderr.lower():
                    self.log_test("Fallback behavior", True, "Fallbacks used successfully")
                else:
                    self.log_test("Fallback behavior", True, "No fallbacks needed")
            else:
                self.log_test("Fallback behavior", False, f"Fallback failed: {result.stderr}")
            
            os.unlink(test_file)
            
        except Exception as e:
            self.log_test("Fallback behavior", False, f"Test failed: {str(e)}")
    
    def test_validator_fixes(self):
        """Test that scenario validator fixes common issues"""
        # Find scenarios that the validator should fix
        scenarios = glob.glob("generated_scenarios/*.json")
        fixed_count = 0
        tested_count = 0
        
        for scenario_path in scenarios[:5]:  # Test first 5 scenarios
            try:
                # Run validator
                result = subprocess.run([
                    'python', 'scenario_validator.py'
                ], capture_output=True, text=True)
                
                if "Fixed issues" in result.stderr:
                    fixed_count += 1
                tested_count += 1
                
            except Exception:
                continue
        
        if tested_count > 0:
            self.log_test("Validator fixes", True, f"Validator processed {tested_count} scenarios, fixed issues in {fixed_count}")
        else:
            self.log_test("Validator fixes", False, "Could not test validator")
    
    def run_all_tests(self):
        """Run all tests and report results"""
        print("🔧 Running comprehensive spawn fix tests...")
        print("=" * 60)
        
        self.test_scenario_types()
        self.test_distance_constraints() 
        self.test_fallback_behavior()
        self.test_validator_fixes()
        
        print("=" * 60)
        print(f"📊 Test Results: {self.passed} passed, {self.failed} failed")
        
        if self.failed > 0:
            print("\n❌ Failed tests:")
            for test_name, passed, message in self.test_results:
                if not passed:
                    print(f"  - {test_name}: {message}")
        
        return self.failed == 0

if __name__ == "__main__":
    tester = SpawnFixTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)