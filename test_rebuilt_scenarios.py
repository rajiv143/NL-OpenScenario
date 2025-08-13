#!/usr/bin/env python3
"""Test the rebuilt scenarios for conversion quality"""

import sys
import glob
import json

# Mock carla module
class MockCarla:
    def __getattr__(self, name):
        return None

sys.modules['carla'] = MockCarla()

from xosc_json import JsonToXoscConverter

def test_rebuilt_scenarios():
    """Test a sample of rebuilt scenarios"""
    
    # Get sample from each category
    test_files = [
        'rebuilt_scenarios/following_001.json',
        'rebuilt_scenarios/following_075.json', 
        'rebuilt_scenarios/lane_change_151.json',
        'rebuilt_scenarios/lane_change_200.json',
        'rebuilt_scenarios/pedestrian_251.json',
        'rebuilt_scenarios/emergency_331.json',
        'rebuilt_scenarios/static_391.json'
    ]
    
    converter = JsonToXoscConverter()
    
    print("Testing rebuilt scenarios conversion quality...")
    print("="*60)
    
    success_count = 0
    total_count = 0
    
    for test_file in test_files:
        total_count += 1
        
        try:
            print(f"\n🧪 Testing: {test_file}")
            
            with open(test_file, 'r') as f:
                json_data = json.load(f)
            
            # Convert to XOSC
            xosc_content = converter.convert(json_data)
            
            # Write test output
            output_file = test_file.replace('rebuilt_scenarios/', 'test_').replace('.json', '.xosc')
            with open(output_file, 'w') as f:
                f.write(xosc_content)
            
            print(f"✅ SUCCESS: Converted to {output_file}")
            
            # Check for quality indicators
            quality_checks = {
                'proper_vehicles': 'vehicle.toyota.prius' in xosc_content or 'vehicle.audi.a2' in xosc_content,
                'no_bicycles_in_lane_changes': 'crossbike' not in xosc_content if 'lane_change' in test_file else True,
                'proper_distances': 'distance_success' in xosc_content,
                'clean_criteria': 'criteria_DrivenDistanceTest' in xosc_content and 'RunningStopTest' not in xosc_content
            }
            
            passed_checks = sum(quality_checks.values())
            total_checks = len(quality_checks)
            
            print(f"   Quality: {passed_checks}/{total_checks} checks passed")
            
            if passed_checks == total_checks:
                success_count += 1
                print(f"   🏆 HIGH QUALITY")
            else:
                print(f"   ⚠️  Issues found:")
                for check, passed in quality_checks.items():
                    if not passed:
                        print(f"      - {check}: FAILED")
            
        except Exception as e:
            print(f"❌ FAILED: {e}")
    
    print(f"\n{'='*60}")
    print(f"RESULTS: {success_count}/{total_count} scenarios converted successfully")
    print(f"Success rate: {success_count/total_count*100:.1f}%")
    
    if success_count == total_count:
        print("🎉 All test scenarios passed! Ready for batch conversion.")
        return True
    else:
        print("⚠️  Some scenarios have issues. Check the output above.")
        return False

if __name__ == '__main__':
    test_rebuilt_scenarios()