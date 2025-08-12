#!/usr/bin/env python3
"""
Validation script for enhanced scenario constraints.
Tests that logical spawn relationships are now properly defined.
"""

import json
import glob
import os
from typing import Dict, List, Any

def validate_scenario_file(file_path: str) -> Dict[str, Any]:
    """Validate a single enhanced scenario file."""
    try:
        with open(file_path, 'r') as f:
            scenario = json.load(f)
        
        filename = os.path.basename(file_path)
        scenario_name = scenario.get("scenario_name", "")
        description = scenario.get("description", "")
        
        validation = {
            "file": filename,
            "scenario_name": scenario_name,
            "valid": True,
            "improvements": [],
            "issues": [],
            "actors": len(scenario.get("actors", []))
        }
        
        # Check following scenarios
        if any(keyword in scenario_name.lower() for keyword in ["following", "brake", "lead", "ahead"]):
            validation["category"] = "following"
            for actor in scenario.get("actors", []):
                actor_id = actor.get("id", "")
                criteria = actor.get("spawn", {}).get("criteria", {})
                
                if "lead" in actor_id:
                    if "road_relationship" in criteria and criteria["road_relationship"] == "same_road":
                        validation["improvements"].append(f"✓ {actor_id}: Added same_road constraint")
                    else:
                        validation["issues"].append(f"✗ {actor_id}: Missing road_relationship")
                        validation["valid"] = False
                    
                    if "lane_relationship" in criteria and criteria["lane_relationship"] == "same_lane":
                        validation["improvements"].append(f"✓ {actor_id}: Added same_lane constraint")
                    else:
                        validation["issues"].append(f"✗ {actor_id}: Missing lane_relationship")
                        validation["valid"] = False
        
        # Check lane change scenarios
        elif any(keyword in scenario_name.lower() for keyword in ["lane_change", "cut_in", "merge", "overtake"]):
            validation["category"] = "lane_change"
            for actor in scenario.get("actors", []):
                actor_id = actor.get("id", "")
                criteria = actor.get("spawn", {}).get("criteria", {})
                
                if any(keyword in actor_id for keyword in ["chang", "cut", "merg"]):
                    if "road_relationship" in criteria and criteria["road_relationship"] == "same_road":
                        validation["improvements"].append(f"✓ {actor_id}: Added same_road constraint")
                    else:
                        validation["issues"].append(f"✗ {actor_id}: Missing road_relationship")
                        validation["valid"] = False
                    
                    if "lane_relationship" in criteria and criteria["lane_relationship"] == "adjacent_lane":
                        validation["improvements"].append(f"✓ {actor_id}: Added adjacent_lane constraint")
                    else:
                        validation["issues"].append(f"✗ {actor_id}: Missing lane_relationship")
                        validation["valid"] = False
        
        # Check pedestrian scenarios
        elif any(keyword in scenario_name.lower() for keyword in ["pedestrian", "crossing", "dart", "child", "elderly"]):
            validation["category"] = "pedestrian"
            for actor in scenario.get("actors", []):
                actor_id = actor.get("id", "")
                actor_type = actor.get("type", "")
                criteria = actor.get("spawn", {}).get("criteria", {})
                
                if actor_type == "pedestrian":
                    if "spawn_type" in criteria and criteria["spawn_type"] == "sidewalk_adjacent":
                        validation["improvements"].append(f"✓ {actor_id}: Added sidewalk_adjacent spawn")
                    else:
                        validation["issues"].append(f"✗ {actor_id}: Missing spawn_type for pedestrian")
                        validation["valid"] = False
        
        # Check static obstacle scenarios
        elif any(keyword in scenario_name.lower() for keyword in ["broken", "accident", "construction", "parked"]):
            validation["category"] = "static_obstacles"
            for actor in scenario.get("actors", []):
                actor_id = actor.get("id", "")
                criteria = actor.get("spawn", {}).get("criteria", {})
                
                if "road_relationship" in criteria and criteria["road_relationship"] == "same_road":
                    validation["improvements"].append(f"✓ {actor_id}: Added same_road constraint")
                else:
                    validation["issues"].append(f"✗ {actor_id}: Missing road_relationship")
                    validation["valid"] = False
        
        else:
            validation["category"] = "other"
        
        return validation
        
    except Exception as e:
        return {
            "file": os.path.basename(file_path),
            "scenario_name": "ERROR",
            "valid": False,
            "improvements": [],
            "issues": [f"Validation error: {e}"],
            "actors": 0,
            "category": "error"
        }

