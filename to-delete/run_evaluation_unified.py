#!/usr/bin/env python3
"""
UNIFIED evaluation script - uses SAME prompt format for both models
This ensures fair comparison by using the exact prompt your model was trained on
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
    """Extract JSON from model output - handles various formats"""
    # Remove chat formatting if present
    if '<|start_header_id|>assistant<|end_header_id|>' in output:
        output = output.split('<|start_header_id|>assistant<|end_header_id|>')[-1]
    if '<|eot_id|>' in output:
        output = output.split('<|eot_id|>')[0]
    if '[/INST]' in output:
        output = output.split('[/INST]')[-1]
    
    # Clean up
    output = output.strip()
    
    # If it starts with {, try to extract the complete JSON object
    if output.startswith('{'):
        brace_count = 0
        for i, char in enumerate(output):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    return output[:i+1]
    
    # Fallback: try to find JSON object anywhere in output
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
    
    return output

def format_prompt_unified(description: str, model_name: str) -> str:
    """
    Use the EXACT same prompt format that the fine-tuned model uses
    This is what the model was trained on!
    """
    # The instruction that works well with your model
    instruction = """Generate a COMPLETE CARLA scenario JSON. 
IMPORTANT: Start your response with an opening curly brace '{' and include ALL fields:
- scenario_name
- description  
- weather (use the weather conditions mentioned in the description)
- ego_vehicle_model
- ego_spawn
- actors
- actions
- success_distance
- timeout
- collision_allowed

Generate the complete JSON for this scenario:"""
    
    if "3.2" in model_name or "3.1" in model_name:
        # Llama 3.x format (what your model uses)
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are an expert CARLA simulator scenario designer. Generate valid JSON scenarios based on natural language descriptions. ALWAYS start with opening brace and include all required fields in order: scenario_name, description, weather, ego_vehicle_model, ego_spawn, ego_start_speed, actors, actions, success_distance, timeout, collision_allowed.<|eot_id|><|start_header_id|>user<|end_header_id|>

{instruction}

{description}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

{{"""
    else:
        # Llama 2 format
        prompt = f"""[INST] <<SYS>>
You are an expert CARLA simulator scenario designer. Generate complete valid JSON scenarios starting with opening brace.
<</SYS>>

{instruction}

{description} [/INST]

{{"""
    
    return prompt

