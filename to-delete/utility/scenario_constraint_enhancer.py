#!/usr/bin/env python3
"""
Scenario Constraint Enhancer
Analyzes and fixes spawn constraints in CARLA scenario JSON files to ensure logical actor relationships.
"""

import json
import glob
import os
from typing import Dict, List, Any, Tuple, Optional
import re


class ScenarioConstraintEnhancer:
    """Enhances scenario spawn constraints based on scenario intent and actor relationships."""
    
    # Scenario categorization based on names and descriptions
    SCENARIO_CATEGORIES = {
        "following": ["follow", "lead", "ahead", "behind", "brake_check", "sudden_brake", "slow_leader", "stop_and_go"],
        "lane_change": ["lane_change", "cut_in", "merge", "overtake", "adjacent", "gap_closing", "aggressive_merge", "double_lane"],
        "intersection": ["intersection", "cross", "junction", "turn", "yield", "stop_sign"],
        "roundabout": ["roundabout", "circle", "yield_circle"],  
        "highway": ["highway", "freeway", "onramp", "offramp", "merge", "acceleration", "ramp"],
        "pedestrian": ["pedestrian", "crosswalk", "sidewalk", "walking", "crossing", "dart_out", "child", "elderly", "jogger"],
        "parking": ["parking", "parked", "door", "exit_parking"],
        "emergency": ["emergency", "ambulance", "police", "fire", "breakdown", "hazards"],
        "weather": ["rain", "fog", "snow", "wet", "visibility", "glare"],
        "static_obstacles": ["broken_down", "accident", "construction", "barrier", "delivery_truck", "parked_car"]
    }
    
    # Category-specific spawn requirements
    SPAWN_REQUIREMENTS = {
        "following": {
            "lead_vehicle": {
                "road_relationship": "same_road",
                "lane_relationship": "same_lane",
                "relative_position": "ahead"
            },
            "following_vehicle": {
                "road_relationship": "same_road", 
                "lane_relationship": "same_lane",
                "relative_position": "behind"
            }
        },
        
        "lane_change": {
            "lane_changer": {
                "road_relationship": "same_road",
                "lane_relationship": "adjacent_lane",
                "relative_position": "adjacent"
            },
            "cut_in_vehicle": {
                "road_relationship": "same_road",
                "lane_relationship": "adjacent_lane", 
                "relative_position": "ahead"
            }
        },
        
        "intersection": {
            "crossing_vehicle": {
                "road_relationship": "different_road",
                "junction_proximity": {"min": 5, "max": 30},
                "relative_position": "adjacent"
            }
        },
        
        "roundabout": {
            "roundabout_vehicle": {
                "junction_proximity": {"min": 0, "max": 50},
                "junction_type": "roundabout"
            }
        },
        
        "highway": {
            "merging_vehicle": {
                "road_context": "highway",
                "lane_relationship": "adjacent_lane"
            }
        },
        
        "pedestrian": {
            "pedestrian": {
                "spawn_type": "sidewalk_adjacent",
                "distance_to_ego": {"min": 15, "max": 50}
            }
        },
        
        "static_obstacles": {
            "obstacle_vehicle": {
                "road_relationship": "same_road",
                "lane_relationship": "same_lane",
                "relative_position": "ahead"
            }
        }
    }
    
    # Actor role detection patterns
    ACTOR_ROLE_PATTERNS = {
        "lead": ["lead", "ahead", "front"],
        "following": ["follow", "behind", "rear", "trail"],
        "lane_changer": ["lane_chang", "cut_in", "merg", "overtake"],
        "crossing": ["cross", "intersect", "side"],
        "oncoming": ["oncoming", "opposite"],
        "pedestrian": ["ped", "walker", "person", "child", "elderly", "jogger"],
        "emergency": ["ambulance", "police", "fire", "emergency"],
        "obstacle": ["broken", "parked", "stopped", "accident", "barrier"]
    }

    def __init__(self):
        self.processed_scenarios = []
        self.enhancement_stats = {
            "total_scenarios": 0,
            "enhanced_scenarios": 0,
            "actors_enhanced": 0,
            "constraints_added": 0
        }

    def classify_scenario(self, scenario_name: str, description: str) -> List[str]:
        """Classify scenario into categories based on name and description."""
        text = f"{scenario_name} {description}".lower()
        categories = []
        
        for category, keywords in self.SCENARIO_CATEGORIES.items():
            if any(keyword in text for keyword in keywords):
                categories.append(category)
        
        # If no categories found, try to infer from common patterns
        if not categories:
            if any(word in text for word in ["vehicle", "car", "truck"]):
                categories.append("following")  # Default vehicle category
        
        return categories

    def determine_actor_role(self, actor_id: str, actor_type: str, categories: List[str]) -> str:
        """Determine actor's role based on ID, type, and scenario categories."""
        actor_text = f"{actor_id} {actor_type}".lower()
        
        # Direct pattern matching
        for role, patterns in self.ACTOR_ROLE_PATTERNS.items():
            if any(pattern in actor_text for pattern in patterns):
                return role
        
        # Context-based role assignment
        if "pedestrian" in categories:
            if actor_type == "pedestrian":
                return "pedestrian"
        
        if "following" in categories:
            if "lead" in actor_id or "ahead" in actor_id:
                return "lead"
            elif "follow" in actor_id:
                return "following"
        
        if "lane_change" in categories:
            if any(word in actor_id for word in ["chang", "cut", "merg"]):
                return "lane_changer"
        
        return "generic_vehicle"

    def get_required_constraints(self, actor_role: str, categories: List[str]) -> Dict[str, Any]:
        """Get required constraints for an actor role in given scenario categories."""
        constraints = {}
        
        for category in categories:
            if category in self.SPAWN_REQUIREMENTS:
                category_reqs = self.SPAWN_REQUIREMENTS[category]
                
                # Direct role match
                if actor_role in category_reqs:
                    constraints.update(category_reqs[actor_role])
                
                # Fallback mappings
                elif category == "following":
                    if actor_role == "lead":
                        constraints.update(category_reqs.get("lead_vehicle", {}))
                    elif actor_role == "generic_vehicle":
                        constraints.update(category_reqs.get("lead_vehicle", {}))
                
                elif category == "lane_change":
                    if actor_role in ["lane_changer", "generic_vehicle"]:
                        constraints.update(category_reqs.get("lane_changer", {}))
                
                elif category == "static_obstacles":
                    if actor_role in ["obstacle", "generic_vehicle"]:
                        constraints.update(category_reqs.get("obstacle_vehicle", {}))
        
        return constraints

    def merge_constraints(self, existing: Dict[str, Any], required: Dict[str, Any]) -> Dict[str, Any]:
        """Intelligently merge existing and required constraints."""
        enhanced = existing.copy()
        
        # Add missing critical constraints
        critical_fields = ["road_relationship", "lane_relationship", "junction_proximity", "spawn_type"]
        
        for key, value in required.items():
            if key not in enhanced:
                enhanced[key] = value
                self.enhancement_stats["constraints_added"] += 1
            elif key == "distance_to_ego":
                # Keep existing distance if reasonable, otherwise adjust
                if self._is_distance_reasonable(existing.get(key), required.get(key)):
                    continue
                else:
                    enhanced[key] = value
                    self.enhancement_stats["constraints_added"] += 1
        
        return enhanced

    def _is_distance_reasonable(self, existing_dist: Any, required_context: Any) -> bool:
        """Check if existing distance makes sense for scenario context."""
        if not existing_dist or not isinstance(existing_dist, dict):
            return False
        
        min_dist = existing_dist.get("min", 0)
        max_dist = existing_dist.get("max", 0)
        
        # Basic reasonableness checks
        if min_dist < 5 or max_dist > 200:  # Too close or too far
            return False
        if max_dist <= min_dist:  # Invalid range
            return False
        
        return True

    def enhance_scenario_constraints(self, scenario_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance spawn constraints for a single scenario."""
        scenario_name = scenario_data.get("scenario_name", "")
        description = scenario_data.get("description", "")
        
        # Classify scenario
        categories = self.classify_scenario(scenario_name, description)
        
        if not categories:
            print(f"  Warning: Could not classify scenario '{scenario_name}'")
            return scenario_data
        
        print(f"  Classified as: {', '.join(categories)}")
        
        enhanced_scenario = scenario_data.copy()
        scenario_enhanced = False
        
        # Enhance each actor's spawn constraints
        for actor in enhanced_scenario.get("actors", []):
            actor_id = actor.get("id", "")
            actor_type = actor.get("type", "")
            
            # Determine actor role
            actor_role = self.determine_actor_role(actor_id, actor_type, categories)
            print(f"    Actor '{actor_id}' classified as '{actor_role}'")
            
            # Get required constraints for this role
            required_constraints = self.get_required_constraints(actor_role, categories)
            
            if required_constraints:
                # Get existing spawn criteria
                existing_criteria = actor.get("spawn", {}).get("criteria", {})
                
                # Merge constraints
                enhanced_criteria = self.merge_constraints(existing_criteria, required_constraints)
                
                # Update actor spawn criteria
                if "spawn" not in actor:
                    actor["spawn"] = {}
                actor["spawn"]["criteria"] = enhanced_criteria
                
                scenario_enhanced = True
                self.enhancement_stats["actors_enhanced"] += 1
                
                print(f"      Added constraints: {list(required_constraints.keys())}")
        
        if scenario_enhanced:
            self.enhancement_stats["enhanced_scenarios"] += 1
        
        return enhanced_scenario

    def process_scenario_file(self, file_path: str) -> bool:
        """Process a single scenario JSON file."""
        try:
            print(f"\nProcessing: {os.path.basename(file_path)}")
            
            # Load scenario
            with open(file_path, 'r') as f:
                scenario_data = json.load(f)
            
            self.enhancement_stats["total_scenarios"] += 1
            
            # Enhance constraints
            enhanced_scenario = self.enhance_scenario_constraints(scenario_data)
            
            # Save enhanced scenario
            with open(file_path, 'w') as f:
                json.dump(enhanced_scenario, f, indent=2)
            
            self.processed_scenarios.append(file_path)
            print(f"  ✓ Enhanced and saved")
            return True
            
        except Exception as e:
            print(f"  ✗ Error processing {file_path}: {e}")
            return False

    def process_all_scenarios(self, pattern: str = "demo_scenarios/*.json") -> None:
        """Process all scenario files matching the pattern."""
        scenario_files = glob.glob(pattern)
        
        if not scenario_files:
            print(f"No scenario files found matching pattern: {pattern}")
            return
        
        print(f"Found {len(scenario_files)} scenario files to process")
        
        success_count = 0
        for file_path in sorted(scenario_files):
            if self.process_scenario_file(file_path):
                success_count += 1
        
        # Print summary statistics
        print(f"\n{'='*60}")
        print("ENHANCEMENT SUMMARY")
        print(f"{'='*60}")
        print(f"Total scenarios processed: {self.enhancement_stats['total_scenarios']}")
        print(f"Successfully enhanced: {success_count}")
        print(f"Scenarios with enhancements: {self.enhancement_stats['enhanced_scenarios']}")
        print(f"Actors enhanced: {self.enhancement_stats['actors_enhanced']}")
        print(f"Constraints added: {self.enhancement_stats['constraints_added']}")
        
        if success_count < len(scenario_files):
            print(f"Failed to process: {len(scenario_files) - success_count} files")

    def validate_enhanced_scenario(self, file_path: str) -> Dict[str, Any]:
        """Validate that enhanced scenario has logical constraints."""
        try:
            with open(file_path, 'r') as f:
                scenario = json.load(f)
            
            validation_results = {
                "file": os.path.basename(file_path),
                "valid": True,
                "issues": [],
                "enhancements": []
            }
            
            categories = self.classify_scenario(
                scenario.get("scenario_name", ""),
                scenario.get("description", "")
            )
            
            for actor in scenario.get("actors", []):
                actor_id = actor.get("id", "")
                criteria = actor.get("spawn", {}).get("criteria", {})
                
                # Check for logical constraints
                if "following" in categories and "lead" in actor_id:
                    if "road_relationship" not in criteria:
                        validation_results["issues"].append(f"Missing road_relationship for {actor_id}")
                        validation_results["valid"] = False
                    else:
                        validation_results["enhancements"].append(f"Added road_relationship for {actor_id}")
                
                if "lane_change" in categories and "lane" in actor_id:
                    if "lane_relationship" not in criteria:
                        validation_results["issues"].append(f"Missing lane_relationship for {actor_id}")
                        validation_results["valid"] = False
                    else:
                        validation_results["enhancements"].append(f"Added lane_relationship for {actor_id}")
            
            return validation_results
            
        except Exception as e:
            return {
                "file": os.path.basename(file_path),
                "valid": False,
                "issues": [f"Validation error: {e}"],
                "enhancements": []
            }


def main():
    """Main function to run the scenario constraint enhancer."""
    enhancer = ScenarioConstraintEnhancer()
    
    print("CARLA Scenario Constraint Enhancer")
    print("="*50)
    print("Fixing spawn constraints for logical actor relationships...")
    
    # Process all scenario files
    enhancer.process_all_scenarios()
    
    print("\nEnhancement complete!")
    print("\nKey improvements made:")
    print("- Following scenarios: Lead vehicles now spawn on same road/lane as ego")
    print("- Lane change scenarios: Vehicles spawn in adjacent lanes")  
    print("- Pedestrian scenarios: Pedestrians spawn near sidewalks")
    print("- Static obstacles: Objects spawn on same road ahead of ego")


if __name__ == "__main__":
    main()