#!/usr/bin/env python3
"""
CARLA Scenario Generation Pipeline
Complete pipeline: Natural Language → LLM → JSON → XOSC

This script provides a clean, modular pipeline for generating CARLA scenarios
from natural language descriptions using either base or fine-tuned LLM models.

Author: CARLA Scenario Team
Date: 2024
"""

import json
import argparse
import sys
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import xml.etree.ElementTree as ET

# Add project paths
sys.path.append('/home/user/Desktop/Rajiv')
sys.path.append('/home/user/Desktop/Rajiv/llm')

# Import components
from xosc_json import JsonToXoscConverter
from llm.inference_carla_model import CarlaScenarioGenerator
from llm.run_model_comparison import BaseModelGenerator


class CarlaScenarioPipeline:
    """
    Complete pipeline for CARLA scenario generation
    Handles: NL → LLM → JSON → XOSC conversion with validation
    """
    
    def __init__(self, model_type: str = "finetuned", output_dir: str = "pipeline_output"):
        """
        Initialize the pipeline with specified model
        
        Args:
            model_type: "finetuned" or "base" 
            output_dir: Directory to save outputs
        """
        self.model_type = model_type
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        self.json_dir = self.output_dir / "json"
        self.xosc_dir = self.output_dir / "xosc"
        self.logs_dir = self.output_dir / "logs"
        
        for dir_path in [self.json_dir, self.xosc_dir, self.logs_dir]:
            dir_path.mkdir(exist_ok=True)
        
        # Initialize components
        print(f"\n{'='*60}")
        print(f"Initializing CARLA Scenario Pipeline")
        print(f"Model Type: {model_type}")
        print(f"Output Directory: {output_dir}")
        print(f"{'='*60}\n")
        
        self._init_generator()
        self._init_converter()
        
        # Statistics
        self.stats = {
            "total_processed": 0,
            "json_success": 0,
            "xosc_success": 0,
            "failures": []
        }
    
    def _init_generator(self):
        """Initialize the LLM generator based on model type"""
        print(f"🔄 Loading {self.model_type} model...")
        
        if self.model_type == "finetuned":
            self.generator = CarlaScenarioGenerator(
                model_path="./llm/exported_models/llama-carla-model-v5-improved/exported_model_adapters",
                base_model_name="meta-llama/Llama-3.2-3B-Instruct",
                use_4bit=True,
                merge_lora=False
            )
        elif self.model_type == "base":
            self.generator = BaseModelGenerator("meta-llama/Llama-3.2-3B-Instruct")
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
        
        print(f"✅ {self.model_type.capitalize()} model loaded successfully\n")
    
    def _init_converter(self):
        """Initialize the JSON to XOSC converter"""
        print("🔄 Initializing XOSC converter...")
        self.converter = JsonToXoscConverter()
        print("✅ XOSC converter ready\n")
    
    def process_scenario(self, 
                        description: str, 
                        scenario_name: Optional[str] = None,
                        save_outputs: bool = True) -> Dict:
        """
        Process a single scenario through the complete pipeline
        
        Args:
            description: Natural language scenario description
            scenario_name: Optional name for the scenario (auto-generated if not provided)
            save_outputs: Whether to save JSON and XOSC files
            
        Returns:
            Dictionary with results and status for each stage
        """
        # Generate scenario name if not provided
        if scenario_name is None:
            scenario_name = f"scenario_{int(time.time())}"
        
        result = {
            "scenario_name": scenario_name,
            "description": description,
            "stages": {
                "llm_generation": {"status": "pending"},
                "json_validation": {"status": "pending"},
                "xosc_conversion": {"status": "pending"},
                "xosc_validation": {"status": "pending"}
            },
            "outputs": {},
            "errors": []
        }
        
        print(f"\n{'='*60}")
        print(f"Processing: {scenario_name}")
        print(f"Description: {description[:100]}...")
        print(f"{'='*60}")
        
        # Stage 1: LLM Generation
        print("\n📝 Stage 1: LLM Generation")
        start_time = time.time()
        
        try:
            json_output = self.generator.generate_scenario(description)
            generation_time = time.time() - start_time
            
            if json_output:
                result["stages"]["llm_generation"]["status"] = "success"
                result["stages"]["llm_generation"]["time"] = round(generation_time, 2)
                result["outputs"]["json"] = json_output
                print(f"   ✅ Generated JSON in {generation_time:.2f}s")
            else:
                raise ValueError("LLM failed to generate valid JSON")
                
        except Exception as e:
            result["stages"]["llm_generation"]["status"] = "failed"
            result["stages"]["llm_generation"]["error"] = str(e)
            result["errors"].append(f"LLM Generation: {str(e)}")
            print(f"   ❌ Generation failed: {str(e)}")
            return result
        
        # Stage 2: JSON Validation
        print("\n🔍 Stage 2: JSON Validation")
        
        try:
            # Validate JSON structure
            if isinstance(json_output, dict):
                json_data = json_output
            else:
                json_data = json.loads(json_output)
            
            # Check for required fields
            required_fields = ["scenario_name", "ego_vehicle_model", "ego_spawn"]
            missing_fields = [f for f in required_fields if f not in json_data]
            
            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")
            
            result["stages"]["json_validation"]["status"] = "success"
            result["stages"]["json_validation"]["fields_present"] = list(json_data.keys())
            print(f"   ✅ JSON structure valid")
            
            # Save JSON if requested
            if save_outputs:
                json_path = self.json_dir / f"{scenario_name}.json"
                with open(json_path, 'w') as f:
                    json.dump(json_data, f, indent=2)
                result["outputs"]["json_path"] = str(json_path)
                print(f"   💾 Saved: {json_path}")
                
        except Exception as e:
            result["stages"]["json_validation"]["status"] = "failed"
            result["stages"]["json_validation"]["error"] = str(e)
            result["errors"].append(f"JSON Validation: {str(e)}")
            print(f"   ❌ Validation failed: {str(e)}")
            return result
        
        # Stage 3: XOSC Conversion
        print("\n🔄 Stage 3: XOSC Conversion")
        
        try:
            xosc_output = self.converter.convert(json_data)
            result["stages"]["xosc_conversion"]["status"] = "success"
            result["outputs"]["xosc"] = xosc_output
            print(f"   ✅ Converted to XOSC format")
            
            # Save XOSC if requested
            if save_outputs:
                xosc_path = self.xosc_dir / f"{scenario_name}.xosc"
                with open(xosc_path, 'w') as f:
                    f.write(xosc_output)
                result["outputs"]["xosc_path"] = str(xosc_path)
                print(f"   💾 Saved: {xosc_path}")
                
        except Exception as e:
            result["stages"]["xosc_conversion"]["status"] = "failed"
            result["stages"]["xosc_conversion"]["error"] = str(e)
            result["errors"].append(f"XOSC Conversion: {str(e)}")
            print(f"   ❌ Conversion failed: {str(e)}")
            return result
        
        # Stage 4: XOSC Validation
        print("\n✅ Stage 4: XOSC Validation")
        
        try:
            # Parse as XML
            root = ET.fromstring(xosc_output)
            
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
            
            if missing_elements:
                raise ValueError(f"Missing XOSC elements: {missing_elements}")
            
            result["stages"]["xosc_validation"]["status"] = "success"
            result["stages"]["xosc_validation"]["valid_xml"] = True
            result["stages"]["xosc_validation"]["has_required_elements"] = True
            print(f"   ✅ XOSC structure valid")
            
        except Exception as e:
            result["stages"]["xosc_validation"]["status"] = "failed"
            result["stages"]["xosc_validation"]["error"] = str(e)
            result["errors"].append(f"XOSC Validation: {str(e)}")
            print(f"   ❌ Validation failed: {str(e)}")
        
        # Update statistics
        self.stats["total_processed"] += 1
        if result["stages"]["json_validation"]["status"] == "success":
            self.stats["json_success"] += 1
        if result["stages"]["xosc_validation"]["status"] == "success":
            self.stats["xosc_success"] += 1
        if result["errors"]:
            self.stats["failures"].append(scenario_name)
        
        # Overall success
        success = all(stage["status"] == "success" for stage in result["stages"].values())
        result["success"] = success
        
        if success:
            print(f"\n🎉 Pipeline completed successfully!")
        else:
            print(f"\n⚠️ Pipeline completed with errors")
        
        return result
    
    def process_batch(self, scenarios: List[Dict]) -> List[Dict]:
        """
        Process multiple scenarios in batch
        
        Args:
            scenarios: List of dictionaries with 'description' and optional 'name' keys
            
        Returns:
            List of results for each scenario
        """
        results = []
        total = len(scenarios)
        
        print(f"\n{'='*60}")
        print(f"Batch Processing: {total} scenarios")
        print(f"{'='*60}")
        
        for i, scenario in enumerate(scenarios, 1):
            print(f"\n[{i}/{total}] Processing scenario...")
            
            description = scenario.get("description", scenario.get("prompt", ""))
            name = scenario.get("name", scenario.get("id", f"batch_{i}"))
            
            result = self.process_scenario(description, name)
            results.append(result)
            
            # Save checkpoint every 5 scenarios
            if i % 5 == 0:
                self._save_batch_checkpoint(results)
        
        # Save final results
        self._save_batch_results(results)
        self._print_statistics()
        
        return results
    
    def _save_batch_checkpoint(self, results: List[Dict]):
        """Save intermediate results during batch processing"""
        checkpoint_path = self.logs_dir / f"checkpoint_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(checkpoint_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Checkpoint saved: {checkpoint_path}")
    
    def _save_batch_results(self, results: List[Dict]):
        """Save final batch processing results"""
        results_path = self.logs_dir / f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "model_type": self.model_type,
            "statistics": self.stats,
            "results": results
        }
        
        with open(results_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n💾 Results saved: {results_path}")
    
    def _print_statistics(self):
        """Print processing statistics"""
        print(f"\n{'='*60}")
        print(f"Pipeline Statistics")
        print(f"{'='*60}")
        print(f"Total Processed: {self.stats['total_processed']}")
        print(f"JSON Success: {self.stats['json_success']} ({self.stats['json_success']/max(1, self.stats['total_processed'])*100:.1f}%)")
        print(f"XOSC Success: {self.stats['xosc_success']} ({self.stats['xosc_success']/max(1, self.stats['total_processed'])*100:.1f}%)")
        
        if self.stats['failures']:
            print(f"Failed Scenarios: {len(self.stats['failures'])}")
            for name in self.stats['failures'][:5]:
                print(f"  - {name}")
            if len(self.stats['failures']) > 5:
                print(f"  ... and {len(self.stats['failures']) - 5} more")


def main():
    """Main function with CLI interface"""
    parser = argparse.ArgumentParser(
        description="CARLA Scenario Generation Pipeline: NL → LLM → JSON → XOSC"
    )
    
    parser.add_argument(
        "--model",
        type=str,
        choices=["finetuned", "base"],
        default="finetuned",
        help="Model to use for generation (default: finetuned)"
    )
    
    parser.add_argument(
        "--mode",
        type=str,
        choices=["interactive", "single", "batch", "test"],
        default="interactive",
        help="Operation mode (default: interactive)"
    )
    
    parser.add_argument(
        "--description",
        type=str,
        help="Scenario description for single mode"
    )
    
    parser.add_argument(
        "--batch-file",
        type=str,
        help="JSON file with batch scenarios"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default="pipeline_output",
        help="Output directory (default: pipeline_output)"
    )
    
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save output files"
    )
    
    args = parser.parse_args()
    
    # Initialize pipeline
    pipeline = CarlaScenarioPipeline(
        model_type=args.model,
        output_dir=args.output_dir
    )
    
    # Handle different modes
    if args.mode == "interactive":
        print("\n🎮 Interactive Mode")
        print("Enter scenario descriptions (type 'quit' to exit)\n")
        
        while True:
            description = input("\n📝 Scenario description: ").strip()
            
            if description.lower() in ['quit', 'exit', 'q']:
                break
            
            if not description:
                print("Please enter a description")
                continue
            
            result = pipeline.process_scenario(
                description,
                save_outputs=not args.no_save
            )
            
            if result["success"]:
                print(f"\n✅ Success! Files saved to {pipeline.output_dir}")
            else:
                print(f"\n❌ Errors encountered: {result['errors']}")
    
    elif args.mode == "single":
        if not args.description:
            print("Error: --description required for single mode")
            sys.exit(1)
        
        result = pipeline.process_scenario(
            args.description,
            save_outputs=not args.no_save
        )
        
        # Print result summary
        print(f"\n{'='*60}")
        print("Result Summary")
        print(f"{'='*60}")
        print(json.dumps(result, indent=2))
    
    elif args.mode == "batch":
        if not args.batch_file:
            print("Error: --batch-file required for batch mode")
            sys.exit(1)
        
        # Load batch file
        with open(args.batch_file, 'r') as f:
            data = json.load(f)
        
        # Extract scenarios (handle different formats)
        if "test_scenarios" in data:
            scenarios = data["test_scenarios"]
        elif isinstance(data, list):
            scenarios = data
        else:
            scenarios = [data]
        
        results = pipeline.process_batch(scenarios)
        
        print(f"\n✅ Batch processing complete!")
        print(f"📊 Success rate: {pipeline.stats['xosc_success']}/{len(scenarios)}")
    
    elif args.mode == "test":
        # Test with sample scenarios
        test_scenarios = [
            {
                "id": "test_simple",
                "description": "A red car stops at a traffic light"
            },
            {
                "id": "test_medium",
                "description": "Heavy rain reduces visibility while following a vehicle"
            },
            {
                "id": "test_complex",
                "description": "At a roundabout, multiple vehicles enter while a cyclist navigates"
            }
        ]
        
        print("\n🧪 Test Mode - Running sample scenarios")
        results = pipeline.process_batch(test_scenarios)
        
        print(f"\n✅ Test complete!")
        print(f"📊 Success rate: {pipeline.stats['xosc_success']}/{len(test_scenarios)}")
    
    # Final statistics
    pipeline._print_statistics()
    print(f"\n👋 Pipeline complete! Outputs saved to: {pipeline.output_dir}")


if __name__ == "__main__":
    main()