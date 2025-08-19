#!/usr/bin/env python3
"""
JSON to OpenSCENARIO 2.0 Converter for ADS Testing
Transforms high-level scenario JSON descriptions into valid OSC 2.0 format
where NPC vehicles perform actions to test the ADS-controlled ego vehicle.
"""

import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VehicleType(Enum):
    """Supported vehicle types in OSC 2.0"""
    MODEL3 = "Model3"
    RUBICON = "Rubicon"
    SEDAN = "vehicle.sedan"
    SUV = "vehicle.suv"
    TRUCK = "vehicle.truck"
    VAN = "vehicle.van"
    MOTORCYCLE = "vehicle.motorcycle"


class BehaviorType(Enum):
    """Supported behavior types"""
    CUT_IN = "cut_in"
    CUT_OUT = "cut_out"
    FOLLOW = "follow"
    LANE_CHANGE = "lane_change"
    BRAKE = "brake"
    ACCELERATE = "accelerate"
    OVERTAKE = "overtake"
    MERGE = "merge"
    DRIVE = "drive"


@dataclass
class Actor:
    """Represents an actor in the scenario"""
    name: str
    type: str  # Model3, Rubicon, etc.
    initial_speed: float = 30.0  # kph
    initial_lane: Optional[int] = None
    initial_position: Optional[Dict[str, Any]] = None


@dataclass 
class Action:
    """Represents an action in the scenario"""
    name: str
    type: str  # parallel, serial
    duration: Optional[float] = None
    actions: List[Any] = None
    
    def __post_init__(self):
        if self.actions is None:
            self.actions = []


@dataclass
class DriveAction:
    """Represents a drive action with modifiers"""
    actor: str
    speed: Optional[float] = None  # kph
    lane: Optional[Any] = None  # int or relative position
    position: Optional[Dict[str, Any]] = None
    duration: Optional[float] = None


