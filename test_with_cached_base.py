#!/usr/bin/env python3
"""
Test script that uses CACHED base model and your fine-tuned models
No downloading - everything runs from local storage
"""
import json
import time
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from datetime import datetime
import sys
import os

# Force using local cache
os.environ['TRANSFORMERS_OFFLINE'] = '1'  # Prevent downloading
os.environ['HF_DATASETS_OFFLINE'] = '1'   # Use only cached data

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

def test_base_model_cached(scenarios):
    """Test the CACHED base model (no downloading)"""
    print("\n" + "="*60)
    print("Testing CACHED BASE Model (Meta-Llama-3.2-3B)")
    print("="*60)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # Use the cached model path directly
    cache_dir = "/home/user/.cache/huggingface/hub"
    model_name = "meta-llama/Llama-3.2-3B"
    
    print(f"Loading CACHED base model from {cache_dir}")
    print(f"Model: {model_name}")
    print(f"Using device: {device}")
    
    try:
        # Load from cache - this should NOT download anything
        print("Loading tokenizer from cache...")
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            cache_dir=cache_dir,
            local_files_only=True  # IMPORTANT: Only use local files
        )
        print("✓ Tokenizer loaded from cache")
        
        print("Loading model from cache (this may take a minute)...")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            cache_dir=cache_dir,
            local_files_only=True,  # IMPORTANT: Only use local files
            torch_dtype=torch.float16 if device.type == "cuda" else torch.float32,
            low_cpu_mem_usage=True,
            device_map="auto" if device.type == "cuda" else None
        )
        
        if device.type != "cuda" and hasattr(model, 'to'):
            model = model.to(device)
            
        print("✓ Model loaded from cache successfully")
        
    except Exception as e:
        print(f"❌ Error loading cached model: {str(e)}")
        print("\nNOTE: The base model needs to be in cache. If not cached:")
        print("  1. Run your training script once (it will cache the base model)")
        print("  2. Or load it once with: from transformers import AutoModelForCausalLM")
        print("     model = AutoModelForCausalLM.from_pretrained('meta-llama/Llama-3.2-3B')")
        return []
    
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    results = []
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n[{i}/{len(scenarios)}] Testing: {scenario['id']} ({scenario['category']})")
        print(f"  Prompt: {scenario['prompt'][:80]}...")
        
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
        
        try:
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
            if prompt in output_text:
                output_text = output_text[len(prompt):].strip()
            
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
            print(f"  [Checkpoint saved: {i} scenarios]")
    
    # Clean up
    del model
    del tokenizer
    if device.type == "cuda":
        torch.cuda.empty_cache()
    
    return results

def test_finetuned_model(scenarios, model_path, model_name="Fine-tuned"):
    """Test your fine-tuned model"""
    print("\n" + "="*60)
    print(f"Testing {model_name}")
    print(f"Path: {model_path}")
    print("="*60)
    
    print(f"Loading fine-tuned model...")
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
                "output_length": len(json_output)
            }
            
            print(f"  Valid JSON: {'✓' if is_valid else '✗'}")
            print(f"  Generation time: {generation_time:.2f}s")
            
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
            with open(f'{model_name.lower().replace(" ", "_")}_results_partial.json', 'w') as f:
                json.dump(results, f, indent=2)
            print(f"  [Checkpoint saved: {i} scenarios]")
    
    return results

def analyze_and_compare(base_results, finetuned_results):
    """Compare base vs fine-tuned results"""
    print("\n" + "="*60)
    print("COMPARISON ANALYSIS")
    print("="*60)
    
    def calculate_stats(results):
        total = len(results)
        valid = sum(1 for r in results if r['json_valid'])
        return {
            "total": total,
            "valid": valid,
            "success_rate": round(valid / total * 100, 1) if total > 0 else 0,
            "avg_time": round(sum(r['generation_time'] for r in results) / total, 2) if total > 0 else 0,
            "avg_length": round(sum(r['output_length'] for r in results) / total, 0) if total > 0 else 0
        }
    
    base_stats = calculate_stats(base_results)
    fine_stats = calculate_stats(finetuned_results)
    
    print("\n📊 OVERALL COMPARISON:")
    print("-" * 40)
    print(f"{'Metric':<20} {'Base Model':<15} {'Fine-tuned':<15} {'Improvement':<15}")
    print("-" * 40)
    
    # Success rate
    improvement = fine_stats['success_rate'] - base_stats['success_rate']
    print(f"{'Valid JSON':<20} {base_stats['valid']}/{base_stats['total']} ({base_stats['success_rate']}%) "
          f"{fine_stats['valid']}/{fine_stats['total']} ({fine_stats['success_rate']}%) "
          f"{'+' if improvement > 0 else ''}{improvement:.1f}%")
    
    # Speed
    speed_improvement = ((base_stats['avg_time'] - fine_stats['avg_time']) / base_stats['avg_time'] * 100) if base_stats['avg_time'] > 0 else 0
    print(f"{'Avg Time (s)':<20} {base_stats['avg_time']:<15} {fine_stats['avg_time']:<15} "
          f"{speed_improvement:.1f}% faster")
    
    # Output length
    print(f"{'Avg Output (chars)':<20} {base_stats['avg_length']:<15.0f} {fine_stats['avg_length']:<15.0f}")
    
    # By complexity
    print("\n📈 BY COMPLEXITY:")
    print("-" * 40)
    
    complexities = set(r['complexity'] for r in base_results)
    for complexity in sorted(complexities):
        base_comp = [r for r in base_results if r['complexity'] == complexity]
        fine_comp = [r for r in finetuned_results if r['complexity'] == complexity]
        
        base_valid = sum(1 for r in base_comp if r['json_valid'])
        fine_valid = sum(1 for r in fine_comp if r['json_valid'])
        
        base_rate = round(base_valid / len(base_comp) * 100, 1) if base_comp else 0
        fine_rate = round(fine_valid / len(fine_comp) * 100, 1) if fine_comp else 0
        
        print(f"{complexity.upper()}:")
        print(f"  Base: {base_valid}/{len(base_comp)} ({base_rate}%)")
        print(f"  Fine-tuned: {fine_valid}/{len(fine_comp)} ({fine_rate}%)")
        print(f"  Improvement: {'+' if fine_rate > base_rate else ''}{fine_rate - base_rate:.1f}%")
    
    return {
        "base_model": base_stats,
        "finetuned_model": fine_stats,
        "improvements": {
            "success_rate": improvement,
            "speed": speed_improvement
        }
    }

