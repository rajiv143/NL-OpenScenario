#!/usr/bin/env python3
"""
Model comparison using the SAME inference infrastructure
This ensures both models use identical prompt formatting and generation logic
"""

import json
import time
import torch
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
import sys
import os
from typing import Dict, List, Optional

# Add the llm directory to path
sys.path.append('/home/user/Desktop/Rajiv/llm')

class BaseModelGenerator:
    """
    Generator for base model - uses same format as CarlaScenarioGenerator
    but without LoRA weights
    """
    def __init__(self, base_model_name: str = "meta-llama/Llama-3.2-3B-Instruct"):
        self.base_model_name = base_model_name
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        print(f"Loading BASE model: {base_model_name}")
        print(f"Using device: {self.device}")
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            base_model_name,
            trust_remote_code=True,
            padding_side="left"
        )
        
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
        
        # Load base model WITHOUT LoRA
        print("Loading base model (this may take a minute)...")
        self.model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
            device_map="auto" if self.device.type == "cuda" else None,
            trust_remote_code=True,
            low_cpu_mem_usage=True
        )
        
        self.model.eval()
        print("✓ Base model loaded successfully")
        
        # Warm up the model (SAME as CarlaScenarioGenerator)
        self._warmup()
    
    def _warmup(self):
        """Warm up the model with a dummy generation - SAME as CarlaScenarioGenerator"""
        print("Warming up model...")
        dummy_input = "Generate a simple scenario"
        prompt = self.format_prompt(dummy_input)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            _ = self.model.generate(
                **inputs,
                max_new_tokens=10,
                use_cache=True,
            )
        print("✓ Model warmed up")
    
    def format_prompt(self, description: str, instruction: Optional[str] = None) -> str:
        """Format prompt - EXACT SAME as CarlaScenarioGenerator"""
        if instruction is None:
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
        
        # Use Llama 3.x format
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are an expert CARLA simulator scenario designer. Generate valid JSON scenarios based on natural language descriptions. ALWAYS start with opening brace and include all required fields in order: scenario_name, description, weather, ego_vehicle_model, ego_spawn, ego_start_speed, actors, actions, success_distance, timeout, collision_allowed.<|eot_id|><|start_header_id|>user<|end_header_id|>

{instruction}

{description}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""
        return prompt
    
    def _extract_json(self, generated_text: str, prompt: str) -> str:
        """Extract JSON from generated text - SAME as CarlaScenarioGenerator"""
        # Remove the prompt from the output
        if prompt in generated_text:
            generated_text = generated_text[len(prompt):]
        
        # Remove any remaining chat tokens
        generated_text = generated_text.replace('<|eot_id|>', '')
        generated_text = generated_text.replace('<|end_of_text|>', '')
        
        # Find the JSON content
        generated_text = generated_text.strip()
        
        # If starts with {, find the matching }
        if generated_text.startswith('{'):
            brace_count = 0
            for i, char in enumerate(generated_text):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return generated_text[:i+1]
        
        # Try to find JSON anywhere
        start_idx = generated_text.find('{')
        if start_idx != -1:
            brace_count = 0
            for i in range(start_idx, len(generated_text)):
                if generated_text[i] == '{':
                    brace_count += 1
                elif generated_text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return generated_text[start_idx:i+1]
        
        return generated_text
    
    def generate_scenario(self, 
                         description: str,
                         max_new_tokens: int = 1500,
                         temperature: float = 0.7,
                         top_p: float = 0.9,
                         do_sample: bool = True) -> Dict:
        """Generate scenario - EXACT SAME as CarlaScenarioGenerator"""
        # Format prompt
        prompt = self.format_prompt(description)
        
        # Tokenize
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        
        print(f"Generating (input tokens: {inputs['input_ids'].shape[1]})...")
        start_time = time.time()
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                min_new_tokens=100,  # EXACT same as CarlaScenarioGenerator
                temperature=temperature,
                top_p=top_p,
                do_sample=do_sample,
                repetition_penalty=1.1,
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                use_cache=True,  # Critical for speed - SAME as CarlaScenarioGenerator
                num_beams=1  # Greedy is faster - SAME as CarlaScenarioGenerator
            )
        
        generation_time = time.time() - start_time
        tokens_generated = outputs.shape[1] - inputs['input_ids'].shape[1]
        print(f"Generated {tokens_generated} tokens in {generation_time:.2f}s")
        
        # Decode
        generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=False)
        
        # Extract JSON
        json_text = self._extract_json(generated_text, prompt)
        
        # Parse JSON
        try:
            scenario = json.loads(json_text)
            return scenario
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            print("Generated text (first 500 chars):")
            print(json_text[:500])
            return None

def load_test_scenarios(file_path):
    """Load test scenarios"""
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data['test_scenarios']

