def _detect_scenario_type(data):
    """Detect scenario type based on scenario content"""
    scenario_name = data.get('scenario_name', '').lower()
    description = data.get('description', '').lower()
    
    print(f"DEBUG: scenario_name='{scenario_name}'")
    print(f"DEBUG: description='{description}'")
    
    # Check for highway scenarios FIRST (highest priority)
    if any(keyword in scenario_name or keyword in description for keyword in
           ['highway', 'freeway', 'motorway']):
        print("DEBUG: Detected as highway!")
        return 'highway'
    
    print("DEBUG: Not detected as highway")
    return 'general'

import json
with open('./llm/generated_scenarios/generated_007.json') as f:
    data = json.load(f)

result = _detect_scenario_type(data)
print(f"Result: {result}")
