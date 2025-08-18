#!/usr/bin/env python3
"""
Generate 300 Basic CARLA Scenarios with Systematic Variation
Focus on fundamental building blocks with comprehensive coverage of variables
"""

import json
import os
import random
from typing import Dict, List, Tuple, Any
from datetime import datetime

# ===========================
# CONFIGURATION CONSTANTS
# ===========================

# Vehicle Models
EGO_MODELS = [
    "vehicle.audi.a2", "vehicle.toyota.prius", "vehicle.bmw.grandtourer",
    "vehicle.ford.crown", "vehicle.mercedes.sprinter", "vehicle.audi.tt",
    "vehicle.nissan.patrol", "vehicle.chevrolet.impala", "vehicle.mini.cooper_s"
]

ACTOR_MODELS = [
    "vehicle.toyota.prius", "vehicle.bmw.grandtourer", "vehicle.ford.crown",
    "vehicle.mercedes.sprinter", "vehicle.audi.tt", "vehicle.nissan.patrol",
    "vehicle.chevrolet.impala", "vehicle.mini.cooper_s", "vehicle.yamaha.yzf",
    "vehicle.bh.crossbike", "vehicle.harley.low_rider"
]

# Color Variations (RGB format)
COLORS = {
    # Primary colors
    "red": "255,0,0",
    "green": "0,255,0", 
    "blue": "0,0,255",
    "yellow": "255,255,0",
    
    # Secondary colors  
    "orange": "255,165,0",
    "purple": "128,0,128",
    "pink": "255,192,203",
    "cyan": "0,255,255",
    "magenta": "255,0,255",
    
    # Neutral colors
    "white": "255,255,255", 
    "black": "0,0,0",
    "gray": "128,128,128",
    "silver": "192,192,192",
}

# Speed Ranges (m/s)
SPEED_RANGES = {
    "very_slow": [3, 5],      # Parking/residential
    "slow": [6, 8],           # City streets  
    "medium": [9, 12],        # Suburban roads
    "fast": [13, 16],         # Main roads
    "highway": [17, 20]       # Highway speeds
}

# Weather Conditions
WEATHER_CONDITIONS = [
    "clear", "cloudy", "soft_rain", "wet", 
    "clear_sunset", "cloudy_sunset", "wet_sunset", "hard_rain"
]

# Directory Structure
SCENARIO_LEVELS = {
    "01_static_actors": 50,
    "02_moving_actors": 50,
    "03_speed_changes": 50,
    "04_stop_start": 50,
    "05_multi_actors": 60,
    "06_interactions": 40
}

BASE_DIR = "claude_scenarios"

# ===========================
# UTILITY FUNCTIONS
# ===========================

def get_scenario_variables(scenario_index: int) -> Tuple[str, str, str, str]:
    """Rotate variables systematically"""
    ego_model = EGO_MODELS[scenario_index % len(EGO_MODELS)]
    actor_model = ACTOR_MODELS[scenario_index % len(ACTOR_MODELS)]
    color_name = list(COLORS.keys())[scenario_index % len(COLORS)]
    weather = WEATHER_CONDITIONS[scenario_index % len(WEATHER_CONDITIONS)]
    
    return ego_model, actor_model, color_name, weather

def get_random_speed(speed_category: str) -> float:
    """Get a random speed from the specified category"""
    speed_range = SPEED_RANGES[speed_category]
    return round(random.uniform(speed_range[0], speed_range[1]), 1)

def create_actor(actor_id: str, model: str, color_name: str, spawn_criteria: Dict) -> Dict:
    """Create an actor with color specification"""
    color_rgb = COLORS[color_name]
    return {
        "id": actor_id,
        "type": "vehicle", 
        "model": model,
        "spawn": {"criteria": spawn_criteria},
        "color": color_rgb  # ALWAYS INCLUDE
    }

def create_ego_spawn() -> Dict:
    """Create ego spawn criteria"""
    return {
        "criteria": {
            "lane_type": "Driving",
            "lane_id": {"min": 1, "max": 4},
            "is_intersection": False
        }
    }

def save_scenario(level_dir: str, scenario_name: str, scenario_data: Dict, description: str):
    """Save scenario JSON and description files"""
    # Ensure directory exists
    os.makedirs(level_dir, exist_ok=True)
    
    # Save JSON
    json_path = os.path.join(level_dir, f"{scenario_name}.json")
    with open(json_path, 'w') as f:
        json.dump(scenario_data, f, indent=2)
    
    # Save description
    desc_path = os.path.join(level_dir, f"{scenario_name}_description.txt")
    with open(desc_path, 'w') as f:
        f.write(description)

