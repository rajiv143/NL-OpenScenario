#!/usr/bin/env python3
"""
CARLA Scenario JSON Generator for Autonomous Vehicle Testing
Generates diverse, realistic scenarios with proper sequential timing and actor behaviors.
"""

import json
import os
import random
import uuid
from typing import Dict, List, Any, Tuple
from datetime import datetime

class CARLAScenarioGenerator:
    def __init__(self, output_dir: str = "generated_scenarios"):
        """Initialize the scenario generator"""
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Configuration constants
        self.WEATHER_OPTIONS = [
            "clear", "cloudy", "soft_rain", "hard_rain", "wet", "clear_sunset"
        ]
        
        self.VEHICLE_MODELS = [
            "vehicle.audi.a2", "vehicle.toyota.prius", "vehicle.bmw.grandtourer",
            "vehicle.ford.crown", "vehicle.mercedes.sprinter", 
            "vehicle.carlamotors.european_hgv", "vehicle.yamaha.yzf", "vehicle.bh.crossbike"
        ]
        
        self.PEDESTRIAN_MODELS = [
            "walker.pedestrian.0001", "walker.pedestrian.0020", "walker.pedestrian.0025",
            "walker.pedestrian.0030", "walker.pedestrian.0048"
        ]
        
        self.VEHICLE_COLORS = [
            "255,0,0", "0,255,0", "0,0,255", "255,255,0", "255,0,255", 
            "0,255,255", "128,128,128", "255,128,0", "128,0,255"
        ]
        
        # Speed configurations (m/s)
        self.PEDESTRIAN_SPEEDS = {"slow": 0.8, "normal": 1.4, "fast": 2.5}
        self.VEHICLE_SPEEDS = {
            "very_slow": 3, "slow": 8, "normal": 12, "fast": 18, "highway": 25
        }
        
        self.generated_count = 0
        
    def create_base_scenario(self, name: str, description: str, weather: str = None) -> Dict[str, Any]:
        """Create a base scenario structure"""
        return {
            "scenario_name": name,
            "description": description,
            "weather": weather or random.choice(self.WEATHER_OPTIONS),
            "ego_vehicle_model": "vehicle.audi.a2",
            "ego_spawn": {
                "criteria": {
                    "lane_type": "Driving",
                    "lane_id": {"min": 1, "max": 10},
                    "is_intersection": False
                }
            },
            "ego_start_speed": 0,
            "actors": [],
            "actions": [],
            "success_distance": random.randint(60, 120),
            "timeout": random.randint(45, 90),
            "collision_allowed": False
        }
    
    def create_actor(self, actor_id: str, actor_type: str, spawn_criteria: Dict[str, Any], 
                     model: str = None, color: str = None) -> Dict[str, Any]:
        """Create an actor configuration"""
        if actor_type == "vehicle":
            model = model or random.choice(self.VEHICLE_MODELS)
            actor = {
                "id": actor_id,
                "type": "vehicle",
                "model": model,
                "spawn": {"criteria": spawn_criteria}
            }
            if color or random.random() < 0.7:  # 70% chance of having color
                actor["color"] = color or random.choice(self.VEHICLE_COLORS)
            
        elif actor_type == "pedestrian":
            model = model or random.choice(self.PEDESTRIAN_MODELS)
            actor = {
                "id": actor_id,
                "type": "pedestrian", 
                "model": model,
                "spawn": {"criteria": spawn_criteria}
            }
        
        return actor
    
    def create_action(self, actor_id: str, action_type: str, trigger_type: str, 
                     trigger_value: float = None, **kwargs) -> Dict[str, Any]:
        """Create an action configuration"""
        action = {
            "actor_id": actor_id,
            "action_type": action_type,
            "trigger_type": trigger_type
        }
        
        if trigger_value is not None:
            action["trigger_value"] = trigger_value
            
        if trigger_type == "distance_to_ego" and "trigger_comparison" not in kwargs:
            action["trigger_comparison"] = "<"  # Default comparison
            
        # Add specific parameters based on action type
        if action_type == "speed":
            action["speed_value"] = kwargs.get("speed_value", 8.0)
            action["dynamics_dimension"] = "time"
            action["dynamics_value"] = kwargs.get("dynamics_value", 2.0)
            
        elif action_type == "lane_change":
            action["lane_direction"] = kwargs.get("lane_direction", "left")
            action["dynamics_dimension"] = "time"
            action["dynamics_value"] = kwargs.get("dynamics_value", 3.0)
            
        elif action_type == "wait":
            action["wait_duration"] = kwargs.get("wait_duration", 2.0)
            
        elif action_type == "stop":
            action["dynamics_dimension"] = "time"
            action["dynamics_value"] = kwargs.get("dynamics_value", 2.0)
        
        # Add other optional parameters
        for key in ["dynamics_dimension", "dynamics_shape"]:
            if key in kwargs:
                action[key] = kwargs[key]
                
        return action
    
    def save_scenario(self, scenario: Dict[str, Any], category: str = "general") -> str:
        """Save a scenario to a JSON file"""
        self.generated_count += 1
        filename = f"{category}_{self.generated_count:03d}_{scenario['scenario_name']}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(scenario, f, indent=2)
            
        return filepath

    # =============================================================================
    # BASIC INTERACTION SCENARIOS
    # =============================================================================
    
    def generate_vehicle_following_scenarios(self, count: int = 25) -> List[str]:
        """Generate vehicle following and stopping scenarios"""
        scenarios = []
        
        for i in range(count):
            scenario_types = [
                ("following_slow_leader", "Vehicle follows slow-moving lead vehicle"),
                ("sudden_brake_ahead", "Lead vehicle suddenly brakes, testing ego response"),
                ("gradual_slowdown", "Lead vehicle gradually slows down"),
                ("stop_and_go_traffic", "Lead vehicle alternates between stop and go"),
                ("merge_gap_closing", "Vehicle ahead reduces gap during merge")
            ]
            
            scenario_type, description = random.choice(scenario_types)
            name = f"{scenario_type}_{i+1:02d}"
            
            scenario = self.create_base_scenario(name, description)
            
            # Create lead vehicle
            lead_distance = random.randint(25, 50)
            lead_actor = self.create_actor(
                "lead_vehicle",
                "vehicle",
                {
                    "lane_type": "Driving",
                    "road_relationship": "same_road",
                    "lane_relationship": "same_lane",
                    "distance_to_ego": {"min": lead_distance, "max": lead_distance + 10},
                    "relative_position": "ahead"
                }
            )
            scenario["actors"].append(lead_actor)
            
            # Create action sequence based on scenario type
            if scenario_type == "following_slow_leader":
                actions = [
                    self.create_action("lead_vehicle", "speed", "distance_to_ego", 
                                     trigger_value=30, speed_value=6.0, dynamics_value=2.0),
                ]
            
            elif scenario_type == "sudden_brake_ahead":
                actions = [
                    self.create_action("lead_vehicle", "speed", "distance_to_ego",
                                     trigger_value=25, speed_value=15.0, dynamics_value=1.5),
                    self.create_action("lead_vehicle", "stop", "after_previous",
                                     dynamics_value=1.0),
                    self.create_action("lead_vehicle", "wait", "after_previous",
                                     wait_duration=3.0)
                ]
            
            elif scenario_type == "gradual_slowdown":
                actions = [
                    self.create_action("lead_vehicle", "speed", "distance_to_ego",
                                     trigger_value=30, speed_value=12.0, dynamics_value=2.0),
                    self.create_action("lead_vehicle", "speed", "after_previous",
                                     speed_value=6.0, dynamics_value=4.0),
                    self.create_action("lead_vehicle", "speed", "after_previous",
                                     speed_value=2.0, dynamics_value=3.0)
                ]
            
            elif scenario_type == "stop_and_go_traffic":
                actions = [
                    self.create_action("lead_vehicle", "speed", "distance_to_ego",
                                     trigger_value=25, speed_value=8.0, dynamics_value=2.0),
                    self.create_action("lead_vehicle", "stop", "after_previous",
                                     dynamics_value=2.0),
                    self.create_action("lead_vehicle", "wait", "after_previous",
                                     wait_duration=4.0),
                    self.create_action("lead_vehicle", "speed", "after_previous",
                                     speed_value=10.0, dynamics_value=2.0)
                ]
            
            else:  # merge_gap_closing
                actions = [
                    self.create_action("lead_vehicle", "speed", "distance_to_ego",
                                     trigger_value=35, speed_value=14.0, dynamics_value=1.5),
                    self.create_action("lead_vehicle", "speed", "after_previous",
                                     speed_value=8.0, dynamics_value=3.0)
                ]
            
            scenario["actions"].extend(actions)
            filepath = self.save_scenario(scenario, "basic_following")
            scenarios.append(filepath)
        
        return scenarios
    
    def generate_pedestrian_crossing_scenarios(self, count: int = 25) -> List[str]:
        """Generate pedestrian crossing scenarios"""
        scenarios = []
        
        for i in range(count):
            scenario_types = [
                ("crosswalk_waiting", "Pedestrian waits at crosswalk then crosses"),
                ("sudden_crossing", "Pedestrian suddenly enters roadway"),
                ("slow_elderly_crossing", "Elderly pedestrian crosses slowly"),
                ("child_dart_out", "Child darts into street unexpectedly"),
                ("jogger_crossing", "Jogger crosses at intersection")
            ]
            
            scenario_type, description = random.choice(scenario_types)
            name = f"{scenario_type}_{i+1:02d}"
            
            scenario = self.create_base_scenario(name, description)
            
            # Create pedestrian
            ped_distance = random.randint(20, 40)
            spawn_criteria = {
                "lane_type": "Sidewalk" if random.random() < 0.6 else "Driving",
                "distance_to_ego": {"min": ped_distance, "max": ped_distance + 15}
            }
            
            # Choose appropriate pedestrian model based on scenario
            if scenario_type == "child_dart_out":
                ped_model = "walker.pedestrian.0025"  # Child model
            elif scenario_type == "slow_elderly_crossing":
                ped_model = "walker.pedestrian.0030"  # Elderly model
            else:
                ped_model = random.choice(self.PEDESTRIAN_MODELS)
            
            pedestrian = self.create_actor("pedestrian", "pedestrian", spawn_criteria, ped_model)
            scenario["actors"].append(pedestrian)
            
            # Create action sequence based on scenario type
            if scenario_type == "crosswalk_waiting":
                speed = self.PEDESTRIAN_SPEEDS["normal"]
                actions = [
                    self.create_action("pedestrian", "wait", "distance_to_ego",
                                     trigger_value=25, wait_duration=2.0),
                    self.create_action("pedestrian", "speed", "after_previous",
                                     speed_value=speed, dynamics_value=1.0)
                ]
            
            elif scenario_type == "sudden_crossing":
                speed = self.PEDESTRIAN_SPEEDS["fast"]
                actions = [
                    self.create_action("pedestrian", "speed", "distance_to_ego",
                                     trigger_value=20, speed_value=speed, dynamics_value=0.5)
                ]
            
            elif scenario_type == "slow_elderly_crossing":
                speed = self.PEDESTRIAN_SPEEDS["slow"]
                actions = [
                    self.create_action("pedestrian", "wait", "distance_to_ego",
                                     trigger_value=30, wait_duration=3.0),
                    self.create_action("pedestrian", "speed", "after_previous",
                                     speed_value=speed, dynamics_value=2.0)
                ]
            
            elif scenario_type == "child_dart_out":
                speed = self.PEDESTRIAN_SPEEDS["fast"]
                actions = [
                    self.create_action("pedestrian", "speed", "distance_to_ego",
                                     trigger_value=15, speed_value=speed, dynamics_value=0.3)
                ]
            
            else:  # jogger_crossing
                speed = self.PEDESTRIAN_SPEEDS["fast"]
                actions = [
                    self.create_action("pedestrian", "speed", "distance_to_ego",
                                     trigger_value=25, speed_value=speed, dynamics_value=1.0)
                ]
            
            scenario["actions"].extend(actions)
            filepath = self.save_scenario(scenario, "pedestrian_crossing")
            scenarios.append(filepath)
        
        return scenarios
    
    def generate_lane_change_scenarios(self, count: int = 25) -> List[str]:
        """Generate lane changing scenarios"""
        scenarios = []
        
        for i in range(count):
            scenario_types = [
                ("cut_in_ahead", "Vehicle cuts in front of ego from adjacent lane"),
                ("merge_from_ramp", "Vehicle merges from on-ramp"),
                ("slow_vehicle_overtake", "Slow vehicle forces lane change"),
                ("double_lane_change", "Vehicle makes double lane change maneuver"),
                ("aggressive_merge", "Vehicle aggressively merges with small gap")
            ]
            
            scenario_type, description = random.choice(scenario_types)
            name = f"{scenario_type}_{i+1:02d}"
            
            scenario = self.create_base_scenario(name, description)
            
            # Create vehicle in adjacent lane
            vehicle_distance = random.randint(30, 60)
            vehicle = self.create_actor(
                "lane_changer",
                "vehicle",
                {
                    "lane_type": "Driving",
                    "road_relationship": "same_road",
                    "lane_relationship": "adjacent_lane", 
                    "distance_to_ego": {"min": vehicle_distance, "max": vehicle_distance + 20},
                    "relative_position": random.choice(["ahead", "behind", "adjacent"])
                }
            )
            scenario["actors"].append(vehicle)
            
            # Create action sequence based on scenario type
            if scenario_type == "cut_in_ahead":
                actions = [
                    self.create_action("lane_changer", "speed", "distance_to_ego",
                                     trigger_value=35, speed_value=16.0, dynamics_value=1.5),
                    self.create_action("lane_changer", "lane_change", "after_previous",
                                     lane_direction="right", dynamics_value=2.5),
                    self.create_action("lane_changer", "speed", "after_previous",
                                     speed_value=12.0, dynamics_value=2.0)
                ]
            
            elif scenario_type == "merge_from_ramp":
                actions = [
                    self.create_action("lane_changer", "speed", "distance_to_ego",
                                     trigger_value=40, speed_value=12.0, dynamics_value=2.0),
                    self.create_action("lane_changer", "lane_change", "after_previous",
                                     lane_direction="left", dynamics_value=3.0)
                ]
            
            elif scenario_type == "slow_vehicle_overtake":
                actions = [
                    self.create_action("lane_changer", "speed", "distance_to_ego",
                                     trigger_value=30, speed_value=5.0, dynamics_value=2.0),
                    self.create_action("lane_changer", "wait", "after_previous",
                                     wait_duration=3.0)
                ]
            
            elif scenario_type == "double_lane_change":
                direction1 = random.choice(["left", "right"])
                direction2 = "right" if direction1 == "left" else "left"
                actions = [
                    self.create_action("lane_changer", "speed", "distance_to_ego",
                                     trigger_value=35, speed_value=14.0, dynamics_value=1.5),
                    self.create_action("lane_changer", "lane_change", "after_previous",
                                     lane_direction=direction1, dynamics_value=2.5),
                    self.create_action("lane_changer", "wait", "after_previous",
                                     wait_duration=2.0),
                    self.create_action("lane_changer", "lane_change", "after_previous",
                                     lane_direction=direction2, dynamics_value=2.5)
                ]
            
            else:  # aggressive_merge
                actions = [
                    self.create_action("lane_changer", "speed", "distance_to_ego",
                                     trigger_value=25, speed_value=18.0, dynamics_value=1.0),
                    self.create_action("lane_changer", "lane_change", "after_previous",
                                     lane_direction="right", dynamics_value=1.8)
                ]
            
            scenario["actions"].extend(actions)
            filepath = self.save_scenario(scenario, "lane_change")
            scenarios.append(filepath)
        
        return scenarios

    def generate_static_obstacle_scenarios(self, count: int = 20) -> List[str]:
        """Generate static obstacle avoidance scenarios"""
        scenarios = []
        
        for i in range(count):
            scenario_types = [
                ("parked_car_ahead", "Parked car blocking lane ahead"),
                ("broken_down_vehicle", "Broken down vehicle with hazard lights"),
                ("construction_barrier", "Construction barrier blocking lane"),
                ("delivery_truck_stopped", "Delivery truck stopped in lane"),
                ("accident_scene", "Accident scene requiring lane change")
            ]
            
            scenario_type, description = random.choice(scenario_types)
            name = f"{scenario_type}_{i+1:02d}"
            
            scenario = self.create_base_scenario(name, description)
            
            # Create static obstacle
            obstacle_distance = random.randint(40, 80)
            
            # Choose appropriate vehicle model for obstacle
            if scenario_type == "delivery_truck_stopped":
                obstacle_model = "vehicle.mercedes.sprinter"
            elif scenario_type == "construction_barrier":
                obstacle_model = "vehicle.carlamotors.european_hgv"
            else:
                obstacle_model = random.choice(self.VEHICLE_MODELS[:4])  # Use common cars
            
            obstacle = self.create_actor(
                "obstacle",
                "vehicle",
                {
                    "lane_type": "Driving",
                    "road_relationship": "same_road",
                    "lane_relationship": "same_lane",
                    "distance_to_ego": {"min": obstacle_distance, "max": obstacle_distance + 10},
                    "relative_position": "ahead"
                },
                model=obstacle_model
            )
            scenario["actors"].append(obstacle)
            
            # Static obstacles typically don't move, but may have warning actions
            actions = []
            if scenario_type == "broken_down_vehicle":
                # Simulate hazard lights by brief movements
                actions = [
                    self.create_action("obstacle", "wait", "distance_to_ego",
                                     trigger_value=50, wait_duration=5.0)
                ]
            
            scenario["actions"].extend(actions)
            filepath = self.save_scenario(scenario, "static_obstacles")
            scenarios.append(filepath)
        
        return scenarios

    # =============================================================================
    # WEATHER/VISIBILITY SCENARIOS  
    # =============================================================================
    
    def generate_weather_scenarios(self, count: int = 25) -> List[str]:
        """Generate weather and visibility challenge scenarios"""
        scenarios = []
        
        weather_configs = [
            ("hard_rain", "Heavy rain reducing visibility and traction"),
            ("soft_rain", "Light rain with wet road conditions"),
            ("clear_sunset", "Sunset glare affecting visibility"), 
            ("cloudy", "Overcast conditions with reduced lighting"),
            ("wet", "Wet roads after rain")
        ]
        
        for i in range(count):
            weather, weather_desc = random.choice(weather_configs)
            
            scenario_types = [
                ("rain_following", f"Vehicle following in {weather_desc.lower()}"),
                ("weather_pedestrian", f"Pedestrian crossing during {weather_desc.lower()}"),
                ("visibility_merge", f"Lane merge with {weather_desc.lower()}"), 
                ("wet_braking", f"Emergency braking on {weather_desc.lower()}"),
                ("glare_detection", f"Object detection with {weather_desc.lower()}")
            ]
            
            scenario_type, description = random.choice(scenario_types)
            name = f"{scenario_type}_{weather}_{i+1:02d}"
            
            scenario = self.create_base_scenario(name, description, weather=weather)
            
            # Adjust ego start speed for weather conditions
            if weather in ["hard_rain", "wet"]:
                scenario["ego_start_speed"] = random.randint(0, 2)  # Start slower in bad weather
            
            # Create appropriate actor and actions based on scenario type
            if scenario_type == "rain_following":
                lead_distance = random.randint(35, 55)  # Longer following distance
                vehicle = self.create_actor(
                    "lead_vehicle", "vehicle",
                    {
                        "lane_type": "Driving",
                        "road_relationship": "same_road",
                        "lane_relationship": "same_lane", 
                        "distance_to_ego": {"min": lead_distance, "max": lead_distance + 15},
                        "relative_position": "ahead"
                    }
                )
                scenario["actors"].append(vehicle)
                
                # Slower, more cautious speeds in bad weather
                speed_mult = 0.7 if weather == "hard_rain" else 0.85
                actions = [
                    self.create_action("lead_vehicle", "speed", "distance_to_ego",
                                     trigger_value=40, 
                                     speed_value=self.VEHICLE_SPEEDS["normal"] * speed_mult,
                                     dynamics_value=3.0),
                    self.create_action("lead_vehicle", "speed", "after_previous",
                                     speed_value=self.VEHICLE_SPEEDS["slow"] * speed_mult,
                                     dynamics_value=4.0)
                ]
                scenario["actions"].extend(actions)
                
            elif scenario_type == "weather_pedestrian":
                ped_distance = random.randint(25, 45)
                pedestrian = self.create_actor(
                    "pedestrian", "pedestrian", 
                    {
                        "lane_type": "Sidewalk",
                        "distance_to_ego": {"min": ped_distance, "max": ped_distance + 15}
                    }
                )
                scenario["actors"].append(pedestrian)
                
                # Pedestrians move slower in bad weather
                speed_mult = 0.8 if weather in ["hard_rain", "soft_rain"] else 1.0
                actions = [
                    self.create_action("pedestrian", "wait", "distance_to_ego",
                                     trigger_value=30, wait_duration=3.0),
                    self.create_action("pedestrian", "speed", "after_previous",
                                     speed_value=self.PEDESTRIAN_SPEEDS["normal"] * speed_mult,
                                     dynamics_value=2.5)
                ]
                scenario["actions"].extend(actions)
                
            elif scenario_type == "visibility_merge":
                merger_distance = random.randint(40, 70)
                vehicle = self.create_actor(
                    "merger", "vehicle",
                    {
                        "lane_type": "Driving",
                        "road_relationship": "same_road",
                        "lane_relationship": "adjacent_lane",
                        "distance_to_ego": {"min": merger_distance, "max": merger_distance + 20},
                        "relative_position": "adjacent"
                    }
                )
                scenario["actors"].append(vehicle)
                
                actions = [
                    self.create_action("merger", "speed", "distance_to_ego",
                                     trigger_value=45, speed_value=10.0, dynamics_value=2.5),
                    self.create_action("merger", "lane_change", "after_previous",
                                     lane_direction="right", dynamics_value=4.0)  # Slower lane change
                ]
                scenario["actions"].extend(actions)
                
            elif scenario_type == "wet_braking":
                vehicle_distance = random.randint(30, 50)
                vehicle = self.create_actor(
                    "brake_vehicle", "vehicle",
                    {
                        "lane_type": "Driving",
                        "road_relationship": "same_road",
                        "lane_relationship": "same_lane",
                        "distance_to_ego": {"min": vehicle_distance, "max": vehicle_distance + 10},
                        "relative_position": "ahead"
                    }
                )
                scenario["actors"].append(vehicle)
                
                actions = [
                    self.create_action("brake_vehicle", "speed", "distance_to_ego",
                                     trigger_value=35, speed_value=15.0, dynamics_value=1.5),
                    self.create_action("brake_vehicle", "stop", "after_previous",
                                     dynamics_value=2.5)  # Longer braking distance
                ]
                scenario["actions"].extend(actions)
                
            else:  # glare_detection
                # Mixed actor type for detection challenge
                if random.random() < 0.6:
                    actor_distance = random.randint(20, 40)
                    pedestrian = self.create_actor(
                        "hard_to_see", "pedestrian",
                        {
                            "lane_type": "Sidewalk",
                            "distance_to_ego": {"min": actor_distance, "max": actor_distance + 15}
                        }
                    )
                    scenario["actors"].append(pedestrian)
                    
                    actions = [
                        self.create_action("hard_to_see", "speed", "distance_to_ego",
                                         trigger_value=25, 
                                         speed_value=self.PEDESTRIAN_SPEEDS["normal"],
                                         dynamics_value=1.5)
                    ]
                else:
                    vehicle_distance = random.randint(35, 55)
                    vehicle = self.create_actor(
                        "hard_to_see", "vehicle",
                        {
                            "lane_type": "Driving",
                            "road_relationship": "same_road",
                            "lane_relationship": "adjacent_lane",
                            "distance_to_ego": {"min": vehicle_distance, "max": vehicle_distance + 15},
                            "relative_position": "adjacent"
                        },
                        color="128,128,128"  # Gray car harder to see
                    )
                    scenario["actors"].append(vehicle)
                    
                    actions = [
                        self.create_action("hard_to_see", "lane_change", "distance_to_ego",
                                         trigger_value=30, lane_direction="right",
                                         dynamics_value=3.0)
                    ]
                
                scenario["actions"].extend(actions)
            
            # Increase timeout for weather scenarios
            scenario["timeout"] = random.randint(60, 120)
            
            filepath = self.save_scenario(scenario, "weather_visibility")
            scenarios.append(filepath)
        
        return scenarios
    
    # =============================================================================
    # EMERGENCY/PRIORITY SCENARIOS
    # =============================================================================
    
    def generate_emergency_scenarios(self, count: int = 20) -> List[str]:
        """Generate emergency vehicle and priority scenarios"""
        scenarios = []
        
        for i in range(count):
            scenario_types = [
                ("ambulance_approach", "Ambulance approaching from behind with sirens"),
                ("fire_truck_clearing", "Fire truck needs lane clearance"),
                ("police_pursuit", "Police vehicle in high-speed pursuit"),
                ("emergency_stop", "Emergency vehicle sudden stop"),
                ("breakdown_hazards", "Broken down vehicle with hazard indicators")
            ]
            
            scenario_type, description = random.choice(scenario_types)
            name = f"{scenario_type}_{i+1:02d}"
            
            scenario = self.create_base_scenario(name, description)
            
            # Create emergency vehicle
            emerg_distance = random.randint(50, 100)
            
            if scenario_type in ["ambulance_approach", "fire_truck_clearing"]:
                # Emergency vehicle approaching from behind
                emergency_vehicle = self.create_actor(
                    "emergency",
                    "vehicle",
                    {
                        "lane_type": "Driving",
                        "road_relationship": "same_road",
                        "lane_relationship": "same_lane",
                        "distance_to_ego": {"min": emerg_distance, "max": emerg_distance + 20},
                        "relative_position": "behind"
                    },
                    model="vehicle.ford.ambulance" if "ambulance" in scenario_type else "vehicle.carlamotors.firetruck",
                    color="255,255,255"  # White emergency vehicle
                )
                scenario["actors"].append(emergency_vehicle)
                
                # Emergency vehicle approaches at high speed
                actions = [
                    self.create_action("emergency", "speed", "distance_to_ego",
                                     trigger_value=80, speed_value=25.0, dynamics_value=2.0),
                    self.create_action("emergency", "speed", "after_previous", 
                                     speed_value=18.0, dynamics_value=3.0)
                ]
                
            elif scenario_type == "police_pursuit":
                # Police vehicle in pursuit
                police_vehicle = self.create_actor(
                    "police",
                    "vehicle", 
                    {
                        "lane_type": "Driving",
                        "road_relationship": "same_road",
                        "lane_relationship": "adjacent_lane",  # Police often uses adjacent lane for passing
                        "distance_to_ego": {"min": emerg_distance + 20, "max": emerg_distance + 40},
                        "relative_position": "behind"
                    },
                    model="vehicle.dodge.charger_police_2020",
                    color="0,0,0"  # Black police car
                )
                scenario["actors"].append(police_vehicle)
                
                # High-speed pursuit
                actions = [
                    self.create_action("police", "speed", "distance_to_ego",
                                     trigger_value=100, speed_value=28.0, dynamics_value=1.5),
                    self.create_action("police", "lane_change", "after_previous",
                                     lane_direction="left", dynamics_value=2.0),
                    self.create_action("police", "speed", "after_previous",
                                     speed_value=30.0, dynamics_value=2.0)
                ]
                
            elif scenario_type == "emergency_stop":
                emergency_vehicle = self.create_actor(
                    "emergency",
                    "vehicle",
                    {
                        "lane_type": "Driving",
                        "road_relationship": "same_road",
                        "lane_relationship": "same_lane",
                        "distance_to_ego": {"min": 40, "max": 60},
                        "relative_position": "ahead"
                    },
                    model="vehicle.ford.ambulance"
                )
                scenario["actors"].append(emergency_vehicle)
                
                actions = [
                    self.create_action("emergency", "speed", "distance_to_ego",
                                     trigger_value=50, speed_value=15.0, dynamics_value=1.0),
                    self.create_action("emergency", "stop", "after_previous",
                                     dynamics_value=1.5)  # Quick emergency stop
                ]
                
            else:  # breakdown_hazards
                breakdown_vehicle = self.create_actor(
                    "breakdown",
                    "vehicle",
                    {
                        "lane_type": "Driving",
                        "road_relationship": "same_road",
                        "lane_relationship": "same_lane", 
                        "distance_to_ego": {"min": 60, "max": 90},
                        "relative_position": "ahead"
                    }
                )
                scenario["actors"].append(breakdown_vehicle)
                
                # Simulate breakdown - slow down then stop
                actions = [
                    self.create_action("breakdown", "speed", "distance_to_ego",
                                     trigger_value=70, speed_value=12.0, dynamics_value=2.0),
                    self.create_action("breakdown", "speed", "after_previous",
                                     speed_value=4.0, dynamics_value=3.0),
                    self.create_action("breakdown", "stop", "after_previous",
                                     dynamics_value=2.0)
                ]
            
            scenario["actions"].extend(actions)
            filepath = self.save_scenario(scenario, "emergency_priority")
            scenarios.append(filepath)
        
        return scenarios
    
    # =============================================================================
    # VULNERABLE ROAD USER SCENARIOS
    # =============================================================================
    
    def generate_vulnerable_user_scenarios(self, count: int = 25) -> List[str]:
        """Generate scenarios with vulnerable road users (children, elderly, cyclists)"""
        scenarios = []
        
        for i in range(count):
            scenario_types = [
                ("child_playing", "Child playing near roadway, sudden movement"),
                ("elderly_crossing", "Elderly person crossing slowly"), 
                ("cyclist_overtake", "Cyclist riding in vehicle lane"),
                ("school_zone", "Children crossing near school zone"),
                ("cyclist_door_zone", "Cyclist avoiding parked car door zone"),
                ("blind_pedestrian", "Visually impaired pedestrian with guide"),
                ("wheelchair_user", "Person in wheelchair crossing"),
                ("jogger_headphones", "Jogger with headphones, distracted")
            ]
            
            scenario_type, description = random.choice(scenario_types)
            name = f"{scenario_type}_{i+1:02d}"
            
            scenario = self.create_base_scenario(name, description)
            
            if scenario_type == "child_playing":
                # Child model with unpredictable behavior
                child = self.create_actor(
                    "child",
                    "pedestrian", 
                    {
                        "lane_type": "Sidewalk",
                        "distance_to_ego": {"min": 15, "max": 30}
                    },
                    model="walker.pedestrian.0025"  # Child model
                )
                scenario["actors"].append(child)
                
                # Erratic child behavior
                actions = [
                    self.create_action("child", "speed", "distance_to_ego",
                                     trigger_value=20, speed_value=2.0, dynamics_value=0.5),
                    self.create_action("child", "wait", "after_previous", wait_duration=1.5),
                    self.create_action("child", "speed", "after_previous",
                                     speed_value=3.0, dynamics_value=0.8)  # Sudden dash
                ]
                
            elif scenario_type == "elderly_crossing":
                elderly = self.create_actor(
                    "elderly",
                    "pedestrian",
                    {
                        "lane_type": "Sidewalk",
                        "distance_to_ego": {"min": 25, "max": 45}
                    },
                    model="walker.pedestrian.0030"  # Elderly model
                )
                scenario["actors"].append(elderly)
                
                # Very slow crossing
                actions = [
                    self.create_action("elderly", "wait", "distance_to_ego",
                                     trigger_value=35, wait_duration=4.0),
                    self.create_action("elderly", "speed", "after_previous",
                                     speed_value=0.6, dynamics_value=3.0)  # Very slow
                ]
                
            elif scenario_type == "cyclist_overtake":
                cyclist = self.create_actor(
                    "cyclist",
                    "vehicle",  # Cyclists are vehicles in CARLA
                    {
                        "lane_type": "Driving",
                        "road_relationship": "same_road",
                        "lane_relationship": "same_lane",
                        "distance_to_ego": {"min": 30, "max": 50},
                        "relative_position": "ahead"
                    },
                    model="vehicle.bh.crossbike"
                )
                scenario["actors"].append(cyclist)
                
                # Cyclist maintaining lane position
                actions = [
                    self.create_action("cyclist", "speed", "distance_to_ego",
                                     trigger_value=40, speed_value=6.0, dynamics_value=2.0),
                ]
                
            elif scenario_type == "school_zone":
                # Multiple children near school
                child1 = self.create_actor(
                    "child1",
                    "pedestrian",
                    {
                        "lane_type": "Sidewalk",
                        "distance_to_ego": {"min": 20, "max": 35}
                    },
                    model="walker.pedestrian.0025"
                )
                child2 = self.create_actor(
                    "child2", 
                    "pedestrian",
                    {
                        "lane_type": "Sidewalk",
                        "distance_to_ego": {"min": 40, "max": 55}
                    },
                    model="walker.pedestrian.0025"
                )
                scenario["actors"].extend([child1, child2])
                
                actions = [
                    self.create_action("child1", "wait", "distance_to_ego",
                                     trigger_value=30, wait_duration=2.0),
                    self.create_action("child1", "speed", "after_previous",
                                     speed_value=1.8, dynamics_value=1.5),
                    self.create_action("child2", "speed", "distance_to_ego",
                                     trigger_value=45, speed_value=1.5, dynamics_value=2.0)
                ]
                
            elif scenario_type == "cyclist_door_zone":
                # Parked car and cyclist
                parked_car = self.create_actor(
                    "parked_car",
                    "vehicle",
                    {
                        "lane_type": "Driving",
                        "road_relationship": "same_road",
                        "lane_relationship": "same_lane",
                        "distance_to_ego": {"min": 50, "max": 70},
                        "relative_position": "ahead"
                    }
                )
                cyclist = self.create_actor(
                    "cyclist",
                    "vehicle",
                    {
                        "lane_type": "Driving",
                        "road_relationship": "same_road",
                        "lane_relationship": "same_lane", 
                        "distance_to_ego": {"min": 35, "max": 55},
                        "relative_position": "ahead"
                    },
                    model="vehicle.bh.crossbike"
                )
                scenario["actors"].extend([parked_car, cyclist])
                
                # Cyclist swerves to avoid door zone
                actions = [
                    self.create_action("cyclist", "speed", "distance_to_ego",
                                     trigger_value=45, speed_value=5.0, dynamics_value=1.5),
                    self.create_action("cyclist", "lane_change", "after_previous",
                                     lane_direction="left", dynamics_value=2.0),
                    self.create_action("cyclist", "lane_change", "after_previous", 
                                     lane_direction="right", dynamics_value=2.5)
                ]
                
            elif scenario_type in ["blind_pedestrian", "wheelchair_user"]:
                # Slower moving, predictable but vulnerable
                ped_model = "walker.pedestrian.0030" if scenario_type == "wheelchair_user" else "walker.pedestrian.0001"
                vulnerable_ped = self.create_actor(
                    "vulnerable_pedestrian",
                    "pedestrian",
                    {
                        "lane_type": "Sidewalk",
                        "distance_to_ego": {"min": 30, "max": 50}
                    },
                    model=ped_model
                )
                scenario["actors"].append(vulnerable_ped)
                
                # Slow, steady movement
                actions = [
                    self.create_action("vulnerable_pedestrian", "wait", "distance_to_ego",
                                     trigger_value=40, wait_duration=3.0),
                    self.create_action("vulnerable_pedestrian", "speed", "after_previous",
                                     speed_value=0.8, dynamics_value=4.0)
                ]
                
            else:  # jogger_headphones
                jogger = self.create_actor(
                    "jogger",
                    "pedestrian",
                    {
                        "lane_type": "Sidewalk",
                        "distance_to_ego": {"min": 25, "max": 40}
                    },
                    model="walker.pedestrian.0020"
                )
                scenario["actors"].append(jogger)
                
                # Jogger with unpredictable path (distracted)
                actions = [
                    self.create_action("jogger", "speed", "distance_to_ego",
                                     trigger_value=30, speed_value=2.2, dynamics_value=1.0),
                    self.create_action("jogger", "wait", "after_previous", wait_duration=1.0),
                    self.create_action("jogger", "speed", "after_previous",
                                     speed_value=2.8, dynamics_value=1.2)
                ]
            
            scenario["actions"].extend(actions)
            filepath = self.save_scenario(scenario, "vulnerable_users")
            scenarios.append(filepath)
            
        return scenarios
    
    # =============================================================================  
    # COMPLEX MULTI-ACTOR SCENARIOS
    # =============================================================================
    
    def generate_multi_actor_scenarios(self, count: int = 30) -> List[str]:
        """Generate complex scenarios with multiple interacting actors"""
        scenarios = []
        
        for i in range(count):
            scenario_types = [
                ("intersection_chaos", "Multiple vehicles at busy intersection"),
                ("highway_merge", "Multiple vehicles merging onto highway"),
                ("delivery_zone", "Delivery truck with pedestrian activity"),
                ("school_pickup", "Multiple vehicles and pedestrians at school"),
                ("market_street", "Busy street with mixed traffic"),
                ("construction_detour", "Multiple vehicles navigating construction"),
                ("parking_lot_exit", "Vehicles and pedestrians in parking area"),
                ("bus_stop_activity", "Bus with boarding passengers and traffic")
            ]
            
            scenario_type, description = random.choice(scenario_types)
            name = f"{scenario_type}_{i+1:02d}"
            
            scenario = self.create_base_scenario(name, description)
            
            if scenario_type == "intersection_chaos":
                # Multiple vehicles from different directions
                vehicle1 = self.create_actor(
                    "cross_traffic1", "vehicle",
                    {
                        "lane_type": "Driving",
                        "road_relationship": "same_road",
                        "lane_relationship": "same_lane",
                        "distance_to_ego": {"min": 40, "max": 60},
                        "relative_position": "ahead"
                    }
                )
                vehicle2 = self.create_actor(
                    "cross_traffic2", "vehicle",
                    {
                        "lane_type": "Driving",
                        "road_relationship": "different_road",  # Cross traffic from different road
                        "distance_to_ego": {"min": 35, "max": 55},
                        "relative_position": "adjacent",
                        "is_intersection": True
                    }
                )
                pedestrian = self.create_actor(
                    "crossing_ped", "pedestrian",
                    {
                        "lane_type": "Sidewalk",
                        "distance_to_ego": {"min": 20, "max": 35}
                    }
                )
                scenario["actors"].extend([vehicle1, vehicle2, pedestrian])
                
                # Staggered timing to simulate intersection behavior
                actions = [
                    self.create_action("cross_traffic1", "speed", "distance_to_ego",
                                     trigger_value=50, speed_value=8.0, dynamics_value=2.0),
                    self.create_action("cross_traffic2", "speed", "distance_to_ego", 
                                     trigger_value=45, speed_value=12.0, dynamics_value=1.8),
                    self.create_action("cross_traffic2", "stop", "after_previous",
                                     dynamics_value=2.5),
                    self.create_action("crossing_ped", "wait", "distance_to_ego",
                                     trigger_value=30, wait_duration=3.0),
                    self.create_action("crossing_ped", "speed", "after_previous",
                                     speed_value=1.4, dynamics_value=2.0)
                ]
                
            elif scenario_type == "highway_merge":
                # Multiple merging vehicles
                merger1 = self.create_actor(
                    "merger1", "vehicle",
                    {
                        "lane_type": "Driving",
                        "road_relationship": "same_road",
                        "lane_relationship": "adjacent_lane",  # Merging from adjacent lane
                        "distance_to_ego": {"min": 60, "max": 80}, 
                        "relative_position": "behind"
                    }
                )
                merger2 = self.create_actor(
                    "merger2", "vehicle",
                    {
                        "lane_type": "Driving",
                        "road_relationship": "same_road",
                        "lane_relationship": "adjacent_lane",  # Also merging from adjacent lane
                        "distance_to_ego": {"min": 80, "max": 100},
                        "relative_position": "behind"
                    }
                )
                highway_traffic = self.create_actor(
                    "highway_vehicle", "vehicle",
                    {
                        "lane_type": "Driving",
                        "road_relationship": "same_road",
                        "lane_relationship": "same_lane",  # Existing traffic in same lane
                        "distance_to_ego": {"min": 40, "max": 60},
                        "relative_position": "adjacent"
                    }
                )
                scenario["actors"].extend([merger1, merger2, highway_traffic])
                
                # Highway merge sequence
                actions = [
                    self.create_action("highway_vehicle", "speed", "distance_to_ego",
                                     trigger_value=50, speed_value=22.0, dynamics_value=1.5),
                    self.create_action("merger1", "speed", "distance_to_ego",
                                     trigger_value=70, speed_value=18.0, dynamics_value=2.0),
                    self.create_action("merger1", "lane_change", "after_previous",
                                     lane_direction="left", dynamics_value=3.0),
                    self.create_action("merger2", "speed", "distance_to_ego",
                                     trigger_value=90, speed_value=20.0, dynamics_value=2.5),
                    self.create_action("merger2", "lane_change", "after_previous",
                                     lane_direction="left", dynamics_value=3.5)
                ]
                
            elif scenario_type == "delivery_zone":
                # Delivery truck with pedestrian activity
                delivery_truck = self.create_actor(
                    "delivery", "vehicle",
                    {
                        "lane_type": "Driving",
                        "road_relationship": "same_road",
                        "lane_relationship": "same_lane",
                        "distance_to_ego": {"min": 40, "max": 60},
                        "relative_position": "ahead"
                    },
                    model="vehicle.mercedes.sprinter"
                )
                worker = self.create_actor(
                    "delivery_worker", "pedestrian", 
                    {
                        "lane_type": "Sidewalk",
                        "distance_to_ego": {"min": 35, "max": 50}
                    }
                )
                customer = self.create_actor(
                    "customer", "pedestrian",
                    {
                        "lane_type": "Sidewalk", 
                        "distance_to_ego": {"min": 45, "max": 60}
                    }
                )
                scenario["actors"].extend([delivery_truck, worker, customer])
                
                # Delivery scenario with truck stopping and people moving
                actions = [
                    self.create_action("delivery", "speed", "distance_to_ego",
                                     trigger_value=50, speed_value=6.0, dynamics_value=2.0),
                    self.create_action("delivery", "stop", "after_previous",
                                     dynamics_value=2.5),
                    self.create_action("delivery_worker", "speed", "distance_to_ego",
                                     trigger_value=40, speed_value=1.2, dynamics_value=1.5),
                    self.create_action("customer", "wait", "distance_to_ego",
                                     trigger_value=55, wait_duration=2.0),
                    self.create_action("customer", "speed", "after_previous",
                                     speed_value=1.0, dynamics_value=2.0)
                ]
                
            else:  # Other complex scenarios use similar patterns
                # Create 2-3 actors with varied behaviors
                num_actors = random.randint(2, 3)
                actor_ids = []
                
                for j in range(num_actors):
                    if j == 0 or random.random() < 0.7:  # Mostly vehicles
                        actor_id = f"actor_{j+1}"
                        distance = random.randint(30 + j*15, 50 + j*15)
                        actor = self.create_actor(
                            actor_id, "vehicle",
                            {
                                "lane_type": "Driving",
                                "road_relationship": "same_road",
                                "lane_relationship": random.choice(["same_lane", "adjacent_lane"]),
                                "distance_to_ego": {"min": distance, "max": distance + 15},
                                "relative_position": random.choice(["ahead", "behind", "adjacent"])
                            }
                        )
                    else:  # Some pedestrians
                        actor_id = f"pedestrian_{j+1}"
                        distance = random.randint(20 + j*10, 35 + j*10)
                        actor = self.create_actor(
                            actor_id, "pedestrian",
                            {
                                "lane_type": "Sidewalk",
                                "distance_to_ego": {"min": distance, "max": distance + 10}
                            }
                        )
                    
                    scenario["actors"].append(actor)
                    actor_ids.append(actor_id)
                
                # Create varied action sequences
                actions = []
                for j, actor_id in enumerate(actor_ids):
                    trigger_dist = 40 + j*10
                    is_vehicle = "actor_" in actor_id
                    
                    if is_vehicle:
                        speed = random.choice([6.0, 10.0, 15.0])
                        actions.append(
                            self.create_action(actor_id, "speed", "distance_to_ego",
                                             trigger_value=trigger_dist, speed_value=speed,
                                             dynamics_value=2.0)
                        )
                        
                        # Some vehicles do additional maneuvers
                        if random.random() < 0.4:
                            actions.append(
                                self.create_action(actor_id, "lane_change", "after_previous",
                                                 lane_direction=random.choice(["left", "right"]),
                                                 dynamics_value=3.0)
                            )
                    else:  # Pedestrian
                        speed = random.choice([0.8, 1.4, 2.0])
                        actions.append(
                            self.create_action(actor_id, "wait", "distance_to_ego",
                                             trigger_value=trigger_dist, wait_duration=2.0)
                        )
                        actions.append(
                            self.create_action(actor_id, "speed", "after_previous", 
                                             speed_value=speed, dynamics_value=2.5)
                        )
                        
            scenario["actions"].extend(actions)
            
            # Longer timeout for complex scenarios
            scenario["timeout"] = random.randint(90, 150)
            
            filepath = self.save_scenario(scenario, "multi_actor")
            scenarios.append(filepath)
            
        return scenarios

    def generate_basic_scenarios(self) -> List[str]:
        """Generate all basic interaction scenarios"""
        all_scenarios = []
        
        print("Generating basic interaction scenarios...")
        all_scenarios.extend(self.generate_vehicle_following_scenarios(25))
        all_scenarios.extend(self.generate_pedestrian_crossing_scenarios(25))
        all_scenarios.extend(self.generate_lane_change_scenarios(25))
        all_scenarios.extend(self.generate_static_obstacle_scenarios(20))
        
        print(f"Generated {len(all_scenarios)} basic scenarios")
        return all_scenarios
    
    def generate_advanced_scenarios(self) -> List[str]:
        """Generate weather and emergency scenarios"""
        all_scenarios = []
        
        print("Generating advanced scenarios...")
        all_scenarios.extend(self.generate_weather_scenarios(25))
        all_scenarios.extend(self.generate_emergency_scenarios(20))
        
        print(f"Generated {len(all_scenarios)} advanced scenarios")
        return all_scenarios
    
    def generate_specialized_scenarios(self) -> List[str]:
        """Generate vulnerable user and multi-actor scenarios"""
        all_scenarios = []
        
        print("Generating specialized scenarios...")
        all_scenarios.extend(self.generate_vulnerable_user_scenarios(25))
        all_scenarios.extend(self.generate_multi_actor_scenarios(30))
        
        print(f"Generated {len(all_scenarios)} specialized scenarios")
        return all_scenarios
    
    def generate_all_scenarios(self) -> List[str]:
        """Generate the complete dataset of scenarios"""
        all_scenarios = []
        
        print("Starting comprehensive scenario generation...")
        print("=" * 60)
        
        # Generate all scenario categories
        all_scenarios.extend(self.generate_basic_scenarios())
        all_scenarios.extend(self.generate_advanced_scenarios()) 
        all_scenarios.extend(self.generate_specialized_scenarios())
        
        print("\n" + "=" * 60)
        print("GENERATION COMPLETE!")
        print(f"Total scenarios generated: {self.generated_count}")
        print(f"Output directory: {self.output_dir}")
        
        # Print detailed breakdown
        print("\nDetailed Scenario Breakdown:")
        print("-" * 40)
        print("BASIC INTERACTIONS (95 scenarios):")
        print("  • Vehicle following & stopping: 25")
        print("  • Pedestrian crossings: 25") 
        print("  • Lane changing maneuvers: 25")
        print("  • Static obstacle avoidance: 20")
        print("\nADVANCED CONDITIONS (45 scenarios):")
        print("  • Weather/visibility challenges: 25")
        print("  • Emergency/priority vehicles: 20")
        print("\nSPECIALIZED SITUATIONS (55 scenarios):")
        print("  • Vulnerable road users: 25")
        print("  • Complex multi-actor: 30")
        
        print(f"\nKey Features:")
        print("✓ Sequential action timing with 'after_previous' chaining")
        print("✓ Realistic speeds and reaction times")
        print("✓ Diverse weather conditions")
        print("✓ Proper spawn criteria for auto-map selection")
        print("✓ Edge cases and challenging scenarios")
        print("✓ Full CARLA vehicle/pedestrian model coverage")
        
        return all_scenarios
    
    def create_sample_scenarios(self, count: int = 5) -> List[str]:
        """Create a small set of sample scenarios for testing"""
        print(f"Creating {count} sample scenarios for testing...")
        
        sample_scenarios = []
        
        # One of each basic type
        sample_scenarios.extend(self.generate_vehicle_following_scenarios(1))
        sample_scenarios.extend(self.generate_pedestrian_crossing_scenarios(1)) 
        sample_scenarios.extend(self.generate_weather_scenarios(1))
        sample_scenarios.extend(self.generate_vulnerable_user_scenarios(1))
        sample_scenarios.extend(self.generate_multi_actor_scenarios(1))
        
        print(f"Generated {len(sample_scenarios)} sample scenarios")
        return sample_scenarios

