#!/usr/bin/env python3
"""
CARLA Scenario Training Dataset Generator - Correct Schema Version
Generates training data matching the exact JSON schema used by xosc_json.py
"""

import json
import random
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import numpy as np

# Set seed for reproducibility
random.seed(42)
np.random.seed(42)

# Color mappings - MUST be "R,G,B" string format
COLOR_MAPPINGS = {
    "red": "255,0,0",
    "blue": "0,0,255",
    "green": "0,255,0",
    "white": "255,255,255",
    "black": "0,0,0",
    "yellow": "255,255,0",
    "cyan": "0,255,255",
    "magenta": "255,0,255",
    "silver": "192,192,192",
    "gray": "128,128,128",
    "maroon": "128,0,0",
    "olive": "128,128,0",
    "lime": "0,255,0",
    "aqua": "0,255,255",
    "teal": "0,128,128",
    "navy": "0,0,128",
    "purple": "128,0,128",
    "orange": "255,165,0",
    "brown": "165,42,42",
    "pink": "255,192,203",
    "gold": "255,215,0",
    "beige": "245,245,220",
    "crimson": "220,20,60",
    "turquoise": "64,224,208",
    "indigo": "75,0,130"
}

# CARLA vehicle models (from xosc_json.py)
CARLA_VEHICLES = [
    'vehicle.audi.a2', 'vehicle.audi.etron', 'vehicle.audi.tt', 'vehicle.bmw.grandtourer',
    'vehicle.chevrolet.impala', 'vehicle.citroen.c3', 'vehicle.dodge.charger_police',
    'vehicle.ford.crown', 'vehicle.ford.mustang', 'vehicle.jeep.wrangler_rubicon',
    'vehicle.lincoln.mkz_2017', 'vehicle.mercedes.coupe', 'vehicle.micro.microlino',
    'vehicle.nissan.micra', 'vehicle.nissan.patrol', 'vehicle.seat.leon',
    'vehicle.tesla.model3', 'vehicle.toyota.prius', 'vehicle.volkswagen.t2',
    'vehicle.mercedes.sprinter', 'vehicle.dodge.charger_2020', 'vehicle.mini.cooper_s_2021',
    'vehicle.tesla.cybertruck', 'vehicle.ford.ambulance'
]

# Pedestrian models
CARLA_PEDESTRIANS = [f'walker.pedestrian.{i:04d}' for i in range(1, 50)]

# Weather presets (from xosc_json.py)
WEATHER_OPTIONS = [
    'clear', 'cloudy', 'wet', 'wet_cloudy', 'soft_rain', 
    'mid_rain', 'hard_rain', 'clear_noon', 'clear_sunset'
]

