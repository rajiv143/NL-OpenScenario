#!/usr/bin/env python3
"""
CARLA Scenario Generator for LLM Training
Generates 300+ basic CARLA scenarios organized by complexity levels
"""

import json
import os
import random
from pathlib import Path
from typing import Dict, List, Any, Tuple

class CarlaScenarioGenerator:
    def __init__(self, output_dir: str = "claude_scenarios"):
        self.output_dir = Path(output_dir)
        self.vehicle_models = [
            "vehicle.audi.a2",
            "vehicle.toyota.prius", 
            "vehicle.bmw.grandtourer",
            "vehicle.ford.crown",
            "vehicle.mercedes.sprinter",
            "vehicle.audi.tt"
        ]
        self.weather_conditions = ["clear", "cloudy", "soft_rain", "wet"]
        self.colors = [
            "255,0,0",    # Red
            "0,255,0",    # Green
            "0,0,255",    # Blue
            "255,255,0",  # Yellow
            "255,128,0",  # Orange
            "128,0,128",  # Purple
            "0,128,128",  # Teal
            "128,128,128" # Gray
        ]
        
        # Create directory structure
        self.levels = {
            "01_static_actors": 50,
            "02_moving_actors": 50,
            "03_speed_changes": 50,
            "04_stop_start": 50,
            "05_multi_actors": 60,
            "06_interactions": 40
        }
        
        self._create_directories()
    
    def _create_directories(self):
        """Create the directory structure for all complexity levels"""
        for level_dir in self.levels.keys():
            level_path = self.output_dir / level_dir
            level_path.mkdir(parents=True, exist_ok=True)
    
    def _get_random_vehicle(self) -> str:
        """Get a random vehicle model"""
        return random.choice(self.vehicle_models)
    
    def _get_random_color(self) -> str:
        """Get a random RGB color"""
        return random.choice(self.colors)
    
    def _get_random_weather(self) -> str:
        """Get a random weather condition"""
        return random.choice(self.weather_conditions)
    
    def _create_base_scenario(self, name: str, description: str) -> Dict[str, Any]:
        """Create the base scenario structure"""
        return {
            "scenario_name": name,
            "description": description,
            "weather": self._get_random_weather(),
            "ego_vehicle_model": "vehicle.audi.a2",
            "ego_spawn": {
                "criteria": {
                    "lane_type": "Driving",
                    "lane_id": {"min": 1, "max": 4},
                    "is_intersection": False
                }
            },
            "ego_start_speed": 0,
            "actors": [],
            "actions": [],
            "success_distance": 100,
            "timeout": 60,
            "collision_allowed": False
        }
    
    def _create_actor(self, actor_id: str, position: str, distance_min: int, 
                     distance_max: int, lane_relationship: str = "same_lane") -> Dict[str, Any]:
        """Create an actor definition"""
        return {
            "id": actor_id,
            "type": "vehicle",
            "model": self._get_random_vehicle(),
            "spawn": {
                "criteria": {
                    "lane_type": "Driving",
                    "distance_to_ego": {"min": distance_min, "max": distance_max},
                    "relative_position": position,
                    "lane_relationship": lane_relationship
                }
            },
            "color": self._get_random_color()
        }
    
    def _create_speed_action(self, actor_id: str, speed: float, trigger_type: str,
                            trigger_value: float, comparison: str = "<",
                            dynamics_time: float = 2.0, delay: float = 0.2) -> Dict[str, Any]:
        """Create a speed action"""
        return {
            "actor_id": actor_id,
            "action_type": "speed",
            "trigger_type": trigger_type,
            "trigger_value": trigger_value,
            "trigger_comparison": comparison,
            "speed_value": speed,
            "dynamics_dimension": "time",
            "dynamics_value": dynamics_time,
            "dynamics_shape": "linear",
            "delay": delay
        }
    
    def _create_stop_action(self, actor_id: str, trigger_type: str,
                           trigger_value: float = 0, delay: float = 0.2) -> Dict[str, Any]:
        """Create a stop action"""
        return {
            "actor_id": actor_id,
            "action_type": "stop",
            "trigger_type": trigger_type,
            "trigger_value": trigger_value,
            "trigger_comparison": "<",
            "dynamics_dimension": "time",
            "dynamics_value": 2.0,
            "dynamics_shape": "linear",
            "delay": delay
        }
    
    def _create_wait_action(self, actor_id: str, wait_time: float, delay: float = 0.2) -> Dict[str, Any]:
        """Create a wait action"""
        return {
            "actor_id": actor_id,
            "action_type": "wait",
            "trigger_type": "after_previous",
            "trigger_value": 0,
            "wait_time": wait_time,
            "delay": delay
        }
    
    def _create_lane_change_action(self, actor_id: str, direction: str, trigger_type: str,
                                  trigger_value: float, delay: float = 0.2) -> Dict[str, Any]:
        """Create a lane change action"""
        return {
            "actor_id": actor_id,
            "action_type": "lane_change",
            "trigger_type": trigger_type,
            "trigger_value": trigger_value,
            "trigger_comparison": "<",
            "lane_change_direction": direction,
            "dynamics_dimension": "time",
            "dynamics_value": 3.0,
            "dynamics_shape": "linear",
            "delay": delay
        }
    
    def _save_scenario(self, scenario: Dict[str, Any], description: str, level_dir: str, index: int):
        """Save scenario JSON and description files"""
        level_path = self.output_dir / level_dir
        
        # Save JSON file
        json_filename = f"{scenario['scenario_name']}.json"
        json_path = level_path / json_filename
        with open(json_path, 'w') as f:
            json.dump(scenario, f, indent=2)
        
        # Save description file
        desc_filename = f"{scenario['scenario_name']}_description.txt"
        desc_path = level_path / desc_filename
        with open(desc_path, 'w') as f:
            f.write(description)
    
    def generate_level1_static_actors(self):
        """Generate Level 1 - Static Actors (50 scenarios)"""
        print("\n=== Generating Level 1: Static Actors (50 scenarios) ===")
        
        positions = ["ahead", "behind"]
        distances = [(10, 20), (25, 35), (40, 50)]  # close, medium, far
        distance_names = ["close", "medium", "far"]
        
        scenario_count = 0
        for i in range(50):
            # Vary parameters
            position = positions[i % 2]
            dist_idx = (i // 2) % 3
            distance = distances[dist_idx]
            distance_name = distance_names[dist_idx]
            
            # Create scenario
            name = f"static_actor_{i+1:03d}"
            tech_desc = f"Static {position} vehicle at {distance_name} distance"
            scenario = self._create_base_scenario(name, tech_desc)
            
            # Add actor
            actor = self._create_actor("static_vehicle", position, distance[0], distance[1])
            scenario["actors"].append(actor)
            
            # No actions for static scenarios
            
            # Create natural language description
            vehicle_name = actor["model"].split(".")[-1]
            nl_description = (f"A {vehicle_name} is parked {position} of the ego vehicle at "
                            f"{distance_name} distance ({distance[0]}-{distance[1]} meters). "
                            f"It remains completely stationary throughout the scenario.")
            
            self._save_scenario(scenario, nl_description, "01_static_actors", i+1)
            scenario_count += 1
            
            if scenario_count % 10 == 0:
                print(f"  Generated {scenario_count}/50 static actor scenarios")
        
        print(f"✓ Completed Level 1: {scenario_count} scenarios generated")
    
    def generate_level2_moving_actors(self):
        """Generate Level 2 - Moving Actors (50 scenarios)"""
        print("\n=== Generating Level 2: Moving Actors (50 scenarios) ===")
        
        positions = ["ahead", "behind"]
        trigger_distances = [15, 20, 25, 30, 35]
        speeds = [3, 5, 7, 10, 12, 15, 18, 20]  # Various speeds from slow to fast
        
        scenario_count = 0
        for i in range(50):
            position = positions[i % 2]
            trigger_dist = trigger_distances[i % 5]
            speed = speeds[i % 8]
            
            # Spawn distance should be greater than trigger distance
            spawn_min = trigger_dist + 10
            spawn_max = trigger_dist + 20
            
            name = f"moving_actor_{i+1:03d}"
            tech_desc = f"Actor {position} starts moving at {speed} m/s when ego approaches"
            scenario = self._create_base_scenario(name, tech_desc)
            
            # Add actor
            actor = self._create_actor("moving_vehicle", position, spawn_min, spawn_max)
            scenario["actors"].append(actor)
            
            # Add movement action
            action = self._create_speed_action(
                "moving_vehicle", speed, "distance_to_ego", trigger_dist, "<", 2.0
            )
            scenario["actions"].append(action)
            
            # Natural language description
            vehicle_name = actor["model"].split(".")[-1]
            nl_description = (f"A {vehicle_name} is positioned {position} of the ego vehicle "
                            f"at {spawn_min}-{spawn_max} meters. When the ego vehicle approaches "
                            f"within {trigger_dist} meters, the {vehicle_name} starts moving "
                            f"at a constant speed of {speed} m/s.")
            
            self._save_scenario(scenario, nl_description, "02_moving_actors", i+1)
            scenario_count += 1
            
            if scenario_count % 10 == 0:
                print(f"  Generated {scenario_count}/50 moving actor scenarios")
        
        print(f"✓ Completed Level 2: {scenario_count} scenarios generated")
    
    def generate_level3_speed_changes(self):
        """Generate Level 3 - Speed Changes (50 scenarios)"""
        print("\n=== Generating Level 3: Speed Changes (50 scenarios) ===")
        
        initial_speeds = [5, 8, 10, 12, 15]
        speed_changes = [
            (5, 10), (10, 5),   # Speed up, slow down
            (8, 15), (15, 8),   # Larger changes
            (12, 3), (3, 12),   # Extreme changes
            (10, 18), (18, 10),
        ]
        
        scenario_count = 0
        for i in range(50):
            position = "ahead" if i % 2 == 0 else "behind"
            speed_pair = speed_changes[i % len(speed_changes)]
            initial_speed = speed_pair[0]
            final_speed = speed_pair[1]
            
            name = f"speed_change_{i+1:03d}"
            tech_desc = f"Actor changes speed from {initial_speed} to {final_speed} m/s"
            scenario = self._create_base_scenario(name, tech_desc)
            
            # Add actor
            actor = self._create_actor("speed_changing_vehicle", position, 30, 40)
            scenario["actors"].append(actor)
            
            # First action: initial speed
            action1 = self._create_speed_action(
                "speed_changing_vehicle", initial_speed, "distance_to_ego", 25, "<", 2.0
            )
            scenario["actions"].append(action1)
            
            # Second action: speed change (triggered after previous)
            action2 = self._create_speed_action(
                "speed_changing_vehicle", final_speed, "after_previous", 0, "<", 3.0, 0.5
            )
            scenario["actions"].append(action2)
            
            # Natural language description
            vehicle_name = actor["model"].split(".")[-1]
            change_type = "accelerates" if final_speed > initial_speed else "decelerates"
            nl_description = (f"A {vehicle_name} positioned {position} of the ego vehicle "
                            f"initially moves at {initial_speed} m/s when ego approaches. "
                            f"After completing the initial movement, it {change_type} to "
                            f"{final_speed} m/s in a smooth transition.")
            
            self._save_scenario(scenario, nl_description, "03_speed_changes", i+1)
            scenario_count += 1
            
            if scenario_count % 10 == 0:
                print(f"  Generated {scenario_count}/50 speed change scenarios")
        
        print(f"✓ Completed Level 3: {scenario_count} scenarios generated")
    
    def generate_level4_stop_start(self):
        """Generate Level 4 - Stop and Start (50 scenarios)"""
        print("\n=== Generating Level 4: Stop and Start (50 scenarios) ===")
        
        speed_patterns = [
            (8, 2, 10),   # Initial speed, wait time, resume speed
            (10, 3, 8),
            (12, 1, 12),
            (15, 4, 5),
            (5, 2, 15),
            (7, 3, 7),
        ]
        
        scenario_count = 0
        for i in range(50):
            position = "ahead" if i % 2 == 0 else "behind"
            pattern = speed_patterns[i % len(speed_patterns)]
            initial_speed, wait_time, resume_speed = pattern
            
            name = f"stop_start_{i+1:03d}"
            tech_desc = f"Actor moves, stops for {wait_time}s, then resumes"
            scenario = self._create_base_scenario(name, tech_desc)
            
            # Add actor
            actor = self._create_actor("stop_start_vehicle", position, 35, 45)
            scenario["actors"].append(actor)
            
            # Action sequence: move -> stop -> wait -> move
            # 1. Initial movement
            action1 = self._create_speed_action(
                "stop_start_vehicle", initial_speed, "distance_to_ego", 30, "<", 2.0
            )
            scenario["actions"].append(action1)
            
            # 2. Stop
            action2 = self._create_stop_action(
                "stop_start_vehicle", "after_previous", 0, 0.5
            )
            scenario["actions"].append(action2)
            
            # 3. Wait
            action3 = self._create_wait_action(
                "stop_start_vehicle", wait_time, 0.3
            )
            scenario["actions"].append(action3)
            
            # 4. Resume movement
            action4 = self._create_speed_action(
                "stop_start_vehicle", resume_speed, "after_previous", 0, "<", 2.0, 0.3
            )
            scenario["actions"].append(action4)
            
            # Natural language description
            vehicle_name = actor["model"].split(".")[-1]
            nl_description = (f"A {vehicle_name} positioned {position} of the ego vehicle "
                            f"moves at {initial_speed} m/s, then comes to a complete stop. "
                            f"After waiting for {wait_time} seconds, it resumes movement "
                            f"at {resume_speed} m/s.")
            
            self._save_scenario(scenario, nl_description, "04_stop_start", i+1)
            scenario_count += 1
            
            if scenario_count % 10 == 0:
                print(f"  Generated {scenario_count}/50 stop-start scenarios")
        
        print(f"✓ Completed Level 4: {scenario_count} scenarios generated")
    
    def generate_level5_multi_actors(self):
        """Generate Level 5 - Multi-Actors (60 scenarios)"""
        print("\n=== Generating Level 5: Multi-Actors (60 scenarios) ===")
        
        scenario_count = 0
        for i in range(60):
            num_actors = 2 if i < 30 else 3  # First 30 with 2 actors, next 30 with 3
            
            name = f"multi_actor_{i+1:03d}"
            tech_desc = f"Multiple actors ({num_actors}) with independent behaviors"
            scenario = self._create_base_scenario(name, tech_desc)
            
            nl_parts = []
            
            # Generate actors and their behaviors
            for j in range(num_actors):
                actor_id = f"vehicle_{chr(65+j)}"  # vehicle_A, vehicle_B, vehicle_C
                
                # Vary positions and lanes
                if j == 0:
                    position = "ahead"
                    lane_rel = "same_lane"
                    dist = (25, 35)
                elif j == 1:
                    position = "ahead" if i % 2 == 0 else "behind"
                    lane_rel = "adjacent_lane"
                    dist = (30, 40)
                else:
                    position = "behind"
                    lane_rel = "same_lane" if i % 3 == 0 else "adjacent_lane"
                    dist = (20, 30)
                
                # Add actor
                actor = self._create_actor(actor_id, position, dist[0], dist[1], lane_rel)
                scenario["actors"].append(actor)
                
                # Add behavior for each actor
                behavior_type = (i + j) % 4
                vehicle_name = actor["model"].split(".")[-1]
                
                if behavior_type == 0:
                    # Simple constant speed
                    speed = 8 + j * 2
                    action = self._create_speed_action(
                        actor_id, speed, "distance_to_ego", 20 + j*5, "<", 2.0
                    )
                    scenario["actions"].append(action)
                    nl_parts.append(f"Vehicle {chr(65+j)} ({vehicle_name}) is {position} in "
                                  f"{lane_rel.replace('_', ' ')}, moving at {speed} m/s")
                
                elif behavior_type == 1:
                    # Speed change
                    speed1, speed2 = 10, 5
                    action1 = self._create_speed_action(
                        actor_id, speed1, "distance_to_ego", 25, "<", 2.0
                    )
                    action2 = self._create_speed_action(
                        actor_id, speed2, "after_previous", 0, "<", 2.0, 0.5
                    )
                    scenario["actions"].extend([action1, action2])
                    nl_parts.append(f"Vehicle {chr(65+j)} ({vehicle_name}) is {position} in "
                                  f"{lane_rel.replace('_', ' ')}, starts at {speed1} m/s "
                                  f"then slows to {speed2} m/s")
                
                elif behavior_type == 2:
                    # Stop and go
                    action1 = self._create_speed_action(
                        actor_id, 12, "distance_to_ego", 30, "<", 2.0
                    )
                    action2 = self._create_stop_action(
                        actor_id, "after_previous", 0, 0.5
                    )
                    action3 = self._create_wait_action(actor_id, 2.0, 0.3)
                    action4 = self._create_speed_action(
                        actor_id, 8, "after_previous", 0, "<", 2.0, 0.3
                    )
                    scenario["actions"].extend([action1, action2, action3, action4])
                    nl_parts.append(f"Vehicle {chr(65+j)} ({vehicle_name}) is {position} in "
                                  f"{lane_rel.replace('_', ' ')}, performs stop-and-go behavior")
                
                else:
                    # Static
                    nl_parts.append(f"Vehicle {chr(65+j)} ({vehicle_name}) is {position} in "
                                  f"{lane_rel.replace('_', ' ')}, remaining stationary")
            
            # Natural language description
            nl_description = ". ".join(nl_parts) + "."
            
            self._save_scenario(scenario, nl_description, "05_multi_actors", i+1)
            scenario_count += 1
            
            if scenario_count % 10 == 0:
                print(f"  Generated {scenario_count}/60 multi-actor scenarios")
        
        print(f"✓ Completed Level 5: {scenario_count} scenarios generated")
    
    def generate_level6_interactions(self):
        """Generate Level 6 - Interactions (40 scenarios)"""
        print("\n=== Generating Level 6: Interactions (40 scenarios) ===")
        
        scenario_count = 0
        for i in range(40):
            name = f"interaction_{i+1:03d}"
            tech_desc = f"Actors interact based on relative positions"
            scenario = self._create_base_scenario(name, tech_desc)
            
            interaction_type = i % 5
            
            if interaction_type == 0:
                # Following behavior
                # Lead vehicle ahead
                actor1 = self._create_actor("lead_vehicle", "ahead", 30, 40, "same_lane")
                actor2 = self._create_actor("following_vehicle", "ahead", 15, 25, "same_lane")
                scenario["actors"].extend([actor1, actor2])
                
                # Lead vehicle moves
                action1 = self._create_speed_action(
                    "lead_vehicle", 10, "distance_to_ego", 35, "<", 2.0
                )
                # Following vehicle maintains distance
                action2 = self._create_speed_action(
                    "following_vehicle", 10, "distance_to_ego", 20, "<", 2.0, 0.5
                )
                # If lead slows, follower slows
                action3 = self._create_speed_action(
                    "lead_vehicle", 5, "after_previous", 0, "<", 2.0, 1.0
                )
                action4 = self._create_speed_action(
                    "following_vehicle", 5, "after_previous", 0, "<", 2.0, 0.3
                )
                scenario["actions"].extend([action1, action2, action3, action4])
                
                nl_description = (f"Lead vehicle ahead moves at 10 m/s. Following vehicle "
                                f"maintains safe distance behind lead. When lead vehicle "
                                f"slows to 5 m/s, following vehicle also reduces speed.")
            
            elif interaction_type == 1:
                # Lane change interaction
                actor1 = self._create_actor("lane_changer", "ahead", 25, 35, "adjacent_lane")
                actor2 = self._create_actor("lane_vehicle", "ahead", 40, 50, "same_lane")
                scenario["actors"].extend([actor1, actor2])
                
                # Lane vehicle moves
                action1 = self._create_speed_action(
                    "lane_vehicle", 8, "distance_to_ego", 45, "<", 2.0
                )
                # Lane changer moves and changes lane
                action2 = self._create_speed_action(
                    "lane_changer", 12, "distance_to_ego", 30, "<", 2.0
                )
                action3 = self._create_lane_change_action(
                    "lane_changer", "left", "after_previous", 0, 0.5
                )
                # Lane vehicle reacts by slowing
                action4 = self._create_speed_action(
                    "lane_vehicle", 6, "after_previous", 0, "<", 2.0, 0.3
                )
                scenario["actions"].extend([action1, action2, action3, action4])
                
                nl_description = (f"Vehicle in adjacent lane moves at 12 m/s then changes "
                                f"to ego's lane. Vehicle ahead in same lane reacts by "
                                f"slowing from 8 to 6 m/s to maintain safe distance.")
            
            elif interaction_type == 2:
                # Merge interaction
                actor1 = self._create_actor("merging_vehicle", "ahead", 20, 30, "adjacent_lane")
                actor2 = self._create_actor("main_vehicle", "ahead", 35, 45, "same_lane")
                scenario["actors"].extend([actor1, actor2])
                
                # Both vehicles start moving
                action1 = self._create_speed_action(
                    "main_vehicle", 15, "distance_to_ego", 40, "<", 2.0
                )
                action2 = self._create_speed_action(
                    "merging_vehicle", 10, "distance_to_ego", 25, "<", 2.0, 0.3
                )
                # Merging vehicle speeds up to merge
                action3 = self._create_speed_action(
                    "merging_vehicle", 15, "after_previous", 0, "<", 2.0, 0.5
                )
                action4 = self._create_lane_change_action(
                    "merging_vehicle", "left", "after_previous", 0, 0.5
                )
                scenario["actions"].extend([action1, action2, action3, action4])
                
                nl_description = (f"Merging vehicle in adjacent lane accelerates from 10 to "
                                f"15 m/s to match traffic speed, then merges into main lane "
                                f"ahead of ego vehicle.")
            
            elif interaction_type == 3:
                # Cut-in scenario
                actor1 = self._create_actor("cutting_vehicle", "ahead", 15, 20, "adjacent_lane")
                actor2 = self._create_actor("ahead_vehicle", "ahead", 30, 40, "same_lane")
                scenario["actors"].extend([actor1, actor2])
                
                # Ahead vehicle maintains speed
                action1 = self._create_speed_action(
                    "ahead_vehicle", 10, "distance_to_ego", 35, "<", 2.0
                )
                # Cutting vehicle speeds up and cuts in
                action2 = self._create_speed_action(
                    "cutting_vehicle", 15, "distance_to_ego", 18, "<", 2.0
                )
                action3 = self._create_lane_change_action(
                    "cutting_vehicle", "left", "after_previous", 0, 0.3
                )
                scenario["actions"].extend([action1, action2, action3])
                
                nl_description = (f"Vehicle in adjacent lane accelerates to 15 m/s and "
                                f"performs aggressive cut-in maneuver into ego's lane, "
                                f"positioning between ego and vehicle ahead.")
            
            else:
                # Coordinated movement
                actor1 = self._create_actor("vehicle_A", "ahead", 25, 35, "same_lane")
                actor2 = self._create_actor("vehicle_B", "ahead", 40, 50, "same_lane")
                scenario["actors"].extend([actor1, actor2])
                
                # Both vehicles move in coordination
                action1 = self._create_speed_action(
                    "vehicle_B", 12, "distance_to_ego", 45, "<", 2.0
                )
                action2 = self._create_speed_action(
                    "vehicle_A", 12, "distance_to_ego", 30, "<", 2.0, 0.5
                )
                # Both brake together
                action3 = self._create_speed_action(
                    "vehicle_B", 5, "after_previous", 0, "<", 3.0, 1.0
                )
                action4 = self._create_speed_action(
                    "vehicle_A", 5, "after_previous", 0, "<", 3.0, 0.2
                )
                scenario["actions"].extend([action1, action2, action3, action4])
                
                nl_description = (f"Two vehicles ahead move in coordination at 12 m/s. "
                                f"When front vehicle brakes to 5 m/s, following vehicle "
                                f"immediately responds with matching deceleration.")
            
            self._save_scenario(scenario, nl_description, "06_interactions", i+1)
            scenario_count += 1
            
            if scenario_count % 10 == 0:
                print(f"  Generated {scenario_count}/40 interaction scenarios")
        
        print(f"✓ Completed Level 6: {scenario_count} scenarios generated")
    
    def generate_all_scenarios(self):
        """Generate all scenarios across all complexity levels"""
        print("\n" + "="*60)
        print("CARLA Scenario Generator for LLM Training")
        print("Generating 300+ scenarios across 6 complexity levels")
        print("="*60)
        
        # Generate each level
        self.generate_level1_static_actors()
        self.generate_level2_moving_actors()
        self.generate_level3_speed_changes()
        self.generate_level4_stop_start()
        self.generate_level5_multi_actors()
        self.generate_level6_interactions()
        
        # Summary
        print("\n" + "="*60)
        print("GENERATION COMPLETE!")
        print("="*60)
        total_scenarios = sum(self.levels.values())
        print(f"Total scenarios generated: {total_scenarios}")
        print(f"Output directory: {self.output_dir}")
        print("\nScenario distribution:")
        for level, count in self.levels.items():
            print(f"  {level}: {count} scenarios")
        print("\nEach scenario includes:")
        print("  - JSON configuration file")
        print("  - Natural language description file")
        print("\n✓ Ready for LLM training!")


def main():
    """Main function to run the scenario generator"""
    generator = CarlaScenarioGenerator()
    generator.generate_all_scenarios()


if __name__ == "__main__":
    main()