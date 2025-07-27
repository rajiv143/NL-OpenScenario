#!/usr/bin/env python3
"""
Complete CARLA XODR Analysis Pipeline
Runs the full analysis from XODR parsing to enhanced scenario generation
"""

import os
import sys
import json
import time
from pathlib import Path

# Import our custom modules
from xodr_parser import XODRAnalyzer, analyze_all_towns
from road_network_analyzer import RoadNetworkAnalyzer, analyze_network_from_database
from enhanced_scenario_constraints import EnhancedSpawnSelector, EnhancedSpawnCriteria


def create_output_directories():
    """Create necessary output directories"""
    directories = [
        "road_intelligence",
        "network_analysis", 
        "enhanced_spawns",
        "sample_scenarios"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"Created directory: {directory}")


def run_xodr_analysis(maps_directory="maps/"):
    """Step 1: Parse all XODR files and extract road intelligence"""
    print("\n" + "="*60)
    print("STEP 1: XODR PARSING AND ROAD INTELLIGENCE EXTRACTION")
    print("="*60)
    
    if not os.path.exists(maps_directory):
        print(f"Error: Maps directory '{maps_directory}' not found!")
        return None
    
    # Analyze all towns
    all_databases = analyze_all_towns(maps_directory, "road_intelligence/")
    
    print(f"\nAnalyzed {len(all_databases)} CARLA towns:")
    for town_name, db in all_databases.items():
        roads = len(db['roads'])
        junctions = len(db['junctions'])
        roundabouts = len(db['roundabouts'])
        print(f"  {town_name}: {roads} roads, {junctions} junctions, {roundabouts} roundabouts")
    
    return all_databases


