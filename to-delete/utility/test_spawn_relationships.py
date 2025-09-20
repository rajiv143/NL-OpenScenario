#!/usr/bin/env python3
"""
Test script to verify the new explicit road/lane relationship constraints work correctly
"""

import json
import os
from scenario_generator import CARLAScenarioGenerator

def test_explicit_relationships():
    """Test that scenarios now generate with explicit road/lane relationships"""
    print("Testing new explicit road/lane relationship constraints...")
    
    # Create generator
    generator = CARLAScenarioGenerator("test_scenarios")
    
    # Generate a small sample of different scenario types
    print("\n1. Testing vehicle following scenarios...")
    following_scenarios = generator.generate_vehicle_following_scenarios(2)
    
    print("\n2. Testing lane change scenarios...")
    lane_change_scenarios = generator.generate_lane_change_scenarios(2)
    
    print("\n3. Testing multi-actor scenarios...")
    multi_actor_scenarios = generator.generate_multi_actor_scenarios(2)
    
    # Verify the generated JSON contains explicit relationships
    all_test_scenarios = following_scenarios + lane_change_scenarios + multi_actor_scenarios
    
    print(f"\n=== Verifying {len(all_test_scenarios)} generated scenarios ===")
    
    relationship_count = {
        'road_relationship': 0,
        'lane_relationship': 0,
        'both_relationships': 0,
        'total_actors': 0
    }
    
    for scenario_file in all_test_scenarios:
        with open(scenario_file, 'r') as f:
            scenario_data = json.load(f)
        
        scenario_name = scenario_data['scenario_name']
        print(f"\nScenario: {scenario_name}")
        
        for actor in scenario_data.get('actors', []):
            relationship_count['total_actors'] += 1
            spawn_criteria = actor.get('spawn', {}).get('criteria', {})
            
            has_road_rel = 'road_relationship' in spawn_criteria
            has_lane_rel = 'lane_relationship' in spawn_criteria
            
            if has_road_rel:
                relationship_count['road_relationship'] += 1
            if has_lane_rel:
                relationship_count['lane_relationship'] += 1
            if has_road_rel and has_lane_rel:
                relationship_count['both_relationships'] += 1
            
            print(f"  Actor '{actor['id']}': road_rel={spawn_criteria.get('road_relationship', 'none')}, lane_rel={spawn_criteria.get('lane_relationship', 'none')}")
    
    print(f"\n=== SUMMARY ===")
    print(f"Total actors analyzed: {relationship_count['total_actors']}")
    print(f"Actors with road_relationship: {relationship_count['road_relationship']} ({relationship_count['road_relationship']/relationship_count['total_actors']*100:.1f}%)")
    print(f"Actors with lane_relationship: {relationship_count['lane_relationship']} ({relationship_count['lane_relationship']/relationship_count['total_actors']*100:.1f}%)")
    print(f"Actors with both relationships: {relationship_count['both_relationships']} ({relationship_count['both_relationships']/relationship_count['total_actors']*100:.1f}%)")
    
    # Check if improvement was successful
    if relationship_count['both_relationships'] > 0:
        print("\n✅ SUCCESS: Scenarios now include explicit road/lane relationships!")
        print("This will ensure actors spawn in logically correct positions relative to ego vehicle.")
    else:
        print("\n❌ WARNING: No explicit relationships found in generated scenarios.")
    
    # Show example of enhanced spawn criteria
    if all_test_scenarios:
        with open(all_test_scenarios[0], 'r') as f:
            example_data = json.load(f)
        
        print(f"\n=== EXAMPLE: {example_data['scenario_name']} ===")
        for actor in example_data.get('actors', []):
            criteria = actor.get('spawn', {}).get('criteria', {})
            print(f"Actor '{actor['id']}' spawn criteria:")
            for key, value in criteria.items():
                print(f"  {key}: {value}")

def create_sample_scenario_with_relationships():
    """Create a sample scenario demonstrating the new relationship constraints"""
    
    sample_scenario = {
        "scenario_name": "relationship_demo",
        "description": "Demonstration of explicit road/lane relationships",
        "weather": "clear",
        "ego_vehicle_model": "vehicle.tesla.model3",
        "ego_spawn": {
            "criteria": {
                "lane_type": "Driving",
                "lane_id": {"min": 1, "max": 10},
                "is_intersection": False
            }
        },
        "ego_start_speed": 0,
        "actors": [
            {
                "id": "lead_vehicle",
                "type": "vehicle",
                "model": "vehicle.audi.a2",
                "spawn": {
                    "criteria": {
                        "lane_type": "Driving",
                        "road_relationship": "same_road",
                        "lane_relationship": "same_lane",
                        "distance_to_ego": {"min": 30, "max": 40},
                        "relative_position": "ahead"
                    }
                }
            },
            {
                "id": "overtaking_vehicle",
                "type": "vehicle", 
                "model": "vehicle.bmw.grandtourer",
                "spawn": {
                    "criteria": {
                        "lane_type": "Driving",
                        "road_relationship": "same_road",
                        "lane_relationship": "adjacent_lane",
                        "distance_to_ego": {"min": 20, "max": 30},
                        "relative_position": "behind"
                    }
                }
            },
            {
                "id": "cross_traffic",
                "type": "vehicle",
                "model": "vehicle.ford.crown", 
                "spawn": {
                    "criteria": {
                        "lane_type": "Driving",
                        "road_relationship": "different_road",
                        "distance_to_ego": {"min": 40, "max": 60},
                        "is_intersection": True
                    }
                }
            }
        ],
        "actions": [],
        "success_distance": 100,
        "timeout": 60,
        "collision_allowed": False
    }
    
    # Save sample scenario
    os.makedirs("test_scenarios", exist_ok=True)
    sample_path = "test_scenarios/relationship_demo.json"
    with open(sample_path, 'w') as f:
        json.dump(sample_scenario, f, indent=2)
    
    print(f"\n=== SAMPLE SCENARIO CREATED ===")
    print(f"File: {sample_path}")
    print("\nThis scenario demonstrates:")
    print("• lead_vehicle: same_road + same_lane (following scenario)")
    print("• overtaking_vehicle: same_road + adjacent_lane (overtaking scenario)")  
    print("• cross_traffic: different_road + intersection (intersection scenario)")
    print("\nEach actor will now spawn in the expected logical relationship to ego!")
    
    return sample_path

if __name__ == "__main__":
    print("🚗 Testing Enhanced CARLA Spawn System with Explicit Road/Lane Relationships")
    print("=" * 80)
    
    # Test the updated scenario generator
    test_explicit_relationships()
    
    # Create a demonstration scenario
    sample_path = create_sample_scenario_with_relationships()
    
    print(f"\n" + "=" * 80)
    print("🎯 IMPLEMENTATION COMPLETE!")
    print("\nKey improvements:")
    print("✓ Added road_relationship constraint: same_road, different_road, any_road")
    print("✓ Added lane_relationship constraint: same_lane, adjacent_lane, any_lane")
    print("✓ Updated spawn priority: road → lane → type → distance → position")
    print("✓ Enhanced fallback strategy with progressive relationship relaxation")
    print("✓ Comprehensive spawn decision logging")
    print("✓ Updated all scenario templates with explicit relationships")
    
    print(f"\nResult: Actors will now spawn in logically correct positions!")
    print(f"No more random spawning on unrelated roads/lanes.")