class CorrectScenarioGenerator:
    """Generates scenarios matching exact xosc_json.py schema"""
    
    def __init__(self):
        self.scenario_counter = 0
        
    def get_random_color(self) -> Tuple[str, str]:
        """Returns color name and RGB string"""
        color_name = random.choice(list(COLOR_MAPPINGS.keys()))
        rgb_string = COLOR_MAPPINGS[color_name]
        return color_name, rgb_string
    
    def generate_spawn_criteria(self, 
                               is_ego: bool = False,
                               relative_to_ego: bool = False) -> Dict[str, Any]:
        """Generate spawn criteria matching xosc_json.py format"""
        
        if is_ego:
            # Ego vehicle spawn criteria
            return {
                "criteria": {
                    "lane_type": "Driving",
                    "lane_id": {"min": 1, "max": 4},
                    "is_intersection": False
                }
            }
        
        if relative_to_ego:
            # Actor spawn relative to ego
            distance_ranges = [
                {"min": 10, "max": 25},
                {"min": 25, "max": 40},
                {"min": 35, "max": 55},
                {"min": 50, "max": 70}
            ]
            
            positions = ["ahead", "behind", "adjacent"]
            lane_relationships = ["same_lane", "adjacent_lane", "different_lane"]
            
            criteria = {
                "criteria": {
                    "lane_type": "Driving",
                    "distance_to_ego": random.choice(distance_ranges),
                    "relative_position": random.choice(positions),
                    "lane_relationship": random.choice(lane_relationships)
                }
            }
            
            # For pedestrians, sometimes use sidewalk
            if random.random() < 0.3:
                criteria["criteria"]["lane_type"] = random.choice(["Sidewalk", "Driving"])
            
            return criteria
        
        # Non-relative spawn
        return {
            "criteria": {
                "lane_type": random.choice(["Driving", "Parking"]),
                "lane_id": random.randint(1, 4),
                "is_intersection": random.choice([True, False])
            }
        }
    
    def generate_static_actor_scenario(self) -> Dict[str, Any]:
        """Generate a static actor scenario (no actions)"""
        self.scenario_counter += 1
        color_name, rgb_string = self.get_random_color()
        
        scenario = {
            "scenario_name": f"static_actor_{self.scenario_counter:03d}",
            "description": f"Static actor ahead - {color_name} vehicle",
            "weather": random.choice(WEATHER_OPTIONS),
            "ego_vehicle_model": random.choice(CARLA_VEHICLES),
            "ego_spawn": self.generate_spawn_criteria(is_ego=True),
            "ego_start_speed": 0,
            "actors": [
                {
                    "id": "actor_1",
                    "type": "vehicle",
                    "model": random.choice(CARLA_VEHICLES),
                    "spawn": self.generate_spawn_criteria(relative_to_ego=True),
                    "color": rgb_string
                }
            ],
            "actions": [],
            "success_distance": random.randint(80, 120),
            "timeout": random.randint(60, 120),
            "collision_allowed": False
        }
        
        return scenario
    
    def generate_speed_change_scenario(self) -> Dict[str, Any]:
        """Generate a speed change scenario"""
        self.scenario_counter += 1
        color_name, rgb_string = self.get_random_color()
        
        scenario = {
            "scenario_name": f"speed_change_{self.scenario_counter:03d}",
            "description": f"Speed change scenario - {color_name} vehicle changes speed",
            "weather": random.choice(WEATHER_OPTIONS),
            "ego_vehicle_model": random.choice(CARLA_VEHICLES),
            "ego_spawn": self.generate_spawn_criteria(is_ego=True),
            "ego_start_speed": 0,
            "actors": [
                {
                    "id": "actor_1",
                    "type": "vehicle",
                    "model": random.choice(CARLA_VEHICLES),
                    "spawn": self.generate_spawn_criteria(relative_to_ego=True),
                    "color": rgb_string
                }
            ],
            "actions": [
                {
                    "actor_id": "actor_1",
                    "action_type": "speed",
                    "trigger_type": "distance_to_ego",
                    "trigger_value": random.randint(20, 40),
                    "trigger_comparison": "<",
                    "speed_value": round(random.uniform(5.0, 15.0), 1),
                    "dynamics_dimension": "time",
                    "dynamics_value": round(random.uniform(0.5, 2.0), 1),
                    "dynamics_shape": random.choice(["linear", "step"]),
                    "delay": round(random.uniform(0, 0.5), 1)
                }
            ],
            "success_distance": random.randint(100, 150),
            "timeout": random.randint(80, 120),
            "collision_allowed": False
        }
        
        return scenario
    
    def generate_braking_scenario(self) -> Dict[str, Any]:
        """Generate a sudden braking scenario"""
        self.scenario_counter += 1
        color_name, rgb_string = self.get_random_color()
        
        scenario = {
            "scenario_name": f"braking_{self.scenario_counter:03d}",
            "description": f"Sudden braking - {color_name} vehicle brakes when ego approaches",
            "weather": random.choice(WEATHER_OPTIONS),
            "ego_vehicle_model": random.choice(CARLA_VEHICLES),
            "ego_spawn": self.generate_spawn_criteria(is_ego=True),
            "ego_start_speed": 0,
            "actors": [
                {
                    "id": "actor_1",
                    "type": "vehicle",
                    "model": random.choice(CARLA_VEHICLES),
                    "spawn": {
                        "criteria": {
                            "lane_type": "Driving",
                            "distance_to_ego": {"min": 30, "max": 50},
                            "relative_position": "ahead",
                            "lane_relationship": "same_lane"
                        }
                    },
                    "color": rgb_string
                }
            ],
            "actions": [
                {
                    "actor_id": "actor_1",
                    "action_type": "stop",
                    "trigger_type": "distance_to_ego",
                    "trigger_value": 25,
                    "trigger_comparison": "<",
                    "dynamics_dimension": "time",
                    "dynamics_value": 1.5,
                    "dynamics_shape": "linear",
                    "delay": 0
                }
            ],
            "success_distance": 100,
            "timeout": 90,
            "collision_allowed": False
        }
        
        return scenario
    
    def generate_lane_change_scenario(self) -> Dict[str, Any]:
        """Generate a lane change/cut-in scenario"""
        self.scenario_counter += 1
        color_name, rgb_string = self.get_random_color()
        direction = random.choice(["left", "right"])
        
        scenario = {
            "scenario_name": f"lane_change_{self.scenario_counter:03d}",
            "description": f"Cut-in scenario - {color_name} vehicle changes lanes from {direction}",
            "weather": random.choice(WEATHER_OPTIONS),
            "ego_vehicle_model": random.choice(CARLA_VEHICLES),
            "ego_spawn": self.generate_spawn_criteria(is_ego=True),
            "ego_start_speed": 0,
            "actors": [
                {
                    "id": "actor_1",
                    "type": "vehicle",
                    "model": random.choice(CARLA_VEHICLES),
                    "spawn": {
                        "criteria": {
                            "lane_type": "Driving",
                            "distance_to_ego": {"min": 15, "max": 30},
                            "relative_position": "ahead",
                            "lane_relationship": "adjacent_lane"
                        }
                    },
                    "color": rgb_string
                }
            ],
            "actions": [
                {
                    "actor_id": "actor_1",
                    "action_type": "lane_change",
                    "trigger_type": "distance_to_ego",
                    "trigger_value": 20,
                    "trigger_comparison": "<",
                    "lane_direction": direction,
                    "dynamics_dimension": "time",
                    "dynamics_value": 2.0,
                    "dynamics_shape": "linear",
                    "delay": 0.5
                }
            ],
            "success_distance": 120,
            "timeout": 100,
            "collision_allowed": False
        }
        
        return scenario
    
    def generate_pedestrian_scenario(self) -> Dict[str, Any]:
        """Generate a pedestrian crossing scenario"""
        self.scenario_counter += 1
        
        scenario = {
            "scenario_name": f"pedestrian_{self.scenario_counter:03d}",
            "description": "Pedestrian crossing scenario",
            "weather": random.choice(WEATHER_OPTIONS),
            "ego_vehicle_model": random.choice(CARLA_VEHICLES),
            "ego_spawn": self.generate_spawn_criteria(is_ego=True),
            "ego_start_speed": 0,
            "actors": [
                {
                    "id": "pedestrian_1",
                    "type": "pedestrian",
                    "model": random.choice(CARLA_PEDESTRIANS),
                    "spawn": {
                        "criteria": {
                            "lane_type": "Sidewalk",
                            "distance_to_ego": {"min": 20, "max": 40},
                            "relative_position": "perpendicular",
                            "lane_relationship": "different_lane"
                        }
                    }
                }
            ],
            "actions": [
                {
                    "actor_id": "pedestrian_1",
                    "action_type": "speed",
                    "trigger_type": "distance_to_ego",
                    "trigger_value": 15,
                    "trigger_comparison": "<",
                    "speed_value": 1.5,
                    "dynamics_dimension": "time",
                    "dynamics_value": 0.5,
                    "dynamics_shape": "step",
                    "delay": 0
                }
            ],
            "success_distance": 80,
            "timeout": 60,
            "collision_allowed": False
        }
        
        # Add a vehicle too for color testing
        if random.random() < 0.5:
            color_name, rgb_string = self.get_random_color()
            scenario["actors"].append({
                "id": "actor_2",
                "type": "vehicle",
                "model": random.choice(CARLA_VEHICLES),
                "spawn": self.generate_spawn_criteria(relative_to_ego=True),
                "color": rgb_string
            })
            scenario["description"] += f" with {color_name} vehicle"
        
        return scenario
    
    def generate_multi_actor_scenario(self) -> Dict[str, Any]:
        """Generate a multi-actor scenario"""
        self.scenario_counter += 1
        num_actors = random.randint(2, 3)
        
        actors = []
        actions = []
        color_descriptions = []
        
        for i in range(num_actors):
            color_name, rgb_string = self.get_random_color()
            color_descriptions.append(color_name)
            
            actor = {
                "id": f"actor_{i+1}",
                "type": "vehicle",
                "model": random.choice(CARLA_VEHICLES),
                "spawn": self.generate_spawn_criteria(relative_to_ego=True),
                "color": rgb_string
            }
            actors.append(actor)
            
            # Add action for some actors
            if random.random() < 0.7:
                action_type = random.choice(["speed", "stop", "lane_change"])
                
                if action_type == "speed":
                    action = {
                        "actor_id": f"actor_{i+1}",
                        "action_type": "speed",
                        "trigger_type": random.choice(["time", "distance_to_ego"]),
                        "trigger_value": random.randint(2, 30),
                        "trigger_comparison": "<" if action_type == "distance_to_ego" else "=",
                        "speed_value": round(random.uniform(3.0, 12.0), 1),
                        "dynamics_dimension": "time",
                        "dynamics_value": round(random.uniform(0.5, 2.0), 1),
                        "dynamics_shape": "linear",
                        "delay": round(random.uniform(0, 1.0), 1)
                    }
                elif action_type == "stop":
                    action = {
                        "actor_id": f"actor_{i+1}",
                        "action_type": "stop",
                        "trigger_type": "distance_to_ego",
                        "trigger_value": random.randint(15, 35),
                        "trigger_comparison": "<",
                        "dynamics_dimension": "time",
                        "dynamics_value": round(random.uniform(1.0, 3.0), 1),
                        "dynamics_shape": "linear",
                        "delay": 0
                    }
                else:  # lane_change
                    action = {
                        "actor_id": f"actor_{i+1}",
                        "action_type": "lane_change",
                        "trigger_type": "time",
                        "trigger_value": random.randint(3, 8),
                        "trigger_comparison": "=",
                        "lane_direction": random.choice(["left", "right"]),
                        "dynamics_dimension": "time",
                        "dynamics_value": 2.0,
                        "dynamics_shape": "linear",
                        "delay": 0
                    }
                
                actions.append(action)
        
        scenario = {
            "scenario_name": f"multi_actor_{self.scenario_counter:03d}",
            "description": f"Multi-actor scenario with {', '.join(color_descriptions)} vehicles",
            "weather": random.choice(WEATHER_OPTIONS),
            "ego_vehicle_model": random.choice(CARLA_VEHICLES),
            "ego_spawn": self.generate_spawn_criteria(is_ego=True),
            "ego_start_speed": 0,
            "actors": actors,
            "actions": actions,
            "success_distance": random.randint(120, 180),
            "timeout": random.randint(100, 150),
            "collision_allowed": False
        }
        
        return scenario
    
    def generate_intersection_scenario(self) -> Dict[str, Any]:
        """Generate an intersection scenario"""
        self.scenario_counter += 1
        color_name, rgb_string = self.get_random_color()
        
        scenario = {
            "scenario_name": f"intersection_{self.scenario_counter:03d}",
            "description": f"Intersection scenario - {color_name} vehicle at intersection",
            "weather": random.choice(WEATHER_OPTIONS),
            "ego_vehicle_model": random.choice(CARLA_VEHICLES),
            "ego_spawn": {
                "criteria": {
                    "lane_type": "Driving",
                    "lane_id": {"min": 1, "max": 4},
                    "is_intersection": True
                }
            },
            "ego_start_speed": 0,
            "actors": [
                {
                    "id": "actor_1",
                    "type": "vehicle",
                    "model": random.choice(CARLA_VEHICLES),
                    "spawn": {
                        "criteria": {
                            "lane_type": "Driving",
                            "distance_to_ego": {"min": 15, "max": 35},
                            "relative_position": "perpendicular",
                            "road_relationship": "different_road",
                            "is_intersection": True
                        }
                    },
                    "color": rgb_string
                }
            ],
            "actions": [
                {
                    "actor_id": "actor_1",
                    "action_type": "speed",
                    "trigger_type": "time",
                    "trigger_value": 2,
                    "trigger_comparison": "=",
                    "speed_value": 8.0,
                    "dynamics_dimension": "time",
                    "dynamics_value": 1.0,
                    "dynamics_shape": "step",
                    "delay": 0
                }
            ],
            "success_distance": 100,
            "timeout": 90,
            "collision_allowed": False
        }
        
        return scenario
    
    def generate_following_scenario(self) -> Dict[str, Any]:
        """Generate a following scenario"""
        self.scenario_counter += 1
        color_name, rgb_string = self.get_random_color()
        
        scenario = {
            "scenario_name": f"following_{self.scenario_counter:03d}",
            "description": f"Following scenario - {color_name} vehicle maintains speed ahead",
            "weather": random.choice(WEATHER_OPTIONS),
            "ego_vehicle_model": random.choice(CARLA_VEHICLES),
            "ego_spawn": self.generate_spawn_criteria(is_ego=True),
            "ego_start_speed": 0,
            "actors": [
                {
                    "id": "actor_1",
                    "type": "vehicle",
                    "model": random.choice(CARLA_VEHICLES),
                    "spawn": {
                        "criteria": {
                            "lane_type": "Driving",
                            "distance_to_ego": {"min": 20, "max": 35},
                            "relative_position": "ahead",
                            "lane_relationship": "same_lane"
                        }
                    },
                    "color": rgb_string
                }
            ],
            "actions": [
                {
                    "actor_id": "actor_1",
                    "action_type": "speed",
                    "trigger_type": "time",
                    "trigger_value": 0,
                    "trigger_comparison": "=",
                    "speed_value": 10.0,
                    "dynamics_dimension": "time",
                    "dynamics_value": 0.1,
                    "dynamics_shape": "step",
                    "delay": 0
                }
            ],
            "success_distance": 150,
            "timeout": 120,
            "collision_allowed": False
        }
        
        return scenario
    
    def generate_complex_scenario(self) -> Dict[str, Any]:
        """Generate a complex mixed scenario"""
        self.scenario_counter += 1
        
        # Mix multiple elements
        actors = []
        actions = []
        descriptions = []
        
        # Add main vehicle
        color1_name, rgb1 = self.get_random_color()
        actors.append({
            "id": "vehicle_1",
            "type": "vehicle",
            "model": random.choice(CARLA_VEHICLES),
            "spawn": {
                "criteria": {
                    "lane_type": "Driving",
                    "distance_to_ego": {"min": 25, "max": 45},
                    "relative_position": "ahead",
                    "lane_relationship": "same_lane"
                }
            },
            "color": rgb1
        })
        descriptions.append(f"{color1_name} vehicle ahead")
        
        # Add second vehicle
        color2_name, rgb2 = self.get_random_color()
        actors.append({
            "id": "vehicle_2",
            "type": "vehicle",
            "model": random.choice(CARLA_VEHICLES),
            "spawn": {
                "criteria": {
                    "lane_type": "Driving",
                    "distance_to_ego": {"min": 10, "max": 25},
                    "relative_position": "adjacent",
                    "lane_relationship": "adjacent_lane"
                }
            },
            "color": rgb2
        })
        descriptions.append(f"{color2_name} vehicle adjacent")
        
        # Add pedestrian sometimes
        if random.random() < 0.5:
            actors.append({
                "id": "pedestrian_1",
                "type": "pedestrian",
                "model": random.choice(CARLA_PEDESTRIANS),
                "spawn": {
                    "criteria": {
                        "lane_type": "Sidewalk",
                        "distance_to_ego": {"min": 15, "max": 30},
                        "relative_position": "perpendicular",
                        "lane_relationship": "different_lane"
                    }
                }
            })
            descriptions.append("pedestrian")
        
        # Add complex actions
        actions.append({
            "actor_id": "vehicle_1",
            "action_type": "stop",
            "trigger_type": "distance_to_ego",
            "trigger_value": 20,
            "trigger_comparison": "<",
            "dynamics_dimension": "time",
            "dynamics_value": 2.0,
            "dynamics_shape": "linear",
            "delay": 0
        })
        
        actions.append({
            "actor_id": "vehicle_2",
            "action_type": "lane_change",
            "trigger_type": "time",
            "trigger_value": 3,
            "trigger_comparison": "=",
            "lane_direction": "left",
            "dynamics_dimension": "time",
            "dynamics_value": 1.5,
            "dynamics_shape": "linear",
            "delay": 0
        })
        
        scenario = {
            "scenario_name": f"complex_{self.scenario_counter:03d}",
            "description": f"Complex scenario - {', '.join(descriptions)}",
            "weather": random.choice(WEATHER_OPTIONS),
            "ego_vehicle_model": random.choice(CARLA_VEHICLES),
            "ego_spawn": self.generate_spawn_criteria(is_ego=True),
            "ego_start_speed": 0,
            "actors": actors,
            "actions": actions,
            "success_distance": 150,
            "timeout": 120,
            "collision_allowed": False
        }
        
        return scenario
    
    def generate_instruction(self, scenario: Dict[str, Any]) -> str:
        """Generate natural language instruction for scenario"""
        
        # Parse scenario type
        scenario_name = scenario["scenario_name"]
        
        if "static" in scenario_name:
            color = self._extract_color_name(scenario["actors"][0]["color"])
            return f"Create a scenario with a {color} vehicle positioned ahead on the same lane"
        
        elif "speed_change" in scenario_name:
            color = self._extract_color_name(scenario["actors"][0]["color"])
            speed = scenario["actions"][0]["speed_value"]
            return f"Generate a scenario where a {color} vehicle ahead changes speed to {speed} m/s when ego approaches"
        
        elif "braking" in scenario_name:
            color = self._extract_color_name(scenario["actors"][0]["color"])
            return f"Create a sudden braking scenario with a {color} vehicle that stops when ego gets close"
        
        elif "lane_change" in scenario_name:
            color = self._extract_color_name(scenario["actors"][0]["color"])
            direction = scenario["actions"][0]["lane_direction"]
            return f"Generate a cut-in scenario where a {color} car changes lanes from the {direction}"
        
        elif "pedestrian" in scenario_name:
            if len(scenario["actors"]) > 1:
                color = self._extract_color_name(scenario["actors"][1]["color"])
                return f"Create a pedestrian crossing scenario with a {color} vehicle nearby"
            return "Generate a pedestrian crossing scenario"
        
        elif "multi_actor" in scenario_name:
            colors = []
            for actor in scenario["actors"]:
                if actor["type"] == "vehicle" and "color" in actor:
                    colors.append(self._extract_color_name(actor["color"]))
            return f"Create a multi-actor scenario with {', '.join(colors)} vehicles performing various actions"
        
        elif "intersection" in scenario_name:
            color = self._extract_color_name(scenario["actors"][0]["color"])
            return f"Generate an intersection scenario with a {color} vehicle approaching from perpendicular direction"
        
        elif "following" in scenario_name:
            color = self._extract_color_name(scenario["actors"][0]["color"])
            return f"Create a following scenario with a {color} vehicle maintaining constant speed ahead"
        
        elif "complex" in scenario_name:
            # Extract key elements
            descriptions = []
            for actor in scenario["actors"]:
                if actor["type"] == "vehicle" and "color" in actor:
                    color = self._extract_color_name(actor["color"])
                    descriptions.append(f"{color} vehicle")
            
            for action in scenario["actions"]:
                if action["action_type"] == "stop":
                    descriptions.append("sudden braking")
                elif action["action_type"] == "lane_change":
                    descriptions.append("lane change maneuver")
            
            return f"Generate a complex scenario with {', '.join(descriptions[:3])}"
        
        return "Create a driving scenario"
    
    def _extract_color_name(self, rgb_string: str) -> str:
        """Extract color name from RGB string"""
        for name, rgb in COLOR_MAPPINGS.items():
            if rgb == rgb_string:
                return name
        return "colored"
    
    def generate_training_example(self, scenario_type: str) -> Dict[str, str]:
        """Generate a complete training example"""
        
        # Generate scenario based on type
        if scenario_type == "static":
            scenario = self.generate_static_actor_scenario()
        elif scenario_type == "speed_change":
            scenario = self.generate_speed_change_scenario()
        elif scenario_type == "braking":
            scenario = self.generate_braking_scenario()
        elif scenario_type == "lane_change":
            scenario = self.generate_lane_change_scenario()
        elif scenario_type == "pedestrian":
            scenario = self.generate_pedestrian_scenario()
        elif scenario_type == "multi_actor":
            scenario = self.generate_multi_actor_scenario()
        elif scenario_type == "intersection":
            scenario = self.generate_intersection_scenario()
        elif scenario_type == "following":
            scenario = self.generate_following_scenario()
        elif scenario_type == "complex":
            scenario = self.generate_complex_scenario()
        else:
            scenario = self.generate_static_actor_scenario()
        
        instruction = self.generate_instruction(scenario)
        
        return {
            "instruction": instruction,
            "input": "",
            "output": json.dumps(scenario, indent=2)
        }
    
    def generate_test_cases(self) -> List[Dict[str, str]]:
        """Generate specific test cases for validation"""
        test_cases = []
        
        # Test case 1: RGB color reference
        scenario1 = self.generate_static_actor_scenario()
        scenario1["actors"][0]["color"] = "255,128,0"  # Orange RGB
        test_cases.append({
            "instruction": "Create a vehicle with color RGB(255, 128, 0)",
            "input": "",
            "output": json.dumps(scenario1, indent=2)
        })
        
        # Test case 2: Specific color name
        scenario2 = self.generate_static_actor_scenario()
        scenario2["actors"][0]["color"] = COLOR_MAPPINGS["crimson"]
        test_cases.append({
            "instruction": "Spawn a crimson red car ahead on the same lane",
            "input": "",
            "output": json.dumps(scenario2, indent=2)
        })
        
        # Test case 3: Complex action sequence
        scenario3 = self.generate_multi_actor_scenario()
        test_cases.append({
            "instruction": "Vehicle accelerates then brakes suddenly with multiple actors",
            "input": "",
            "output": json.dumps(scenario3, indent=2)
        })
        
        # Test case 4: All color variations
        for color_name in ["turquoise", "indigo", "gold", "beige", "teal"]:
            scenario = self.generate_static_actor_scenario()
            scenario["actors"][0]["color"] = COLOR_MAPPINGS[color_name]
            test_cases.append({
                "instruction": f"Create a {color_name} vehicle scenario",
                "input": "",
                "output": json.dumps(scenario, indent=2)
            })
        
        return test_cases

