#!/usr/bin/env python3
import json
import time
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from datetime import datetime
import os
import sys
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
            # Find matching closing brace
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

def test_base_model(scenarios):
    print("\n" + "="*60)
    print("Testing BASE Model (Meta-Llama-3.2-3B)")
    print("="*60)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model_name = "meta-llama/Llama-3.2-3B"
    
    print(f"Loading base model from {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16,
        device_map="auto"
    )
    
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    results = []
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n[{i}/{len(scenarios)}] Testing: {scenario['id']} ({scenario['category']})")
        print(f"Prompt: {scenario['prompt'][:100]}...")
        
        prompt = f"""Generate a CARLA scenario JSON for the following description:
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
        
        start_time = time.time()
        
        inputs = tokenizer(prompt, return_tensors="pt", padding=True, truncation=True, max_length=512)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=1024,
                temperature=0.1,
                do_sample=True,
                top_p=0.95,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id
            )
        
        output_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        # Remove the input prompt from output
        if prompt in output_text:
            output_text = output_text[len(prompt):].strip()
        
        generation_time = time.time() - start_time
        
        # Extract and validate JSON
        json_output = extract_json_from_output(output_text)
        is_valid, error = validate_json(json_output)
        
        result = {
            "scenario_id": scenario['id'],
            "category": scenario['category'],
            "complexity": scenario['complexity'],
            "prompt": scenario['prompt'],
            "output": json_output[:500] + "..." if len(json_output) > 500 else json_output,
            "full_output": json_output,
            "json_valid": is_valid,
            "error": error,
            "generation_time": round(generation_time, 2),
            "output_length": len(json_output)
        }
        
        results.append(result)
        
        print(f"  Valid JSON: {'✓' if is_valid else '✗'}")
        print(f"  Generation time: {generation_time:.2f}s")
        print(f"  Output length: {len(json_output)} chars")
        
        if not is_valid:
            print(f"  Error: {error[:100]}...")
    
    # Clean up
    del model
    del tokenizer
    torch.cuda.empty_cache()
    
    return results

def test_finetuned_model(scenarios):
    print("\n" + "="*60)
    print("Testing FINE-TUNED Model (v5)")
    print("="*60)
    
    model_path = "/home/user/Desktop/Rajiv/llm/llama3.2_3b_carla_v5"
    
    print(f"Loading fine-tuned model from {model_path}...")
    generator = CarlaScenarioGenerator(
        model_path=model_path,
        use_4bit=True,
        merge_lora=False
    )
    
    results = []
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n[{i}/{len(scenarios)}] Testing: {scenario['id']} ({scenario['category']})")
        print(f"Prompt: {scenario['prompt'][:100]}...")
        
        start_time = time.time()
        
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
            "output": json_output[:500] + "..." if len(json_output) > 500 else json_output,
            "full_output": json_output,
            "json_valid": is_valid,
            "error": error,
            "generation_time": round(generation_time, 2),
            "output_length": len(json_output)
        }
        
        results.append(result)
        
        print(f"  Valid JSON: {'✓' if is_valid else '✗'}")
        print(f"  Generation time: {generation_time:.2f}s")
        print(f"  Output length: {len(json_output)} chars")
        
        if not is_valid:
            print(f"  Error: {error[:100]}...")
    
    return results

def analyze_results(base_results, finetuned_results):
    print("\n" + "="*60)
    print("ANALYSIS & COMPARISON")
    print("="*60)
    
    analysis = {
        "timestamp": datetime.now().isoformat(),
        "total_scenarios": len(base_results),
        "base_model": {
            "name": "Meta-Llama-3.2-3B",
            "valid_json_count": sum(1 for r in base_results if r['json_valid']),
            "avg_generation_time": round(sum(r['generation_time'] for r in base_results) / len(base_results), 2),
            "avg_output_length": round(sum(r['output_length'] for r in base_results) / len(base_results), 2),
            "by_category": {},
            "by_complexity": {}
        },
        "finetuned_model": {
            "name": "llama3.2_3b_carla_v5",
            "valid_json_count": sum(1 for r in finetuned_results if r['json_valid']),
            "avg_generation_time": round(sum(r['generation_time'] for r in finetuned_results) / len(finetuned_results), 2),
            "avg_output_length": round(sum(r['output_length'] for r in finetuned_results) / len(finetuned_results), 2),
            "by_category": {},
            "by_complexity": {}
        }
    }
    
    # Analyze by category
    categories = set(r['category'] for r in base_results)
    for category in categories:
        base_cat = [r for r in base_results if r['category'] == category]
        fine_cat = [r for r in finetuned_results if r['category'] == category]
        
        analysis['base_model']['by_category'][category] = {
            "count": len(base_cat),
            "valid_json": sum(1 for r in base_cat if r['json_valid']),
            "success_rate": round(sum(1 for r in base_cat if r['json_valid']) / len(base_cat) * 100, 1)
        }
        
        analysis['finetuned_model']['by_category'][category] = {
            "count": len(fine_cat),
            "valid_json": sum(1 for r in fine_cat if r['json_valid']),
            "success_rate": round(sum(1 for r in fine_cat if r['json_valid']) / len(fine_cat) * 100, 1)
        }
    
    # Analyze by complexity
    complexities = set(r['complexity'] for r in base_results)
    for complexity in complexities:
        base_comp = [r for r in base_results if r['complexity'] == complexity]
        fine_comp = [r for r in finetuned_results if r['complexity'] == complexity]
        
        analysis['base_model']['by_complexity'][complexity] = {
            "count": len(base_comp),
            "valid_json": sum(1 for r in base_comp if r['json_valid']),
            "success_rate": round(sum(1 for r in base_comp if r['json_valid']) / len(base_comp) * 100, 1)
        }
        
        analysis['finetuned_model']['by_complexity'][complexity] = {
            "count": len(fine_comp),
            "valid_json": sum(1 for r in fine_comp if r['json_valid']),
            "success_rate": round(sum(1 for r in fine_comp if r['json_valid']) / len(fine_comp) * 100, 1)
        }
    
    # Print summary
    print("\n📊 Overall Results:")
    print(f"Base Model - Valid JSON: {analysis['base_model']['valid_json_count']}/{analysis['total_scenarios']} ({analysis['base_model']['valid_json_count']/analysis['total_scenarios']*100:.1f}%)")
    print(f"Fine-tuned Model - Valid JSON: {analysis['finetuned_model']['valid_json_count']}/{analysis['total_scenarios']} ({analysis['finetuned_model']['valid_json_count']/analysis['total_scenarios']*100:.1f}%)")
    
    print(f"\n⏱️  Generation Speed:")
    print(f"Base Model: {analysis['base_model']['avg_generation_time']}s average")
    print(f"Fine-tuned Model: {analysis['finetuned_model']['avg_generation_time']}s average")
    print(f"Speed improvement: {(analysis['base_model']['avg_generation_time'] - analysis['finetuned_model']['avg_generation_time']) / analysis['base_model']['avg_generation_time'] * 100:.1f}%")
    
    print(f"\n📈 By Complexity:")
    for complexity in complexities:
        print(f"\n{complexity.upper()}:")
        print(f"  Base: {analysis['base_model']['by_complexity'][complexity]['valid_json']}/{analysis['base_model']['by_complexity'][complexity]['count']} ({analysis['base_model']['by_complexity'][complexity]['success_rate']}%)")
        print(f"  Fine-tuned: {analysis['finetuned_model']['by_complexity'][complexity]['valid_json']}/{analysis['finetuned_model']['by_complexity'][complexity]['count']} ({analysis['finetuned_model']['by_complexity'][complexity]['success_rate']}%)")
    
    return analysis

def main():
    # Load test scenarios
    scenarios = load_test_scenarios('expanded_test_scenarios.json')
    print(f"Loaded {len(scenarios)} test scenarios")
    
    # Test base model
    base_results = test_base_model(scenarios)
    
    # Save base results
    with open('base_model_results.json', 'w') as f:
        json.dump(base_results, f, indent=2)
    print("\nBase model results saved to base_model_results.json")
    
    # Test fine-tuned model
    finetuned_results = test_finetuned_model(scenarios)
    
    # Save fine-tuned results
    with open('finetuned_model_results.json', 'w') as f:
        json.dump(finetuned_results, f, indent=2)
    print("\nFine-tuned model results saved to finetuned_model_results.json")
    
    # Analyze and compare
    analysis = analyze_results(base_results, finetuned_results)
    
    # Save analysis
    with open('evaluation_analysis.json', 'w') as f:
        json.dump(analysis, f, indent=2)
    print("\nAnalysis saved to evaluation_analysis.json")
    
    # Create combined results for semantic evaluation
    combined_results = {
        "timestamp": datetime.now().isoformat(),
        "scenarios": []
    }
    
    for i in range(len(scenarios)):
        combined_results["scenarios"].append({
            "scenario": scenarios[i],
            "base_model": base_results[i],
            "finetuned_model": finetuned_results[i]
        })
    
    with open('combined_test_results.json', 'w') as f:
        json.dump(combined_results, f, indent=2)
    print("\nCombined results saved to combined_test_results.json")
    
    print("\n" + "="*60)
    print("EVALUATION COMPLETE!")
    print("="*60)
    print("\nFiles created:")
    print("  - base_model_results.json")
    print("  - finetuned_model_results.json")
    print("  - evaluation_analysis.json")
    print("  - combined_test_results.json")
    print("\nYou can now review these files for semantic accuracy scoring.")

if __name__ == "__main__":
    main()