def main():
    """Main entry point for scenario generation"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate CARLA scenario JSON files')
    parser.add_argument('--output-dir', default='generated_scenarios',
                       help='Output directory for scenarios (default: generated_scenarios)')
    parser.add_argument('--sample-only', action='store_true',
                       help='Generate only 5 sample scenarios for testing')
    parser.add_argument('--count', type=int,
                       help='Override scenario counts (for testing)')
    
    args = parser.parse_args()
    
    print("🚗 CARLA Scenario Generator for Autonomous Vehicle Testing")
    print("=" * 60)
    
    generator = CARLAScenarioGenerator(args.output_dir)
    
    try:
        if args.sample_only:
            scenarios = generator.create_sample_scenarios()
        else:
            scenarios = generator.generate_all_scenarios()
        
        print(f"\n✅ Successfully generated {len(scenarios)} scenario files")
        print(f"📁 Find them in: {generator.output_dir}/")
        
        # Show some example files
        if scenarios:
            print(f"\n📋 Example generated files:")
            for i, filepath in enumerate(scenarios[:3]):
                filename = os.path.basename(filepath)
                print(f"   {i+1}. {filename}")
            if len(scenarios) > 3:
                print(f"   ... and {len(scenarios) - 3} more")
    
    except KeyboardInterrupt:
        print(f"\n⚠️  Generation interrupted. {generator.generated_count} scenarios created.")
    except Exception as e:
        print(f"\n❌ Error during generation: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())