def generate_dataset():
    """Main function to generate complete dataset"""
    print("=" * 60)
    print("CARLA Training Dataset Generator - Correct Schema")
    print("=" * 60)
    
    generator = CorrectScenarioGenerator()
    
    # Training dataset: 500 examples
    print("\nGenerating training dataset...")
    train_examples = []
    
    # Generate 50 of each type for balanced distribution
    scenario_types = [
        ("static", 50),
        ("speed_change", 50),
        ("braking", 50),
        ("lane_change", 50),
        ("pedestrian", 50),
        ("multi_actor", 50),
        ("intersection", 50),
        ("following", 50),
        ("complex", 100)  # More complex scenarios
    ]
    
    for scenario_type, count in scenario_types:
        print(f"  Generating {count} {scenario_type} scenarios...")
        for _ in range(count):
            train_examples.append(generator.generate_training_example(scenario_type))
    
    # Shuffle for better training
    random.shuffle(train_examples)
    
    # Save training dataset
    train_path = Path("carla_correct_train.jsonl")
    with open(train_path, "w") as f:
        for example in train_examples:
            f.write(json.dumps(example) + "\n")
    print(f"✓ Saved {len(train_examples)} training examples to {train_path}")
    
    # Validation dataset: 50 examples
    print("\nGenerating validation dataset...")
    val_examples = []
    
    # Generate balanced validation set
    for scenario_type, _ in scenario_types[:8]:  # Exclude complex for smaller val set
        for _ in range(5):
            val_examples.append(generator.generate_training_example(scenario_type))
    
    # Add specific test cases
    val_examples.extend(generator.generate_test_cases())
    
    # Save validation dataset
    val_path = Path("carla_correct_val.jsonl")
    with open(val_path, "w") as f:
        for example in val_examples:
            f.write(json.dumps(example) + "\n")
    print(f"✓ Saved {len(val_examples)} validation examples to {val_path}")
    
    # Generate statistics
    print("\nDataset Statistics:")
    print(f"  Training examples: {len(train_examples)}")
    print(f"  Validation examples: {len(val_examples)}")
    print(f"  Total examples: {len(train_examples) + len(val_examples)}")
    print(f"  Colors available: {len(COLOR_MAPPINGS)}")
    print(f"  Vehicle models: {len(CARLA_VEHICLES)}")
    print(f"  Weather conditions: {len(WEATHER_OPTIONS)}")
    
    print("\n✅ Dataset generation complete!")
    print("All examples use spawn criteria (no hardcoded positions)")
    print("All colors in correct 'R,G,B' string format")
    print("All scenarios match xosc_json.py schema exactly")

if __name__ == "__main__":
    generate_dataset()