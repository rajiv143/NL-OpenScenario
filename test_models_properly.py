#!/usr/bin/env python3
"""
Proper evaluation script using your existing inference code
This uses the SAME base model loading that your fine-tuned model uses
"""
import json
import time
import sys
from datetime import datetime
import torch
from pathlib import Path

# Add path for your inference module
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

def test_base_model_via_generator(scenarios):
    """
    Test base model using a dummy LoRA path
    This loads the base model the same way your fine-tuned model does
    """
    print("\n" + "="*60)
    print("Testing BASE Model (via CarlaScenarioGenerator)")
    print("="*60)
    
    # Create a minimal LoRA config that points to base model
    # We'll use one of your model directories but load WITHOUT the LoRA weights
    dummy_path = Path("/home/user/Desktop/Rajiv/llm/models/llama-carla-model-v5-improved/final_model")
    
    if not dummy_path.exists():
        print("❌ Can't find model path to use as base")
        return []
    
    # Create a temporary adapter config that loads base model only
    temp_config_path = Path("/tmp/base_model_adapter_config.json")
    temp_config = {
        "base_model_name_or_path": "meta-llama/Llama-3.2-3B-Instruct",
        "peft_type": "LORA",
        "task_type": "CAUSAL_LM"
    }
    
    with open(temp_config_path, 'w') as f:
        json.dump(temp_config, f)
    
    print("Loading base model through generator (this uses cached model)...")
    
    # Load base model by using generator with no_lora flag
    class BaseModelGenerator(CarlaScenarioGenerator):
        def _load_model(self):
            """Override to load only base model without LoRA"""
            print(f"Loading base model: {self.base_model_name}")
            from transformers import AutoTokenizer, AutoModelForCausalLM
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.base_model_name,
                trust_remote_code=True,
                padding_side="left"
            )
            
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
                self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
            
            # Load base model WITHOUT LoRA weights
            self.model = AutoModelForCausalLM.from_pretrained(
                self.base_model_name,
                torch_dtype=torch.float16,
                device_map="auto",
                trust_remote_code=True,
                local_files_only=False  # Allow using cache or downloading if needed
            )
            
            self.model.eval()
            print("✓ Base model loaded successfully")
    
    try:
        generator = BaseModelGenerator(
            model_path=dummy_path,
            base_model_name="meta-llama/Llama-3.2-3B-Instruct",
            use_4bit=False,  # Don't use 4bit for base model comparison
            merge_lora=False
        )
        print("✓ Base model loaded via generator")
    except Exception as e:
        print(f"❌ Failed to load base model: {e}")
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
        
        if i % 5 == 0:
            with open('base_model_results_partial.json', 'w') as f:
                json.dump(results, f, indent=2)
            print(f"  [Checkpoint saved: {i} scenarios]")
    
    return results

def test_finetuned_model(scenarios):
    """Test your fine-tuned v5 model"""
    print("\n" + "="*60)
    print("Testing FINE-TUNED Model v5")
    print("="*60)
    
    model_path = "/home/user/Desktop/Rajiv/llm/models/llama-carla-model-v5-improved/final_model"
    
    print(f"Loading fine-tuned model from {model_path}...")
    try:
        generator = CarlaScenarioGenerator(
            model_path=model_path,
            use_4bit=True,
            merge_lora=False
        )
        print("✓ Fine-tuned model loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load fine-tuned model: {e}")
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
        
        if i % 5 == 0:
            with open('finetuned_model_results_partial.json', 'w') as f:
                json.dump(results, f, indent=2)
            print(f"  [Checkpoint saved: {i} scenarios]")
    
    return results

def analyze_and_compare(base_results, finetuned_results):
    """Analyze and compare results"""
    print("\n" + "="*60)
    print("ANALYSIS & COMPARISON")
    print("="*60)
    
    def calc_stats(results):
        total = len(results)
        valid = sum(1 for r in results if r['json_valid'])
        return {
            "total": total,
            "valid": valid,
            "invalid": total - valid,
            "success_rate": round(valid / total * 100, 1) if total > 0 else 0,
            "avg_time": round(sum(r['generation_time'] for r in results) / total, 2) if total > 0 else 0
        }
    
    base_stats = calc_stats(base_results) if base_results else {"total": 0, "valid": 0, "success_rate": 0, "avg_time": 0}
    fine_stats = calc_stats(finetuned_results)
    
    print(f"\n📊 RESULTS:")
    print(f"Base Model:      {base_stats['valid']}/{base_stats['total']} valid ({base_stats['success_rate']}%)")
    print(f"Fine-tuned v5:   {fine_stats['valid']}/{fine_stats['total']} valid ({fine_stats['success_rate']}%)")
    
    if base_results:
        print(f"\n⚡ IMPROVEMENTS:")
        print(f"Success Rate:    +{fine_stats['success_rate'] - base_stats['success_rate']:.1f}%")
        if base_stats['avg_time'] > 0:
            speed_improvement = (base_stats['avg_time'] - fine_stats['avg_time']) / base_stats['avg_time'] * 100
            print(f"Speed:           {speed_improvement:.1f}% faster")
    
    return {
        "base_model": base_stats,
        "finetuned_model": fine_stats
    }

def main():
    print("="*60)
    print("MODEL EVALUATION")
    print("Using your existing inference infrastructure")
    print("="*60)
    
    # Load test scenarios
    scenarios = load_test_scenarios('expanded_test_scenarios.json')
    print(f"\n📋 Loaded {len(scenarios)} test scenarios")
    
    # Ask user what to test
    print("\nWhat would you like to test?")
    print("1. Both base and fine-tuned models")
    print("2. Only fine-tuned model")
    print("3. Only base model")
    
    choice = input("\nEnter choice (1/2/3) [default: 2]: ").strip() or "2"
    
    base_results = []
    finetuned_results = []
    
    if choice in ["1", "3"]:
        print("\n🔵 Testing BASE model...")
        base_results = test_base_model_via_generator(scenarios)
        if base_results:
            with open('base_model_results.json', 'w') as f:
                json.dump(base_results, f, indent=2)
            print("\n✅ Base model results saved to base_model_results.json")
    
    if choice in ["1", "2"]:
        print("\n🟢 Testing FINE-TUNED model...")
        finetuned_results = test_finetuned_model(scenarios)
        if finetuned_results:
            with open('finetuned_model_results.json', 'w') as f:
                json.dump(finetuned_results, f, indent=2)
            print("\n✅ Fine-tuned model results saved to finetuned_model_results.json")
    
    # Analyze results
    if base_results or finetuned_results:
        analysis = analyze_and_compare(base_results, finetuned_results)
        
        # Save comprehensive results
        comprehensive = {
            "timestamp": datetime.now().isoformat(),
            "total_scenarios": len(scenarios),
            "analysis": analysis,
            "scenarios_tested": []
        }
        
        for i, scenario in enumerate(scenarios):
            comprehensive["scenarios_tested"].append({
                "scenario": scenario,
                "base_result": base_results[i] if i < len(base_results) else None,
                "finetuned_result": finetuned_results[i] if i < len(finetuned_results) else None
            })
        
        with open('evaluation_results.json', 'w') as f:
            json.dump(comprehensive, f, indent=2)
        print("\n✅ Complete evaluation saved to evaluation_results.json")
    
    print("\n" + "="*60)
    print("🎉 EVALUATION COMPLETE!")
    print("="*60)

if __name__ == "__main__":
    main()