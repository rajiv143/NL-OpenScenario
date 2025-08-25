#!/usr/bin/env python3
"""
Test only the fine-tuned model on expanded scenarios
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
    
    # Clean up common issues
    output = output.strip()
    if output.startswith('{') and output.endswith('}'):
        return output
    
    # Try to find JSON object in the output
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

def test_finetuned_model(scenarios, limit=10):
    print("\n" + "="*60)
    print(f"Testing FINE-TUNED Model (v5) - First {limit} scenarios")
    print("="*60)
    
    model_path = "/home/user/Desktop/Rajiv/llm/llama3.2_3b_carla_v5"
    
    print(f"Loading fine-tuned model from {model_path}...")
    generator = CarlaScenarioGenerator(
        model_path=model_path,
        use_4bit=True,
        merge_lora=False
    )
    
    results = []
    
    # Test only first 'limit' scenarios
    test_scenarios = scenarios[:limit]
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n[{i}/{len(test_scenarios)}] Testing: {scenario['id']} ({scenario['category']})")
        print(f"Prompt: {scenario['prompt'][:80]}...")
        
        start_time = time.time()
        
        try:
            output_text = generator.generate(scenario['prompt'])
            generation_time = time.time() - start_time
            
            # Extract and validate JSON
            json_output = extract_json_from_output(output_text)
            is_valid, error = validate_json(json_output)
            
            result = {
                "scenario_id": scenario['id'],
                "category": scenario['category'],
                "complexity": scenario['complexity'],
                "prompt": scenario['prompt'],
                "output": json_output[:300] + "..." if len(json_output) > 300 else json_output,
                "full_output": json_output,
                "json_valid": is_valid,
                "error": error,
                "generation_time": round(generation_time, 2),
                "output_length": len(json_output)
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
                "output": "",
                "full_output": "",
                "json_valid": False,
                "error": str(e),
                "generation_time": 0,
                "output_length": 0
            }
        
        results.append(result)
        
        # Save intermediate results
        with open(f'finetuned_results_partial_{limit}.json', 'w') as f:
            json.dump(results, f, indent=2)
    
    return results

def analyze_results(results):
    print("\n" + "="*60)
    print("ANALYSIS")
    print("="*60)
    
    valid_count = sum(1 for r in results if r['json_valid'])
    total = len(results)
    
    print(f"\n📊 Overall Results:")
    print(f"Valid JSON: {valid_count}/{total} ({valid_count/total*100:.1f}%)")
    
    # By complexity
    complexities = set(r['complexity'] for r in results)
    print(f"\n📈 By Complexity:")
    for complexity in sorted(complexities):
        comp_results = [r for r in results if r['complexity'] == complexity]
        comp_valid = sum(1 for r in comp_results if r['json_valid'])
        print(f"  {complexity}: {comp_valid}/{len(comp_results)} ({comp_valid/len(comp_results)*100:.1f}%)")
    
    # By category
    categories = set(r['category'] for r in results)
    print(f"\n📂 By Category:")
    for category in sorted(categories):
        cat_results = [r for r in results if r['category'] == category]
        cat_valid = sum(1 for r in cat_results if r['json_valid'])
        print(f"  {category}: {cat_valid}/{len(cat_results)} ({cat_valid/len(cat_results)*100:.1f}% valid)")
    
    # Average generation time
    avg_time = sum(r['generation_time'] for r in results) / len(results)
    print(f"\n⏱️  Average generation time: {avg_time:.2f}s")

def main():
    # Load test scenarios
    scenarios = load_test_scenarios('expanded_test_scenarios.json')
    print(f"Loaded {len(scenarios)} test scenarios")
    
    # Test fine-tuned model on first 10 scenarios
    results = test_finetuned_model(scenarios, limit=10)
    
    # Save results
    output_file = 'finetuned_model_results_10.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_file}")
    
    # Analyze
    analyze_results(results)
    
    print("\n" + "="*60)
    print("TEST COMPLETE!")
    print("="*60)

if __name__ == "__main__":
    main()