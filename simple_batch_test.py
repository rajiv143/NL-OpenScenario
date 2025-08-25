#!/usr/bin/env python3
"""
Simplified batch testing script for expanded evaluation
Creates test prompts and prepares them for manual testing if needed
"""

import json
from datetime import datetime

def create_test_batch():
    # Load the expanded test scenarios
    with open('expanded_test_scenarios.json', 'r') as f:
        data = json.load(f)
    
    scenarios = data['test_scenarios']
    
    # Create formatted prompts for testing
    test_prompts = []
    
    for scenario in scenarios:
        formatted_prompt = f"""Generate a CARLA scenario JSON for the following description:
{scenario['prompt']}

Return ONLY a valid JSON object with this structure:
{{
  "scenarioName": "descriptive_name",
  "description": "scenario description",
  "ego_vehicle": {{"model": "vehicle.tesla.model3", "spawn_point": {{"x": 0, "y": 0, "z": 0.5, "yaw": 0}}}},
  "other_actors": [...],
  "weather": {{"cloudiness": 0, "precipitation": 0, "sun_altitude_angle": 45}},
  "triggers": [...],
  "success_criteria": {{...}},
  "timeout": 60
}}"""
        
        test_prompts.append({
            "id": scenario['id'],
            "category": scenario['category'],
            "complexity": scenario['complexity'],
            "original_prompt": scenario['prompt'],
            "formatted_prompt": formatted_prompt
        })
    
    # Save the test prompts
    with open('test_prompts_batch.json', 'w') as f:
        json.dump(test_prompts, f, indent=2)
    
    print(f"✅ Created {len(test_prompts)} test prompts")
    print("📁 Saved to: test_prompts_batch.json")
    
    # Create summary statistics
    stats = {
        "total_scenarios": len(scenarios),
        "by_complexity": {},
        "by_category": {},
        "timestamp": datetime.now().isoformat()
    }
    
    # Count by complexity
    for scenario in scenarios:
        complexity = scenario['complexity']
        if complexity not in stats['by_complexity']:
            stats['by_complexity'][complexity] = 0
        stats['by_complexity'][complexity] += 1
        
        category = scenario['category']
        if category not in stats['by_category']:
            stats['by_category'][category] = 0
        stats['by_category'][category] += 1
    
    # Print summary
    print("\n📊 Test Set Summary:")
    print(f"Total scenarios: {stats['total_scenarios']}")
    
    print("\nBy Complexity:")
    for complexity, count in stats['by_complexity'].items():
        print(f"  {complexity}: {count} scenarios")
    
    print("\nBy Category:")
    for category, count in sorted(stats['by_category'].items()):
        print(f"  {category}: {count} scenarios")
    
    # Save statistics
    with open('test_set_statistics.json', 'w') as f:
        json.dump(stats, f, indent=2)
    
    print("\n📈 Statistics saved to: test_set_statistics.json")
    
    # Create a sample output template for manual testing
    sample_template = {
        "instructions": "Use this template to record test results for each scenario",
        "example_result": {
            "scenario_id": "test_001",
            "base_model": {
                "output": "paste base model output here",
                "json_valid": False,
                "generation_time": 0.0,
                "notes": "any observations"
            },
            "finetuned_model": {
                "output": "paste fine-tuned model output here",
                "json_valid": True,
                "generation_time": 0.0,
                "notes": "any observations"
            },
            "semantic_accuracy": {
                "base_score": 0,  # 1-5 scale
                "finetuned_score": 0,  # 1-5 scale
                "notes": "accuracy assessment"
            }
        },
        "results": []
    }
    
    with open('manual_test_template.json', 'w') as f:
        json.dump(sample_template, f, indent=2)
    
    print("\n📝 Manual test template saved to: manual_test_template.json")
    
    return test_prompts, stats

if __name__ == "__main__":
    print("="*60)
    print("EXPANDED TEST SET PREPARATION")
    print("="*60)
    
    prompts, stats = create_test_batch()
    
    print("\n" + "="*60)
    print("NEXT STEPS:")
    print("="*60)
    print("1. Use test_prompts_batch.json to test both models")
    print("2. Record results in manual_test_template.json")
    print("3. Share results for semantic accuracy scoring")
    print("\nYou now have 25 diverse test scenarios ready for evaluation!")