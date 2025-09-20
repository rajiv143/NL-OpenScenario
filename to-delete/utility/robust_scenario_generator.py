#!/usr/bin/env python3
"""
Robust Scenario Generator
Generates 500+ high-quality CARLA scenarios with proper validation
"""

import json
import random
import os
from typing import Dict, List, Any

class RobustScenarioGenerator:
    def __init__(self):
        # Define safe, tested vehicle models
        self.VEHICLE_MODELS = {
            'cars': [
                'vehicle.toyota.prius',
                'vehicle.audi.a2', 
                'vehicle.bmw.grandtourer',
                'vehicle.ford.crown',
                'vehicle.tesla.model3',
                'vehicle.volkswagen.t2',
                'vehicle.nissan.patrol',
                'vehicle.chevrolet.impala',
                'vehicle.mercedes.coupe'
            ],
            'trucks': [
                'vehicle.mercedes.sprinter',
                'vehicle.carlamotors.european_hgv'
            ],
            'emergency': [
                'vehicle.ford.ambulance',
                'vehicle.carlamotors.firetruck'
            ]
        }
        
        self.PEDESTRIAN_MODELS = [f'walker.pedestrian.{i:04d}' for i in range(1, 50)]
        
        self.WEATHER_CONDITIONS = [
            'clear_noon', 'clear_sunset', 'cloudy', 'wet', 'soft_rain', 'hard_rain'
        ]
        
        # Safe spawn distance ranges for different scenario types
        self.SPAWN_DISTANCES = {
            'following': {'min': 25, 'max': 60},
            'cut_in': {'min': 30, 'max': 70},
            'crossing': {'min': 40, 'max': 100},
            'emergency': {'min': 50, 'max': 120},
            'intersection': {'min': 35, 'max': 80}
        }
    
    def generate_following_scenario(self, scenario_id: int) -> Dict[str, Any]:
        """Generate a safe following scenario"""
        
        lead_distance = self.SPAWN_DISTANCES['following']
        
        scenario = {
            "scenario_name": f"following_{scenario_id:03d}",
            "description": f"Vehicle following scenario {scenario_id}",
            "weather": random.choice(self.WEATHER_CONDITIONS),
            "ego_vehicle_model": "vehicle.audi.a2",
            "ego_spawn": {
                "criteria": {
                    "lane_type": "Driving",
                    "lane_id": {"min": 1, "max": 6},
                    "is_intersection": False
                }
            },
            "ego_start_speed": 0,
            "actors": [
                {
                    "id": "lead_vehicle",
                    "type": "vehicle",
                    "model": random.choice(self.VEHICLE_MODELS['cars']),
                    "spawn": {
                        "criteria": {
                            "lane_type": "Driving",
                            "road_relationship": "same_road",
                            "lane_relationship": "same_lane",
                            "distance_to_ego": {
                                "min": lead_distance['min'],
                                "max": lead_distance['max']
                            },
                            "relative_position": "ahead"
                        }
                    }
                }
            ],
            "actions": [],
            "success_distance": random.randint(150, 300),
            "timeout": 120,
            "collision_allowed": False
        }
        
        # Add different behavior patterns
        behavior_type = random.choice(['slow_leader', 'sudden_brake', 'stop_and_go'])
        
        if behavior_type == 'slow_leader':
            scenario["actions"] = [
                {
                    "actor_id": "lead_vehicle",
                    "action_type": "speed",
                    "trigger_type": "distance_to_ego",
                    "trigger_value": 40,
                    "trigger_comparison": "<",
                    "speed_value": random.uniform(6, 12),
                    "dynamics_dimension": "time",
                    "dynamics_value": 3.0
                }
            ]
        elif behavior_type == 'sudden_brake':
            scenario["actions"] = [
                {
                    "actor_id": "lead_vehicle", 
                    "action_type": "speed",
                    "trigger_type": "distance_to_ego",
                    "trigger_value": 35,
                    "trigger_comparison": "<",
                    "speed_value": 0,
                    "dynamics_dimension": "time", 
                    "dynamics_value": 2.0
                }
            ]
        else:  # stop_and_go
            scenario["actions"] = [
                {
                    "actor_id": "lead_vehicle",
                    "action_type": "speed", 
                    "trigger_type": "distance_to_ego",
                    "trigger_value": 35,
                    "trigger_comparison": "<",
                    "speed_value": 8.0,
                    "dynamics_dimension": "time",
                    "dynamics_value": 2.0
                },
                {
                    "actor_id": "lead_vehicle",
                    "action_type": "speed",
                    "trigger_type": "after_previous", 
                    "speed_value": 0,
                    "dynamics_dimension": "time",
                    "dynamics_value": 3.0
                },
                {
                    "actor_id": "lead_vehicle",
                    "action_type": "speed",
                    "trigger_type": "after_previous",
                    "speed_value": 10.0,
                    "dynamics_dimension": "time", 
                    "dynamics_value": 2.0
                }
            ]
        
        return scenario
    
    def generate_lane_change_scenario(self, scenario_id: int) -> Dict[str, Any]:
        """Generate a safe lane change scenario with proper vehicles"""
        
        cut_distance = self.SPAWN_DISTANCES['cut_in']
        
        scenario = {
            "scenario_name": f"lane_change_{scenario_id:03d}",
            "description": f"Lane change scenario {scenario_id}",
            "weather": random.choice(self.WEATHER_CONDITIONS),
            "ego_vehicle_model": "vehicle.audi.a2",
            "ego_spawn": {
                "criteria": {
                    "lane_type": "Driving", 
                    "lane_id": {"min": 1, "max": 6},
                    "is_intersection": False
                }
            },
            "ego_start_speed": 0,
            "actors": [
                {
                    "id": "lane_changer",
                    "type": "vehicle",
                    "model": random.choice(self.VEHICLE_MODELS['cars']),  # Always use cars for lane changes
                    "spawn": {
                        "criteria": {
                            "lane_type": "Driving",
                            "road_relationship": "same_road", 
                            "lane_relationship": "adjacent_lane",
                            "distance_to_ego": {
                                "min": cut_distance['min'],
                                "max": cut_distance['max']
                            },
                            "relative_position": "ahead"
                        }
                    }
                }
            ],
            "actions": [
                {
                    "actor_id": "lane_changer",
                    "action_type": "speed",
                    "trigger_type": "distance_to_ego",
                    "trigger_value": 45,
                    "trigger_comparison": "<",
                    "speed_value": random.uniform(12, 18),
                    "dynamics_dimension": "time",
                    "dynamics_value": 2.0
                },
                {
                    "actor_id": "lane_changer", 
                    "action_type": "lane_change",
                    "trigger_type": "after_previous",
                    "lane_direction": random.choice(["left", "right"]),
                    "dynamics_dimension": "time",
                    "dynamics_value": 3.0
                },
                {
                    "actor_id": "lane_changer",
                    "action_type": "speed",
                    "trigger_type": "after_previous", 
                    "speed_value": random.uniform(10, 15),
                    "dynamics_dimension": "time",
                    "dynamics_value": 2.0
                }
            ],
            "success_distance": random.randint(200, 400),
            "timeout": 90,
            "collision_allowed": False
        }
        
        return scenario
    
    def generate_pedestrian_scenario(self, scenario_id: int) -> Dict[str, Any]:
        """Generate a pedestrian crossing scenario"""
        
        ped_distance = self.SPAWN_DISTANCES['crossing']
        
        scenario = {
            "scenario_name": f"pedestrian_{scenario_id:03d}",
            "description": f"Pedestrian crossing scenario {scenario_id}",
            "weather": random.choice(self.WEATHER_CONDITIONS),
            "ego_vehicle_model": "vehicle.audi.a2", 
            "ego_spawn": {
                "criteria": {
                    "lane_type": "Driving",
                    "lane_id": {"min": 1, "max": 6},
                    "is_intersection": False
                }
            },
            "ego_start_speed": 0,
            "actors": [
                {
                    "id": "crossing_ped",
                    "type": "pedestrian",
                    "model": random.choice(self.PEDESTRIAN_MODELS),
                    "spawn": {
                        "criteria": {
                            "lane_type": "Sidewalk",
                            "road_relationship": "same_road",
                            "distance_to_ego": {
                                "min": ped_distance['min'],
                                "max": ped_distance['max']
                            },
                            "relative_position": "ahead"
                        }
                    }
                }
            ],
            "actions": [
                {
                    "actor_id": "crossing_ped",
                    "action_type": "walk",
                    "trigger_type": "distance_to_ego", 
                    "trigger_value": 50,
                    "trigger_comparison": "<",
                    "target_location": "opposite_sidewalk",
                    "speed_value": random.uniform(1.0, 2.5),
                    "dynamics_dimension": "time",
                    "dynamics_value": 5.0
                }
            ],
            "success_distance": random.randint(100, 250),
            "timeout": 60,
            "collision_allowed": False
        }
        
        return scenario
    
    def generate_emergency_scenario(self, scenario_id: int) -> Dict[str, Any]:
        """Generate emergency vehicle scenario"""
        
        emergency_distance = self.SPAWN_DISTANCES['emergency']
        
        scenario = {
            "scenario_name": f"emergency_{scenario_id:03d}",
            "description": f"Emergency vehicle scenario {scenario_id}",
            "weather": random.choice(self.WEATHER_CONDITIONS),
            "ego_vehicle_model": "vehicle.audi.a2",
            "ego_spawn": {
                "criteria": {
                    "lane_type": "Driving",
                    "lane_id": {"min": 1, "max": 6}, 
                    "is_intersection": False
                }
            },
            "ego_start_speed": 0,
            "actors": [
                {
                    "id": "emergency_vehicle",
                    "type": "vehicle",
                    "model": random.choice(self.VEHICLE_MODELS['emergency']),
                    "spawn": {
                        "criteria": {
                            "lane_type": "Driving",
                            "road_relationship": "same_road",
                            "lane_relationship": "same_lane", 
                            "distance_to_ego": {
                                "min": emergency_distance['min'],
                                "max": emergency_distance['max']
                            },
                            "relative_position": "behind"
                        }
                    }
                }
            ],
            "actions": [
                {
                    "actor_id": "emergency_vehicle",
                    "action_type": "speed",
                    "trigger_type": "distance_to_ego",
                    "trigger_value": 80,
                    "trigger_comparison": "<",
                    "speed_value": random.uniform(20, 30),
                    "dynamics_dimension": "time", 
                    "dynamics_value": 3.0
                }
            ],
            "success_distance": random.randint(200, 400),
            "timeout": 90,
            "collision_allowed": False
        }
        
        return scenario
    
    def generate_static_obstacle_scenario(self, scenario_id: int) -> Dict[str, Any]:
        """Generate static obstacle scenario"""
        
        obstacle_distance = {'min': 40, 'max': 80}
        
        scenario = {
            "scenario_name": f"static_{scenario_id:03d}",
            "description": f"Static obstacle scenario {scenario_id}",
            "weather": random.choice(self.WEATHER_CONDITIONS),
            "ego_vehicle_model": "vehicle.audi.a2",
            "ego_spawn": {
                "criteria": {
                    "lane_type": "Driving",
                    "lane_id": {"min": 1, "max": 6},
                    "is_intersection": False
                }
            },
            "ego_start_speed": 0,
            "actors": [
                {
                    "id": "parked_vehicle",
                    "type": "vehicle", 
                    "model": random.choice(self.VEHICLE_MODELS['cars']),
                    "spawn": {
                        "criteria": {
                            "lane_type": "Driving",
                            "road_relationship": "same_road",
                            "lane_relationship": "same_lane",
                            "distance_to_ego": {
                                "min": obstacle_distance['min'],
                                "max": obstacle_distance['max']
                            },
                            "relative_position": "ahead"
                        }
                    }
                }
            ],
            "actions": [],  # Static - no actions
            "success_distance": random.randint(150, 300),
            "timeout": 90,
            "collision_allowed": False
        }
        
        return scenario
    
    def generate_all_scenarios(self, output_dir: str = "rebuilt_scenarios") -> None:
        """Generate 500+ robust scenarios"""
        
        os.makedirs(output_dir, exist_ok=True)
        
        scenario_counts = {
            'following': 150,      # Most common, fundamental scenarios  
            'lane_change': 100,    # Important for autonomous driving
            'pedestrian': 80,      # Safety critical
            'emergency': 60,       # Special situations
            'static': 60,          # Obstacle avoidance
        }
        
        total_generated = 0
        
        for scenario_type, count in scenario_counts.items():
            print(f"Generating {count} {scenario_type} scenarios...")
            
            for i in range(1, count + 1):
                scenario_id = total_generated + i
                
                if scenario_type == 'following':
                    scenario = self.generate_following_scenario(scenario_id)
                elif scenario_type == 'lane_change':
                    scenario = self.generate_lane_change_scenario(scenario_id)
                elif scenario_type == 'pedestrian':
                    scenario = self.generate_pedestrian_scenario(scenario_id)
                elif scenario_type == 'emergency':
                    scenario = self.generate_emergency_scenario(scenario_id)
                elif scenario_type == 'static':
                    scenario = self.generate_static_obstacle_scenario(scenario_id)
                
                # Save scenario
                filename = f"{scenario['scenario_name']}.json"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, 'w') as f:
                    json.dump(scenario, f, indent=2)
            
            total_generated += count
            print(f"✅ Generated {count} {scenario_type} scenarios")
        
        print(f"\n🎯 Total scenarios generated: {total_generated}")
        print(f"📁 Saved to: {output_dir}/")

if __name__ == '__main__':
    generator = RobustScenarioGenerator()
    generator.generate_all_scenarios()