class JSONToOSCConverter:
    """Converter for JSON to OSC 2.0 format for ADS testing"""
    
    def __init__(self):
        self.scenario_name: str = "top"  # Use 'top' as default like the working example
        self.map_name: str = "Town04"
        self.min_lanes: int = 2
        self.actors: List[Actor] = []
        self.actions: List[Action] = []
        self.total_duration: float = 30.0
        
    def json_to_osc(self, json_input: Dict[str, Any]) -> str:
        """
        Convert JSON scenario to OSC 2.0 format
        
        Args:
            json_input: Dictionary containing scenario description
            
        Returns:
            String containing valid OSC 2.0 scenario
        """
        try:
            # Reset state for each conversion
            self.scenario_name = "top"  # Always use 'top' like the working example
            self.map_name = "Town04"
            self.min_lanes = 2
            self.actors = []
            self.actions = []
            self.total_duration = 30.0
            
            # Parse JSON input
            self._parse_json(json_input)
            
            # Generate OSC content
            osc_content = self._generate_osc()
            
            return osc_content
            
        except Exception as e:
            logger.error(f"Conversion failed: {str(e)}")
            raise
    
    def _parse_json(self, json_input: Dict[str, Any]) -> None:
        """Parse JSON input and extract scenario components"""
        
        # Map configuration
        map_config = json_input.get("map", {})
        if isinstance(map_config, str):
            self.map_name = map_config
        else:
            self.map_name = map_config.get("name", "Town04")
            self.min_lanes = map_config.get("min_lanes", 2)
        
        # Parse actors
        actors_data = json_input.get("actors", [])
        for actor_data in actors_data:
            actor = Actor(
                name=actor_data.get("name", ""),
                type=actor_data.get("type", "Model3"),
                initial_speed=actor_data.get("initial_speed", 30.0),
                initial_lane=actor_data.get("initial_lane"),
                initial_position=actor_data.get("initial_position")
            )
            self.actors.append(actor)
        
        # Parse actions/behaviors
        self.total_duration = json_input.get("duration", 30.0)
        actions_data = json_input.get("actions", [])
        self.actions = self._parse_actions(actions_data)
    
    def _parse_actions(self, actions_data: List[Dict[str, Any]]) -> List[Action]:
        """Parse action definitions"""
        actions = []
        
        for action_data in actions_data:
            action_type = action_data.get("type", "parallel")
            
            if action_type in ["parallel", "serial"]:
                action = Action(
                    name=action_data.get("name", ""),
                    type=action_type,
                    duration=action_data.get("duration")
                )
                
                # Parse nested actions
                if "actions" in action_data:
                    action.actions = self._parse_actions(action_data["actions"])
                
                # Parse drive actions
                if "drive" in action_data:
                    drive_data = action_data["drive"]
                    drive_action = DriveAction(
                        actor=drive_data.get("actor", "npc"),
                        speed=drive_data.get("speed"),
                        lane=drive_data.get("lane"),
                        position=drive_data.get("position"),
                        duration=action_data.get("duration")
                    )
                    action.actions.append(drive_action)
                
                actions.append(action)
                
            elif action_type == "drive":
                # Direct drive action
                drive_action = DriveAction(
                    actor=action_data.get("actor", "npc"),
                    speed=action_data.get("speed"),
                    lane=action_data.get("lane"),
                    position=action_data.get("position"),
                    duration=action_data.get("duration")
                )
                actions.append(drive_action)
        
        return actions
    
    def _generate_osc(self) -> str:
        """Generate OSC 2.0 content"""
        lines = []
        
        # Import basic definitions
        lines.append("import basic.osc")
        lines.append("")
        
        # Start scenario - always use 'top' like the working example
        lines.append("scenario top:")
        
        # Path configuration with exact formatting from working example
        lines.append("    path: Path                 ")
        lines.append(f'    path.set_map("{self.map_name}")')
        lines.append(f"    path.path_min_driving_lanes({self.min_lanes})")
        lines.append("")
        
        # Define actors with exact formatting
        # Ego vehicle is always first for ADS testing
        lines.append(f"    ego_vehicle: Model3                 # ego car")
        
        # Add NPC vehicles
        for i, actor in enumerate(self.actors):
            if actor.name != "ego_vehicle":
                if i == 1 or (i == 0 and len(self.actors) == 1):  # First NPC
                    lines.append(f"    {actor.name}: {actor.type}                        # The other car")
                else:
                    lines.append(f"    {actor.name}: {actor.type}")
        lines.append("")
        
        # Events
        lines.append("    event start")
        lines.append("    event end")
        
        # Main action block
        lines.append(f"    do parallel(duration: {self.total_duration}s):")
        
        # Generate actions
        action_lines = self._generate_actions(self.actions, indent=2)
        lines.extend(action_lines)
        
        # Ensure file ends with newline
        return "\n".join(lines) + "\n"
    
    def _generate_actions(self, actions: List[Any], indent: int = 0) -> List[str]:
        """Generate action lines with proper indentation"""
        lines = []
        base_indent = "    " * indent
        
        for i, action in enumerate(actions):
            if isinstance(action, Action):
                # Handle parallel/serial blocks
                duration_str = f"(duration: {action.duration}s)" if action.duration else ""
                
                if action.name:
                    lines.append(f"{base_indent}{action.name}: {action.type}{duration_str}:")
                else:
                    # Add extra line before serial block if it's not the first action
                    if action.type == "serial" and i > 0:
                        lines.append(f"{base_indent}")
                    lines.append(f"{base_indent}{action.type}{duration_str}:")
                
                # Recursively generate nested actions
                nested_lines = self._generate_actions(action.actions, indent + 1)
                lines.extend(nested_lines)
                
                # Add spacing after parallel blocks in serial
                if action.type == "parallel" and action.name:
                    lines.append("")
                    
            elif isinstance(action, DriveAction):
                # Generate drive action
                drive_lines = self._generate_drive_action(action, indent)
                lines.extend(drive_lines)
        
        return lines
    
    def _generate_drive_action(self, drive: DriveAction, indent: int) -> List[str]:
        """Generate drive action with modifiers"""
        lines = []
        base_indent = "    " * indent
        
        # Format drive action
        lines.append(f"{base_indent}{drive.actor}.drive(path) with:")
        
        # Add modifiers
        if drive.speed is not None:
            lines.append(f"{base_indent}    speed({drive.speed}kph)")
        
        if drive.lane is not None:
            if isinstance(drive.lane, int):
                # Add comment for first lane assignment
                if drive.actor == "ego_vehicle":
                    lines.append(f"{base_indent}    lane({drive.lane}, at: start)")
                else:
                    lines.append(f"{base_indent}    lane({drive.lane}, at: start) # left to right: [1..n]")
            elif isinstance(drive.lane, dict):
                # Relative lane position
                if "same_as" in drive.lane:
                    at_pos = drive.lane.get("at", "start")
                    lines.append(f"{base_indent}    lane(same_as: {drive.lane['same_as']}, at: {at_pos})")
                elif "left_of" in drive.lane:
                    at_pos = drive.lane.get("at", "end")
                    lines.append(f"{base_indent}    lane(left_of: {drive.lane['left_of']}, at: {at_pos})")
                elif "right_of" in drive.lane:
                    at_pos = drive.lane.get("at", "end")
                    lines.append(f"{base_indent}    lane(right_of: {drive.lane['right_of']}, at: {at_pos})")
        
        if drive.position is not None:
            # Position relative to another actor
            distance = drive.position.get("distance", "10m")
            relative = drive.position.get("relative", "behind")
            target = drive.position.get("target", "ego_vehicle")
            at_pos = drive.position.get("at", "start")
            
            # Fix relative position syntax (ahead -> ahead_of)
            if relative == "ahead":
                relative = "ahead_of"
            
            lines.append(f"{base_indent}    position({distance}, {relative}: {target}, at: {at_pos})")
        
        return lines


