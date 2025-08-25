#!/usr/bin/env python3
"""
End-to-End XOSC Generation Evaluation
Tests models' ability to generate executable CARLA scenarios
"""

import json
import time
import sys
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# Add paths
sys.path.append('/home/user/Desktop/Rajiv')
sys.path.append('/home/user/Desktop/Rajiv/llm')

from xosc_json import JsonToXoscConverter
from inference_carla_model import CarlaScenarioGenerator

class XOSCEvaluator:
    """Evaluates model outputs through the full pipeline to XOSC"""
    
    def __init__(self):
        self.converter = JsonToXoscConverter()
        self.results = []
        
    def evaluate_json_to_xosc(self, json_output: str, scenario_id: str) -> Dict:
        """
        Evaluate a JSON output through the full pipeline
        Returns evaluation metrics at each stage
        """
        evaluation = {
            "scenario_id": scenario_id,
            "json_valid": False,
            "json_has_required_fields": False,
            "xosc_conversion_success": False,
            "xosc_valid_xml": False,
            "xosc_has_required_elements": False,
            "errors": []
        }
        
        # Stage 1: JSON Validation
        try:
            if isinstance(json_output, str):
                json_data = json.loads(json_output)
            else:
                json_data = json_output
            evaluation["json_valid"] = True
            
            # Check required fields (based on your converter expectations)
            required_fields = ["scenario_name", "ego_vehicle_model", "ego_spawn"]
            missing_fields = [f for f in required_fields if f not in json_data]
            
            if not missing_fields:
                evaluation["json_has_required_fields"] = True
            else:
                evaluation["errors"].append(f"Missing JSON fields: {missing_fields}")
                
        except json.JSONDecodeError as e:
            evaluation["errors"].append(f"JSON parse error: {str(e)}")
            return evaluation
        except Exception as e:
            evaluation["errors"].append(f"JSON validation error: {str(e)}")
            return evaluation
        
        # Stage 2: XOSC Conversion
        try:
            xosc_output = self.converter.convert(json_data)
            evaluation["xosc_conversion_success"] = True
            
            # Save XOSC for inspection
            output_path = f"evaluation_output/{scenario_id}.xosc"
            os.makedirs("evaluation_output", exist_ok=True)
            
            with open(output_path, 'w') as f:
                f.write(xosc_output)
                
        except Exception as e:
            evaluation["errors"].append(f"XOSC conversion error: {str(e)}")
            return evaluation
        
        # Stage 3: XOSC XML Validation
        try:
            root = ET.fromstring(xosc_output)
            evaluation["xosc_valid_xml"] = True
            
            # Check for required XOSC elements
            required_elements = [
                ".//Entities",
                ".//Storyboard",
                ".//Init",
                ".//Story"
            ]
            
            missing_elements = []
            for element_path in required_elements:
                if root.find(element_path) is None:
                    missing_elements.append(element_path)
            
            if not missing_elements:
                evaluation["xosc_has_required_elements"] = True
            else:
                evaluation["errors"].append(f"Missing XOSC elements: {missing_elements}")
                
        except ET.ParseError as e:
            evaluation["errors"].append(f"XOSC XML parse error: {str(e)}")
        except Exception as e:
            evaluation["errors"].append(f"XOSC validation error: {str(e)}")
        
        return evaluation
    
    def calculate_success_rate(self, evaluations: List[Dict]) -> Dict:
        """Calculate success rates at each stage"""
        total = len(evaluations)
        if total == 0:
            return {}
        
        metrics = {
            "total_scenarios": total,
            "json_valid": sum(1 for e in evaluations if e["json_valid"]),
            "json_complete": sum(1 for e in evaluations if e["json_has_required_fields"]),
            "xosc_converted": sum(1 for e in evaluations if e["xosc_conversion_success"]),
            "xosc_valid": sum(1 for e in evaluations if e["xosc_valid_xml"]),
            "xosc_complete": sum(1 for e in evaluations if e["xosc_has_required_elements"]),
            "fully_successful": sum(1 for e in evaluations if all([
                e["json_valid"],
                e["json_has_required_fields"],
                e["xosc_conversion_success"],
                e["xosc_valid_xml"],
                e["xosc_has_required_elements"]
            ]))
        }
        
        # Calculate percentages
        metrics["success_rates"] = {
            "json_valid": f"{metrics['json_valid']/total*100:.1f}%",
            "json_complete": f"{metrics['json_complete']/total*100:.1f}%",
            "xosc_converted": f"{metrics['xosc_converted']/total*100:.1f}%",
            "xosc_valid": f"{metrics['xosc_valid']/total*100:.1f}%",
            "xosc_complete": f"{metrics['xosc_complete']/total*100:.1f}%",
            "end_to_end": f"{metrics['fully_successful']/total*100:.1f}%"
        }
        
        return metrics