def run_network_analysis(all_databases):
    """Step 2: Perform network topology analysis"""
    print("\n" + "="*60)
    print("STEP 2: ROAD NETWORK TOPOLOGY ANALYSIS")
    print("="*60)
    
    network_analyses = {}
    
    for town_name, road_db in all_databases.items():
        print(f"\nAnalyzing network topology for {town_name}...")
        
        analyzer = RoadNetworkAnalyzer(road_db)
        analysis = analyzer.analyze_full_network()
        
        # Save network analysis
        output_file = f"network_analysis/{town_name}_network_analysis.json"
        with open(output_file, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        
        network_analyses[town_name] = analysis
        
        # Print summary
        stats = analysis['network_statistics']
        print(f"  Network density: {stats['network_topology']['network_density']:.3f}")
        print(f"  Avg connections per road: {stats['network_topology']['average_connections_per_road']:.1f}")
        print(f"  High complexity intersections: {len(stats['intersection_analysis']['high_complexity_intersections'])}")
        
        # Print traffic zones
        zones = stats['traffic_zones']
        print(f"  Traffic zones: {zones}")
    
    return network_analyses


def generate_enhanced_spawn_examples(all_databases, network_analyses):
    """Step 3: Generate enhanced spawn point examples"""
    print("\n" + "="*60)
    print("STEP 3: ENHANCED SPAWN POINT GENERATION")
    print("="*60)
    
    spawn_examples = {}
    
    for town_name in all_databases.keys():
        print(f"\nGenerating enhanced spawns for {town_name}...")
        
        road_db = all_databases[town_name]
        network_analysis = network_analyses[town_name]
        
        # Create enhanced spawn selector
        spawn_selector = EnhancedSpawnSelector(road_db, network_analysis)
        
        # Example ego position (use first available waypoint)
        if road_db.get('enhanced_waypoints'):
            first_road_waypoints = next(iter(road_db['enhanced_waypoints'].values()))
            if first_road_waypoints:
                ego_position = {
                    'x': first_road_waypoints[0]['x'],
                    'y': first_road_waypoints[0]['y'],
                    'z': first_road_waypoints[0]['z'],
                    'road_id': int(next(iter(road_db['enhanced_waypoints'].keys())))
                }
                
                # Generate examples for different scenario types
                scenario_examples = {}
                
                scenario_types = [
                    "roundabout_navigation",
                    "highway_merge", 
                    "intersection_crossing",
                    "lane_change_urban",
                    "parking_lot_navigation"
                ]
                
                for scenario_type in scenario_types:
                    spawns = spawn_selector.generate_scenario_specific_spawns(
                        scenario_type, ego_position, num_actors=5
                    )
                    scenario_examples[scenario_type] = spawns
                    print(f"  {scenario_type}: {len(spawns)} spawn points")
                
                spawn_examples[town_name] = {
                    'ego_position': ego_position,
                    'scenario_spawns': scenario_examples,
                    'total_available_waypoints': len(spawn_selector.available_waypoints)
                }
        
        # Save spawn examples
        output_file = f"enhanced_spawns/{town_name}_enhanced_spawns.json"
        with open(output_file, 'w') as f:
            json.dump(spawn_examples.get(town_name, {}), f, indent=2, default=str)
    
    return spawn_examples


def create_sample_scenarios(spawn_examples):
    """Step 4: Create sample scenario configurations"""
    print("\n" + "="*60)
    print("STEP 4: SAMPLE SCENARIO CREATION")
    print("="*60)
    
    scenario_templates = {
        "roundabout_yield_scenario": {
            "description": "Vehicle must yield when entering busy roundabout",
            "spawn_criteria": {
                "road_context": "roundabout_entry",
                "junction_type": "roundabout",
                "distance_range": [50, 150]
            },
            "expected_behaviors": [
                "yield_to_circulating_traffic",
                "gap_acceptance",
                "smooth_merging"
            ]
        },
        
        "highway_merge_conflict": {
            "description": "Multiple vehicles merging simultaneously on highway",
            "spawn_criteria": {
                "road_context": "highway_merge", 
                "road_type": "highway",
                "distance_range": [100, 300]
            },
            "expected_behaviors": [
                "acceleration_lane_usage",
                "gap_selection",
                "merge_coordination"
            ]
        },
        
        "complex_intersection_navigation": {
            "description": "Navigate through high-complexity signalized intersection",
            "spawn_criteria": {
                "junction_type": "signalized",
                "intersection_complexity_range": [0.7, 1.0],
                "distance_to_junction_range": [30, 100]
            },
            "expected_behaviors": [
                "signal_obedience",
                "turn_sequence_coordination", 
                "pedestrian_awareness"
            ]
        },
        
        "urban_lane_change_pressure": {
            "description": "Lane change in dense urban traffic",
            "spawn_criteria": {
                "traffic_zone": "urban_zone",
                "road_context": "straight_section",
                "distance_range": [20, 150]
            },
            "expected_behaviors": [
                "gap_assessment",
                "signal_usage",
                "gradual_maneuvering"
            ]
        }
    }
    
    # Create sample scenarios for each town
    for town_name, spawn_data in spawn_examples.items():
        town_scenarios = {}
        
        for scenario_name, template in scenario_templates.items():
            # Find relevant spawns from the generated examples
            relevant_spawns = []
            
            for scenario_type, spawns in spawn_data.get('scenario_spawns', {}).items():
                if len(spawns) > 0:
                    # Take first few spawns as example
                    relevant_spawns.extend(spawns[:2])
            
            if relevant_spawns:
                town_scenarios[scenario_name] = {
                    **template,
                    "town": town_name,
                    "ego_spawn": spawn_data.get('ego_position'),
                    "actor_spawns": relevant_spawns[:3],  # Limit to 3 actors
                    "scenario_id": f"{town_name}_{scenario_name}_{int(time.time())}"
                }
        
        # Save town scenarios
        if town_scenarios:
            output_file = f"sample_scenarios/{town_name}_sample_scenarios.json"
            with open(output_file, 'w') as f:
                json.dump(town_scenarios, f, indent=2, default=str)
            
            print(f"Created {len(town_scenarios)} sample scenarios for {town_name}")


def generate_summary_report(all_databases, network_analyses, spawn_examples):
    """Generate comprehensive summary report"""
    print("\n" + "="*60)
    print("STEP 5: GENERATING SUMMARY REPORT")
    print("="*60)
    
    summary = {
        "analysis_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "towns_analyzed": list(all_databases.keys()),
        "total_statistics": {
            "total_roads": sum(len(db['roads']) for db in all_databases.values()),
            "total_junctions": sum(len(db['junctions']) for db in all_databases.values()),
            "total_roundabouts": sum(len(db['roundabouts']) for db in all_databases.values()),
            "total_waypoints": sum(
                len(spawn_data.get('total_available_waypoints', 0)) 
                for spawn_data in spawn_examples.values()
            )
        },
        "town_summaries": {}
    }
    
    for town_name in all_databases.keys():
        road_db = all_databases[town_name]
        network_analysis = network_analyses[town_name]
        spawn_data = spawn_examples.get(town_name, {})
        
        town_summary = {
            "road_network": {
                "roads": len(road_db['roads']),
                "junctions": len(road_db['junctions']),
                "roundabouts": len(road_db['roundabouts']),
                "total_length_km": round(
                    sum(road['length'] for road in road_db['roads'].values()) / 1000, 2
                )
            },
            "network_topology": network_analysis['network_statistics']['network_topology'],
            "intersection_analysis": {
                "total_intersections": network_analysis['network_statistics']['intersection_analysis']['total_intersections'],
                "avg_complexity": round(
                    network_analysis['network_statistics']['intersection_analysis']['avg_complexity'], 3
                ),
                "intersection_types": network_analysis['network_statistics']['intersection_analysis']['by_type']
            },
            "traffic_zones": network_analysis['network_statistics']['traffic_zones'],
            "enhanced_spawns": {
                "total_waypoints": spawn_data.get('total_available_waypoints', 0),
                "scenario_types_supported": len(spawn_data.get('scenario_spawns', {}))
            }
        }
        
        summary['town_summaries'][town_name] = town_summary
    
    # Save summary report
    with open('CARLA_Road_Intelligence_Summary.json', 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    # Print summary
    print(f"\nCARLA Road Intelligence Analysis Complete!")
    print(f"Towns analyzed: {len(summary['towns_analyzed'])}")
    print(f"Total roads: {summary['total_statistics']['total_roads']}")
    print(f"Total junctions: {summary['total_statistics']['total_junctions']}")
    print(f"Total roundabouts: {summary['total_statistics']['total_roundabouts']}")
    print(f"\nDetailed summary saved to: CARLA_Road_Intelligence_Summary.json")
    
    return summary


def main():
    """Run the complete CARLA XODR analysis pipeline"""
    print("CARLA OpenDRIVE Road Intelligence Analysis Pipeline")
    print("=" * 60)
    
    start_time = time.time()
    
    try:
        # Setup
        create_output_directories()
        
        # Step 1: Parse XODR files
        all_databases = run_xodr_analysis()
        if not all_databases:
            print("Error: Could not parse XODR files. Exiting.")
            return
        
        # Step 2: Network analysis
        network_analyses = run_network_analysis(all_databases)
        
        # Step 3: Enhanced spawn generation
        spawn_examples = generate_enhanced_spawn_examples(all_databases, network_analyses)
        
        # Step 4: Sample scenarios
        create_sample_scenarios(spawn_examples)
        
        # Step 5: Summary report
        summary = generate_summary_report(all_databases, network_analyses, spawn_examples)
        
        # Final timing
        elapsed_time = time.time() - start_time
        print(f"\nTotal analysis time: {elapsed_time:.1f} seconds")
        
        print("\nOutput files created:")
        print("  road_intelligence/     - XODR parsing results")
        print("  network_analysis/      - Network topology analysis")
        print("  enhanced_spawns/       - Enhanced spawn point data")
        print("  sample_scenarios/      - Sample scenario configurations")
        print("  CARLA_Road_Intelligence_Summary.json - Complete summary")
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()