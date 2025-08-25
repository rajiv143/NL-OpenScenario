#!/usr/bin/env python3
"""
Salvage and analyze the evaluation results from the crashed run
"""

import json
import os
from pathlib import Path
from datetime import datetime

def analyze_console_output():
    """Parse the console output you provided to extract results"""
    
    # Direct XOSC test results (first 3 scenarios)
    direct_xosc_results = [
        {"scenario_id": "test_001", "direct_xosc_valid": False},
        {"scenario_id": "test_002", "direct_xosc_valid": True},
        {"scenario_id": "test_003", "direct_xosc_valid": True}
    ]
    
    # Base model JSON->XOSC results (all 25)
    base_model_results = [
        {"scenario_id": "test_001", "json_valid": False, "xosc_converted": False},
        {"scenario_id": "test_002", "json_valid": False, "xosc_converted": False},
        {"scenario_id": "test_003", "json_valid": True, "xosc_converted": False},
        {"scenario_id": "test_004", "json_valid": False, "xosc_converted": False},
        {"scenario_id": "test_005", "json_valid": True, "xosc_converted": False},
        {"scenario_id": "test_006", "json_valid": False, "xosc_converted": False},
        {"scenario_id": "test_007", "json_valid": True, "xosc_converted": False},
        {"scenario_id": "test_008", "json_valid": True, "xosc_converted": False},
        {"scenario_id": "test_009", "json_valid": False, "xosc_converted": False},
        {"scenario_id": "test_010", "json_valid": True, "xosc_converted": False},
        {"scenario_id": "test_011", "json_valid": True, "xosc_converted": False},
        {"scenario_id": "test_012", "json_valid": True, "xosc_converted": False},
        {"scenario_id": "test_013", "json_valid": True, "xosc_converted": False},
        {"scenario_id": "test_014", "json_valid": True, "xosc_converted": False},
        {"scenario_id": "test_015", "json_valid": True, "xosc_converted": False},
        {"scenario_id": "test_016", "json_valid": True, "xosc_converted": False},
        {"scenario_id": "test_017", "json_valid": True, "xosc_converted": False},
        {"scenario_id": "test_018", "json_valid": False, "xosc_converted": False},
        {"scenario_id": "test_019", "json_valid": True, "xosc_converted": False},
        {"scenario_id": "test_020", "json_valid": True, "xosc_converted": False},
        {"scenario_id": "test_021", "json_valid": True, "xosc_converted": False},
        {"scenario_id": "test_022", "json_valid": True, "xosc_converted": False},
        {"scenario_id": "test_023", "json_valid": True, "xosc_converted": False},
        {"scenario_id": "test_024", "json_valid": True, "xosc_converted": False},
        {"scenario_id": "test_025", "json_valid": False, "xosc_converted": False}
    ]
    
    # Fine-tuned model results (all 25)
    finetuned_results = [
        {"scenario_id": "test_001", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_002", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_003", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_004", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_005", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_006", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_007", "json_valid": True, "xosc_converted": False, "note": "No spawn points found"},
        {"scenario_id": "test_008", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_009", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_010", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_011", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_012", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_013", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_014", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_015", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_016", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_017", "json_valid": True, "xosc_converted": False, "note": "XOSC conversion failed"},
        {"scenario_id": "test_018", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_019", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_020", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_021", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_022", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_023", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_024", "json_valid": True, "xosc_converted": True},
        {"scenario_id": "test_025", "json_valid": True, "xosc_converted": True}
    ]
    
    return direct_xosc_results, base_model_results, finetuned_results

def check_generated_xosc_files():
    """Check what XOSC files were actually generated"""
    output_dir = Path("evaluation_output")
    xosc_files = []
    
    if output_dir.exists():
        for xosc_file in output_dir.glob("*.xosc"):
            xosc_files.append(xosc_file.name)
    
    return sorted(xosc_files)

def calculate_metrics(results, model_name):
    """Calculate success metrics for a model"""
    total = len(results)
    json_valid = sum(1 for r in results if r.get('json_valid', False))
    xosc_converted = sum(1 for r in results if r.get('xosc_converted', False))
    
    return {
        "model": model_name,
        "total_scenarios": total,
        "json_valid": json_valid,
        "json_valid_rate": f"{json_valid/total*100:.1f}%",
        "xosc_converted": xosc_converted,
        "xosc_conversion_rate": f"{xosc_converted/total*100:.1f}%",
        "end_to_end_success": xosc_converted,
        "end_to_end_rate": f"{xosc_converted/total*100:.1f}%"
    }

def main():
    print("="*60)
    print("SALVAGING EVALUATION RESULTS")
    print("="*60)
    
    # Parse console output
    direct_xosc, base_results, finetuned_results = analyze_console_output()
    
    # Check actual XOSC files
    xosc_files = check_generated_xosc_files()
    
    print(f"\n📁 Found {len(xosc_files)} XOSC files in evaluation_output/")
    if xosc_files:
        print("Files generated:")
        for f in xosc_files[:10]:  # Show first 10
            print(f"  - {f}")
        if len(xosc_files) > 10:
            print(f"  ... and {len(xosc_files)-10} more")
    
    # Calculate metrics
    base_metrics = calculate_metrics(base_results, "Base Model")
    finetuned_metrics = calculate_metrics(finetuned_results, "Fine-tuned v5")
    
    # Direct XOSC test metrics
    direct_success = sum(1 for r in direct_xosc if r['direct_xosc_valid'])
    direct_metrics = {
        "test": "Direct XOSC Generation",
        "scenarios_tested": len(direct_xosc),
        "successful": direct_success,
        "success_rate": f"{direct_success/len(direct_xosc)*100:.1f}%"
    }
    
    # Print results
    print("\n" + "="*60)
    print("RECOVERED RESULTS")
    print("="*60)
    
    print("\n🔍 Test 1: Direct XOSC Generation (Base Model)")
    print(f"  Tested: {direct_metrics['scenarios_tested']} scenarios")
    print(f"  Success: {direct_metrics['successful']}/{direct_metrics['scenarios_tested']} ({direct_metrics['success_rate']})")
    print("  → Base model CAN generate XOSC directly (2/3 success)")
    
    print("\n📊 Test 2: JSON → XOSC Pipeline Comparison")
    print("-"*40)
    
    print(f"\nBase Model:")
    print(f"  JSON Valid:      {base_metrics['json_valid']}/{base_metrics['total_scenarios']} ({base_metrics['json_valid_rate']})")
    print(f"  XOSC Converted:  {base_metrics['xosc_converted']}/{base_metrics['total_scenarios']} ({base_metrics['xosc_conversion_rate']})")
    print(f"  End-to-End:      {base_metrics['end_to_end_success']}/{base_metrics['total_scenarios']} ({base_metrics['end_to_end_rate']})")
    
    print(f"\nFine-tuned Model v5:")
    print(f"  JSON Valid:      {finetuned_metrics['json_valid']}/{finetuned_metrics['total_scenarios']} ({finetuned_metrics['json_valid_rate']})")
    print(f"  XOSC Converted:  {finetuned_metrics['xosc_converted']}/{finetuned_metrics['total_scenarios']} ({finetuned_metrics['xosc_conversion_rate']})")
    print(f"  End-to-End:      {finetuned_metrics['end_to_end_success']}/{finetuned_metrics['total_scenarios']} ({finetuned_metrics['end_to_end_rate']})")
    
    print("\n" + "="*60)
    print("KEY FINDINGS")
    print("="*60)
    
    print("\n✅ MAJOR SUCCESS:")
    print(f"  • Fine-tuned model: {finetuned_metrics['end_to_end_rate']} end-to-end success")
    print(f"  • Base model: {base_metrics['end_to_end_rate']} end-to-end success")
    print(f"  • Improvement: {finetuned_metrics['xosc_converted']}/{finetuned_metrics['total_scenarios']} vs {base_metrics['xosc_converted']}/{base_metrics['total_scenarios']}")
    
    print("\n📈 JSON Generation:")
    print(f"  • Base model struggles with JSON format ({base_metrics['json_valid_rate']} valid)")
    print(f"  • Fine-tuned excels at JSON ({finetuned_metrics['json_valid_rate']} valid)")
    
    print("\n🔄 XOSC Conversion:")
    print(f"  • Base model: 0% of valid JSONs convert to XOSC")
    print(f"  • Fine-tuned: 92% of valid JSONs convert to XOSC (23/25)")
    
    print("\n💡 Insights:")
    print("  • Base model CAN generate XOSC directly (67% success on 3 tests)")
    print("  • Base model's JSON doesn't match converter's requirements")
    print("  • Fine-tuning teaches both JSON structure AND CARLA semantics")
    print("  • 2 fine-tuned failures: spawn point issues (test_007, test_017)")
    
    # Save recovered results
    recovered_data = {
        "timestamp": datetime.now().isoformat(),
        "direct_xosc_test": {
            "results": direct_xosc,
            "metrics": direct_metrics
        },
        "json_to_xosc_pipeline": {
            "base_model": {
                "results": base_results,
                "metrics": base_metrics
            },
            "finetuned_model": {
                "results": finetuned_results,
                "metrics": finetuned_metrics
            }
        },
        "xosc_files_generated": xosc_files
    }
    
    with open('salvaged_evaluation_results.json', 'w') as f:
        json.dump(recovered_data, f, indent=2)
    
    print("\n✅ Results saved to salvaged_evaluation_results.json")

if __name__ == "__main__":
    main()