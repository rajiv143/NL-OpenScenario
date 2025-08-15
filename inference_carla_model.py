#!/usr/bin/env python3
"""
Inference script for trained Llama CARLA scenario model
Supports both interactive and batch generation
"""

import json
import torch
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
                 use_4bit: bool = True):
        """
        Initialize the generator with trained model
        
        Args:
            model_path: Path to the trained LoRA model
            base_model_name: Base model name if not stored in adapter config
            use_4bit: Whether to load in 4-bit for inference
        """
        self.model_path = Path(model_path)
        self.use_4bit = use_4bit
        
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
            base_model_name = "meta-llama/Llama-3.2-1B-Instruct"
            print(f"Warning: Base model not specified, using default: {base_model_name}")
        
        self.base_model_name = base_model_name
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")
        
        # Load model and tokenizer
        self._load_model()
    
    def _load_model(self):
        """Load the trained model and tokenizer"""
        print(f"Loading model from {self.model_path}")
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_path,
            trust_remote_code=True,
            padding_side="left"
        )
        
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
        
        # Setup quantization config if using 4-bit
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
        
        # Set to evaluation mode
        self.model.eval()
        print("✓ Model loaded successfully")
    
    def format_prompt(self, description: str, instruction: Optional[str] = None) -> str:
        """Format the input prompt for generation"""
        if instruction is None:
            instruction = "Generate a CARLA scenario JSON based on this description:"
        
        # Check model format
        if "3.2" in self.base_model_name or "3.1" in self.base_model_name:
            # Llama 3.x format
            prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are an expert CARLA simulator scenario designer. Generate valid JSON scenarios based on natural language descriptions. The JSON should follow the exact CARLA scenario format with proper structure for actors, actions, spawn criteria, and triggers.<|eot_id|><|start_header_id|>user<|end_header_id|>

{instruction}

{description}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""
        else:
            # Llama 2 format
            prompt = f"""[INST] <<SYS>>
You are an expert CARLA simulator scenario designer. Generate valid JSON scenarios based on natural language descriptions.
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
                         do_sample: bool = True) -> Dict:
        """
        Generate a CARLA scenario from natural language description
        
        Args:
            description: Natural language description of the scenario
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            do_sample: Whether to use sampling
        
        Returns:
            Generated scenario as dictionary
        """
        # Format prompt
        prompt = self.format_prompt(description)
        
        # Tokenize
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        
        # Generate
        print("Generating scenario...")
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=do_sample,
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id
            )
        
        # Decode
        generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Extract JSON from response
        json_text = self._extract_json(generated_text, len(prompt))
        
        # Parse JSON
        try:
            scenario = json.loads(json_text)
            return scenario
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            print("Generated text:")
            print(json_text)
            return None
    
    def _extract_json(self, text: str, prompt_length: int) -> str:
        """Extract JSON from generated text"""
        # Remove the prompt part
        response = text[prompt_length:].strip()
        
        # Try to find JSON block
        # Look for opening and closing braces
        start_idx = response.find('{')
        if start_idx == -1:
            return response
        
        # Find matching closing brace
        brace_count = 0
        end_idx = -1
        for i in range(start_idx, len(response)):
            if response[i] == '{':
                brace_count += 1
            elif response[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        
        if end_idx != -1:
            return response[start_idx:end_idx]
        
        return response
    
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
            
            scenario = self.generate_scenario(description)
            
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

def run_test_cases(generator: CarlaScenarioGenerator):
    """Run test cases to evaluate the model"""
    test_cases = [
        # Level 1 - Static
        "A blue sedan is parked 20 meters ahead of the ego vehicle",
        "A truck is stationary behind the ego at far distance",
        
        # Level 2 - Moving
        "A vehicle ahead starts moving at 8 m/s when ego gets within 15 meters",
        "A car behind ego accelerates to 15 m/s when ego approaches",
        
        # Level 3 - Speed changes
        "A vehicle ahead speeds up from 5 to 12 m/s",
        "A car slows down from 15 m/s to 5 m/s gradually",
        
        # Level 4 - Stop and start
        "A vehicle moves at 10 m/s, stops for 3 seconds, then continues at 8 m/s",
        "A car ahead brakes to a stop, waits briefly, then resumes",
        
        # Level 5 - Multi actors
        "Two cars ahead: one moving slowly at 5 m/s, another overtaking at 15 m/s",
        "Three vehicles: one ahead static, one behind moving, one in adjacent lane",
        
        # Level 6 - Interactions
        "A vehicle cuts in from the adjacent lane when ego approaches",
        "Two vehicles ahead maintain safe following distance while decelerating"
    ]
    
    print("\n" + "="*60)
    print("Running Model Test Cases")
    print("="*60)
    
    results = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[Test {i}/{len(test_cases)}]")
        print(f"Description: {test_case}")
        
        scenario = generator.generate_scenario(test_case, temperature=0.5)
        
        if scenario:
            # Validate structure
            required_fields = ["scenario_name", "actors", "actions", "ego_spawn"]
            valid = all(field in scenario for field in required_fields)
            
            if valid:
                print("✓ Generated valid scenario")
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
    parser.add_argument("--model-path", type=str, default="./llama-carla-model/final_model",
                       help="Path to trained model")
    parser.add_argument("--base-model", type=str, default=None,
                       help="Base model name (if not in adapter config)")
    parser.add_argument("--mode", type=str, choices=["interactive", "test", "batch"], 
                       default="interactive",
                       help="Generation mode")
    parser.add_argument("--input-file", type=str,
                       help="Input file with descriptions (one per line) for batch mode")
    parser.add_argument("--output-dir", type=str, default="generated_scenarios",
                       help="Output directory for batch generation")
    parser.add_argument("--no-4bit", action="store_true",
                       help="Disable 4-bit quantization")
    parser.add_argument("--temperature", type=float, default=0.7,
                       help="Generation temperature")
    parser.add_argument("--max-tokens", type=int, default=1500,
                       help="Maximum tokens to generate")
    
    args = parser.parse_args()
    
    # Initialize generator
    generator = CarlaScenarioGenerator(
        model_path=args.model_path,
        base_model_name=args.base_model,
        use_4bit=not args.no_4bit
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

if __name__ == "__main__":
    main()