def main():
    print("="*60)
    print("CACHED MODEL EVALUATION")
    print("Using local cached models only - no downloading")
    print("="*60)
    
    # Load test scenarios
    scenarios = load_test_scenarios('expanded_test_scenarios.json')
    print(f"\n📋 Loaded {len(scenarios)} test scenarios")
    
    # Test base model from cache
    print("\n🔵 Testing CACHED base model...")
    base_results = test_base_model_cached(scenarios)
    
    if base_results:
        with open('base_model_results.json', 'w') as f:
            json.dump(base_results, f, indent=2)
        print("\n✅ Base model results saved to base_model_results.json")
    else:
        print("\n⚠️  Base model testing failed - check if model is cached")
    
    # Test your fine-tuned model (using correct path)
    print("\n🟢 Testing fine-tuned model...")
    
    # Check which v5 model exists
    v5_paths = [
        "/home/user/Desktop/Rajiv/llm/llama3.2_3b_carla_v5",  # Original path
        "/home/user/Desktop/Rajiv/llm/models/llama-carla-model-v5-improved"  # New path
    ]
    
    finetuned_path = None
    for path in v5_paths:
        if os.path.exists(path):
            finetuned_path = path
            break
    
    if not finetuned_path:
        print("❌ Could not find v5 model. Checking available models...")
        print("Available models in ./llm/models/:")
        os.system("ls -la /home/user/Desktop/Rajiv/llm/models/")
        finetuned_path = "/home/user/Desktop/Rajiv/llm/models/llama-carla-model-v5-improved"
    
    finetuned_results = test_finetuned_model(scenarios, finetuned_path, "Fine-tuned v5")
    
    if finetuned_results:
        with open('finetuned_model_results.json', 'w') as f:
            json.dump(finetuned_results, f, indent=2)
        print("\n✅ Fine-tuned model results saved to finetuned_model_results.json")
    
    # Compare results
    if base_results and finetuned_results:
        analysis = analyze_and_compare(base_results, finetuned_results)
        
        # Save comprehensive analysis
        comprehensive = {
            "timestamp": datetime.now().isoformat(),
            "total_scenarios": len(scenarios),
            "analysis": analysis,
            "base_results": base_results,
            "finetuned_results": finetuned_results
        }
        
        with open('comprehensive_comparison.json', 'w') as f:
            json.dump(comprehensive, f, indent=2)
        print("\n✅ Comprehensive comparison saved to comprehensive_comparison.json")
        
        # Create combined results for semantic scoring
        combined = {
            "timestamp": datetime.now().isoformat(),
            "scenarios": []
        }
        
        for i in range(len(scenarios)):
            combined["scenarios"].append({
                "scenario": scenarios[i],
                "base_model": base_results[i] if i < len(base_results) else None,
                "finetuned_model": finetuned_results[i] if i < len(finetuned_results) else None
            })
        
        with open('combined_test_results.json', 'w') as f:
            json.dump(combined, f, indent=2)
        print("✅ Combined results saved to combined_test_results.json")
    
    print("\n" + "="*60)
    print("🎉 EVALUATION COMPLETE!")
    print("="*60)
    print("\nFiles created:")
    print("  - base_model_results.json")
    print("  - finetuned_model_results.json")
    print("  - comprehensive_comparison.json")
    print("  - combined_test_results.json")
    print("\n📝 Share combined_test_results.json for semantic accuracy scoring!")

if __name__ == "__main__":
    main()