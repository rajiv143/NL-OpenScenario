#!/usr/bin/env python3
"""
CARLA Scenario Training Dataset Generator
Generates diverse training examples for fine-tuning LLMs to create CARLA driving scenarios.
Ensures all examples include RGB colors, color names, and proper JSON structure.
"""

import json
import random
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Optional, Any
from enum import Enum
import numpy as np
from pathlib import Path

# Set random seed for reproducibility
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# Color mappings with accurate RGB values
COLOR_MAPPINGS = {
    "red": [255, 0, 0],
    "crimson": [220, 20, 60],
    "blue": [0, 0, 255],
    "navy": [0, 0, 128],
    "sky_blue": [135, 206, 235],
    "white": [255, 255, 255],
    "black": [0, 0, 0],
    "silver": [192, 192, 192],
    "gray": [128, 128, 128],
    "green": [0, 255, 0],
    "forest_green": [34, 139, 34],
    "yellow": [255, 255, 0],
    "gold": [255, 215, 0],
    "orange": [255, 165, 0],
    "purple": [128, 0, 128],
    "pink": [255, 192, 203],
    "brown": [139, 69, 19],
    "beige": [245, 245, 220],
    "maroon": [128, 0, 0],
    "teal": [0, 128, 128],
    "lime": [0, 255, 0],
    "cyan": [0, 255, 255],
    "magenta": [255, 0, 255],
    "indigo": [75, 0, 130],
    "violet": [238, 130, 238]
}

# CARLA vehicle models
CARLA_VEHICLES = [
    "vehicle.tesla.model3",
    "vehicle.audi.tt",
    "vehicle.audi.a2",
    "vehicle.bmw.grandtourer",
    "vehicle.chevrolet.impala",
    "vehicle.dodge.charger_2020",
    "vehicle.ford.mustang",
    "vehicle.jeep.wrangler_rubicon",
    "vehicle.lincoln.mkz_2017",
    "vehicle.mercedes.coupe",
    "vehicle.mini.cooper_s",
    "vehicle.nissan.patrol",
    "vehicle.toyota.prius",
    "vehicle.volkswagen.t2",
    "vehicle.tesla.cybertruck"
]

# CARLA pedestrian models
CARLA_PEDESTRIANS = [f"walker.pedestrian.{i:04d}" for i in range(1, 50)]

# Weather conditions
WEATHER_CONDITIONS = [
    "clear", "cloudy", "wet", "wet_cloudy", "soft_rain", 
    "mid_rain", "hard_rain", "foggy", "storm"
]

# Times of day
TIMES_OF_DAY = ["dawn", "morning", "noon", "afternoon", "sunset", "night"]

# Action types
ACTION_TYPES = [
    "spawn", "move", "stop", "accelerate", "brake", 
    "turn_left", "turn_right", "lane_change", "park", "reverse"
]