def main():
    """Main validation function."""
    print("Validating Enhanced Scenario Constraints")
    print("="*50)
    
    scenario_files = sorted(glob.glob("demo_scenarios/*.json"))
    
    if not scenario_files:
        print("No scenario files found!")
        return
    
    # Statistics
    stats = {
        "total": 0,
        "valid": 0,
        "following": 0,
        "lane_change": 0,
        "pedestrian": 0,
        "static_obstacles": 0,
        "other": 0,
        "improvements": 0,
        "issues": 0
    }
    
    validation_results = []
    
    # Validate each scenario
    for file_path in scenario_files:
        result = validate_scenario_file(file_path)
        validation_results.append(result)
        
        stats["total"] += 1
        if result["valid"]:
            stats["valid"] += 1
        stats[result["category"]] += 1
        stats["improvements"] += len(result["improvements"])
        stats["issues"] += len(result["issues"])
    
    # Print summary by category
    print(f"\nValidation Results Summary:")
    print(f"Total scenarios: {stats['total']}")
    print(f"Valid scenarios: {stats['valid']}")
    print(f"Following scenarios: {stats['following']}")
    print(f"Lane change scenarios: {stats['lane_change']}")
    print(f"Pedestrian scenarios: {stats['pedestrian']}")
    print(f"Static obstacle scenarios: {stats['static_obstacles']}")
    print(f"Other scenarios: {stats['other']}")
    print(f"Total improvements: {stats['improvements']}")
    print(f"Total issues: {stats['issues']}")
    
    # Show sample improvements
    print(f"\n{'='*60}")
    print("SAMPLE VALIDATION RESULTS")
    print(f"{'='*60}")
    
    # Show some successful enhancements
    following_examples = [r for r in validation_results if r["category"] == "following" and r["valid"]][:3]
    lane_change_examples = [r for r in validation_results if r["category"] == "lane_change" and r["valid"]][:3]
    pedestrian_examples = [r for r in validation_results if r["category"] == "pedestrian" and r["valid"]][:3]
    
    if following_examples:
        print("\nFOLLOWING SCENARIOS (Fixed):")
        for example in following_examples:
            print(f"  {example['file']}:")
            for improvement in example["improvements"]:
                print(f"    {improvement}")
    
    if lane_change_examples:
        print("\nLANE CHANGE SCENARIOS (Fixed):")
        for example in lane_change_examples:
            print(f"  {example['file']}:")
            for improvement in example["improvements"]:
                print(f"    {improvement}")
    
    if pedestrian_examples:
        print("\nPEDESTRIAN SCENARIOS (Fixed):")
        for example in pedestrian_examples:
            print(f"  {example['file']}:")
            for improvement in example["improvements"]:
                print(f"    {improvement}")
    
    # Show any remaining issues
    issues_found = [r for r in validation_results if not r["valid"]]
    if issues_found:
        print(f"\nREMAINING ISSUES ({len(issues_found)} scenarios):")
        for issue in issues_found[:5]:  # Show first 5
            print(f"  {issue['file']}:")
            for problem in issue["issues"]:
                print(f"    {problem}")
    else:
        print(f"\n✓ ALL SCENARIOS VALIDATED SUCCESSFULLY!")
    
    # Calculate success rate
    success_rate = (stats["valid"] / stats["total"]) * 100 if stats["total"] > 0 else 0
    print(f"\nOverall Success Rate: {success_rate:.1f}%")
    
    if success_rate >= 90:
        print("🎉 Excellent! Most scenarios now have proper logical constraints.")
    elif success_rate >= 75:
        print("👍 Good progress! Most spawn issues have been resolved.")
    else:
        print("⚠️  Some scenarios still need attention.")

if __name__ == "__main__":
    main()