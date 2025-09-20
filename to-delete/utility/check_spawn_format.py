#!/usr/bin/env python3
"""Check spawn data format"""

import sys
import math

# Mock carla module
class MockCarla:
    def __getattr__(self, name):
        return None

sys.modules['carla'] = MockCarla()

from xosc_json import JsonToXoscConverter

def check_format():
    converter = JsonToXoscConverter()
    
    # Get a sample spawn point
    spawn_points = converter._get_spawn_points_for_map('Town04')
    sample = spawn_points[0]
    
    print("Sample spawn point data:")
    print(f"  x: {sample.get('x')}")
    print(f"  y: {sample.get('y')}")
    print(f"  z: {sample.get('z')}")
    print(f"  yaw: {sample.get('yaw')}")
    
    yaw_raw = sample.get('yaw', 0)
    print(f"\nYaw interpretation:")
    print(f"  Raw yaw: {yaw_raw}")
    print(f"  If degrees: {yaw_raw}° = {math.radians(yaw_raw):.6f} radians")
    print(f"  If radians: {yaw_raw} rad = {math.degrees(yaw_raw):.1f}°")
    
    # 180.59 should be degrees and convert to ~3.15 radians
    print(f"\nThe problem value:")
    print(f"  Raw: 180.59")
    print(f"  As degrees->radians: {math.radians(180.59):.6f} rad")
    print(f"  As radians->degrees: {math.degrees(180.59):.1f}°")

if __name__ == '__main__':
    check_format()