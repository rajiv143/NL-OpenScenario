#!/usr/bin/env python3
"""
Comprehensive Test Suite for Scenario Validation and Conversion
Tests validated scenarios with the converter to ensure proper spawning
"""
import json
import os
import glob
import logging
import subprocess
import re
import sys
from typing import Dict, List, Tuple, Any
from scenario_validator import ScenarioValidator

class ScenarioTestSuite:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.validator = ScenarioValidator()
        self.test_results = {
            'total_scenarios': 0,
            'validation_passed': 0,
            'conversion_passed': 0,
            'spawn_tests_passed': 0,
            'failed_scenarios': [],
            'warnings': []
        }
        
    def run_all_tests(self, scenario_dir: str = "generated_scenarios", max_tests: int = 50):
        """Run comprehensive test suite on scenarios"""
        self.logger.info(f"Running comprehensive test suite on {scenario_dir}")
        
        # Get scenario files
        scenario_files = glob.glob(os.path.join(scenario_dir, "*.json"))
        
        if max_tests and len(scenario_files) > max_tests:
            # Test a representative sample
            import random
            random.seed(42)  # Reproducible sampling
            scenario_files = random.sample(scenario_files, max_tests)
            self.logger.info(f"Testing {max_tests} randomly sampled scenarios")
        
        self.test_results['total_scenarios'] = len(scenario_files)
        
        for i, scenario_file in enumerate(scenario_files, 1):
            self.logger.info(f"Testing {i}/{len(scenario_files)}: {os.path.basename(scenario_file)}")
            self._test_single_scenario(scenario_file)
        
        self._generate_test_report()
    
    def _test_single_scenario(self, scenario_path: str):
        """Test a single scenario through validation and conversion pipeline"""
        scenario_name = os.path.basename(scenario_path)
        
        # Step 1: JSON Validation
        issues = self.validator.validate_scenario(scenario_path)
        if issues:
            self.test_results['failed_scenarios'].append({
                'scenario': scenario_name,
                'stage': 'validation',
                'issues': issues
            })
            return
        
        self.test_results['validation_passed'] += 1
        
        # Step 2: Conversion Test
        try:
            result = subprocess.run([
                'python', 'xosc_json.py', scenario_path, '--log-level', 'INFO'
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                self.test_results['failed_scenarios'].append({
                    'scenario': scenario_name,
                    'stage': 'conversion',
                    'error': result.stderr
                })
                return
                
        except subprocess.TimeoutExpired:
            self.test_results['failed_scenarios'].append({
                'scenario': scenario_name,
                'stage': 'conversion',
                'error': 'Conversion timeout (>30s)'
            })
            return
        except Exception as e:
            self.test_results['failed_scenarios'].append({
                'scenario': scenario_name,
                'stage': 'conversion',
                'error': str(e)
            })
            return
        
        self.test_results['conversion_passed'] += 1
        
        # Step 3: Spawn Analysis
        spawn_analysis = self._analyze_spawn_logs(result.stderr, scenario_path)
        if spawn_analysis['passed']:
            self.test_results['spawn_tests_passed'] += 1
        else:
            self.test_results['failed_scenarios'].append({
                'scenario': scenario_name,
                'stage': 'spawn_analysis',
                'issues': spawn_analysis['issues']
            })
        
        # Collect warnings
        if spawn_analysis['warnings']:
            self.test_results['warnings'].append({
                'scenario': scenario_name,
                'warnings': spawn_analysis['warnings']
            })
    
    def _analyze_spawn_logs(self, log_output: str, scenario_path: str) -> Dict[str, Any]:
        """Analyze converter logs to validate spawn behavior"""
        issues = []
        warnings = []
        passed = True
        
        try:
            with open(scenario_path, 'r') as f:
                scenario_data = json.load(f)
        except:
            return {'passed': False, 'issues': ['Could not load scenario data'], 'warnings': []}
        
        # Check for fallback usage
        if 'fallback' in log_output.lower():
            fallback_matches = re.findall(r'Fallback \d+ \([^)]+\):', log_output)
            if fallback_matches:
                warnings.append(f"Used fallbacks: {', '.join(fallback_matches)}")
                
            # Critical: Check if road relationship was relaxed
            if 'LAST RESORT' in log_output and 'road_relationship' in log_output:
                issues.append("Critical: Road relationship constraint was relaxed as last resort")
                passed = False
        
        # Analyze spawn distances
        distance_matches = re.findall(r'Distance: ([\d.]+)m', log_output)
        actor_distances = [float(d) for d in distance_matches]
        
        for i, actor in enumerate(scenario_data.get('actors', [])):
            if i < len(actor_distances):
                actual_distance = actor_distances[i]
                spawn_criteria = actor.get('spawn', {}).get('criteria', {})
                distance_constraint = spawn_criteria.get('distance_to_ego')
                
                if isinstance(distance_constraint, dict):
                    min_dist = distance_constraint.get('min', 0)
                    max_dist = distance_constraint.get('max', float('inf'))
                    
                    if not (min_dist <= actual_distance <= max_dist):
                        issues.append(f"Actor '{actor['id']}' spawned at {actual_distance:.1f}m, outside requested range {min_dist}-{max_dist}m")
                        passed = False
                    elif actual_distance > 100:
                        warnings.append(f"Actor '{actor['id']}' spawned far away at {actual_distance:.1f}m")
        
        # Check constraint satisfaction
        constraint_matches = re.findall(r'Constraints: (.+)', log_output)
        for constraint_line in constraint_matches:
            if '✗' in constraint_line:
                failed_constraints = re.findall(r'(\w+_\w+)\([^)]+\): ✗', constraint_line)
                if failed_constraints:
                    issues.append(f"Failed constraints: {', '.join(failed_constraints)}")
                    passed = False
        
        # Check for intersection scenarios
        scenario_name = scenario_data.get('scenario_name', '').lower()
        if 'intersection' in scenario_name or 'chaos' in scenario_name:
            # Verify cross-traffic spawns on different roads
            road_matches = re.findall(r'road_id=(\d+)', log_output)
            if len(set(road_matches)) < 2:
                warnings.append("Intersection scenario may not have cross-traffic on different roads")
        
        return {
            'passed': passed,
            'issues': issues,
            'warnings': warnings
        }
    
    def _generate_test_report(self):
        """Generate comprehensive test report"""
        results = self.test_results
        
        print(f"\n{'='*80}")
        print(f"SCENARIO TEST SUITE RESULTS")
        print(f"{'='*80}")
        
        print(f"Total Scenarios Tested: {results['total_scenarios']}")
        print(f"Validation Passed: {results['validation_passed']} ({results['validation_passed']/results['total_scenarios']*100:.1f}%)")
        print(f"Conversion Passed: {results['conversion_passed']} ({results['conversion_passed']/results['total_scenarios']*100:.1f}%)")
        print(f"Spawn Tests Passed: {results['spawn_tests_passed']} ({results['spawn_tests_passed']/results['total_scenarios']*100:.1f}%)")
        
        print(f"\nFAILED SCENARIOS: {len(results['failed_scenarios'])}")
        if results['failed_scenarios']:
            for failure in results['failed_scenarios']:
                print(f"\n❌ {failure['scenario']} (Stage: {failure['stage']})")
                if 'issues' in failure:
                    for issue in failure['issues']:
                        print(f"   - {issue}")
                if 'error' in failure:
                    print(f"   Error: {failure['error']}")
        
        print(f"\nWARNINGS: {len(results['warnings'])}")
        if results['warnings']:
            for warning in results['warnings']:
                print(f"\n⚠️  {warning['scenario']}")
                for warn in warning['warnings']:
                    print(f"   - {warn}")
        
        # Success rate calculation
        overall_success = results['spawn_tests_passed'] / results['total_scenarios'] * 100
        print(f"\nOVERALL SUCCESS RATE: {overall_success:.1f}%")
        
        if overall_success >= 90:
            print("✅ EXCELLENT: Scenario validation and conversion working properly!")
        elif overall_success >= 75:
            print("✅ GOOD: Most scenarios working, minor issues to address")
        elif overall_success >= 50:
            print("⚠️  NEEDS IMPROVEMENT: Significant issues found")
        else:
            print("❌ CRITICAL: Major problems with scenario validation/conversion")
    
    def test_intersection_scenarios(self):
        """Focused test on intersection scenarios"""
        self.logger.info("Running focused intersection scenario tests")
        
        intersection_files = []
        for pattern in ['*intersection*', '*chaos*', '*cross*']:
            intersection_files.extend(glob.glob(os.path.join("generated_scenarios", pattern)))
        
        if not intersection_files:
            self.logger.warning("No intersection scenarios found")
            return
        
        print(f"\n🔍 TESTING {len(intersection_files)} INTERSECTION SCENARIOS")
        
        for scenario_file in intersection_files:
            print(f"\nTesting: {os.path.basename(scenario_file)}")
            
            # Run conversion with detailed logging
            result = subprocess.run([
                'python', 'xosc_json.py', scenario_file, '--log-level', 'DEBUG'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                # Check for proper cross-traffic spawning
                log_lines = result.stderr.split('\n')
                road_ids = []
                
                for line in log_lines:
                    if 'road_id=' in line and 'Actor:' in line:
                        match = re.search(r'road_id=(\d+)', line)
                        if match:
                            road_ids.append(int(match.group(1)))
                
                if len(set(road_ids)) >= 2:
                    print("  ✅ Cross-traffic spawned on different roads")
                else:
                    print(f"  ⚠️  All actors on same roads: {road_ids}")
            else:
                print(f"  ❌ Conversion failed: {result.stderr[:100]}...")

def main():
    """Main test runner"""
    logging.basicConfig(level=logging.INFO)
    
    if not os.path.exists('xosc_json.py'):
        print("❌ xosc_json.py not found. Please run from the correct directory.")
        sys.exit(1)
    
    suite = ScenarioTestSuite()
    
    # Run comprehensive tests
    suite.run_all_tests(max_tests=50)  # Test 50 representative scenarios
    
    # Run focused intersection tests
    suite.test_intersection_scenarios()

if __name__ == '__main__':
    main()