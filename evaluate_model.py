#!/usr/bin/env python3
"""
Evaluation script for CARLA scenario generation model
Tests JSON validity, schema compliance, and semantic accuracy
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any
import argparse
from collections import Counter

class CarlaScenarioEvaluator:
    def __init__(self):
        """Initialize the evaluator with schema requirements"""
        self.required_fields = {
            "scenario_name", "description", "weather", 
            "ego_vehicle_model", "ego_spawn", "ego_start_speed",
            "actors", "actions", "success_distance", 
            "timeout", "collision_allowed"
        }
        
        self.valid_weather = {"clear", "cloudy", "soft_rain", "wet", "hard_rain"}
        self.valid_action_types = {"speed", "stop", "wait", "lane_change"}
        self.valid_trigger_types = {"distance_to_ego", "after_previous", "time"}
        self.valid_vehicle_models = {
            "vehicle.audi.a2", "vehicle.toyota.prius", 
            "vehicle.bmw.grandtourer", "vehicle.ford.crown",
            "vehicle.mercedes.sprinter", "vehicle.audi.tt"
        }
        
        self.evaluation_results = []
    
    def validate_json_structure(self, scenario: Dict) -> Tuple[bool, List[str]]:
        """Validate JSON structure and required fields"""
        errors = []
        
        # Check required fields
        missing_fields = self.required_fields - set(scenario.keys())
        if missing_fields:
            errors.append(f"Missing required fields: {missing_fields}")
        
        # Validate weather
        if "weather" in scenario and scenario["weather"] not in self.valid_weather:
            errors.append(f"Invalid weather: {scenario['weather']}")
        
        # Validate ego_spawn structure
        if "ego_spawn" in scenario:
            if not isinstance(scenario["ego_spawn"], dict):
                errors.append("ego_spawn must be a dictionary")
            elif "criteria" not in scenario["ego_spawn"]:
                errors.append("ego_spawn missing 'criteria' field")
        
        # Validate actors
        if "actors" in scenario:
            if not isinstance(scenario["actors"], list):
                errors.append("actors must be a list")
            else:
                for i, actor in enumerate(scenario["actors"]):
                    actor_errors = self._validate_actor(actor, i)
                    errors.extend(actor_errors)
        
        # Validate actions
        if "actions" in scenario:
            if not isinstance(scenario["actions"], list):
                errors.append("actions must be a list")
            else:
                for i, action in enumerate(scenario["actions"]):
                    action_errors = self._validate_action(action, i)
                    errors.extend(action_errors)
        
        return len(errors) == 0, errors
    
    def _validate_actor(self, actor: Dict, index: int) -> List[str]:
        """Validate individual actor structure"""
        errors = []
        prefix = f"Actor {index}"
        
        required_actor_fields = {"id", "type", "spawn"}
        missing = required_actor_fields - set(actor.keys())
        if missing:
            errors.append(f"{prefix}: Missing fields {missing}")
        
        if "model" in actor:
            # Check if model is valid (allow partial matches for flexibility)
            model = actor["model"]
            if not any(valid in model for valid in ["vehicle", "walker", "prop"]):
                errors.append(f"{prefix}: Invalid model type: {model}")
        
        if "spawn" in actor and isinstance(actor["spawn"], dict):
            if "criteria" not in actor["spawn"]:
                errors.append(f"{prefix}: spawn missing 'criteria'")
        
        return errors
    
    def _validate_action(self, action: Dict, index: int) -> List[str]:
        """Validate individual action structure"""
        errors = []
        prefix = f"Action {index}"
        
        required_action_fields = {"actor_id", "action_type"}
        missing = required_action_fields - set(action.keys())
        if missing:
            errors.append(f"{prefix}: Missing fields {missing}")
        
        if "action_type" in action:
            if action["action_type"] not in self.valid_action_types:
                errors.append(f"{prefix}: Invalid action_type: {action['action_type']}")
        
        if "trigger_type" in action:
            if action["trigger_type"] not in self.valid_trigger_types:
                errors.append(f"{prefix}: Invalid trigger_type: {action['trigger_type']}")
        
        # Validate action-specific fields
        if action.get("action_type") == "speed":
            if "speed_value" not in action:
                errors.append(f"{prefix}: speed action missing 'speed_value'")
        elif action.get("action_type") == "wait":
            if "wait_time" not in action:
                errors.append(f"{prefix}: wait action missing 'wait_time'")
        elif action.get("action_type") == "lane_change":
            if "lane_change_direction" not in action:
                errors.append(f"{prefix}: lane_change action missing 'lane_change_direction'")
        
        return errors
    
    def evaluate_semantic_accuracy(self, description: str, scenario: Dict) -> Tuple[float, Dict]:
        """Evaluate how well the scenario matches the description"""
        metrics = {
            "actor_count_match": 0,
            "position_match": 0,
            "speed_match": 0,
            "action_match": 0,
            "weather_match": 0
        }
        
        description_lower = description.lower()
        
        # Check actor count
        actor_count_in_desc = len(re.findall(r'\b(vehicle|car|truck|sedan|suv)\b', description_lower))
        actor_count_in_scenario = len(scenario.get("actors", []))
        if actor_count_in_desc > 0:
            metrics["actor_count_match"] = 1.0 if actor_count_in_scenario == actor_count_in_desc else 0.5
        
        # Check positions
        if "ahead" in description_lower:
            has_ahead = any(
                actor.get("spawn", {}).get("criteria", {}).get("relative_position") == "ahead"
                for actor in scenario.get("actors", [])
            )
            metrics["position_match"] = 1.0 if has_ahead else 0.0
        elif "behind" in description_lower:
            has_behind = any(
                actor.get("spawn", {}).get("criteria", {}).get("relative_position") == "behind"
                for actor in scenario.get("actors", [])
            )
            metrics["position_match"] = 1.0 if has_behind else 0.0
        else:
            metrics["position_match"] = 0.5  # No specific position mentioned
        
        # Check speeds mentioned
        speed_pattern = r'(\d+)\s*m/s'
        speeds_in_desc = [int(m) for m in re.findall(speed_pattern, description_lower)]
        speeds_in_scenario = []
        for action in scenario.get("actions", []):
            if "speed_value" in action:
                speeds_in_scenario.append(action["speed_value"])
        
        if speeds_in_desc:
            matching_speeds = sum(1 for s in speeds_in_desc if s in speeds_in_scenario)
            metrics["speed_match"] = matching_speeds / len(speeds_in_desc)
        
        # Check actions
        action_keywords = {
            "stop": ["stop", "stops", "stopping", "brake", "brakes"],
            "speed": ["move", "moves", "moving", "accelerate", "speed"],
            "wait": ["wait", "waits", "pause", "pauses"],
            "lane_change": ["lane change", "changes lane", "overtake", "merge"]
        }
        
        found_actions = set()
        for action_type, keywords in action_keywords.items():
            if any(kw in description_lower for kw in keywords):
                found_actions.add(action_type)
        
        scenario_actions = set(action.get("action_type") for action in scenario.get("actions", []))
        
        if found_actions:
            matching_actions = len(found_actions & scenario_actions)
            metrics["action_match"] = matching_actions / len(found_actions)
        
        # Check weather
        weather_keywords = ["clear", "cloudy", "rain", "wet"]
        for weather in weather_keywords:
            if weather in description_lower:
                scenario_weather = scenario.get("weather", "").lower()
                metrics["weather_match"] = 1.0 if weather in scenario_weather else 0.0
                break
        
        # Calculate overall score
        weights = {
            "actor_count_match": 0.2,
            "position_match": 0.2,
            "speed_match": 0.25,
            "action_match": 0.25,
            "weather_match": 0.1
        }
        
        overall_score = sum(metrics[k] * weights.get(k, 0) for k in metrics)
        
        return overall_score, metrics
    
    def evaluate_scenario(self, description: str, scenario: Dict) -> Dict:
        """Evaluate a single scenario"""
        result = {
            "description": description[:100] + "..." if len(description) > 100 else description,
            "valid_json": False,
            "structure_valid": False,
            "semantic_score": 0.0,
            "errors": [],
            "metrics": {}
        }
        
        # Check if scenario is valid
        if scenario is None:
            result["errors"].append("Failed to generate scenario")
            return result
        
        result["valid_json"] = True
        
        # Validate structure
        structure_valid, errors = self.validate_json_structure(scenario)
        result["structure_valid"] = structure_valid
        result["errors"].extend(errors)
        
        # Evaluate semantic accuracy
        semantic_score, metrics = self.evaluate_semantic_accuracy(description, scenario)
        result["semantic_score"] = semantic_score
        result["metrics"] = metrics
        
        return result
    
    def evaluate_batch(self, test_file: str) -> Dict:
        """Evaluate a batch of test results"""
        with open(test_file, 'r') as f:
            test_results = json.load(f)
        
        evaluations = []
        for test in test_results:
            description = test.get("test", "")
            scenario = test.get("scenario")
            
            eval_result = self.evaluate_scenario(description, scenario)
            eval_result["test_status"] = test.get("status", "unknown")
            evaluations.append(eval_result)
        
        # Calculate statistics
        stats = self._calculate_statistics(evaluations)
        
        return {
            "evaluations": evaluations,
            "statistics": stats
        }
    
    def _calculate_statistics(self, evaluations: List[Dict]) -> Dict:
        """Calculate overall statistics"""
        total = len(evaluations)
        
        stats = {
            "total_tests": total,
            "valid_json": sum(1 for e in evaluations if e["valid_json"]),
            "structure_valid": sum(1 for e in evaluations if e["structure_valid"]),
            "avg_semantic_score": sum(e["semantic_score"] for e in evaluations) / total if total > 0 else 0,
            "error_types": Counter(),
            "metric_averages": {}
        }
        
        # Count error types
        for eval in evaluations:
            for error in eval["errors"]:
                error_type = error.split(":")[0] if ":" in error else error
                stats["error_types"][error_type] += 1
        
        # Calculate metric averages
        metric_names = ["actor_count_match", "position_match", "speed_match", "action_match", "weather_match"]
        for metric in metric_names:
            values = [e["metrics"].get(metric, 0) for e in evaluations if e["metrics"]]
            stats["metric_averages"][metric] = sum(values) / len(values) if values else 0
        
        return stats
    
    def generate_report(self, evaluation_results: Dict, output_file: str = "evaluation_report.md"):
        """Generate a detailed evaluation report"""
        stats = evaluation_results["statistics"]
        evaluations = evaluation_results["evaluations"]
        
        report = []
        report.append("# CARLA Scenario Generation Model Evaluation Report\n")
        report.append("## Overall Statistics\n")
        report.append(f"- **Total Tests**: {stats['total_tests']}")
        report.append(f"- **Valid JSON**: {stats['valid_json']} ({stats['valid_json']/stats['total_tests']*100:.1f}%)")
        report.append(f"- **Structure Valid**: {stats['structure_valid']} ({stats['structure_valid']/stats['total_tests']*100:.1f}%)")
        report.append(f"- **Average Semantic Score**: {stats['avg_semantic_score']:.2f}/1.0\n")
        
        report.append("## Semantic Accuracy Metrics\n")
        for metric, value in stats["metric_averages"].items():
            metric_name = metric.replace("_", " ").title()
            report.append(f"- **{metric_name}**: {value:.2f}")
        report.append("")
        
        if stats["error_types"]:
            report.append("## Common Errors\n")
            for error_type, count in stats["error_types"].most_common(5):
                report.append(f"- {error_type}: {count} occurrences")
            report.append("")
        
        report.append("## Detailed Test Results\n")
        for i, eval in enumerate(evaluations, 1):
            status = "✓" if eval["structure_valid"] else "✗"
            report.append(f"### Test {i}: {status}")
            report.append(f"**Description**: {eval['description']}")
            report.append(f"- JSON Valid: {eval['valid_json']}")
            report.append(f"- Structure Valid: {eval['structure_valid']}")
            report.append(f"- Semantic Score: {eval['semantic_score']:.2f}")
            
            if eval["errors"]:
                report.append("- **Errors**:")
                for error in eval["errors"][:3]:  # Show first 3 errors
                    report.append(f"  - {error}")
            report.append("")
        
        # Write report
        with open(output_file, 'w') as f:
            f.write("\n".join(report))
        
        print(f"✓ Evaluation report saved to {output_file}")
        
        # Also print summary to console
        print("\n" + "="*60)
        print("Evaluation Summary")
        print("="*60)
        print(f"Valid JSON: {stats['valid_json']}/{stats['total_tests']} ({stats['valid_json']/stats['total_tests']*100:.1f}%)")
        print(f"Structure Valid: {stats['structure_valid']}/{stats['total_tests']} ({stats['structure_valid']/stats['total_tests']*100:.1f}%)")
        print(f"Semantic Score: {stats['avg_semantic_score']:.2f}/1.0")
        print("="*60)

def main():
    parser = argparse.ArgumentParser(description="Evaluate CARLA scenario generation model")
    parser.add_argument("--test-file", type=str, default="test_results.json",
                       help="Test results file from inference script")
    parser.add_argument("--output", type=str, default="evaluation_report.md",
                       help="Output file for evaluation report")
    parser.add_argument("--single", type=str,
                       help="Evaluate a single scenario file")
    parser.add_argument("--description", type=str,
                       help="Description for single scenario evaluation")
    
    args = parser.parse_args()
    
    evaluator = CarlaScenarioEvaluator()
    
    if args.single:
        # Evaluate single scenario
        with open(args.single, 'r') as f:
            scenario = json.load(f)
        
        description = args.description or "No description provided"
        result = evaluator.evaluate_scenario(description, scenario)
        
        print("\nEvaluation Result:")
        print(f"Valid JSON: {result['valid_json']}")
        print(f"Structure Valid: {result['structure_valid']}")
        print(f"Semantic Score: {result['semantic_score']:.2f}")
        if result['errors']:
            print("Errors:")
            for error in result['errors']:
                print(f"  - {error}")
    else:
        # Evaluate batch
        if not Path(args.test_file).exists():
            print(f"Error: Test file {args.test_file} not found")
            print("Run 'python inference_carla_model.py --mode test' first")
            return
        
        results = evaluator.evaluate_batch(args.test_file)
        evaluator.generate_report(results, args.output)

if __name__ == "__main__":
    main()