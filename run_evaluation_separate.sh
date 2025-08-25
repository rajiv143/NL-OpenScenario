#!/bin/bash
# Script to run evaluation in parts to avoid timeout issues

echo "================================================"
echo "MODEL EVALUATION SCRIPT"
echo "================================================"

# Activate conda environment
source /home/user/anaconda3_new/etc/profile.d/conda.sh
conda activate llm310

echo ""
echo "Step 1: Testing BASE model only..."
echo "--------------------------------"
python3 -c "
import sys
sys.path.insert(0, '/home/user/Desktop/Rajiv')
from run_full_evaluation import *

scenarios = load_test_scenarios('expanded_test_scenarios.json')
print(f'Testing {len(scenarios)} scenarios on BASE model...')
base_results = test_base_model(scenarios)

import json
with open('base_model_results.json', 'w') as f:
    json.dump(base_results, f, indent=2)
print('✅ Base model results saved to base_model_results.json')
"

echo ""
echo "Step 2: Testing FINE-TUNED model only..."
echo "----------------------------------------"
python3 -c "
import sys
sys.path.insert(0, '/home/user/Desktop/Rajiv')
from run_full_evaluation import *

scenarios = load_test_scenarios('expanded_test_scenarios.json')
print(f'Testing {len(scenarios)} scenarios on FINE-TUNED model...')
finetuned_results = test_finetuned_model(scenarios)

import json
with open('finetuned_model_results.json', 'w') as f:
    json.dump(finetuned_results, f, indent=2)
print('✅ Fine-tuned model results saved to finetuned_model_results.json')
"

echo ""
echo "Step 3: Analyzing and comparing results..."
echo "------------------------------------------"
python3 -c "
import sys
sys.path.insert(0, '/home/user/Desktop/Rajiv')
from run_full_evaluation import *
import json
from datetime import datetime

# Load saved results
with open('base_model_results.json', 'r') as f:
    base_results = json.load(f)
    
with open('finetuned_model_results.json', 'r') as f:
    finetuned_results = json.load(f)

# Load scenarios
scenarios = load_test_scenarios('expanded_test_scenarios.json')

# Analyze
analysis = analyze_and_compare(base_results, finetuned_results)
with open('comprehensive_analysis.json', 'w') as f:
    json.dump(analysis, f, indent=2)
print('✅ Analysis saved to comprehensive_analysis.json')

# Create combined results
combined_results = {
    'timestamp': datetime.now().isoformat(),
    'scenarios': []
}

for i in range(len(scenarios)):
    combined_results['scenarios'].append({
        'scenario': scenarios[i],
        'base_model': base_results[i],
        'finetuned_model': finetuned_results[i]
    })

with open('combined_test_results.json', 'w') as f:
    json.dump(combined_results, f, indent=2)
print('✅ Combined results saved to combined_test_results.json')
"

echo ""
echo "================================================"
echo "✅ EVALUATION COMPLETE!"
echo "================================================"
echo ""
echo "Output files created:"
echo "  - base_model_results.json"
echo "  - finetuned_model_results.json"  
echo "  - comprehensive_analysis.json"
echo "  - combined_test_results.json"
echo ""
echo "Share combined_test_results.json for semantic accuracy scoring!"