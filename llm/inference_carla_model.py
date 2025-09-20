#!/usr/bin/env python3
"""
Optimized inference script for trained Llama CARLA scenario model
Complete version with all modes: interactive, test, batch, and benchmark
"""

import json
import torch
import time
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel
import argparse
from typing import Dict, List, Optional
import re

class CarlaScenarioGenerator:
    def __init__(self, 
                 model_path: str = "./llama-carla-model/final_model",
                 base_model_name: Optional[str] = None,
                 use_4bit: bool = True,
                 merge_lora: bool = False):
        """
        Initialize the generator with trained model
        
        Args:
            model_path: Path to the trained LoRA model
            base_model_name: Base model name if not stored in adapter config
            use_4bit: Whether to load in 4-bit for inference
            merge_lora: Whether to merge LoRA weights for faster inference
        """
        self.model_path = Path(model_path)
        self.use_4bit = use_4bit
        self.merge_lora = merge_lora
        
        # Check if model exists
        if not self.model_path.exists():
            raise ValueError(f"Model not found at {self.model_path}")
        
        # Try to load adapter config to get base model name
        adapter_config_path = self.model_path / "adapter_config.json"
        if adapter_config_path.exists() and base_model_name is None:
            with open(adapter_config_path, 'r') as f:
                adapter_config = json.load(f)
                base_model_name = adapter_config.get("base_model_name_or_path")
        
        if base_model_name is None:
            base_model_name = "meta-llama/Llama-3.2-3B-Instruct"
            print(f"Warning: Base model not specified, using default: {base_model_name}")
        
        self.base_model_name = base_model_name
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Check CUDA status
        print(f"Using device: {self.device}")
        if self.device.type == "cuda":
            print(f"GPU: {torch.cuda.get_device_name()}")
            print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
            # Enable TF32 for faster computation on Ampere GPUs (RTX 3090)
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
        
        # Load model and tokenizer
        self._load_model()
        
        # Warm-up the model
        self._warmup()
    
    def _load_model(self):
        """Load the trained model and tokenizer"""
        print(f"Loading model from {self.model_path}")
        start_time = time.time()
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_path,
            trust_remote_code=True,
            padding_side="left"
        )
        
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
        
        # Better quantization config
        bnb_config = None
        if self.use_4bit:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
            )
        
        # Load base model
        print(f"Loading base model: {self.base_model_name}")
        base_model = AutoModelForCausalLM.from_pretrained(
            self.base_model_name,
            quantization_config=bnb_config,
            torch_dtype=torch.float16 if not self.use_4bit else None,
            device_map="auto",
            trust_remote_code=True
        )
        
        # Load LoRA weights
        print("Loading LoRA weights...")
        self.model = PeftModel.from_pretrained(base_model, self.model_path)
        
        # Merge LoRA weights if requested (and not using 4-bit)
        if self.merge_lora and not self.use_4bit:
            print("Merging LoRA weights for faster inference...")
            self.model = self.model.merge_and_unload()
        
        # Set to evaluation mode
        self.model.eval()
        
        # Disable gradient checkpointing for inference
        if hasattr(self.model, 'gradient_checkpointing_disable'):
            self.model.gradient_checkpointing_disable()
        
        load_time = time.time() - start_time
        print(f"✓ Model loaded successfully in {load_time:.2f} seconds")
        
        # Check model is on GPU
        if next(self.model.parameters()).is_cuda:
            print("✓ Model is on GPU")
        else:
            print("⚠️ WARNING: Model is on CPU - inference will be slow!")
    
    def _warmup(self):
        """Warm up the model with a dummy generation"""
        print("Warming up model...")
        dummy_input = "Generate a simple scenario"
        prompt = self.format_prompt(dummy_input)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        
        with torch.no_grad():
            _ = self.model.generate(
                **inputs,
                max_new_tokens=10,
                use_cache=True,
            )
        print("✓ Model warmed up")
    
    def format_prompt(self, description: str, instruction: Optional[str] = None) -> str:
        """Format the input prompt for generation"""
        if instruction is None:
            # Emphasize complete JSON generation with explicit start
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
        
        # Check model format
        if "3.2" in self.base_model_name or "3.1" in self.base_model_name:
            # Llama 3.x format
            prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are an expert CARLA simulator scenario designer. Generate valid JSON scenarios based on natural language descriptions. ALWAYS start with opening brace and include all required fields in order: scenario_name, description, weather, ego_vehicle_model, ego_spawn, ego_start_speed, actors, actions, success_distance, timeout, collision_allowed.<|eot_id|><|start_header_id|>user<|end_header_id|>