def print_progress(level: str, scenario_num: int, total: int, color: str, ego_model: str):
    """Print progress information"""
    model_short = ego_model.split('.')[-1]
    print(f"  [{scenario_num:3d}/{total:3d}] Color: {color:8s} | Ego: {model_short:15s}")

# ===========================
# LEVEL 1: STATIC ACTORS
# ===========================

def generate_level_1_static_actors(base_index: int = 0) -> int:
    """Generate 50 static actor scenarios"""
    level_dir = os.path.join(BASE_DIR, "01_static_actors")
    scenarios_count = SCENARIO_LEVELS["01_static_actors"]
    
    print("\n" + "="*60)
    print("LEVEL 1: STATIC ACTORS (50 scenarios)")
    print("="*60)
    
    for i in range(scenarios_count):
        scenario_index = base_index + i
        ego_model, actor_model, color_name, weather = get_scenario_variables(scenario_index)
        
        # Alternate between ahead and behind
        is_ahead = i < 25
        relative_position = "ahead" if is_ahead else "behind"
        
        # Vary distances
        distance_categories = [(10, 25), (26, 45), (46, 70)]
        distance_min, distance_max = distance_categories[i % 3]
        
        scenario_name = f"static_actor_{i+1:03d}"
        
        # Natural language description
        avg_distance = (distance_min + distance_max) // 2
        vehicle_name = actor_model.split('.')[-1].replace('_', ' ').title()
        description = (f"A {color_name} {vehicle_name} is parked {avg_distance} meters "
                      f"{relative_position} of the ego vehicle. It remains completely "
                      f"stationary throughout the scenario.")
        
        # Create scenario data
        scenario_data = {
            "scenario_name": scenario_name,
            "description": f"Static actor {relative_position} - {color_name} vehicle",
            "weather": weather,
            "ego_vehicle_model": ego_model,
            "ego_spawn": create_ego_spawn(),
            "ego_start_speed": 0,
            "actors": [
                create_actor(
                    "actor_1",
                    actor_model,
                    color_name,
                    {
                        "lane_type": "Driving",
                        "distance_to_ego": {"min": distance_min, "max": distance_max},
                        "relative_position": relative_position,
                        "lane_relationship": "same_lane"
                    }
                )
            ],
            "actions": [],  # No actions for static actors
            "success_distance": 100,
            "timeout": 90,
            "collision_allowed": False
        }
        
        save_scenario(level_dir, scenario_name, scenario_data, description)
        print_progress("1", i+1, scenarios_count, color_name, ego_model)
    
    print(f"✅ Level 1 Complete: {scenarios_count} static actor scenarios generated")
    return base_index + scenarios_count

# ===========================
# LEVEL 2: MOVING ACTORS
# ===========================

def generate_level_2_moving_actors(base_index: int = 0) -> int:
    """Generate 50 moving actor scenarios"""
    level_dir = os.path.join(BASE_DIR, "02_moving_actors")
    scenarios_count = SCENARIO_LEVELS["02_moving_actors"]
    
    print("\n" + "="*60)
    print("LEVEL 2: MOVING ACTORS (50 scenarios)")
    print("="*60)
    
    trigger_distances = [15, 20, 25, 30, 35]
    speed_categories = list(SPEED_RANGES.keys())
    
    for i in range(scenarios_count):
        scenario_index = base_index + i
        ego_model, actor_model, color_name, weather = get_scenario_variables(scenario_index)
        
        # Systematic trigger distance rotation
        trigger_distance = trigger_distances[i % len(trigger_distances)]
        
        # Systematic speed category rotation
        speed_category = speed_categories[i % len(speed_categories)]
        speed_value = get_random_speed(speed_category)
        
        # Mix ahead and behind positions
        is_ahead = i % 2 == 0
        relative_position = "ahead" if is_ahead else "behind"
        
        # Distance ranges
        distance_min = 30 if is_ahead else 35
        distance_max = 50 if is_ahead else 55
        
        scenario_name = f"moving_actor_{i+1:03d}"
        
        # Natural language description
        vehicle_name = actor_model.split('.')[-1].replace('_', ' ').title()
        avg_distance = (distance_min + distance_max) // 2
        description = (f"A {color_name} {vehicle_name} is positioned {avg_distance} meters "
                      f"{relative_position} of the ego vehicle. When the ego approaches within "
                      f"{trigger_distance} meters, the {vehicle_name} begins moving at {speed_value} m/s forward.")
        
        # Create scenario data
        scenario_data = {
            "scenario_name": scenario_name,
            "description": f"Moving actor triggered by proximity - {color_name} {speed_category} speed",
            "weather": weather,
            "ego_vehicle_model": ego_model,
            "ego_spawn": create_ego_spawn(),
            "ego_start_speed": 0,
            "actors": [
                create_actor(
                    "actor_1",
                    actor_model,
                    color_name,
                    {
                        "lane_type": "Driving",
                        "distance_to_ego": {"min": distance_min, "max": distance_max},
                        "relative_position": relative_position,
                        "lane_relationship": "same_lane"
                    }
                )
            ],
            "actions": [
                {
                    "actor_id": "actor_1",
                    "action_type": "speed",
                    "trigger_type": "distance_to_ego",
                    "trigger_value": trigger_distance,
                    "trigger_comparison": "<",
                    "speed_value": speed_value,
                    "dynamics_dimension": "time",
                    "dynamics_value": 2.0,
                    "dynamics_shape": "linear",
                    "delay": 0.2
                }
            ],
            "success_distance": 100,
            "timeout": 90,
            "collision_allowed": False
        }
        
        save_scenario(level_dir, scenario_name, scenario_data, description)
        print_progress("2", i+1, scenarios_count, color_name, ego_model)
    
    print(f"✅ Level 2 Complete: {scenarios_count} moving actor scenarios generated")
    return base_index + scenarios_count