def create_test_scenarios() -> List[Dict[str, Any]]:
    """Create test JSON scenarios for ADS testing"""
    
    # Scenario 1: NPC cuts in front of ego (ADS must handle cut-in)
    cut_in_scenario = {
        "name": "npc_cut_in",
        "map": {
            "name": "Town04",
            "min_lanes": 2
        },
        "actors": [
            {
                "name": "npc",
                "type": "Rubicon",
                "initial_speed": 50.0
            }
        ],
        "duration": 20,
        "actions": [
            {
                "type": "drive",
                "actor": "ego_vehicle",
                "speed": 40,
                "lane": 2
            },
            {
                "type": "serial",
                "actions": [
                    {
                        "name": "npc_approach",
                        "type": "parallel",
                        "duration": 5,
                        "drive": {
                            "actor": "npc",
                            "speed": 50,
                            "lane": 1,
                            "position": {
                                "distance": "30m",
                                "relative": "behind",
                                "target": "ego_vehicle",
                                "at": "start"
                            }
                        }
                    },
                    {
                        "name": "npc_overtake",
                        "type": "parallel",
                        "duration": 3,
                        "drive": {
                            "actor": "npc",
                            "speed": 55,
                            "position": {
                                "distance": "10m",
                                "relative": "ahead_of",
                                "target": "ego_vehicle",
                                "at": "end"
                            }
                        }
                    },
                    {
                        "name": "npc_cut_in",
                        "type": "parallel",
                        "duration": 3,
                        "drive": {
                            "actor": "npc",
                            "lane": {"same_as": "ego_vehicle", "at": "end"}
                        }
                    },
                    {
                        "name": "npc_brake",
                        "type": "parallel",
                        "duration": 4,
                        "drive": {
                            "actor": "npc",
                            "speed": 25
                        }
                    }
                ]
            }
        ]
    }
    
    # Scenario 2: NPC suddenly brakes in front (ADS must maintain safe distance)
    sudden_brake_scenario = {
        "name": "npc_sudden_brake",
        "map": {
            "name": "Town04",
            "min_lanes": 2
        },
        "actors": [
            {
                "name": "npc",
                "type": "Rubicon",
                "initial_speed": 50.0
            }
        ],
        "duration": 15,
        "actions": [
            {
                "type": "drive",
                "actor": "ego_vehicle",
                "speed": 50,
                "lane": 1
            },
            {
                "type": "drive",
                "actor": "npc",
                "speed": 50,
                "lane": 1,
                "position": {
                    "distance": "20m",
                    "relative": "ahead_of",
                    "target": "ego_vehicle",
                    "at": "start"
                }
            },
            {
                "type": "serial",
                "actions": [
                    {
                        "name": "cruise",
                        "type": "parallel",
                        "duration": 5,
                        "drive": {
                            "actor": "npc",
                            "speed": 50
                        }
                    },
                    {
                        "name": "sudden_brake",
                        "type": "parallel",
                        "duration": 3,
                        "drive": {
                            "actor": "npc",
                            "speed": 15
                        }
                    },
                    {
                        "name": "resume",
                        "type": "parallel",
                        "duration": 5,
                        "drive": {
                            "actor": "npc",
                            "speed": 40
                        }
                    }
                ]
            }
        ]
    }
    
    # Scenario 3: Multiple NPCs surrounding ego (ADS must navigate complex traffic)
    multi_npc_scenario = {
        "name": "multi_npc_traffic",
        "map": {
            "name": "Town04",
            "min_lanes": 3
        },
        "actors": [
            {
                "name": "npc1",
                "type": "Rubicon",
                "initial_speed": 45.0
            },
            {
                "name": "npc2",
                "type": "Model3",
                "initial_speed": 35.0
            }
        ],
        "duration": 25,
        "actions": [
            # Ego in middle lane
            {
                "type": "drive",
                "actor": "ego_vehicle",
                "speed": 40,
                "lane": 2
            },
            # NPC1 in left lane, slightly ahead
            {
                "type": "drive",
                "actor": "npc1",
                "speed": 45,
                "lane": 1,
                "position": {
                    "distance": "15m",
                    "relative": "ahead_of",
                    "target": "ego_vehicle",
                    "at": "start"
                }
            },
            # NPC2 in right lane, behind
            {
                "type": "drive",
                "actor": "npc2",
                "speed": 35,
                "lane": 3,
                "position": {
                    "distance": "10m",
                    "relative": "behind",
                    "target": "ego_vehicle",
                    "at": "start"
                }
            },
            {
                "type": "serial",
                "actions": [
                    {
                        "name": "initial_cruise",
                        "type": "parallel",
                        "duration": 5
                    },
                    {
                        "name": "npc1_changes_lane",
                        "type": "parallel",
                        "duration": 4,
                        "drive": {
                            "actor": "npc1",
                            "lane": {"same_as": "ego_vehicle", "at": "end"}
                        }
                    },
                    {
                        "name": "npc2_speeds_up",
                        "type": "parallel",
                        "duration": 4,
                        "drive": {
                            "actor": "npc2",
                            "speed": 50
                        }
                    },
                    {
                        "name": "npc1_brakes",
                        "type": "parallel",
                        "duration": 3,
                        "drive": {
                            "actor": "npc1",
                            "speed": 25
                        }
                    }
                ]
            }
        ]
    }
    
    # Scenario 4: NPC swerves into ego's lane (emergency avoidance test)
    swerve_scenario = {
        "name": "npc_swerve",
        "map": {
            "name": "Town04",
            "min_lanes": 2
        },
        "actors": [
            {
                "name": "npc",
                "type": "Rubicon",
                "initial_speed": 60.0
            }
        ],
        "duration": 12,
        "actions": [
            {
                "type": "drive",
                "actor": "ego_vehicle",
                "speed": 50,
                "lane": 2
            },
            {
                "type": "serial",
                "actions": [
                    {
                        "name": "npc_parallel_drive",
                        "type": "parallel",
                        "duration": 5,
                        "drive": {
                            "actor": "npc",
                            "speed": 60,
                            "lane": 1,
                            "position": {
                                "distance": "5m",
                                "relative": "behind",
                                "target": "ego_vehicle",
                                "at": "start"
                            }
                        }
                    },
                    {
                        "name": "npc_sudden_swerve",
                        "type": "parallel",
                        "duration": 2,
                        "drive": {
                            "actor": "npc",
                            "lane": {"same_as": "ego_vehicle", "at": "end"},
                            "speed": 60
                        }
                    }
                ]
            }
        ]
    }
    
    return [cut_in_scenario, sudden_brake_scenario, multi_npc_scenario, swerve_scenario]