def test_base_model_direct_xosc(scenarios: List[Dict]) -> List[Dict]:
    """
    Test base model with direct XOSC generation prompt
    This tests if the base model knows XOSC format natively
    """
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import torch
    
    print("\n" + "="*60)
    print("Testing BASE Model - Direct XOSC Generation")
    print("="*60)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model_name = "meta-llama/Llama-3.2-3B-Instruct"
    
    # Load model
    tokenizer = AutoTokenizer.from_pretrained(model_name, padding_side="left")
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16 if device.type == "cuda" else torch.float32,
        device_map="auto",
        low_cpu_mem_usage=True
    )
    model.eval()
    
    results = []
    evaluator = XOSCEvaluator()
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n[{i}/{len(scenarios)}] {scenario['id']}")
        
        # Try direct XOSC generation
        xosc_prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are an expert at generating OpenSCENARIO (XOSC) files for CARLA simulator. Generate valid XOSC XML format.<|eot_id|><|start_header_id|>user<|end_header_id|>

Generate an OpenSCENARIO file for: {scenario['prompt']}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

<?xml version="1.0" encoding="UTF-8"?>
<OpenSCENARIO>"""
        
        inputs = tokenizer(xosc_prompt, return_tensors="pt", truncation=True, max_length=512)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=1500,
                temperature=0.7,
                do_sample=True,
                pad_token_id=tokenizer.pad_token_id
            )
        
        output_text = tokenizer.decode(outputs[0], skip_special_tokens=False)
        
        # Extract XOSC
        if "<?xml" in output_text:
            xosc_start = output_text.find("<?xml")
            xosc_text = output_text[xosc_start:]
            if "</OpenSCENARIO>" in xosc_text:
                xosc_end = xosc_text.find("</OpenSCENARIO>") + len("</OpenSCENARIO>")
                xosc_text = xosc_text[:xosc_end]
        else:
            xosc_text = ""
        
        # Try to validate as XOSC directly
        try:
            if xosc_text:
                root = ET.fromstring(xosc_text)
                xosc_valid = True
            else:
                xosc_valid = False
        except:
            xosc_valid = False
        
        results.append({
            "scenario_id": scenario['id'],
            "direct_xosc_valid": xosc_valid,
            "output_preview": xosc_text[:500] if xosc_text else "No valid XOSC generated"
        })
        
        print(f"  Direct XOSC: {'✓' if xosc_valid else '✗'}")
    
    # Clean up
    del model
    torch.cuda.empty_cache()
    
    return results

def test_models_json_to_xosc(scenarios: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Test both models through JSON → XOSC pipeline
    """
    evaluator = XOSCEvaluator()
    
    # Test base model with JSON generation
    print("\n" + "="*60)
    print("BASE Model - JSON → XOSC Pipeline")
    print("="*60)
    
    from run_model_comparison import BaseModelGenerator
    
    base_generator = BaseModelGenerator("meta-llama/Llama-3.2-3B-Instruct")
    base_evaluations = []
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n[{i}/{len(scenarios)}] {scenario['id']}")
        
        # Generate JSON
        json_output = base_generator.generate_scenario(scenario['prompt'])
        
        # Evaluate through pipeline
        if json_output:
            evaluation = evaluator.evaluate_json_to_xosc(json_output, f"base_{scenario['id']}")
        else:
            evaluation = {
                "scenario_id": f"base_{scenario['id']}",
                "json_valid": False,
                "errors": ["Failed to generate JSON"]
            }
        
        base_evaluations.append(evaluation)
        print(f"  Pipeline: JSON {'✓' if evaluation['json_valid'] else '✗'} → "
              f"XOSC {'✓' if evaluation.get('xosc_conversion_success', False) else '✗'}")
    
    # Clean up
    del base_generator
    import torch
    torch.cuda.empty_cache()
    
    # Test fine-tuned model
    print("\n" + "="*60)
    print("FINE-TUNED Model - JSON → XOSC Pipeline")
    print("="*60)
    
    finetuned_generator = CarlaScenarioGenerator(
        model_path="/home/user/Desktop/Rajiv/llm/models/llama-carla-model-v5-improved/final_model",
        use_4bit=True
    )
    
    finetuned_evaluations = []
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n[{i}/{len(scenarios)}] {scenario['id']}")
        
        # Generate JSON
        json_output = finetuned_generator.generate_scenario(scenario['prompt'])
        
        # Evaluate through pipeline
        if json_output:
            evaluation = evaluator.evaluate_json_to_xosc(json_output, f"finetuned_{scenario['id']}")
        else:
            evaluation = {
                "scenario_id": f"finetuned_{scenario['id']}",
                "json_valid": False,
                "errors": ["Failed to generate JSON"]
            }
        
        finetuned_evaluations.append(evaluation)
        print(f"  Pipeline: JSON {'✓' if evaluation['json_valid'] else '✗'} → "
              f"XOSC {'✓' if evaluation.get('xosc_conversion_success', False) else '✗'}")
    
    return base_evaluations, finetuned_evaluations