# ===========================
# LEVEL 3: SPEED CHANGES
# ===========================

def generate_level_3_speed_changes(base_index: int = 0) -> int:
    """Generate 50 speed change scenarios"""
    level_dir = os.path.join(BASE_DIR, "03_speed_changes")
    scenarios_count = SCENARIO_LEVELS["03_speed_changes"]
    
    print("\n" + "="*60)
    print("LEVEL 3: SPEED CHANGES (50 scenarios)")
    print("="*60)
    
    dynamics_times = [1.0, 1.5, 2.0, 2.5, 3.0]
    
    for i in range(scenarios_count):
        scenario_index = base_index + i
        ego_model, actor_model, color_name, weather = get_scenario_variables(scenario_index)
        
        # Speed transition patterns
        transition_patterns = [
            ("slow", "fast"),
            ("fast", "slow"),
            ("medium", "very_slow"),
            ("very_slow", "medium"),
            ("slow", "medium")
        ]
        
        pattern_index = i % len(transition_patterns)
        speed1_cat, speed2_cat = transition_patterns[pattern_index]
        speed1 = get_random_speed(speed1_cat)
        speed2 = get_random_speed(speed2_cat)
        
        # Timing variation
        dynamics_time = dynamics_times[i % len(dynamics_times)]
        
        # Position mix (30 ahead, 20 behind)
        is_ahead = i < 30
        relative_position = "ahead" if is_ahead else "behind"
        
        distance_min = 35 if is_ahead else 30
        distance_max = 55 if is_ahead else 50
        
        scenario_name = f"speed_change_{i+1:03d}"
        
        # Natural language description
        vehicle_name = actor_model.split('.')[-1].replace('_', ' ').title()
        description = (f"A {color_name} {vehicle_name} initially moves at {speed1} m/s, "
                      f"then changes to {speed2} m/s after the first action completes.")
        
        # Create scenario data
        scenario_data = {
            "scenario_name": scenario_name,
            "description": f"Speed change scenario - {speed1_cat} to {speed2_cat}",
            "weather": weather,
            "ego_vehicle_model": ego_model,
            "ego_spawn": create_ego_spawn(),
            "ego_start_speed": 0,
            "actors": [
                create_actor(
                    "actor_1",
                    actor_model,
                    color_name,
                    {
                        "lane_type": "Driving",
                        "distance_to_ego": {"min": distance_min, "max": distance_max},
                        "relative_position": relative_position,
                        "lane_relationship": "same_lane"
                    }
                )
            ],
            "actions": [
                {
                    "actor_id": "actor_1",
                    "action_type": "speed",
                    "trigger_type": "distance_to_ego",
                    "trigger_value": 30,
                    "trigger_comparison": "<",
                    "speed_value": speed1,
                    "dynamics_dimension": "time",
                    "dynamics_value": dynamics_time,
                    "dynamics_shape": "linear",
                    "delay": 0.2
                },
                {
                    "actor_id": "actor_1",
                    "action_type": "speed",
                    "trigger_type": "after_previous",
                    "trigger_value": 0,
                    "trigger_comparison": "=",
                    "speed_value": speed2,
                    "dynamics_dimension": "time",
                    "dynamics_value": dynamics_time,
                    "dynamics_shape": "linear",
                    "delay": 0.5
                }
            ],
            "success_distance": 120,
            "timeout": 100,
            "collision_allowed": False
        }
        
        save_scenario(level_dir, scenario_name, scenario_data, description)
        print_progress("3", i+1, scenarios_count, color_name, ego_model)
    
    print(f"✅ Level 3 Complete: {scenarios_count} speed change scenarios generated")
    return base_index + scenarios_count