def convert_and_save_scenarios():
    """Convert test scenarios and save to files"""
    converter = JSONToOSCConverter()
    scenarios = create_test_scenarios()
    
    for i, scenario_json in enumerate(scenarios):
        name = scenario_json["name"]
        try:
            # Reset converter state
            converter = JSONToOSCConverter()
            
            # Convert to OSC
            osc_content = converter.json_to_osc(scenario_json)
            
            # Save OSC file
            output_file = f"ads_test_{name}.osc"
            with open(output_file, 'w') as f:
                f.write(osc_content)
            
            # Save JSON file for reference
            json_file = f"ads_test_{name}.json"
            with open(json_file, 'w') as f:
                json.dump(scenario_json, f, indent=2)
            
            logger.info(f"✓ Converted {name}")
            logger.info(f"  - OSC: {output_file}")
            logger.info(f"  - JSON: {json_file}")
            
        except Exception as e:
            logger.error(f"✗ Failed to convert {name}: {e}")


if __name__ == "__main__":
    print("JSON to OpenSCENARIO 2.0 Converter for ADS Testing")
    print("=" * 50)
    
    # Convert and save test scenarios
    convert_and_save_scenarios()
    
    print("\nConversion complete!")
    print("Generated ADS test scenarios:")
    print("  - ads_test_npc_cut_in.osc")
    print("  - ads_test_npc_sudden_brake.osc")
    print("  - ads_test_multi_npc_traffic.osc")
    print("  - ads_test_npc_swerve.osc")
    print("\nTo test with your ADS:")
    print("1. Copy desired file to /home/user/EvoDrive/scenario_runner/converted_xosc/output.osc")
    print("2. Run: python scenario_runner.py --openscenario2 output.osc --reloadWorld")
    print("\nThese scenarios test the ADS response to:")
    print("  - Cut-in situations")
    print("  - Sudden braking")
    print("  - Multi-vehicle traffic")
    print("  - Emergency swerving")