def test_model(generator, scenarios, model_name="Model"):
    """Test a model with scenarios"""
    results = []
    
    print(f"\n{'='*60}")
    print(f"Testing {model_name}")
    print(f"{'='*60}")
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n[{i}/{len(scenarios)}] {scenario['id']} ({scenario['category']})")
        print(f"  Prompt: {scenario['prompt'][:80]}...")
        
        start_time = time.time()
        
        try:
            # Generate scenario
            scenario_dict = generator.generate_scenario(scenario['prompt'])
            generation_time = time.time() - start_time
            
            if scenario_dict:
                json_output = json.dumps(scenario_dict, indent=2)
                is_valid = True
                error = None
            else:
                json_output = ""
                is_valid = False
                error = "Failed to generate valid JSON"
            
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
            
            print(f"  Valid: {'✓' if is_valid else '✗'} | Time: {generation_time:.2f}s | Length: {len(json_output)}")
            
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
        
        # Save checkpoint every 5
        if i % 5 == 0:
            checkpoint_file = f"{model_name.lower().replace(' ', '_')}_checkpoint.json"
            with open(checkpoint_file, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"  [Checkpoint saved: {i} scenarios]")
    
    return results

def main():
    print("="*60)
    print("MODEL COMPARISON")
    print("Using unified inference infrastructure")
    print("="*60)
    
    # Load scenarios
    scenarios = load_test_scenarios('/home/user/Desktop/Rajiv/expanded_test_scenarios.json')
    print(f"\n📋 Loaded {len(scenarios)} test scenarios")
    
    # Option to test subset
    test_all = input("\nTest all 25 scenarios? (y/n) [default: n]: ").strip().lower() == 'y'
    if not test_all:
        num = int(input("How many scenarios to test? [default: 5]: ").strip() or "5")
        scenarios = scenarios[:num]
        print(f"Testing first {num} scenarios")
    
    # Test base model
    print("\n🔵 Loading BASE model...")
    base_generator = BaseModelGenerator("meta-llama/Llama-3.2-3B-Instruct")
    base_results = test_model(base_generator, scenarios, "Base Model")
    
    # Save base results
    with open('base_model_results.json', 'w') as f:
        json.dump(base_results, f, indent=2)
    print("\n✅ Base model results saved")
    
    # Clean up base model
    del base_generator.model
    del base_generator
    torch.cuda.empty_cache()
    
    # Test fine-tuned model
    print("\n🟢 Loading FINE-TUNED model...")
    from inference_carla_model import CarlaScenarioGenerator
    
    finetuned_generator = CarlaScenarioGenerator(
        model_path="/home/user/Desktop/Rajiv/llm/models/llama-carla-model-v5-improved/final_model",
        use_4bit=True,
        merge_lora=False
    )
    
    finetuned_results = test_model(finetuned_generator, scenarios, "Fine-tuned v5")
    
    # Save fine-tuned results
    with open('finetuned_model_results.json', 'w') as f:
        json.dump(finetuned_results, f, indent=2)
    print("\n✅ Fine-tuned model results saved")
    
    # Analysis
    print("\n" + "="*60)
    print("ANALYSIS")
    print("="*60)
    
    base_valid = sum(1 for r in base_results if r['json_valid'])
    fine_valid = sum(1 for r in finetuned_results if r['json_valid'])
    total = len(scenarios)
    
    print(f"\n📊 Results:")
    print(f"Base Model:      {base_valid}/{total} valid ({base_valid/total*100:.1f}%)")
    print(f"Fine-tuned v5:   {fine_valid}/{total} valid ({fine_valid/total*100:.1f}%)")
    
    base_avg_time = sum(r['generation_time'] for r in base_results) / len(base_results)
    fine_avg_time = sum(r['generation_time'] for r in finetuned_results) / len(finetuned_results)
    
    print(f"\n⏱️  Speed:")
    print(f"Base Model:      {base_avg_time:.2f}s average")
    print(f"Fine-tuned v5:   {fine_avg_time:.2f}s average")
    print(f"Improvement:     {(base_avg_time - fine_avg_time)/base_avg_time*100:.1f}% faster")
    
    # Save combined results
    combined = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_scenarios": len(scenarios),
        "scenarios": []
    }
    
    for i in range(len(scenarios)):
        combined["scenarios"].append({
            "scenario": scenarios[i],
            "base_result": base_results[i],
            "finetuned_result": finetuned_results[i]
        })
    
    with open('model_comparison_results.json', 'w') as f:
        json.dump(combined, f, indent=2)
    
    print("\n✅ Complete results saved to model_comparison_results.json")
    print("\n" + "="*60)
    print("COMPARISON COMPLETE!")
    print("="*60)

if __name__ == "__main__":
    main()