def main():
    print("="*60)
    print("END-TO-END XOSC GENERATION EVALUATION")
    print("="*60)
    
    # Load test scenarios
    with open('/home/user/Desktop/Rajiv/expanded_test_scenarios.json', 'r') as f:
        data = json.load(f)
    scenarios = data['test_scenarios']
    
    # Option to test subset
    test_all = input("\nTest all scenarios? (y/n) [n]: ").strip().lower() == 'y'
    if not test_all:
        num = int(input("Number to test [5]: ").strip() or "5")
        scenarios = scenarios[:num]
    
    print(f"\nTesting {len(scenarios)} scenarios")
    
    # Test 1: Can base model generate XOSC directly?
    print("\n" + "="*40)
    print("TEST 1: Direct XOSC Generation")
    print("="*40)
    direct_results = test_base_model_direct_xosc(scenarios[:3])  # Quick test
    
    direct_success = sum(1 for r in direct_results if r.get('direct_xosc_valid', False))
    print(f"\nDirect XOSC Success: {direct_success}/{len(direct_results)}")
    
    # Test 2: JSON → XOSC Pipeline
    print("\n" + "="*40)
    print("TEST 2: JSON → XOSC Pipeline")
    print("="*40)
    
    base_evals, finetuned_evals = test_models_json_to_xosc(scenarios)
    
    # Calculate metrics
    evaluator = XOSCEvaluator()
    base_metrics = evaluator.calculate_success_rate(base_evals)
    finetuned_metrics = evaluator.calculate_success_rate(finetuned_evals)
    
    # Print comparison
    print("\n" + "="*60)
    print("FINAL COMPARISON")
    print("="*60)
    
    print("\n📊 End-to-End Success Rates:")
    print(f"Base Model:      {base_metrics['success_rates']['end_to_end']}")
    print(f"Fine-tuned:      {finetuned_metrics['success_rates']['end_to_end']}")
    
    print("\n📈 Pipeline Stage Success:")
    print(f"{'Stage':<20} {'Base':<15} {'Fine-tuned':<15}")
    print("-"*50)
    print(f"{'JSON Valid':<20} {base_metrics['success_rates']['json_valid']:<15} {finetuned_metrics['success_rates']['json_valid']:<15}")
    print(f"{'JSON Complete':<20} {base_metrics['success_rates']['json_complete']:<15} {finetuned_metrics['success_rates']['json_complete']:<15}")
    print(f"{'XOSC Converted':<20} {base_metrics['success_rates']['xosc_converted']:<15} {finetuned_metrics['success_rates']['xosc_converted']:<15}")
    print(f"{'XOSC Valid':<20} {base_metrics['success_rates']['xosc_valid']:<15} {finetuned_metrics['success_rates']['xosc_valid']:<15}")
    print(f"{'XOSC Complete':<20} {base_metrics['success_rates']['xosc_complete']:<15} {finetuned_metrics['success_rates']['xosc_complete']:<15}")
    
    # Save detailed results
    results = {
        "timestamp": datetime.now().isoformat(),
        "scenarios_tested": len(scenarios),
        "direct_xosc_test": direct_results,
        "base_model_pipeline": base_evals,
        "finetuned_model_pipeline": finetuned_evals,
        "metrics": {
            "base_model": base_metrics,
            "finetuned_model": finetuned_metrics
        }
    }
    
    with open('xosc_evaluation_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n✅ Results saved to xosc_evaluation_results.json")
    print("✅ XOSC files saved in evaluation_output/")
    
    print("\n" + "="*60)
    print("EVALUATION COMPLETE")
    print("="*60)

if __name__ == "__main__":
    main()