class ScenarioComplexity(Enum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    COMPLEX = "complex"

@dataclass
class Transform:
    """CARLA transform with location and rotation"""
    location: Dict[str, float]
    rotation: Dict[str, float]
    
    @classmethod
    def random(cls, urban: bool = True):
        """Generate random but realistic transform"""
        if urban:
            x = random.uniform(-100, 100)
            y = random.uniform(-100, 100)
        else:
            x = random.uniform(-500, 500)
            y = random.uniform(-500, 500)
        
        return cls(
            location={"x": round(x, 2), "y": round(y, 2), "z": 0.5},
            rotation={"pitch": 0, "yaw": random.uniform(0, 360), "roll": 0}
        )

@dataclass
class Actor:
    """Actor in the scenario"""
    id: str
    type: str
    model: str
    color: Optional[Dict[str, Any]] = None
    spawn_point: Optional[Transform] = None
    
    def to_dict(self):
        data = {
            "id": self.id,
            "type": self.type,
            "model": self.model
        }
        if self.color:
            data["color"] = self.color
        if self.spawn_point:
            data["spawn_point"] = asdict(self.spawn_point)
        return data

@dataclass
class Action:
    """Action in the scenario"""
    timestamp: float
    actor_id: str
    action_type: str
    parameters: Dict[str, Any]
    
    def to_dict(self):
        return asdict(self)

class ScenarioGenerator:
    """Generates diverse CARLA scenarios with consistent structure"""
    
    def __init__(self):
        self.actor_counter = 0
        self.scenario_counter = 0
        
    def generate_color(self) -> Tuple[str, List[int]]:
        """Generate a color with both name and RGB values"""
        color_name = random.choice(list(COLOR_MAPPINGS.keys()))
        rgb = COLOR_MAPPINGS[color_name]
        # Occasionally add slight variations
        if random.random() < 0.3:
            rgb = [
                max(0, min(255, rgb[0] + random.randint(-20, 20))),
                max(0, min(255, rgb[1] + random.randint(-20, 20))),
                max(0, min(255, rgb[2] + random.randint(-20, 20)))
            ]
        return color_name, rgb
    
    def generate_actor(self, actor_type: str = "vehicle") -> Actor:
        """Generate a random actor"""
        self.actor_counter += 1
        actor_id = f"{actor_type}_{self.actor_counter}"
        
        if actor_type == "vehicle":
            model = random.choice(CARLA_VEHICLES)
            color_name, rgb = self.generate_color()
            color = {
                "name": color_name,
                "rgb": rgb
            }
        else:
            model = random.choice(CARLA_PEDESTRIANS)
            color = None
        
        spawn_point = Transform.random()
        
        return Actor(
            id=actor_id,
            type=actor_type,
            model=model,
            color=color,
            spawn_point=spawn_point
        )
    
    def generate_action(self, actor_id: str, timestamp: float) -> Action:
        """Generate a random action"""
        action_type = random.choice(ACTION_TYPES)
        
        parameters = {}
        if action_type in ["accelerate", "brake"]:
            parameters["intensity"] = round(random.uniform(0.3, 1.0), 2)
        elif action_type in ["turn_left", "turn_right"]:
            parameters["angle"] = random.randint(15, 90)
        elif action_type == "move":
            parameters["target"] = {
                "x": round(random.uniform(-100, 100), 2),
                "y": round(random.uniform(-100, 100), 2),
                "z": 0.5
            }
            parameters["speed"] = round(random.uniform(5, 30), 1)
        elif action_type == "lane_change":
            parameters["direction"] = random.choice(["left", "right"])
        
        return Action(
            timestamp=timestamp,
            actor_id=actor_id,
            action_type=action_type,
            parameters=parameters
        )
    
    def generate_weather(self) -> Dict[str, Any]:
        """Generate weather conditions"""
        return {
            "condition": random.choice(WEATHER_CONDITIONS),
            "sun_altitude": round(random.uniform(-90, 90), 1),
            "fog_density": round(random.uniform(0, 100), 1),
            "rain_intensity": round(random.uniform(0, 100), 1),
            "time_of_day": random.choice(TIMES_OF_DAY)
        }
    
    def generate_scenario(self, complexity: ScenarioComplexity) -> Dict[str, Any]:
        """Generate a complete scenario"""
        self.scenario_counter += 1
        
        # Determine number of actors based on complexity
        if complexity == ScenarioComplexity.BASIC:
            num_actors = 1
            num_actions = random.randint(1, 3)
        elif complexity == ScenarioComplexity.INTERMEDIATE:
            num_actors = random.randint(2, 3)
            num_actions = random.randint(3, 6)
        else:  # COMPLEX
            num_actors = random.randint(4, 6)
            num_actions = random.randint(6, 10)
        
        # Generate actors
        actors = []
        for i in range(num_actors):
            actor_type = "vehicle" if random.random() < 0.8 else "pedestrian"
            actors.append(self.generate_actor(actor_type))
        
        # Generate actions
        actions = []
        for i in range(num_actions):
            actor = random.choice(actors)
            timestamp = round(i * random.uniform(0.5, 2.0), 2)
            actions.append(self.generate_action(actor.id, timestamp))
        
        # Generate scenario
        scenario = {
            "scenario_id": f"scenario_{self.scenario_counter}",
            "actors": [actor.to_dict() for actor in actors],
            "actions": [action.to_dict() for action in actions],
            "weather": self.generate_weather(),
            "duration": round(max([a.timestamp for a in actions]) + 5, 1)
        }
        
        return scenario
    
    def generate_description(self, scenario: Dict[str, Any]) -> str:
        """Generate natural language description for a scenario"""
        descriptions = []
        
        # Describe actors
        for actor in scenario["actors"]:
            if actor["type"] == "vehicle":
                color_info = actor["color"]
                color_desc = f"{color_info['name']} (RGB {color_info['rgb'][0]}, {color_info['rgb'][1]}, {color_info['rgb'][2]})"
                desc = f"Spawn a {color_desc} {actor['model']} at position ({actor['spawn_point']['location']['x']}, {actor['spawn_point']['location']['y']})"
                descriptions.append(desc)
            else:
                desc = f"Add a pedestrian {actor['model']} at ({actor['spawn_point']['location']['x']}, {actor['spawn_point']['location']['y']})"
                descriptions.append(desc)
        
        # Describe key actions
        action_descs = []
        for action in scenario["actions"][:3]:  # Limit to first 3 actions for brevity
            actor_id = action["actor_id"]
            action_type = action["action_type"]
            
            if action_type == "accelerate":
                action_descs.append(f"{actor_id} accelerates with intensity {action['parameters']['intensity']}")
            elif action_type == "turn_left":
                action_descs.append(f"{actor_id} turns left {action['parameters']['angle']} degrees")
            elif action_type == "stop":
                action_descs.append(f"{actor_id} stops")
            elif action_type == "move":
                target = action['parameters']['target']
                action_descs.append(f"{actor_id} moves to ({target['x']}, {target['y']})")
        
        if action_descs:
            descriptions.append("Actions: " + ", ".join(action_descs))
        
        # Describe weather
        weather = scenario["weather"]
        descriptions.append(f"Weather: {weather['condition']} during {weather['time_of_day']}")
        
        return ". ".join(descriptions)
    
    def generate_training_example(self, complexity: ScenarioComplexity) -> Dict[str, str]:
        """Generate a complete training example"""
        scenario = self.generate_scenario(complexity)
        description = self.generate_description(scenario)
        
        return {
            "instruction": description,
            "input": "",
            "output": json.dumps(scenario, indent=2)
        }
    
    def generate_dataset(self, num_examples: int, split: str = "train") -> List[Dict[str, str]]:
        """Generate complete dataset"""
        examples = []
        
        # Calculate distribution
        basic_count = int(num_examples * 0.33)
        intermediate_count = int(num_examples * 0.33)
        complex_count = num_examples - basic_count - intermediate_count
        
        # Generate examples
        for _ in range(basic_count):
            examples.append(self.generate_training_example(ScenarioComplexity.BASIC))
        
        for _ in range(intermediate_count):
            examples.append(self.generate_training_example(ScenarioComplexity.INTERMEDIATE))
        
        for _ in range(complex_count):
            examples.append(self.generate_training_example(ScenarioComplexity.COMPLEX))
        
        # Shuffle for better training
        random.shuffle(examples)
        
        # Add specific test cases for validation set
        if split == "val":
            examples.extend(self.generate_test_cases())
        
        return examples
    
    def generate_test_cases(self) -> List[Dict[str, str]]:
        """Generate specific test cases for validation"""
        test_cases = []
        
        # Test case 1: Pure RGB reference
        scenario1 = self.generate_scenario(ScenarioComplexity.BASIC)
        scenario1["actors"][0]["color"] = {"name": "orange", "rgb": [255, 128, 0]}
        test_cases.append({
            "instruction": "Create a vehicle with color RGB(255, 128, 0)",
            "input": "",
            "output": json.dumps(scenario1, indent=2)
        })
        
        # Test case 2: Color name mapping
        scenario2 = self.generate_scenario(ScenarioComplexity.BASIC)
        scenario2["actors"][0]["color"] = {"name": "crimson", "rgb": [220, 20, 60]}
        test_cases.append({
            "instruction": "Spawn a crimson red car",
            "input": "",
            "output": json.dumps(scenario2, indent=2)
        })
        
        # Test case 3: Complex actions
        scenario3 = self.generate_scenario(ScenarioComplexity.INTERMEDIATE)
        scenario3["actions"] = [
            {"timestamp": 0.0, "actor_id": "vehicle_1", "action_type": "accelerate", "parameters": {"intensity": 0.8}},
            {"timestamp": 2.0, "actor_id": "vehicle_1", "action_type": "brake", "parameters": {"intensity": 1.0}}
        ]
        test_cases.append({
            "instruction": "Vehicle accelerates, then brakes suddenly",
            "input": "",
            "output": json.dumps(scenario3, indent=2)
        })
        
        return test_cases

def calculate_statistics(examples: List[Dict[str, str]]) -> Dict[str, Any]:
    """Calculate dataset statistics"""
    stats = {
        "total_examples": len(examples),
        "colors_used": {},
        "action_types": {},
        "vehicle_models": {},
        "complexity_distribution": {"basic": 0, "intermediate": 0, "complex": 0},
        "avg_actors_per_scenario": 0,
        "avg_actions_per_scenario": 0
    }
    
    total_actors = 0
    total_actions = 0
    
    for example in examples:
        try:
            scenario = json.loads(example["output"])
            
            # Count actors
            num_actors = len(scenario["actors"])
            total_actors += num_actors
            
            # Determine complexity
            if num_actors == 1:
                stats["complexity_distribution"]["basic"] += 1
            elif num_actors <= 3:
                stats["complexity_distribution"]["intermediate"] += 1
            else:
                stats["complexity_distribution"]["complex"] += 1
            
            # Count colors
            for actor in scenario["actors"]:
                if "color" in actor and actor["color"]:
                    color_name = actor["color"]["name"]
                    stats["colors_used"][color_name] = stats["colors_used"].get(color_name, 0) + 1
                
                # Count vehicle models
                if actor["type"] == "vehicle":
                    model = actor["model"]
                    stats["vehicle_models"][model] = stats["vehicle_models"].get(model, 0) + 1
            
            # Count actions
            num_actions = len(scenario["actions"])
            total_actions += num_actions
            
            for action in scenario["actions"]:
                action_type = action["action_type"]
                stats["action_types"][action_type] = stats["action_types"].get(action_type, 0) + 1
        
        except json.JSONDecodeError:
            print(f"Warning: Could not parse JSON in example")
            continue
    
    stats["avg_actors_per_scenario"] = round(total_actors / len(examples), 2)
    stats["avg_actions_per_scenario"] = round(total_actions / len(examples), 2)
    
    return stats

def main():
    """Main function to generate datasets"""
    print("CARLA Scenario Training Dataset Generator")
    print("=" * 50)
    
    # Initialize generator
    generator = ScenarioGenerator()
    
    # Generate training dataset
    print("\nGenerating training dataset...")
    train_examples = generator.generate_dataset(500, split="train")
    
    # Save training dataset
    train_path = Path("carla_scenarios_train.jsonl")
    with open(train_path, "w") as f:
        for example in train_examples:
            f.write(json.dumps(example) + "\n")
    print(f"✓ Saved {len(train_examples)} training examples to {train_path}")
    
    # Generate validation dataset
    print("\nGenerating validation dataset...")
    val_examples = generator.generate_dataset(47, split="val")  # 47 + 3 test cases = 50
    
    # Save validation dataset
    val_path = Path("carla_scenarios_val.jsonl")
    with open(val_path, "w") as f:
        for example in val_examples:
            f.write(json.dumps(example) + "\n")
    print(f"✓ Saved {len(val_examples)} validation examples to {val_path}")
    
    # Calculate and save statistics
    print("\nCalculating dataset statistics...")
    all_examples = train_examples + val_examples
    stats = calculate_statistics(all_examples)
    
    stats_path = Path("dataset_statistics.json")
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"✓ Saved statistics to {stats_path}")
    
    # Print summary
    print("\n" + "=" * 50)
    print("Dataset Generation Complete!")
    print(f"Total examples: {stats['total_examples']}")
    print(f"Unique colors: {len(stats['colors_used'])}")
    print(f"Unique actions: {len(stats['action_types'])}")
    print(f"Avg actors/scenario: {stats['avg_actors_per_scenario']}")
    print(f"Avg actions/scenario: {stats['avg_actions_per_scenario']}")
    print("\nComplexity distribution:")
    for level, count in stats['complexity_distribution'].items():
        percentage = (count / stats['total_examples']) * 100
        print(f"  {level.capitalize()}: {count} ({percentage:.1f}%)")

if __name__ == "__main__":
    main()