# ===========================
# LEVEL 4: STOP AND START
# ===========================

def generate_level_4_stop_start(base_index: int = 0) -> int:
    """Generate 50 stop and start scenarios"""
    level_dir = os.path.join(BASE_DIR, "04_stop_start")
    scenarios_count = SCENARIO_LEVELS["04_stop_start"]
    
    print("\n" + "="*60)
    print("LEVEL 4: STOP AND START (50 scenarios)")
    print("="*60)
    
    wait_durations = [1.0, 2.0, 3.0, 4.0, 5.0]
    
    for i in range(scenarios_count):
        scenario_index = base_index + i
        ego_model, actor_model, color_name, weather = get_scenario_variables(scenario_index)
        
        # Wait duration rotation
        wait_duration = wait_durations[i % len(wait_durations)]
        
        # Speed patterns
        initial_speed = get_random_speed(["slow", "medium"][i % 2])
        final_speed = get_random_speed(["slow", "medium", "fast"][i % 3])
        
        # Position variety
        is_ahead = i % 2 == 0
        relative_position = "ahead" if is_ahead else "behind"
        
        distance_min = 30 if is_ahead else 35
        distance_max = 50 if is_ahead else 55
        
        scenario_name = f"stop_start_{i+1:03d}"
        
        # Natural language description
        vehicle_name = actor_model.split('.')[-1].replace('_', ' ').title()
        description = (f"A {color_name} {vehicle_name} moves at {initial_speed} m/s, "
                      f"then stops completely for {wait_duration} seconds, "
                      f"then continues moving at {final_speed} m/s.")
        
        # Create scenario data
        scenario_data = {
            "scenario_name": scenario_name,
            "description": f"Stop and start with {wait_duration}s wait",
            "weather": weather,
            "ego_vehicle_model": ego_model,
            "ego_spawn": create_ego_spawn(),
            "ego_start_speed": 0,
            "actors": [
                create_actor(
                    "actor_1",
                    actor_model,
                    color_name,
                    {
                        "lane_type": "Driving",
                        "distance_to_ego": {"min": distance_min, "max": distance_max},
                        "relative_position": relative_position,
                        "lane_relationship": "same_lane"
                    }
                )
            ],
            "actions": [
                {
                    "actor_id": "actor_1",
                    "action_type": "speed",
                    "trigger_type": "distance_to_ego",
                    "trigger_value": 35,
                    "trigger_comparison": "<",
                    "speed_value": initial_speed,
                    "dynamics_dimension": "time",
                    "dynamics_value": 2.0,
                    "dynamics_shape": "linear",
                    "delay": 0.2
                },
                {
                    "actor_id": "actor_1",
                    "action_type": "speed",
                    "trigger_type": "after_previous",
                    "trigger_value": 0,
                    "trigger_comparison": "=",
                    "speed_value": 0.0,
                    "dynamics_dimension": "time",
                    "dynamics_value": 1.5,
                    "dynamics_shape": "linear",
                    "delay": 2.0
                },
                {
                    "actor_id": "actor_1",
                    "action_type": "wait",
                    "trigger_type": "after_previous",
                    "trigger_value": 0,
                    "trigger_comparison": "=",
                    "wait_duration": wait_duration
                },
                {
                    "actor_id": "actor_1",
                    "action_type": "speed",
                    "trigger_type": "after_previous",
                    "trigger_value": 0,
                    "trigger_comparison": "=",
                    "speed_value": final_speed,
                    "dynamics_dimension": "time",
                    "dynamics_value": 2.0,
                    "dynamics_shape": "linear",
                    "delay": 0.2
                }
            ],
            "success_distance": 150,
            "timeout": 120,
            "collision_allowed": False
        }
        
        save_scenario(level_dir, scenario_name, scenario_data, description)
        print_progress("4", i+1, scenarios_count, color_name, ego_model)
    
    print(f"✅ Level 4 Complete: {scenarios_count} stop and start scenarios generated")
    return base_index + scenarios_count

# ===========================
# LEVEL 5: MULTI-ACTORS
# ===========================

