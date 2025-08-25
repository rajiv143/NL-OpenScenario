#!/usr/bin/env python3
"""
OPTIMIZED evaluation script with CORRECT prompt format
Uses the same Llama 3.2 chat format that your model was trained with
"""
import json
import time
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from datetime import datetime
import sys
import os

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
    """Extract JSON from model output"""
    # Remove any chat formatting if present
    if '<|start_header_id|>assistant<|end_header_id|>' in output:
        output = output.split('<|start_header_id|>assistant<|end_header_id|>')[-1]
    if '<|eot_id|>' in output:
        output = output.split('<|eot_id|>')[0]
    
    # Try to find JSON between markers
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
    
    # If it's already valid JSON, return it
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

def format_prompt_for_llama32(scenario_description, use_instruct=True):
    """
    Format prompt using EXACT same format as training
    This is CRITICAL for good performance!
    """
    if use_instruct:
        # Llama 3.2-Instruct format (what your model was trained with)
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are an expert CARLA simulator scenario designer. Generate valid JSON scenarios based on natural language descriptions. The JSON should follow the exact CARLA scenario format with proper structure for actors, actions, spawn criteria, and triggers.<|eot_id|><|start_header_id|>user<|end_header_id|>

Generate a CARLA scenario JSON for the following description:

{scenario_description}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""
    else:
        # Fallback simple format
        prompt = f"""Generate a CARLA scenario JSON for the following description:
{scenario_description}

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
    
    return prompt

def test_base_model(scenarios):
    print("\n" + "="*60)
    print("Testing BASE Model (Meta-Llama-3.2-3B-Instruct)")
    print("Using CORRECT Llama 3.2 chat format")
    print("="*60)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model_name = "meta-llama/Llama-3.2-3B-Instruct"
    
    print(f"Loading base model from {model_name}...")
    print(f"Using device: {device}")
    
    # Set environment variables
    os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = '600'
    os.environ['TRANSFORMERS_CACHE'] = '/home/user/.cache/huggingface/transformers'
    
    try:
        print("Loading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True,
            padding_side="left"  # Important for generation
        )
        print("✓ Tokenizer loaded")
        
        print("Loading model (this may take a minute)...")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if device.type == "cuda" else torch.float32,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
            device_map="auto" if device.type == "cuda" else None
        )
        print("✓ Model loaded successfully")
        
    except Exception as e:
        print(f"❌ Error loading model: {str(e)}")
        return []
    
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id
    
    model.eval()
    results = []
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n[{i}/{len(scenarios)}] Testing: {scenario['id']} ({scenario['category']})")
        print(f"  Complexity: {scenario['complexity']}")
        print(f"  Prompt: {scenario['prompt'][:80]}...")
        
        # Use CORRECT prompt format!
        prompt = format_prompt_for_llama32(scenario['prompt'], use_instruct=True)
        
        start_time = time.time()
        
        try:
            inputs = tokenizer(
                prompt,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512
            )
            inputs = {k: v.to(device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=1024,
                    temperature=0.7,  # Slightly higher for base model
                    do_sample=True,
                    top_p=0.95,
                    pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id
                )
            
            output_text = tokenizer.decode(outputs[0], skip_special_tokens=False)
            
            # Extract only the assistant's response
            if '<|start_header_id|>assistant<|end_header_id|>' in output_text:
                output_text = output_text.split('<|start_header_id|>assistant<|end_header_id|>')[-1]
            
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
                "output_length": len(json_output)
            }
            
            print(f"  Valid JSON: {'✓' if is_valid else '✗'}")
            print(f"  Generation time: {generation_time:.2f}s")
            print(f"  Output length: {len(json_output)} chars")
            
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
                "output_length": 0
            }
        
        results.append(result)
        
        # Save checkpoint every 5 scenarios
        if i % 5 == 0:
            with open('base_model_results_partial.json', 'w') as f:
                json.dump(results, f, indent=2)
            print(f"  [Checkpoint saved: {i} scenarios completed]")
    
    # Clean up
    del model
    del tokenizer
    if device.type == "cuda":
        torch.cuda.empty_cache()
    
    return results

def test_finetuned_model(scenarios):
    print("\n" + "="*60)
    print("Testing FINE-TUNED Model (v5)")
    print("="*60)
    
    model_path = "/home/user/Desktop/Rajiv/llm/models/llama-carla-model-v5-improved/final_model"
    
    print(f"Loading fine-tuned model from {model_path}...")
    generator = CarlaScenarioGenerator(
        model_path=model_path,
        use_4bit=True,
        merge_lora=False
    )
    print("✓ Model loaded successfully")
    
    results = []
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n[{i}/{len(scenarios)}] Testing: {scenario['id']} ({scenario['category']})")
        print(f"  Complexity: {scenario['complexity']}")
        print(f"  Prompt: {scenario['prompt'][:80]}...")
        
        start_time = time.time()
        
        try:
            # Your generator already handles the prompt formatting internally
            # generate_scenario returns a dict or None
            scenario_dict = generator.generate_scenario(scenario['prompt'])
            generation_time = time.time() - start_time
            
            if scenario_dict:
                # Convert dict back to JSON string for consistency
                json_output = json.dumps(scenario_dict, indent=2)
                is_valid = True
                error = None
            else:
                json_output = ""
                is_valid = False
                error = "Model returned None - failed to generate valid JSON"
            
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
                "output_length": len(json_output)
            }
            
            print(f"  Valid JSON: {'✓' if is_valid else '✗'}")
            print(f"  Generation time: {generation_time:.2f}s")
            print(f"  Output length: {len(json_output)} chars")
            
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
                "output_length": 0
            }
        
        results.append(result)
        
        # Save checkpoint every 5 scenarios
        if i % 5 == 0:
            with open('finetuned_model_results_partial.json', 'w') as f:
                json.dump(results, f, indent=2)
            print(f"  [Checkpoint saved: {i} scenarios completed]")
    
    return results

def analyze_and_compare(base_results, finetuned_results):
    print("\n" + "="*60)
    print("COMPREHENSIVE ANALYSIS & COMPARISON")
    print("="*60)
    
    analysis = {
        "timestamp": datetime.now().isoformat(),
        "total_scenarios": len(base_results),
        "base_model": {
            "name": "Meta-Llama-3.2-3B-Instruct",
            "valid_json_count": sum(1 for r in base_results if r['json_valid']),
            "invalid_json_count": sum(1 for r in base_results if not r['json_valid']),
            "success_rate": round(sum(1 for r in base_results if r['json_valid']) / len(base_results) * 100, 1),
            "avg_generation_time": round(sum(r['generation_time'] for r in base_results) / len(base_results), 2),
            "avg_output_length": round(sum(r['output_length'] for r in base_results) / len(base_results), 2),
            "by_category": {},
            "by_complexity": {}
        },
        "finetuned_model": {
            "name": "llama3.2_3b_carla_v5",
            "valid_json_count": sum(1 for r in finetuned_results if r['json_valid']),
            "invalid_json_count": sum(1 for r in finetuned_results if not r['json_valid']),
            "success_rate": round(sum(1 for r in finetuned_results if r['json_valid']) / len(finetuned_results) * 100, 1),
            "avg_generation_time": round(sum(r['generation_time'] for r in finetuned_results) / len(finetuned_results), 2),
            "avg_output_length": round(sum(r['output_length'] for r in finetuned_results) / len(finetuned_results), 2),
            "by_category": {},
            "by_complexity": {}
        },
        "improvements": {}
    }
    
    # Analyze by category
    categories = set(r['category'] for r in base_results)
    for category in sorted(categories):
        base_cat = [r for r in base_results if r['category'] == category]
        fine_cat = [r for r in finetuned_results if r['category'] == category]
        
        base_valid = sum(1 for r in base_cat if r['json_valid'])
        fine_valid = sum(1 for r in fine_cat if r['json_valid'])
        
        analysis['base_model']['by_category'][category] = {
            "count": len(base_cat),
            "valid_json": base_valid,
            "success_rate": round(base_valid / len(base_cat) * 100, 1) if base_cat else 0
        }
        
        analysis['finetuned_model']['by_category'][category] = {
            "count": len(fine_cat),
            "valid_json": fine_valid,
            "success_rate": round(fine_valid / len(fine_cat) * 100, 1) if fine_cat else 0
        }
    
    # Analyze by complexity
    complexities = set(r['complexity'] for r in base_results)
    for complexity in sorted(complexities):
        base_comp = [r for r in base_results if r['complexity'] == complexity]
        fine_comp = [r for r in finetuned_results if r['complexity'] == complexity]
        
        base_valid = sum(1 for r in base_comp if r['json_valid'])
        fine_valid = sum(1 for r in fine_comp if r['json_valid'])
        
        analysis['base_model']['by_complexity'][complexity] = {
            "count": len(base_comp),
            "valid_json": base_valid,
            "success_rate": round(base_valid / len(base_comp) * 100, 1) if base_comp else 0
        }
        
        analysis['finetuned_model']['by_complexity'][complexity] = {
            "count": len(fine_comp),
            "valid_json": fine_valid,
            "success_rate": round(fine_valid / len(fine_comp) * 100, 1) if fine_comp else 0
        }
    
    # Calculate improvements
    analysis['improvements'] = {
        "json_validity": round(analysis['finetuned_model']['success_rate'] - analysis['base_model']['success_rate'], 1),
        "speed": round((analysis['base_model']['avg_generation_time'] - analysis['finetuned_model']['avg_generation_time']) / analysis['base_model']['avg_generation_time'] * 100, 1),
        "output_consistency": round((analysis['finetuned_model']['avg_output_length'] - analysis['base_model']['avg_output_length']) / analysis['base_model']['avg_output_length'] * 100, 1)
    }
    
    # Print summary
    print("\n📊 OVERALL RESULTS:")
    print("="*40)
    print(f"Base Model:")
    print(f"  Valid JSON: {analysis['base_model']['valid_json_count']}/{analysis['total_scenarios']} ({analysis['base_model']['success_rate']}%)")
    print(f"  Avg Time: {analysis['base_model']['avg_generation_time']}s")
    
    print(f"\nFine-tuned Model:")
    print(f"  Valid JSON: {analysis['finetuned_model']['valid_json_count']}/{analysis['total_scenarios']} ({analysis['finetuned_model']['success_rate']}%)")
    print(f"  Avg Time: {analysis['finetuned_model']['avg_generation_time']}s")
    
    print(f"\n📈 IMPROVEMENTS:")
    print(f"  JSON Validity: {'+' if analysis['improvements']['json_validity'] > 0 else ''}{analysis['improvements']['json_validity']}%")
    print(f"  Speed: {analysis['improvements']['speed']}% faster")
    
    print(f"\n📊 BY COMPLEXITY:")
    for complexity in sorted(complexities):
        base_rate = analysis['base_model']['by_complexity'][complexity]['success_rate']
        fine_rate = analysis['finetuned_model']['by_complexity'][complexity]['success_rate']
        print(f"\n{complexity.upper()}:")
        print(f"  Base: {base_rate}%")
        print(f"  Fine-tuned: {fine_rate}%")
        print(f"  Improvement: {'+' if fine_rate > base_rate else ''}{fine_rate - base_rate:.1f}%")
    
    return analysis

def main():
    print("="*60)
    print("OPTIMIZED MODEL EVALUATION")
    print("Using CORRECT Llama 3.2 prompt format")
    print("="*60)
    
    # Load test scenarios
    scenarios = load_test_scenarios('expanded_test_scenarios.json')
    print(f"\n📋 Loaded {len(scenarios)} test scenarios")
    
    # Test base model
    print("\n🔵 Starting BASE MODEL evaluation...")
    base_results = test_base_model(scenarios)
    with open('base_model_results.json', 'w') as f:
        json.dump(base_results, f, indent=2)
    print("\n✅ Base model results saved to base_model_results.json")
    
    # Test fine-tuned model
    print("\n🟢 Starting FINE-TUNED MODEL evaluation...")
    finetuned_results = test_finetuned_model(scenarios)
    with open('finetuned_model_results.json', 'w') as f:
        json.dump(finetuned_results, f, indent=2)
    print("\n✅ Fine-tuned model results saved to finetuned_model_results.json")
    
    # Analyze and compare
    analysis = analyze_and_compare(base_results, finetuned_results)
    with open('comprehensive_analysis.json', 'w') as f:
        json.dump(analysis, f, indent=2)
    print("\n✅ Analysis saved to comprehensive_analysis.json")
    
    # Create combined results
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
    print("✅ Combined results saved to combined_test_results.json")
    
    print("\n" + "="*60)
    print("🎉 EVALUATION COMPLETE!")
    print("="*60)

if __name__ == "__main__":
    main()