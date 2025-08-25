#!/usr/bin/env python3
"""
Fixed evaluation script - properly implements base model testing
"""
import json
import time
import sys
from datetime import datetime
import torch
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM

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

class SimpleBaseModelTester:
    """Simple class to test base model without LoRA"""
    def __init__(self, model_name="meta-llama/Llama-3.2-3B-Instruct"):
        self.model_name = model_name
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Loading base model: {model_name}")
        print(f"Using device: {self.device}")
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True,
            padding_side="left"
        )
        
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        # Load model
        print("Loading model (this may take a minute)...")
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
            device_map="auto" if self.device.type == "cuda" else None,
            trust_remote_code=True
        )
        
        if self.device.type != "cuda" and hasattr(self.model, 'to'):
            self.model = self.model.to(self.device)
        
        self.model.eval()
        print("✓ Base model loaded successfully")
    
    def generate(self, prompt):
        """Generate scenario from prompt"""
        # Format prompt for scenario generation
        formatted_prompt = f"""Generate a CARLA scenario JSON for the following description:
{prompt}

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
        
        inputs = self.tokenizer(
            formatted_prompt,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512
        )
        
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=1024,
                temperature=0.1,
                do_sample=True,
                top_p=0.95,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id
            )
        
        output_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Remove the input prompt from output
        if formatted_prompt in output_text:
            output_text = output_text[len(formatted_prompt):].strip()
        
        return output_text

def test_base_model(scenarios, limit=None):
    """Test base model"""
    print("\n" + "="*60)
    print("Testing BASE Model (Llama-3.2-3B-Instruct)")
    print("="*60)
    
    if limit:
        scenarios = scenarios[:limit]
        print(f"Testing first {limit} scenarios only")
    
    try:
        tester = SimpleBaseModelTester("meta-llama/Llama-3.2-3B-Instruct")
    except Exception as e:
        print(f"❌ Failed to load base model: {e}")
        print("\nTrying alternative: meta-llama/Llama-3.2-3B")
        try:
            tester = SimpleBaseModelTester("meta-llama/Llama-3.2-3B")
        except Exception as e2:
            print(f"❌ Also failed: {e2}")
            return []
    
    results = []
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n[{i}/{len(scenarios)}] Testing: {scenario['id']} ({scenario['category']})")
        print(f"  Prompt: {scenario['prompt'][:80]}...")
        
        start_time = time.time()
        
        try:
            output_text = tester.generate(scenario['prompt'])
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
    
    # Clean up
    del tester.model
    del tester.tokenizer
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    
    return results

def test_finetuned_model(scenarios, limit=None):
    """Test your fine-tuned v5 model"""
    print("\n" + "="*60)
    print("Testing FINE-TUNED Model v5")
    print("="*60)
    
    if limit:
        scenarios = scenarios[:limit]
        print(f"Testing first {limit} scenarios only")
    
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
            "avg_time": round(sum(r['generation_time'] for r in results) / total, 2) if total > 0 else 0,
            "avg_length": round(sum(r['output_length'] for r in results) / total, 0) if total > 0 else 0
        }
    
    base_stats = calc_stats(base_results) if base_results else {"total": 0, "valid": 0, "success_rate": 0, "avg_time": 0}
    fine_stats = calc_stats(finetuned_results)
    
    print(f"\n📊 OVERALL RESULTS:")
    print("-" * 40)
    
    if base_results:
        print(f"Base Model:      {base_stats['valid']}/{base_stats['total']} valid ({base_stats['success_rate']}%)")
        print(f"                 Avg time: {base_stats['avg_time']}s")
    
    print(f"Fine-tuned v5:   {fine_stats['valid']}/{fine_stats['total']} valid ({fine_stats['success_rate']}%)")
    print(f"                 Avg time: {fine_stats['avg_time']}s")
    
    if base_results:
        print(f"\n⚡ IMPROVEMENTS:")
        print(f"Success Rate:    {'+' if fine_stats['success_rate'] > base_stats['success_rate'] else ''}{fine_stats['success_rate'] - base_stats['success_rate']:.1f}%")
        if base_stats['avg_time'] > 0:
            speed_improvement = (base_stats['avg_time'] - fine_stats['avg_time']) / base_stats['avg_time'] * 100
            print(f"Speed:           {speed_improvement:.1f}% faster")
    
    # By complexity breakdown
    if finetuned_results:
        print(f"\n📈 FINE-TUNED MODEL BY COMPLEXITY:")
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
    print("MODEL EVALUATION (FIXED)")
    print("="*60)
    
    # Load test scenarios
    scenarios = load_test_scenarios('expanded_test_scenarios.json')
    print(f"\n📋 Loaded {len(scenarios)} test scenarios")
    
    # Ask user what to test
    print("\nWhat would you like to test?")
    print("1. Both models (full test)")
    print("2. Only fine-tuned model")
    print("3. Only base model")
    print("4. Quick test (5 scenarios each)")
    
    choice = input("\nEnter choice (1/2/3/4) [default: 2]: ").strip() or "2"
    
    base_results = []
    finetuned_results = []
    
    # Set limit for quick test
    limit = 5 if choice == "4" else None
    
    if choice in ["1", "3", "4"]:
        print("\n🔵 Testing BASE model...")
        base_results = test_base_model(scenarios, limit)
        if base_results:
            with open('base_model_results.json', 'w') as f:
                json.dump(base_results, f, indent=2)
            print("\n✅ Base model results saved to base_model_results.json")
    
    if choice in ["1", "2", "4"]:
        print("\n🟢 Testing FINE-TUNED model...")
        finetuned_results = test_finetuned_model(scenarios, limit)
        if finetuned_results:
            with open('finetuned_model_results.json', 'w') as f:
                json.dump(finetuned_results, f, indent=2)
            print("\n✅ Fine-tuned model results saved to finetuned_model_results.json")
    
    # Analyze results
    if base_results or finetuned_results:
        analysis = analyze_and_compare(base_results, finetuned_results)
        
        # Save comprehensive results
        test_count = len(base_results) if base_results else len(finetuned_results)
        comprehensive = {
            "timestamp": datetime.now().isoformat(),
            "total_scenarios_tested": test_count,
            "analysis": analysis,
            "scenarios_tested": []
        }
        
        for i in range(test_count):
            comprehensive["scenarios_tested"].append({
                "scenario": scenarios[i],
                "base_result": base_results[i] if i < len(base_results) else None,
                "finetuned_result": finetuned_results[i] if i < len(finetuned_results) else None
            })
        
        with open('evaluation_results.json', 'w') as f:
            json.dump(comprehensive, f, indent=2)
        print("\n✅ Complete evaluation saved to evaluation_results.json")
    
    print("\n" + "="*60)
    print("🎉 EVALUATION COMPLETE!")
    print("="*60)
    print("\nFiles created:")
    if base_results:
        print("  - base_model_results.json")
    if finetuned_results:
        print("  - finetuned_model_results.json")
    print("  - evaluation_results.json")

if __name__ == "__main__":
    main()