def generate_level_5_multi_actors(base_index: int = 0) -> int:
    """Generate 60 multi-actor scenarios"""
    level_dir = os.path.join(BASE_DIR, "05_multi_actors")
    scenarios_count = SCENARIO_LEVELS["05_multi_actors"]
    
    print("\n" + "="*60)
    print("LEVEL 5: MULTI-ACTORS (60 scenarios)")
    print("="*60)
    
    for i in range(scenarios_count):
        scenario_index = base_index + i
        ego_model, _, _, weather = get_scenario_variables(scenario_index)
        
        # Determine number of actors (40 two-actor, 20 three-actor)
        num_actors = 2 if i < 40 else 3
        
        scenario_name = f"multi_actor_{i+1:03d}"
        
        # Create actors with different colors
        actors = []
        actions = []
        color_list = list(COLORS.keys())
        
        for actor_num in range(num_actors):
            # Rotate through colors for diversity
            color_index = (scenario_index + actor_num * 5) % len(color_list)
            color_name = color_list[color_index]
            
            # Rotate through actor models
            actor_model = ACTOR_MODELS[(scenario_index + actor_num) % len(ACTOR_MODELS)]
            
            # Vary positions
            position_patterns = [
                ("ahead", 30, 50),
                ("behind", 25, 45),
                ("ahead", 50, 70)
            ]
            relative_position, dist_min, dist_max = position_patterns[actor_num % 3]
            
            # Different lane relationships for variety
            lane_relationships = ["same_lane", "adjacent_left", "adjacent_right"]
            lane_rel = lane_relationships[actor_num % 3] if actor_num > 0 else "same_lane"
            
            actor_id = f"actor_{actor_num + 1}"
            
            actors.append(
                create_actor(
                    actor_id,
                    actor_model,
                    color_name,
                    {
                        "lane_type": "Driving",
                        "distance_to_ego": {"min": dist_min, "max": dist_max},
                        "relative_position": relative_position,
                        "lane_relationship": lane_rel
                    }
                )
            )
            
            # Add varied actions for each actor
            speed = get_random_speed(["slow", "medium", "fast"][actor_num % 3])
            trigger_distance = 20 + (actor_num * 5)
            
            actions.append({
                "actor_id": actor_id,
                "action_type": "speed",
                "trigger_type": "distance_to_ego",
                "trigger_value": trigger_distance,
                "trigger_comparison": "<",
                "speed_value": speed,
                "dynamics_dimension": "time",
                "dynamics_value": 2.0,
                "dynamics_shape": "linear",
                "delay": 0.2 + (actor_num * 0.3)
            })
        
        # Natural language description
        if num_actors == 2:
            description = (f"A {actors[0]['color'].split(',')[0]} vehicle is {actors[0]['spawn']['criteria']['distance_to_ego']['min']}m "
                          f"{actors[0]['spawn']['criteria']['relative_position']} moving at {actions[0]['speed_value']} m/s. "
                          f"A {actors[1]['color'].split(',')[0]} vehicle is {actors[1]['spawn']['criteria']['distance_to_ego']['min']}m "
                          f"{actors[1]['spawn']['criteria']['relative_position']} and accelerates when ego gets within "
                          f"{actions[1]['trigger_value']}m.")
        else:
            description = f"Three actors with independent behaviors: multiple colored vehicles at different positions and speeds."
        
        # Create scenario data
        scenario_data = {
            "scenario_name": scenario_name,
            "description": f"Multi-actor scenario with {num_actors} actors",
            "weather": weather,
            "ego_vehicle_model": ego_model,
            "ego_spawn": create_ego_spawn(),
            "ego_start_speed": 0,
            "actors": actors,
            "actions": actions,
            "success_distance": 150,
            "timeout": 120,
            "collision_allowed": False
        }
        
        save_scenario(level_dir, scenario_name, scenario_data, description)
        print_progress("5", i+1, scenarios_count, actors[0]['color'].split(',')[0], ego_model)
    
    print(f"✅ Level 5 Complete: {scenarios_count} multi-actor scenarios generated")
    return base_index + scenarios_count

# ===========================
# LEVEL 6: INTERACTIONS
# ===========================