{instruction}

{description}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""
        else:
            # Llama 2 format
            prompt = f"""[INST] <<SYS>>
You are an expert CARLA simulator scenario designer. Generate complete valid JSON scenarios starting with opening brace.
<</SYS>>

{instruction}

{description} [/INST]

"""
        
        return prompt
    
    def generate_scenario(self, 
                         description: str,
                         max_new_tokens: int = 1500,
                         temperature: float = 0.7,
                         top_p: float = 0.9,
                         do_sample: bool = True,
                         benchmark: bool = False) -> Dict:
        """
        Generate a CARLA scenario from natural language description
        
        Args:
            description: Natural language description of the scenario
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            do_sample: Whether to use sampling
            benchmark: Whether to print timing information
        
        Returns:
            Generated scenario as dictionary
        """
        # Format prompt
        prompt = self.format_prompt(description)
        
        # Tokenize
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        
        # Generate with timing
        print("Generating scenario...")
        print(f"Input tokens: {inputs['input_ids'].shape[1]}")
        
        start_time = time.time()
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                min_new_tokens=100,  # Reduced from 500
                temperature=temperature,
                top_p=top_p,
                do_sample=do_sample,
                repetition_penalty=1.1,
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                use_cache=True,  # Critical for speed!
                num_beams=1,  # Greedy is faster
            )
        
        generation_time = time.time() - start_time
        tokens_generated = outputs.shape[1] - inputs['input_ids'].shape[1]
        
        if benchmark:
            print(f"⏱️ Generation time: {generation_time:.2f} seconds")
            print(f"📊 Tokens generated: {tokens_generated}")
            print(f"⚡ Tokens per second: {tokens_generated/generation_time:.2f}")
        else:
            print(f"Generated {tokens_generated} new tokens in {generation_time:.2f}s")
        
        # Decode
        generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=False)
        
        # Extract JSON from response - pass the full text for weather extraction
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
    
    def _extract_weather_from_description(self, prompt_text: str) -> str:
        """Extract weather intent from user's description"""
        prompt_lower = prompt_text.lower()
        
        # Check for specific weather keywords
        weather_mappings = {
            'heavy rain': 'hard_rain',
            'hard rain': 'hard_rain',
            'light rain': 'soft_rain',
            'soft rain': 'soft_rain',
            'drizzle': 'soft_rain',
            'fog': 'fog',
            'foggy': 'fog',
            'dense fog': 'fog',
            'wet': 'wet',
            'wet road': 'wet_cloudy',
            'cloudy': 'cloudy',
            'overcast': 'cloudy',
            'sunset': 'clear_sunset',
            'sunrise': 'clear_sunset',
            'night': 'clear_night',
            'dark': 'clear_night',
            'noon': 'clear_noon',
            'midday': 'clear_noon',
            'storm': 'hard_rain',
            'thunder': 'hard_rain',
            'snow': 'soft_rain',  # Approximate since CARLA may not have snow
            'clear': 'clear',
            'sunny': 'clear_noon'
        }
        
        # Check each weather pattern
        for keyword, weather_value in weather_mappings.items():
            if keyword in prompt_lower:
                print(f"  📍 Detected weather request: {keyword} → {weather_value}")
                return weather_value
        
        # Default to clear if no weather specified
        return "clear"
    
    def _extract_json(self, text: str, prompt: str) -> str:
        """Extract JSON from model response - handles start/end tokens"""
        # Get the response part
        if '<|eot_id|><|start_header_id|>assistant<|end_header_id|>' in text:
            response = text.split('<|eot_id|><|start_header_id|>assistant<|end_header_id|>')[-1].strip()
        else:
            response = text[len(prompt):].strip() if len(text) > len(prompt) else text
        
        print(f"🔍 Raw response length: {len(response)} characters")
        
        # NEW: Check for our start/end tokens FIRST
        if '<<<JSON_START>>>' in response:
            print("📍 Found JSON_START token!")
            start_idx = response.find('<<<JSON_START>>>') + len('<<<JSON_START>>>')
            
            # Find the end token or the last closing brace
            if '<<<JSON_END>>>' in response:
                end_idx = response.find('<<<JSON_END>>>')
                print("📍 Found JSON_END token!")
            else:
                end_idx = response.rfind('}') + 1 if '}' in response else len(response)
            
            if start_idx < end_idx:
                json_str = response[start_idx:end_idx].strip()
                try:
                    parsed = json.loads(json_str)
                    print("✅ Successfully extracted JSON with start/end tokens!")
                    return json.dumps(parsed, indent=2)
                except json.JSONDecodeError as e:
                    print(f"⚠️ JSON parsing failed despite tokens: {e}")
                    # Continue to fallback methods
        
        # Fallback: Find JSON boundaries without tokens
        start_idx = response.find('{')
        end_idx = response.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            potential_json = response[start_idx:end_idx+1]
            try:
                parsed = json.loads(potential_json)
                print("✅ Found complete valid JSON (no tokens)!")
                return json.dumps(parsed, indent=2)
            except json.JSONDecodeError:
                pass
        
        # Check if response starts with truncated JSON (missing opening)
        if not response.startswith('{') and not response.startswith('<<<JSON_START>>>'):
            print("⚠️ JSON appears truncated at beginning, attempting smart repair...")
            
            # Extract weather from the user's original description
            weather_hint = self._extract_weather_from_description(prompt)
            
            # Try to detect common truncation patterns
            truncation_patterns = [
                (r'^cle\.', '"ego_vehicle_model": "vehi'),  # Truncated "vehicle"
                (r'^hicle\.', '"ego_vehicle_model": "ve'),   # Truncated "vehicle"
                (r'^ehicle\.', '"ego_vehicle_model": "v'),   # Truncated "vehicle"
                (r'^le\.audi', '"ego_vehicle_model": "vehic'), # Truncated "vehicle.audi"
                (r'^\.audi', '"ego_vehicle_model": "vehicle'), # Truncated at ".audi"
                (r'^audi\.', '"ego_vehicle_model": "vehicle.'), # Truncated at "audi"
                (r'^"ego_', '{'),  # Truncated at ego field
            ]
            
            prefix = None
            for pattern, field_prefix in truncation_patterns:
                if re.match(pattern, response):
                    # Build the prefix up to the truncation point
                    prefix = f'''{{
    "scenario_name": "generated_scenario",
    "description": "Generated CARLA scenario",
    "weather": "{weather_hint}",
    {field_prefix}'''
                    break
            
            if prefix is None and not response.startswith('{'):
                # Generic truncation - add full prefix
                prefix = f'''{{
    "scenario_name": "generated_scenario",
    "description": "Generated CARLA scenario",
    "weather": "{weather_hint}",
    "ego_vehicle_model": "vehicle.audi.a2",
    '''
            
            if prefix:
                repaired = prefix + response
                
                # Try to parse the repaired JSON
                try:
                    start = repaired.find('{')
                    end = repaired.rfind('}')
                    if start != -1 and end != -1:
                        json_str = repaired[start:end+1]
                        parsed = json.loads(json_str)
                        print(f"✅ Successfully repaired truncated JSON! (Weather: {weather_hint})")
                        
                        # Ensure required fields
                        if "scenario_name" not in parsed:
                            parsed["scenario_name"] = "generated_scenario"
                        if "description" not in parsed:
                            parsed["description"] = "Generated CARLA scenario"
                        if "weather" not in parsed:
                            parsed["weather"] = weather_hint
                        
                        return json.dumps(parsed, indent=2)
                except json.JSONDecodeError as e:
                    print(f"⚠️ Repair attempt failed: {e}")
        
        # Final fallback: Build from extracted fields
        print("🔧 Building JSON from extracted fields...")
        
        weather_hint = self._extract_weather_from_description(prompt)
        extracted = {}
        
        # Extract complex nested structures
        patterns = {
            'ego_spawn': r'"ego_spawn":\s*(\{(?:[^{}]|\{[^{}]*\})*\})',
            'actors': r'"actors":\s*(\[(?:[^\[\]]|\[[^\[\]]*\])*\])',
            'actions': r'"actions":\s*(\[(?:[^\[\]]|\[[^\[\]]*\])*\])',
        }
        
        for field, pattern in patterns.items():
            match = re.search(pattern, response, re.DOTALL)
            if match:
                try:
                    extracted[field] = json.loads(match.group(1))
                    print(f"  ✓ Extracted {field}")
                except:
                    print(f"  ✗ Failed to parse {field}")
        
        # Simple fields
        field_patterns = {
            'scenario_name': r'"scenario_name":\s*"([^"]*)"',
            'description': r'"description":\s*"([^"]*)"', 
            'weather': r'"weather":\s*"([^"]*)"',
            'ego_vehicle_model': r'"ego_vehicle_model":\s*"([^"]*)"',
            'ego_start_speed': r'"ego_start_speed":\s*(\d+)',
            'success_distance': r'"success_distance":\s*(\d+)',
            'timeout': r'"timeout":\s*(\d+)',
            'collision_allowed': r'"collision_allowed":\s*(true|false)'
        }
        
        for field, pattern in field_patterns.items():
            if field not in extracted:
                match = re.search(pattern, response)
                if match:
                    value = match.group(1)
                    if field in ['ego_start_speed', 'success_distance', 'timeout']:
                        extracted[field] = int(value)
                    elif field == 'collision_allowed':
                        extracted[field] = value.lower() == 'true'
                    else:
                        extracted[field] = value
                    print(f"  ✓ Extracted {field}")
        
        # Build final scenario with defaults
        scenario = {
            "scenario_name": extracted.get('scenario_name', "generated_scenario"),
            "description": extracted.get('description', "Generated CARLA scenario"),
            "weather": extracted.get('weather', weather_hint),
            "ego_vehicle_model": extracted.get('ego_vehicle_model', "vehicle.audi.a2"),
            "ego_spawn": extracted.get('ego_spawn', {"criteria": {"lane_type": "Driving", "is_intersection": False}}),
            "ego_start_speed": extracted.get('ego_start_speed', 10),
            "actors": extracted.get('actors', []),
            "actions": extracted.get('actions', []),
            "success_distance": extracted.get('success_distance', 100),
            "timeout": extracted.get('timeout', 60),
            "collision_allowed": extracted.get('collision_allowed', False)
        }
        
        print(f"✅ Reconstructed scenario with {len(extracted)} extracted fields")
        return json.dumps(scenario, indent=2)
    
    def generate_batch(self, descriptions: List[str], output_dir: str = "generated_scenarios") -> List[Dict]:
        """Generate scenarios for multiple descriptions"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        results = []
        for i, description in enumerate(descriptions, 1):
            print(f"\n[{i}/{len(descriptions)}] Processing: {description[:50]}...")
            
            scenario = self.generate_scenario(description)
            
            if scenario:
                # Save scenario
                scenario_name = f"generated_{i:03d}"
                scenario["scenario_name"] = scenario_name
                
                # Save JSON
                json_path = output_path / f"{scenario_name}.json"
                with open(json_path, 'w') as f:
                    json.dump(scenario, f, indent=2)
                
                # Save description
                desc_path = output_path / f"{scenario_name}_description.txt"
                with open(desc_path, 'w') as f:
                    f.write(description)
                
                results.append(scenario)
                print(f"✓ Generated successfully: {json_path}")
            else:
                print(f"✗ Failed to generate valid scenario")
        
        print(f"\n✓ Generated {len(results)}/{len(descriptions)} scenarios")
        return results
    
    def interactive_mode(self):
        """Run interactive generation mode"""
        print("\n" + "="*60)
        print("CARLA Scenario Generator - Interactive Mode")
        print("="*60)
        print("Enter scenario descriptions (type 'quit' to exit)")
        print("Example: A red car ahead of ego stops suddenly")
        print("="*60)
        
        while True:
            print("\n> ", end="")
            description = input().strip()
            
            if description.lower() in ['quit', 'exit', 'q']:
                break
            
            if not description:
                continue
            
            scenario = self.generate_scenario(description, temperature=0.3)
            
            if scenario:
                print("\nGenerated Scenario:")
                print(json.dumps(scenario, indent=2))
                
                # Ask if user wants to save
                save = input("\nSave this scenario? (y/n): ").strip().lower()
                if save == 'y':
                    name = input("Enter scenario name (or press Enter for auto): ").strip()
                    if not name:
                        name = f"interactive_{scenario.get('scenario_name', 'unnamed')}"
                    
                    filename = f"{name}.json"
                    with open(filename, 'w') as f:
                        json.dump(scenario, f, indent=2)
                    print(f"✓ Saved to {filename}")
            else:
                print("Failed to generate valid scenario. Try a different description.")
    
    def benchmark_performance(self):
        """Run a performance benchmark"""
        print("\n" + "="*60)
        print("Performance Benchmark")
        print("="*60)
        
        test_descriptions = [
            "A car stops ahead of ego vehicle in heavy rain",
            "Two vehicles moving in adjacent lanes at different speeds during foggy night",
            "A pedestrian crosses the road when ego approaches on a sunny afternoon"
        ]
        
        times = []
        
        for i, desc in enumerate(test_descriptions, 1):
            print(f"\nBenchmark {i}/3: {desc}")
            scenario = self.generate_scenario(desc, benchmark=True, temperature=0.3)
            
            if scenario:
                print(f"  Generated weather: {scenario.get('weather', 'N/A')}")
        
        print("\n" + "="*60)
        print("Benchmark complete!")
        print("="*60)

def run_test_cases(generator: CarlaScenarioGenerator):
    """Run test cases to evaluate the model"""
    test_cases = [
        # Test weather extraction
        "A blue sedan is parked 20 meters ahead in heavy rain",
        "Night time scenario with dense fog and limited visibility",
        "Sunny afternoon highway merge scenario",
        "Wet road conditions with a truck ahead",
        
        # Original test cases
        "A vehicle ahead starts moving at 8 m/s when ego gets within 15 meters",
        "Two cars ahead: one moving slowly at 5 m/s, another overtaking at 15 m/s",
        "A vehicle cuts in from the adjacent lane when ego approaches",
    ]
    
    print("\n" + "="*60)
    print("Running Model Test Cases")
    print("="*60)
    
    results = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[Test {i}/{len(test_cases)}]")
        print(f"Description: {test_case}")
        
        scenario = generator.generate_scenario(test_case, temperature=0.3)
        
        if scenario:
            # Validate structure
            required_fields = ["scenario_name", "actors", "actions", "ego_spawn", "weather"]
            valid = all(field in scenario for field in required_fields)
            
            if valid:
                print(f"✓ Generated valid scenario (weather: {scenario.get('weather')})")
                results.append({"test": test_case, "status": "success", "scenario": scenario})
            else:
                print("✗ Missing required fields")
                results.append({"test": test_case, "status": "invalid", "scenario": scenario})
        else:
            print("✗ Failed to generate")
            results.append({"test": test_case, "status": "failed", "scenario": None})
    
    # Summary
    print("\n" + "="*60)
    print("Test Results Summary")
    print("="*60)
    success_count = sum(1 for r in results if r["status"] == "success")
    print(f"Success: {success_count}/{len(test_cases)}")
    print(f"Invalid: {sum(1 for r in results if r['status'] == 'invalid')}/{len(test_cases)}")
    print(f"Failed: {sum(1 for r in results if r['status'] == 'failed')}/{len(test_cases)}")
    
    # Save results
    with open("test_results.json", 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to test_results.json")

def main():
    parser = argparse.ArgumentParser(description="Generate CARLA scenarios using trained Llama model")
    parser.add_argument("--model-path", type=str, default="./exported_models/llama-carla-model-v5-improved/exported_model_adapters",
                       help="Path to trained model")
    parser.add_argument("--base-model", type=str, default=None,
                       help="Base model name (if not in adapter config)")
    parser.add_argument("--mode", type=str, choices=["interactive", "test", "batch", "benchmark"], 
                       default="interactive",
                       help="Generation mode")
    parser.add_argument("--input-file", type=str,
                       help="Input file with descriptions (one per line) for batch mode")
    parser.add_argument("--output-dir", type=str, default="generated_scenarios",
                       help="Output directory for batch generation")
    parser.add_argument("--merge-lora", action="store_true",
                       help="Merge LoRA weights for faster inference (incompatible with 4-bit)")
    parser.add_argument("--no-4bit", action="store_true",
                       help="Disable 4-bit quantization")
    parser.add_argument("--temperature", type=float, default=0.3,
                       help="Generation temperature")
    parser.add_argument("--max-tokens", type=int, default=1500,
                       help="Maximum tokens to generate")
    
    args = parser.parse_args()
    
    # Initialize generator
    generator = CarlaScenarioGenerator(
        model_path=args.model_path,
        base_model_name=args.base_model,
        use_4bit=not args.no_4bit,
        merge_lora=args.merge_lora and args.no_4bit  # Only merge if not using 4-bit
    )
    
    # Run based on mode
    if args.mode == "interactive":
        generator.interactive_mode()
    elif args.mode == "test":
        run_test_cases(generator)
    elif args.mode == "batch":
        if not args.input_file:
            print("Error: --input-file required for batch mode")
            return
        
        # Read descriptions
        with open(args.input_file, 'r') as f:
            descriptions = [line.strip() for line in f if line.strip()]
        
        print(f"Loaded {len(descriptions)} descriptions")
        generator.generate_batch(descriptions, args.output_dir)
    elif args.mode == "benchmark":
        generator.benchmark_performance()

if __name__ == "__main__":
    main()