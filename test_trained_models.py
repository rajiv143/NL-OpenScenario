#!/usr/bin/env python3
"""
Test YOUR trained models (not downloading anything from HuggingFace)
This script tests your fine-tuned CARLA models that are already on disk
"""
import json
import time
import sys
from datetime import datetime
sys.path.append('/home/user/Desktop/Rajiv/llm')
from inference_carla_model import CarlaScenarioGenerator

def load_test_scenarios(file_path):
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data['test_scenarios']

def validate_json(output_str):
    try:
        json.loads(output_str)
        return True, None
    except json.JSONDecodeError as e:
        return False, str(e)

def extract_json_from_output(output):
    # Try to find JSON between markers or just parse directly
    if '```json' in output:
        start = output.find('```json') + 7
        end = output.find('```', start)
        if end != -1:
            output = output[start:end].strip()
    elif '```' in output:
        start = output.find('```') + 3
        end = output.find('```', start)
        if end != -1:
            output = output[start:end].strip()
    
    output = output.strip()
    if output.startswith('{') and output.endswith('}'):
        return output
    
    # Try to find JSON object
    try:
        start_idx = output.find('{')
        if start_idx != -1:
            brace_count = 0
            for i in range(start_idx, len(output)):
                if output[i] == '{':
                    brace_count += 1
                elif output[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return output[start_idx:i+1]
    except:
        pass
    
    return output

def test_model(scenarios, model_path, model_name="Model"):
    """Test a single trained model"""
    print("\n" + "="*60)
    print(f"Testing {model_name}")
    print(f"Model path: {model_path}")
    print("="*60)
    
    print(f"Loading model from {model_path}...")
    try:
        generator = CarlaScenarioGenerator(
            model_path=model_path,
            use_4bit=True,
            merge_lora=False
        )
        print("✓ Model loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return []
    
    results = []
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n[{i}/{len(scenarios)}] Testing: {scenario['id']} ({scenario['category']})")
        print(f"  Complexity: {scenario['complexity']}")
        print(f"  Prompt: {scenario['prompt'][:80]}...")
        
        start_time = time.time()
        
        try:
            output_text = generator.generate(scenario['prompt'])
            generation_time = time.time() - start_time
            
            json_output = extract_json_from_output(output_text)
            is_valid, error = validate_json(json_output)
            
            result = {
                "scenario_id": scenario['id'],
                "category": scenario['category'],
                "complexity": scenario['complexity'],
                "prompt": scenario['prompt'],
                "output_preview": json_output[:300] + "..." if len(json_output) > 300 else json_output,
                "full_output": json_output,
                "json_valid": is_valid,
                "error": error,
                "generation_time": round(generation_time, 2),
                "output_length": len(json_output),
                "model": model_name
            }
            
            print(f"  Valid JSON: {'✓' if is_valid else '✗'}")
            print(f"  Generation time: {generation_time:.2f}s")
            print(f"  Output length: {len(json_output)} chars")
            
            if not is_valid and error:
                print(f"  Error: {error[:80]}...")
                
        except Exception as e:
            print(f"  ERROR: {str(e)}")
            result = {
                "scenario_id": scenario['id'],
                "category": scenario['category'],
                "complexity": scenario['complexity'],
                "prompt": scenario['prompt'],
                "output_preview": "",
                "full_output": "",
                "json_valid": False,
                "error": str(e),
                "generation_time": 0,
                "output_length": 0,
                "model": model_name
            }
        
        results.append(result)
        
        # Save intermediate results every 5 scenarios
        if i % 5 == 0:
            filename = f'{model_name.lower().replace(" ", "_")}_results_partial.json'
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"  [Checkpoint saved: {i} scenarios completed]")
    
    return results

def analyze_results(results, model_name="Model"):
    """Analyze results for a single model"""
    print(f"\n📊 Analysis for {model_name}:")
    print("-" * 40)
    
    total = len(results)
    valid_count = sum(1 for r in results if r['json_valid'])
    
    analysis = {
        "model": model_name,
        "total_scenarios": total,
        "valid_json_count": valid_count,
        "invalid_json_count": total - valid_count,
        "success_rate": round(valid_count / total * 100, 1) if total > 0 else 0,
        "avg_generation_time": round(sum(r['generation_time'] for r in results) / total, 2) if total > 0 else 0,
        "avg_output_length": round(sum(r['output_length'] for r in results) / total, 2) if total > 0 else 0,
        "by_complexity": {},
        "by_category": {}
    }
    
    # By complexity
    complexities = set(r['complexity'] for r in results)
    for complexity in sorted(complexities):
        comp_results = [r for r in results if r['complexity'] == complexity]
        comp_valid = sum(1 for r in comp_results if r['json_valid'])
        analysis['by_complexity'][complexity] = {
            "count": len(comp_results),
            "valid": comp_valid,
            "success_rate": round(comp_valid / len(comp_results) * 100, 1) if comp_results else 0
        }
    
    # By category
    categories = set(r['category'] for r in results)
    for category in sorted(categories):
        cat_results = [r for r in results if r['category'] == category]
        cat_valid = sum(1 for r in cat_results if r['json_valid'])
        analysis['by_category'][category] = {
            "count": len(cat_results),
            "valid": cat_valid,
            "success_rate": round(cat_valid / len(cat_results) * 100, 1) if cat_results else 0
        }
    
    # Print summary
    print(f"  Overall: {valid_count}/{total} valid ({analysis['success_rate']}%)")
    print(f"  Avg generation time: {analysis['avg_generation_time']}s")
    print(f"  Avg output length: {analysis['avg_output_length']} chars")
    
    print(f"\n  By Complexity:")
    for complexity in sorted(complexities):
        comp = analysis['by_complexity'][complexity]
        print(f"    {complexity}: {comp['valid']}/{comp['count']} ({comp['success_rate']}%)")
    
    print(f"\n  By Category:")
    for category in sorted(categories)[:5]:  # Show top 5 categories
        cat = analysis['by_category'][category]
        print(f"    {category}: {cat['valid']}/{cat['count']} ({cat['success_rate']}%)")
    
    return analysis

def main():
    print("="*60)
    print("TRAINED MODEL EVALUATION")
    print("Testing YOUR locally trained models")
    print("="*60)
    
    # Load test scenarios
    scenarios = load_test_scenarios('expanded_test_scenarios.json')
    print(f"\n📋 Loaded {len(scenarios)} test scenarios")
    
    # Define which models to test (all your local models)
    models_to_test = [
        {
            "name": "Fine-tuned v5 (Latest)",
            "path": "/home/user/Desktop/Rajiv/llm/llama3.2_3b_carla_v5",
            "output_file": "finetuned_v5_results.json"
        },
        # Uncomment if you want to test other versions
        # {
        #     "name": "Fine-tuned v4",
        #     "path": "/home/user/Desktop/Rajiv/llm/llama3.2_3b_carla_v4",
        #     "output_file": "finetuned_v4_results.json"
        # },
        # {
        #     "name": "Fine-tuned v3",
        #     "path": "/home/user/Desktop/Rajiv/llm/llama3.2_3b_carla_v3",
        #     "output_file": "finetuned_v3_results.json"
        # }
    ]
    
    all_results = {}
    all_analyses = {}
    
    # Test each model
    for model_info in models_to_test:
        print(f"\n🟢 Testing {model_info['name']}...")
        
        # Test the model
        results = test_model(
            scenarios, 
            model_info['path'], 
            model_info['name']
        )
        
        if results:
            # Save results
            with open(model_info['output_file'], 'w') as f:
                json.dump(results, f, indent=2)
            print(f"✅ Results saved to {model_info['output_file']}")
            
            # Analyze
            analysis = analyze_results(results, model_info['name'])
            all_results[model_info['name']] = results
            all_analyses[model_info['name']] = analysis
        else:
            print(f"❌ No results for {model_info['name']}")
    
    # Save comprehensive analysis
    comprehensive = {
        "timestamp": datetime.now().isoformat(),
        "total_scenarios": len(scenarios),
        "models_tested": list(all_analyses.keys()),
        "analyses": all_analyses,
        "summary": {
            "best_model": max(all_analyses.items(), key=lambda x: x[1]['success_rate'])[0] if all_analyses else "None",
            "model_comparisons": {
                name: {
                    "success_rate": analysis['success_rate'],
                    "avg_time": analysis['avg_generation_time']
                }
                for name, analysis in all_analyses.items()
            }
        }
    }
    
    with open('trained_models_analysis.json', 'w') as f:
        json.dump(comprehensive, f, indent=2)
    print("\n✅ Comprehensive analysis saved to trained_models_analysis.json")
    
    # Create results for semantic scoring
    if all_results:
        first_model = list(all_results.keys())[0]
        semantic_results = {
            "timestamp": datetime.now().isoformat(),
            "model_tested": first_model,
            "scenarios": []
        }
        
        for i, scenario in enumerate(scenarios):
            semantic_results["scenarios"].append({
                "scenario": scenario,
                "model_output": all_results[first_model][i] if i < len(all_results[first_model]) else None
            })
        
        with open('results_for_semantic_scoring.json', 'w') as f:
            json.dump(semantic_results, f, indent=2)
        print("✅ Results ready for semantic scoring: results_for_semantic_scoring.json")
    
    print("\n" + "="*60)
    print("🎉 EVALUATION COMPLETE!")
    print("="*60)
    print("\n📁 Output files created:")
    for model_info in models_to_test:
        print(f"  - {model_info['output_file']}")
    print("  - trained_models_analysis.json")
    print("  - results_for_semantic_scoring.json")
    print("\n📝 Share results_for_semantic_scoring.json for semantic accuracy assessment!")

if __name__ == "__main__":
    main()