def generate_level_6_interactions(base_index: int = 0) -> int:
    """Generate 40 interaction scenarios"""
    level_dir = os.path.join(BASE_DIR, "06_interactions")
    scenarios_count = SCENARIO_LEVELS["06_interactions"]
    
    print("\n" + "="*60)
    print("LEVEL 6: INTERACTIONS (40 scenarios)")
    print("="*60)
    
    for i in range(scenarios_count):
        scenario_index = base_index + i
        ego_model, _, _, weather = get_scenario_variables(scenario_index)
        
        scenario_name = f"interaction_{i+1:03d}"
        
        # Interaction patterns
        interaction_types = [
            "lane_change",
            "following",
            "responsive_speed",
            "complex_trigger"
        ]
        
        interaction_type = interaction_types[i % len(interaction_types)]
        
        # Get two different colors for actors
        color_list = list(COLORS.keys())
        color1 = color_list[scenario_index % len(color_list)]
        color2 = color_list[(scenario_index + 7) % len(color_list)]  # Offset for different color
        
        # Get different actor models
        actor1_model = ACTOR_MODELS[scenario_index % len(ACTOR_MODELS)]
        actor2_model = ACTOR_MODELS[(scenario_index + 3) % len(ACTOR_MODELS)]
        
        if interaction_type == "lane_change":
            # Lane change scenario
            actors = [
                create_actor(
                    "actor_1",
                    actor1_model,
                    color1,
                    {
                        "lane_type": "Driving",
                        "distance_to_ego": {"min": 30, "max": 50},
                        "relative_position": "ahead",
                        "lane_relationship": "same_lane"
                    }
                ),
                create_actor(
                    "actor_2",
                    actor2_model,
                    color2,
                    {
                        "lane_type": "Driving",
                        "distance_to_ego": {"min": 20, "max": 40},
                        "relative_position": "behind",
                        "lane_relationship": "adjacent_left"
                    }
                )
            ]
            
            actions = [
                {
                    "actor_id": "actor_1",
                    "action_type": "speed",
                    "trigger_type": "distance_to_ego",
                    "trigger_value": 25,
                    "trigger_comparison": "<",
                    "speed_value": 5.0,
                    "dynamics_dimension": "time",
                    "dynamics_value": 2.0,
                    "dynamics_shape": "linear",
                    "delay": 0.2
                },
                {
                    "actor_id": "actor_2",
                    "action_type": "lane_change",
                    "trigger_type": "distance_to_actor",
                    "trigger_actor": "actor_1",
                    "trigger_value": 30,
                    "trigger_comparison": "<",
                    "lane_change_direction": "left",
                    "dynamics_dimension": "time",
                    "dynamics_value": 3.0,
                    "dynamics_shape": "sinusoidal",
                    "delay": 0.5
                }
            ]
            
            vehicle1_name = actor1_model.split('.')[-1].replace('_', ' ').title()
            vehicle2_name = actor2_model.split('.')[-1].replace('_', ' ').title()
            description = (f"A {color1} {vehicle1_name} ahead slows down. When a {color2} {vehicle2_name} "
                          f"gets close, it changes lanes to the left.")
            
        elif interaction_type == "following":
            # Following behavior
            actors = [
                create_actor(
                    "actor_1",
                    actor1_model,
                    color1,
                    {
                        "lane_type": "Driving",
                        "distance_to_ego": {"min": 20, "max": 30},
                        "relative_position": "behind",
                        "lane_relationship": "same_lane"
                    }
                )
            ]
            
            actions = [
                {
                    "actor_id": "actor_1",
                    "action_type": "follow_ego",
                    "trigger_type": "distance_to_ego",
                    "trigger_value": 25,
                    "trigger_comparison": "<",
                    "follow_distance": 15.0,
                    "speed_match": True,
                    "dynamics_dimension": "time",
                    "dynamics_value": 2.0,
                    "dynamics_shape": "linear",
                    "delay": 0.2
                }
            ]
            
            vehicle_name = actor1_model.split('.')[-1].replace('_', ' ').title()
            description = f"A {color1} {vehicle_name} follows 20m behind ego, matching ego speed."
            
        elif interaction_type == "responsive_speed":
            # Responsive speed adjustment
            actors = [
                create_actor(
                    "actor_1",
                    actor1_model,
                    color1,
                    {
                        "lane_type": "Driving",
                        "distance_to_ego": {"min": 40, "max": 60},
                        "relative_position": "ahead",
                        "lane_relationship": "same_lane"
                    }
                ),
                create_actor(
                    "actor_2",
                    actor2_model,
                    color2,
                    {
                        "lane_type": "Driving",
                        "distance_to_ego": {"min": 25, "max": 35},
                        "relative_position": "ahead",
                        "lane_relationship": "same_lane"
                    }
                )
            ]
            
            actions = [
                {
                    "actor_id": "actor_1",
                    "action_type": "speed",
                    "trigger_type": "distance_to_ego",
                    "trigger_value": 40,
                    "trigger_comparison": "<",
                    "speed_value": 6.0,
                    "dynamics_dimension": "time",
                    "dynamics_value": 2.0,
                    "dynamics_shape": "linear",
                    "delay": 0.2
                },
                {
                    "actor_id": "actor_2",
                    "action_type": "speed",
                    "trigger_type": "speed_of_actor",
                    "trigger_actor": "actor_1",
                    "trigger_value": 7.0,
                    "trigger_comparison": "<",
                    "speed_value": 5.0,
                    "dynamics_dimension": "time",
                    "dynamics_value": 1.5,
                    "dynamics_shape": "linear",
                    "delay": 0.5
                }
            ]
            
            vehicle1_name = actor1_model.split('.')[-1].replace('_', ' ').title()
            vehicle2_name = actor2_model.split('.')[-1].replace('_', ' ').title()
            description = (f"When a {color1} {vehicle1_name} ahead slows down, "
                          f"a {color2} {vehicle2_name} also reduces speed in response.")
            
        else:  # complex_trigger
            # Complex multi-condition trigger
            actors = [
                create_actor(
                    "actor_1",
                    actor1_model,
                    color1,
                    {
                        "lane_type": "Driving",
                        "distance_to_ego": {"min": 35, "max": 55},
                        "relative_position": "ahead",
                        "lane_relationship": "adjacent_right"
                    }
                ),
                create_actor(
                    "actor_2",
                    actor2_model,
                    color2,
                    {
                        "lane_type": "Driving",
                        "distance_to_ego": {"min": 30, "max": 45},
                        "relative_position": "behind",
                        "lane_relationship": "same_lane"
                    }
                )
            ]
            
            actions = [
                {
                    "actor_id": "actor_1",
                    "action_type": "speed",
                    "trigger_type": "distance_to_ego",
                    "trigger_value": 30,
                    "trigger_comparison": "<",
                    "speed_value": 10.0,
                    "dynamics_dimension": "time",
                    "dynamics_value": 2.0,
                    "dynamics_shape": "linear",
                    "delay": 0.2
                },
                {
                    "actor_id": "actor_2",
                    "action_type": "speed",
                    "trigger_type": "complex",
                    "trigger_conditions": [
                        {"type": "distance_to_ego", "value": 20, "comparison": "<"},
                        {"type": "distance_to_actor", "actor": "actor_1", "value": 40, "comparison": "<"}
                    ],
                    "trigger_logic": "AND",
                    "speed_value": 12.0,
                    "dynamics_dimension": "time",
                    "dynamics_value": 2.5,
                    "dynamics_shape": "linear",
                    "delay": 0.3
                }
            ]
            
            vehicle1_name = actor1_model.split('.')[-1].replace('_', ' ').title()
            vehicle2_name = actor2_model.split('.')[-1].replace('_', ' ').title()
            description = (f"Complex interaction: A {color2} {vehicle2_name} accelerates only when both "
                          f"close to ego AND near a {color1} {vehicle1_name} in adjacent lane.")
        
        # Create scenario data
        scenario_data = {
            "scenario_name": scenario_name,
            "description": f"Interaction scenario - {interaction_type}",
            "weather": weather,
            "ego_vehicle_model": ego_model,
            "ego_spawn": create_ego_spawn(),
            "ego_start_speed": 0,
            "actors": actors,
            "actions": actions,
            "success_distance": 150,
            "timeout": 120,
            "collision_allowed": False
        }
        
        save_scenario(level_dir, scenario_name, scenario_data, description)
        print_progress("6", i+1, scenarios_count, color1, ego_model)
    
    print(f"✅ Level 6 Complete: {scenarios_count} interaction scenarios generated")
    return base_index + scenarios_count

