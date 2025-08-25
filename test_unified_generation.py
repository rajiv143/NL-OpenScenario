#!/usr/bin/env python3
"""
Quick test of the unified generation architecture
"""

import sys
import json
sys.path.append('/home/user/Desktop/Rajiv/llm')

from run_model_comparison import BaseModelGenerator

# Test with a simple scenario
test_scenario = "A red car stops at a traffic light"

print("Testing unified generation architecture...")
print("="*60)

try:
    # Create base model generator with unified architecture
    generator = BaseModelGenerator("meta-llama/Llama-3.2-3B-Instruct")
    
    # Generate scenario
    result = generator.generate_scenario(test_scenario)
    
    if result:
        print("\n✅ Generation successful!")
        print("\nGenerated JSON:")
        print(json.dumps(result, indent=2)[:500] + "...")
    else:
        print("\n❌ Generation failed")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("Test complete!")