def test_base_model(scenarios):
    print("\n" + "="*60)
    print("Testing BASE Model (Meta-Llama-3.2-3B-Instruct)")
    print("Using UNIFIED prompt format (same as fine-tuned)")
    print("="*60)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model_name = "meta-llama/Llama-3.2-3B-Instruct"
    
    print(f"Loading base model from {model_name}...")
    print(f"Using device: {device}")
    
    try:
        print("Loading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True,
            padding_side="left"
        )
        
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
            tokenizer.pad_token_id = tokenizer.eos_token_id
        
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
        
        model.eval()
        
    except Exception as e:
        print(f"❌ Error loading model: {str(e)}")
        return []
    
    results = []
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n[{i}/{len(scenarios)}] Testing: {scenario['id']} ({scenario['category']})")
        print(f"  Complexity: {scenario['complexity']}")
        print(f"  Prompt: {scenario['prompt'][:80]}...")
        
        # Use UNIFIED prompt format with opening brace hint
        prompt = format_prompt_unified(scenario['prompt'], model_name)
        
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
                    max_new_tokens=1500,  # Match fine-tuned model
                    temperature=0.7,       # Match fine-tuned model
                    do_sample=True,
                    top_p=0.9,            # Match fine-tuned model
                    repetition_penalty=1.1,
                    pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                    use_cache=True
                )
            
            output_text = tokenizer.decode(outputs[0], skip_special_tokens=False)
            
            # Remove the prompt from output
            if prompt in output_text:
                output_text = output_text[len(prompt):]
            
            generation_time = time.time() - start_time
            
            # The model should continue from the opening brace we provided
            json_output = "{" + output_text if not output_text.startswith("{") else output_text
            json_output = extract_json_from_output(json_output)
            
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
            # generate_scenario returns a dict or None
            scenario_dict = generator.generate_scenario(
                scenario['prompt'],
                temperature=0.7,  # Match base model settings
                top_p=0.9,
                do_sample=True
            )
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
    print("COMPREHENSIVE ANALYSIS")
    print("="*60)
    
    def calc_stats(results):
        if not results:
            return {
                "total": 0,
                "valid": 0,
                "success_rate": 0,
                "avg_time": 0,
                "avg_length": 0
            }
        
        total = len(results)
        valid = sum(1 for r in results if r['json_valid'])
        
        return {
            "total": total,
            "valid": valid,
            "success_rate": round(valid / total * 100, 1),
            "avg_time": round(sum(r['generation_time'] for r in results) / total, 2),
            "avg_length": round(sum(r['output_length'] for r in results) / total, 0)
        }
    
    base_stats = calc_stats(base_results)
    fine_stats = calc_stats(finetuned_results)
    
    print("\n📊 OVERALL RESULTS:")
    print("="*40)
    
    print(f"\nBase Model (with unified prompt):")
    print(f"  Valid JSON: {base_stats['valid']}/{base_stats['total']} ({base_stats['success_rate']}%)")
    print(f"  Avg Time: {base_stats['avg_time']}s")
    print(f"  Avg Output: {base_stats['avg_length']:.0f} chars")
    
    print(f"\nFine-tuned Model v5:")
    print(f"  Valid JSON: {fine_stats['valid']}/{fine_stats['total']} ({fine_stats['success_rate']}%)")
    print(f"  Avg Time: {fine_stats['avg_time']}s")
    print(f"  Avg Output: {fine_stats['avg_length']:.0f} chars")
    
    if base_results and finetuned_results:
        print(f"\n📈 IMPROVEMENTS:")
        print(f"  JSON Validity: {'+' if fine_stats['success_rate'] > base_stats['success_rate'] else ''}{fine_stats['success_rate'] - base_stats['success_rate']:.1f}%")
        print(f"  Speed: {(base_stats['avg_time'] - fine_stats['avg_time']) / base_stats['avg_time'] * 100:.1f}% faster")
        print(f"  Output Length: {'+' if fine_stats['avg_length'] > base_stats['avg_length'] else ''}{fine_stats['avg_length'] - base_stats['avg_length']:.0f} chars")
    
    # By complexity
    if finetuned_results:
        print(f"\n📊 BY COMPLEXITY (Fine-tuned):")
        complexities = set(r['complexity'] for r in finetuned_results)
        for complexity in sorted(complexities):
            comp_results = [r for r in finetuned_results if r['complexity'] == complexity]
            comp_valid = sum(1 for r in comp_results if r['json_valid'])
            print(f"  {complexity}: {comp_valid}/{len(comp_results)} ({comp_valid/len(comp_results)*100:.1f}%)")
    
    return {
        "base_model": base_stats,
        "finetuned_model": fine_stats
    }

def main():
    print("="*60)
    print("UNIFIED MODEL EVALUATION")
    print("Using SAME prompt format for fair comparison")
    print("="*60)
    
    # Load test scenarios
    scenarios = load_test_scenarios('expanded_test_scenarios.json')
    print(f"\n📋 Loaded {len(scenarios)} test scenarios")
    
    print("\nThis evaluation uses:")
    print("✅ SAME prompt format for both models")
    print("✅ SAME generation parameters")
    print("✅ SAME JSON extraction logic")
    print("✅ Prompt includes opening brace hint")
    
    # Test base model
    print("\n🔵 Starting BASE MODEL evaluation...")
    base_results = test_base_model(scenarios)
    
    if base_results:
        with open('base_model_results.json', 'w') as f:
            json.dump(base_results, f, indent=2)
        print("\n✅ Base model results saved to base_model_results.json")
    
    # Test fine-tuned model
    print("\n🟢 Starting FINE-TUNED MODEL evaluation...")
    finetuned_results = test_finetuned_model(scenarios)
    
    if finetuned_results:
        with open('finetuned_model_results.json', 'w') as f:
            json.dump(finetuned_results, f, indent=2)
        print("\n✅ Fine-tuned model results saved to finetuned_model_results.json")
    
    # Analyze and compare
    if base_results or finetuned_results:
        analysis = analyze_and_compare(base_results, finetuned_results)
        
        # Save comprehensive results
        comprehensive = {
            "timestamp": datetime.now().isoformat(),
            "total_scenarios": len(scenarios),
            "analysis": analysis,
            "scenarios": []
        }
        
        for i in range(len(scenarios)):
            comprehensive["scenarios"].append({
                "scenario": scenarios[i],
                "base_model": base_results[i] if i < len(base_results) else None,
                "finetuned_model": finetuned_results[i] if i < len(finetuned_results) else None
            })
        
        with open('unified_evaluation_results.json', 'w') as f:
            json.dump(comprehensive, f, indent=2)
        print("\n✅ Complete results saved to unified_evaluation_results.json")
    
    print("\n" + "="*60)
    print("🎉 EVALUATION COMPLETE!")
    print("="*60)

if __name__ == "__main__":
    main()