# ===========================
# VALIDATION AND REPORTING
# ===========================

def validate_scenarios():
    """Validate generated scenarios and create summary report"""
    print("\n" + "="*60)
    print("VALIDATING SCENARIOS")
    print("="*60)
    
    total_scenarios = 0
    validation_results = {}
    color_usage = {color: 0 for color in COLORS.keys()}
    ego_model_usage = {model: 0 for model in EGO_MODELS}
    actor_model_usage = {model: 0 for model in ACTOR_MODELS}
    weather_usage = {weather: 0 for weather in WEATHER_CONDITIONS}
    
    for level_dir, expected_count in SCENARIO_LEVELS.items():
        dir_path = os.path.join(BASE_DIR, level_dir)
        
        if not os.path.exists(dir_path):
            print(f"❌ Directory missing: {dir_path}")
            validation_results[level_dir] = {"status": "missing", "count": 0}
            continue
        
        # Count JSON files
        json_files = [f for f in os.listdir(dir_path) if f.endswith('.json') and not f.endswith('_description.json')]
        actual_count = len(json_files)
        
        # Validate each scenario
        valid_scenarios = 0
        for json_file in json_files:
            json_path = os.path.join(dir_path, json_file)
            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)
                
                # Check required fields
                required_fields = ["scenario_name", "weather", "ego_vehicle_model", "actors", "actions"]
                if all(field in data for field in required_fields):
                    valid_scenarios += 1
                    
                    # Track usage statistics
                    weather_usage[data.get("weather", "")] = weather_usage.get(data.get("weather", ""), 0) + 1
                    ego_model_usage[data.get("ego_vehicle_model", "")] = ego_model_usage.get(data.get("ego_vehicle_model", ""), 0) + 1
                    
                    # Track actor colors and models
                    for actor in data.get("actors", []):
                        if "color" in actor:
                            # Extract color name from RGB
                            for color_name, rgb in COLORS.items():
                                if actor["color"] == rgb:
                                    color_usage[color_name] += 1
                                    break
                        
                        model = actor.get("model", "")
                        if model in ACTOR_MODELS:
                            actor_model_usage[model] += 1
                
            except Exception as e:
                print(f"  ⚠️  Error validating {json_file}: {e}")
        
        validation_results[level_dir] = {
            "status": "✅" if actual_count == expected_count else "⚠️",
            "expected": expected_count,
            "actual": actual_count,
            "valid": valid_scenarios
        }
        
        total_scenarios += actual_count
        print(f"  {level_dir}: {actual_count}/{expected_count} scenarios ({valid_scenarios} valid)")
    
    # Generate summary report
    print("\n" + "="*60)
    print("SUMMARY REPORT")
    print("="*60)
    
    print(f"\nTotal Scenarios Generated: {total_scenarios}/300")
    
    print("\n📊 Level Breakdown:")
    for level, result in validation_results.items():
        if result["status"] != "missing":
            print(f"  {result['status']} {level}: {result['actual']}/{result['expected']} ({result['valid']} valid)")
    
    print("\n🎨 Color Distribution:")
    for color, count in sorted(color_usage.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total_scenarios * 100) if total_scenarios > 0 else 0
        print(f"  {color:12s}: {count:3d} uses ({percentage:.1f}%)")
    
    print("\n🚗 Ego Model Distribution:")
    for model, count in sorted(ego_model_usage.items(), key=lambda x: x[1], reverse=True)[:5]:
        model_name = model.split('.')[-1]
        print(f"  {model_name:15s}: {count:3d} uses")
    
    print("\n🌤️  Weather Distribution:")
    for weather, count in sorted(weather_usage.items(), key=lambda x: x[1], reverse=True):
        print(f"  {weather:15s}: {count:3d} uses")
    
    # Save summary to file
    summary_path = os.path.join(BASE_DIR, "generation_summary.json")
    summary_data = {
        "generation_time": datetime.now().isoformat(),
        "total_scenarios": total_scenarios,
        "target_scenarios": 300,
        "levels": validation_results,
        "color_usage": color_usage,
        "ego_model_usage": ego_model_usage,
        "weather_usage": weather_usage
    }
    
    with open(summary_path, 'w') as f:
        json.dump(summary_data, f, indent=2)
    
    print(f"\n📝 Summary saved to: {summary_path}")
    
    return total_scenarios == 300

