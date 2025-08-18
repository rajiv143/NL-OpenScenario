#!/usr/bin/env python3
"""
CARLA Dataset Validator
Validates the generated CARLA scenario training dataset for data quality and completeness.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from collections import Counter
from dataclasses import dataclass
import sys

@dataclass
class ValidationResult:
    """Result of validation check"""
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None

class DatasetValidator:
    """Validates CARLA scenario datasets"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.stats = {
            "total_examples": 0,
            "valid_json": 0,
            "invalid_json": 0,
            "rgb_errors": 0,
            "missing_fields": 0,
            "color_consistency": 0,
            "action_errors": 0
        }
        
        # Expected color mappings
        self.color_mappings = {
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
    
    def validate_json(self, json_str: str) -> ValidationResult:
        """Validate JSON structure"""
        try:
            data = json.loads(json_str)
            return ValidationResult(True, "Valid JSON", {"data": data})
        except json.JSONDecodeError as e:
            return ValidationResult(False, f"Invalid JSON: {str(e)}")
    
    def validate_rgb_values(self, rgb: List[int]) -> ValidationResult:
        """Validate RGB values are in valid range"""
        if not isinstance(rgb, list) or len(rgb) != 3:
            return ValidationResult(False, "RGB must be a list of 3 values")
        
        for i, value in enumerate(rgb):
            if not isinstance(value, int):
                return ValidationResult(False, f"RGB value {i} is not an integer: {value}")
            if value < 0 or value > 255:
                return ValidationResult(False, f"RGB value {i} out of range [0-255]: {value}")
        
        return ValidationResult(True, "Valid RGB values")
    
    def validate_color_consistency(self, color_name: str, rgb: List[int]) -> ValidationResult:
        """Check if color name matches RGB values (with tolerance)"""
        if color_name not in self.color_mappings:
            return ValidationResult(True, f"Unknown color name: {color_name} (allowing custom colors)")
        
        expected_rgb = self.color_mappings[color_name]
        tolerance = 30  # Allow some variation
        
        for i in range(3):
            if abs(rgb[i] - expected_rgb[i]) > tolerance:
                return ValidationResult(
                    False, 
                    f"Color mismatch: {color_name} RGB {rgb} differs from expected {expected_rgb}"
                )
        
        return ValidationResult(True, f"Color {color_name} matches RGB values")
    
    def validate_required_fields(self, scenario: Dict[str, Any]) -> ValidationResult:
        """Check if all required fields are present"""
        required_fields = ["scenario_id", "actors", "actions"]
        missing_fields = []
        
        for field in required_fields:
            if field not in scenario:
                missing_fields.append(field)
        
        if missing_fields:
            return ValidationResult(False, f"Missing required fields: {missing_fields}")
        
        # Check actor fields
        for actor in scenario.get("actors", []):
            actor_required = ["id", "type", "model"]
            for field in actor_required:
                if field not in actor:
                    return ValidationResult(False, f"Actor missing field: {field}")
            
            # Vehicles must have color
            if actor["type"] == "vehicle" and "color" not in actor:
                return ValidationResult(False, f"Vehicle {actor['id']} missing color")
        
        # Check action fields
        for action in scenario.get("actions", []):
            action_required = ["timestamp", "actor_id", "action_type"]
            for field in action_required:
                if field not in action:
                    return ValidationResult(False, f"Action missing field: {field}")
        
        return ValidationResult(True, "All required fields present")
    
    def validate_actor_references(self, scenario: Dict[str, Any]) -> ValidationResult:
        """Ensure all action actor_ids reference existing actors"""
        actor_ids = {actor["id"] for actor in scenario.get("actors", [])}
        
        for action in scenario.get("actions", []):
            if action["actor_id"] not in actor_ids:
                return ValidationResult(
                    False, 
                    f"Action references non-existent actor: {action['actor_id']}"
                )
        
        return ValidationResult(True, "All actor references valid")
    
    def validate_temporal_consistency(self, scenario: Dict[str, Any]) -> ValidationResult:
        """Check if actions are temporally consistent"""
        actions = scenario.get("actions", [])
        
        if not actions:
            return ValidationResult(True, "No actions to validate")
        
        timestamps = [action["timestamp"] for action in actions]
        
        # Check for negative timestamps
        if any(t < 0 for t in timestamps):
            return ValidationResult(False, "Negative timestamps found")
        
        # Check if duration covers all actions
        if "duration" in scenario:
            max_timestamp = max(timestamps)
            if max_timestamp > scenario["duration"]:
                return ValidationResult(
                    False, 
                    f"Action timestamp {max_timestamp} exceeds scenario duration {scenario['duration']}"
                )
        
        return ValidationResult(True, "Temporal consistency valid")
    
    def validate_example(self, example: Dict[str, str], index: int) -> Dict[str, Any]:
        """Validate a single training example"""
        results = {
            "index": index,
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Check required fields in example
        if "instruction" not in example or "output" not in example:
            results["valid"] = False
            results["errors"].append("Missing instruction or output field")
            return results
        
        # Validate JSON output
        json_result = self.validate_json(example["output"])
        if not json_result.passed:
            results["valid"] = False
            results["errors"].append(json_result.message)
            self.stats["invalid_json"] += 1
            return results
        
        self.stats["valid_json"] += 1
        scenario = json_result.details["data"]
        
        # Validate required fields
        fields_result = self.validate_required_fields(scenario)
        if not fields_result.passed:
            results["errors"].append(fields_result.message)
            self.stats["missing_fields"] += 1
        
        # Validate colors
        for actor in scenario.get("actors", []):
            if "color" in actor and actor["color"]:
                color_data = actor["color"]
                
                # Check RGB values
                if "rgb" in color_data:
                    rgb_result = self.validate_rgb_values(color_data["rgb"])
                    if not rgb_result.passed:
                        results["errors"].append(f"Actor {actor['id']}: {rgb_result.message}")
                        self.stats["rgb_errors"] += 1
                    
                    # Check color consistency
                    if "name" in color_data:
                        consistency_result = self.validate_color_consistency(
                            color_data["name"], 
                            color_data["rgb"]
                        )
                        if not consistency_result.passed:
                            results["warnings"].append(consistency_result.message)
                            self.stats["color_consistency"] += 1
        
        # Validate actor references
        ref_result = self.validate_actor_references(scenario)
        if not ref_result.passed:
            results["errors"].append(ref_result.message)
            self.stats["action_errors"] += 1
        
        # Validate temporal consistency
        temporal_result = self.validate_temporal_consistency(scenario)
        if not temporal_result.passed:
            results["warnings"].append(temporal_result.message)
        
        # Determine overall validity
        if results["errors"]:
            results["valid"] = False
        
        return results
    
    def validate_dataset(self, filepath: Path) -> Dict[str, Any]:
        """Validate entire dataset file"""
        print(f"\nValidating {filepath}...")
        
        if not filepath.exists():
            return {
                "error": f"File not found: {filepath}",
                "valid": False
            }
        
        examples = []
        with open(filepath, "r") as f:
            for line in f:
                if line.strip():
                    try:
                        examples.append(json.loads(line))
                    except json.JSONDecodeError:
                        self.errors.append(f"Could not parse line: {line[:50]}...")
        
        self.stats["total_examples"] = len(examples)
        
        validation_results = []
        for i, example in enumerate(examples):
            result = self.validate_example(example, i)
            validation_results.append(result)
            
            if not result["valid"]:
                self.errors.extend(result["errors"])
            if result["warnings"]:
                self.warnings.extend(result["warnings"])
        
        # Calculate summary statistics
        valid_count = sum(1 for r in validation_results if r["valid"])
        
        return {
            "filepath": str(filepath),
            "total_examples": len(examples),
            "valid_examples": valid_count,
            "invalid_examples": len(examples) - valid_count,
            "validation_rate": (valid_count / len(examples) * 100) if examples else 0,
            "stats": self.stats,
            "errors": self.errors[:10],  # First 10 errors
            "warnings": self.warnings[:10],  # First 10 warnings
            "validation_results": validation_results[:5]  # Sample results
        }
    
    def generate_report(self, train_results: Dict, val_results: Dict) -> str:
        """Generate validation report"""
        report = []
        report.append("=" * 60)
        report.append("CARLA Dataset Validation Report")
        report.append("=" * 60)
        
        # Training dataset summary
        report.append("\n## Training Dataset")
        report.append(f"File: {train_results['filepath']}")
        report.append(f"Total examples: {train_results['total_examples']}")
        report.append(f"Valid examples: {train_results['valid_examples']}")
        report.append(f"Invalid examples: {train_results['invalid_examples']}")
        report.append(f"Validation rate: {train_results['validation_rate']:.2f}%")
        
        # Validation dataset summary
        report.append("\n## Validation Dataset")
        report.append(f"File: {val_results['filepath']}")
        report.append(f"Total examples: {val_results['total_examples']}")
        report.append(f"Valid examples: {val_results['valid_examples']}")
        report.append(f"Invalid examples: {val_results['invalid_examples']}")
        report.append(f"Validation rate: {val_results['validation_rate']:.2f}%")
        
        # Combined statistics
        total_stats = {
            "total_examples": train_results['stats']['total_examples'] + val_results['stats']['total_examples'],
            "valid_json": train_results['stats']['valid_json'] + val_results['stats']['valid_json'],
            "invalid_json": train_results['stats']['invalid_json'] + val_results['stats']['invalid_json'],
            "rgb_errors": train_results['stats']['rgb_errors'] + val_results['stats']['rgb_errors'],
            "missing_fields": train_results['stats']['missing_fields'] + val_results['stats']['missing_fields'],
            "color_consistency": train_results['stats']['color_consistency'] + val_results['stats']['color_consistency'],
            "action_errors": train_results['stats']['action_errors'] + val_results['stats']['action_errors']
        }
        
        report.append("\n## Overall Statistics")
        report.append(f"Total examples processed: {total_stats['total_examples']}")
        report.append(f"Valid JSON: {total_stats['valid_json']}")
        report.append(f"Invalid JSON: {total_stats['invalid_json']}")
        report.append(f"RGB errors: {total_stats['rgb_errors']}")
        report.append(f"Missing fields: {total_stats['missing_fields']}")
        report.append(f"Color consistency warnings: {total_stats['color_consistency']}")
        report.append(f"Action reference errors: {total_stats['action_errors']}")
        
        # Sample errors
        if train_results['errors'] or val_results['errors']:
            report.append("\n## Sample Errors")
            all_errors = train_results['errors'][:5] + val_results['errors'][:5]
            for i, error in enumerate(all_errors[:10], 1):
                report.append(f"{i}. {error}")
        
        # Sample warnings
        if train_results['warnings'] or val_results['warnings']:
            report.append("\n## Sample Warnings")
            all_warnings = train_results['warnings'][:5] + val_results['warnings'][:5]
            for i, warning in enumerate(all_warnings[:10], 1):
                report.append(f"{i}. {warning}")
        
        # Quality assessment
        report.append("\n## Quality Assessment")
        overall_validation_rate = (
            (train_results['valid_examples'] + val_results['valid_examples']) /
            (train_results['total_examples'] + val_results['total_examples']) * 100
        )
        
        if overall_validation_rate >= 95:
            report.append("✅ EXCELLENT: Dataset quality is excellent (>95% valid)")
        elif overall_validation_rate >= 90:
            report.append("✅ GOOD: Dataset quality is good (>90% valid)")
        elif overall_validation_rate >= 80:
            report.append("⚠️ FAIR: Dataset quality is fair (>80% valid)")
        else:
            report.append("❌ POOR: Dataset quality needs improvement (<80% valid)")
        
        report.append(f"Overall validation rate: {overall_validation_rate:.2f}%")
        
        report.append("\n" + "=" * 60)
        
        return "\n".join(report)

def analyze_coverage(filepath: Path) -> Dict[str, Any]:
    """Analyze dataset coverage of different features"""
    coverage = {
        "colors": Counter(),
        "actions": Counter(),
        "vehicles": Counter(),
        "complexity": {"basic": 0, "intermediate": 0, "complex": 0},
        "weather": Counter(),
        "has_rgb": 0,
        "has_color_name": 0,
        "has_both_color_formats": 0
    }
    
    with open(filepath, "r") as f:
        for line in f:
            if not line.strip():
                continue
            
            try:
                example = json.loads(line)
                scenario = json.loads(example["output"])
                
                # Analyze actors
                num_actors = len(scenario.get("actors", []))
                if num_actors == 1:
                    coverage["complexity"]["basic"] += 1
                elif num_actors <= 3:
                    coverage["complexity"]["intermediate"] += 1
                else:
                    coverage["complexity"]["complex"] += 1
                
                for actor in scenario.get("actors", []):
                    if actor["type"] == "vehicle":
                        coverage["vehicles"][actor["model"]] += 1
                        
                        if "color" in actor and actor["color"]:
                            color_data = actor["color"]
                            if "name" in color_data:
                                coverage["colors"][color_data["name"]] += 1
                                coverage["has_color_name"] += 1
                            if "rgb" in color_data:
                                coverage["has_rgb"] += 1
                            if "name" in color_data and "rgb" in color_data:
                                coverage["has_both_color_formats"] += 1
                
                # Analyze actions
                for action in scenario.get("actions", []):
                    coverage["actions"][action["action_type"]] += 1
                
                # Analyze weather
                if "weather" in scenario:
                    coverage["weather"][scenario["weather"].get("condition", "unknown")] += 1
            
            except (json.JSONDecodeError, KeyError):
                continue
    
    return coverage

def main():
    """Main validation function"""
    print("CARLA Dataset Validator")
    print("=" * 60)
    
    validator = DatasetValidator()
    
    # Validate training dataset
    train_path = Path("carla_scenarios_train.jsonl")
    if train_path.exists():
        train_results = validator.validate_dataset(train_path)
        print(f"✓ Validated training dataset: {train_results['validation_rate']:.2f}% valid")
    else:
        print(f"❌ Training dataset not found: {train_path}")
        train_results = {"error": "File not found"}
    
    # Reset validator for validation dataset
    validator = DatasetValidator()
    
    # Validate validation dataset
    val_path = Path("carla_scenarios_val.jsonl")
    if val_path.exists():
        val_results = validator.validate_dataset(val_path)
        print(f"✓ Validated validation dataset: {val_results['validation_rate']:.2f}% valid")
    else:
        print(f"❌ Validation dataset not found: {val_path}")
        val_results = {"error": "File not found"}
    
    # Generate and save report
    if not ("error" in train_results or "error" in val_results):
        report = validator.generate_report(train_results, val_results)
        
        report_path = Path("validation_report.txt")
        with open(report_path, "w") as f:
            f.write(report)
        print(f"\n✓ Validation report saved to {report_path}")
        
        # Analyze coverage
        print("\n## Coverage Analysis")
        
        if train_path.exists():
            train_coverage = analyze_coverage(train_path)
            print(f"\nTraining Dataset Coverage:")
            print(f"  Unique colors: {len(train_coverage['colors'])}")
            print(f"  Unique actions: {len(train_coverage['actions'])}")
            print(f"  Unique vehicles: {len(train_coverage['vehicles'])}")
            print(f"  Has RGB values: {train_coverage['has_rgb']}")
            print(f"  Has color names: {train_coverage['has_color_name']}")
            print(f"  Has both formats: {train_coverage['has_both_color_formats']}")
        
        if val_path.exists():
            val_coverage = analyze_coverage(val_path)
            print(f"\nValidation Dataset Coverage:")
            print(f"  Unique colors: {len(val_coverage['colors'])}")
            print(f"  Unique actions: {len(val_coverage['actions'])}")
            print(f"  Unique vehicles: {len(val_coverage['vehicles'])}")
        
        # Save detailed results
        detailed_results = {
            "training": train_results,
            "validation": val_results,
            "coverage": {
                "training": train_coverage if train_path.exists() else {},
                "validation": val_coverage if val_path.exists() else {}
            }
        }
        
        detailed_path = Path("validation_results.json")
        with open(detailed_path, "w") as f:
            # Filter out large arrays for readability
            filtered_results = {
                "training": {k: v for k, v in train_results.items() if k != "validation_results"},
                "validation": {k: v for k, v in val_results.items() if k != "validation_results"}
            }
            json.dump(filtered_results, f, indent=2, default=str)
        print(f"\n✓ Detailed results saved to {detailed_path}")
        
        print("\n" + report)

if __name__ == "__main__":
    main()