# ===========================
# MAIN EXECUTION
# ===========================

def main():
    """Main execution function"""
    print("\n" + "="*60)
    print(" GENERATING 300 BASIC CARLA SCENARIOS")
    print(" Systematic Variable Coverage Edition")
    print("="*60)
    
    # Create base directory
    os.makedirs(BASE_DIR, exist_ok=True)
    
    # Generate scenarios for each level
    current_index = 0
    
    # Level 1: Static Actors
    current_index = generate_level_1_static_actors(current_index)
    
    # Level 2: Moving Actors
    current_index = generate_level_2_moving_actors(current_index)
    
    # Level 3: Speed Changes
    current_index = generate_level_3_speed_changes(current_index)
    
    # Level 4: Stop and Start
    current_index = generate_level_4_stop_start(current_index)
    
    # Level 5: Multi-Actors
    current_index = generate_level_5_multi_actors(current_index)
    
    # Level 6: Interactions
    current_index = generate_level_6_interactions(current_index)
    
    # Validate and report
    success = validate_scenarios()
    
    if success:
        print("\n" + "="*60)
        print("✅ SUCCESS: All 300 scenarios generated successfully!")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("⚠️  WARNING: Scenario generation incomplete. Check logs above.")
        print("="*60)
    
    print(f"\n📁 Scenarios saved in: {os.path.abspath(BASE_DIR)}/")
    print("\n🎯 Ready for LLM training with comprehensive variable coverage!")

if __name__ == "__main__":
    main()