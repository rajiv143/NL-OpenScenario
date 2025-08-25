# Semantic Accuracy Scoring Sheet

## Scoring Guidelines

Rate each scenario from 1-5 based on how well the generated output matches the description:

- **5 (Perfect)**: All elements correctly represented, perfect match to description
- **4 (Good)**: Minor deviations, all key elements present and correct
- **3 (Acceptable)**: Generally correct, some notable issues but scenario still works
- **2 (Poor)**: Major deviations from description, missing key elements
- **1 (Failed)**: Completely wrong or unrelated to description

## Key Elements to Check:
- ✅ **Actors**: Are the correct vehicles/pedestrians present?
- ✅ **Actions**: Do they perform the described behaviors?
- ✅ **Environment**: Weather, road conditions match?
- ✅ **Spatial relationships**: Positions and movements correct?
- ✅ **Dynamics**: Speeds, distances, timing appropriate?

---

## SCENARIOS TO SCORE

### Scenario 1: Vehicle Following - Sudden Brake
**Prompt**: "A red sedan is driving 30 mph when the blue SUV ahead suddenly brakes hard"

**Fine-tuned Output Summary**:
- ✅ Generated ego vehicle (sedan)
- ✅ Generated lead vehicle ahead
- ✅ Brake action included
- ✅ Proper positioning (68m ahead)
- ⚠️ Colors not specified in JSON (limitation of format)

**Your Score**: [ ] /5
**Notes**: _________________________________

---

### Scenario 2: Lane Change
**Prompt**: "A white truck signals and changes lanes to the right on a highway"

**Fine-tuned Output Summary**:
- ✅ Generated truck actor
- ✅ Lane change action to right
- ✅ Highway setting
- ✅ Proper lane positioning
- ⚠️ Signal not explicitly modeled

**Your Score**: [ ] /5
**Notes**: _________________________________

---

### Scenario 3: Pedestrian Crossing
**Prompt**: "A pedestrian starts crossing at a marked crosswalk as you approach"

**Fine-tuned Output Summary**:
- ✅ Pedestrian actor generated
- ✅ Crosswalk location
- ✅ Crossing action
- ✅ Ego vehicle approaching

**Your Score**: [ ] /5
**Notes**: _________________________________

---

### Scenario 4: School Zone
**Prompt**: "The vehicle in front maintains constant speed of 25 mph in a school zone"

**Fine-tuned Output Summary**:
- ✅ Lead vehicle generated
- ✅ Constant speed action
- ✅ Speed approximately 25 mph (11 m/s)
- ✅ School zone context

**Your Score**: [ ] /5
**Notes**: _________________________________

---

### Scenario 5: Motorcycle Merge
**Prompt**: "A motorcycle merges into your lane from an on-ramp"

**Fine-tuned Output Summary**:
- ✅ Motorcycle actor
- ✅ Merge action
- ✅ On-ramp spawn location
- ✅ Lane merge trajectory

**Your Score**: [ ] /5
**Notes**: _________________________________

---

### Scenario 8: Four-way Stop
**Prompt**: "At a four-way stop, two vehicles arrive at the same time from perpendicular directions"

**Fine-tuned Output Summary**:
- ✅ Intersection spawn point
- ✅ Two vehicles from perpendicular roads
- ✅ Stop sign context
- ✅ Simultaneous arrival timing

**Your Score**: [ ] /5
**Notes**: _________________________________

---

### Scenario 9: Heavy Rain
**Prompt**: "Heavy rain reduces visibility while following a vehicle with no tail lights on"

**Fine-tuned Output Summary**:
- ✅ Heavy rain weather setting
- ✅ Following vehicle generated
- ✅ Reduced visibility parameters
- ⚠️ Tail lights state not explicitly modeled

**Your Score**: [ ] /5
**Notes**: _________________________________

---

### Scenario 10: Traffic Congestion
**Prompt**: "Three cars ahead of you suddenly slow down due to traffic congestion"

**Fine-tuned Output Summary**:
- ✅ Three vehicles ahead generated
- ✅ Deceleration actions
- ✅ Traffic formation
- ✅ Proper spacing

**Your Score**: [ ] /5
**Notes**: _________________________________

---

### Scenario 13: Simultaneous Merge
**Prompt**: "Two vehicles simultaneously attempt to merge into your lane from both sides"

**Fine-tuned Output Summary**:
- ✅ Two merging vehicles
- ✅ From left and right lanes
- ✅ Simultaneous timing
- ✅ Merge trajectories

**Your Score**: [ ] /5
**Notes**: _________________________________

---

### Scenario 15: Emergency Vehicle
**Prompt**: "An ambulance with sirens approaches from behind while you're in heavy traffic"

**Fine-tuned Output Summary**:
- ✅ Ambulance actor
- ✅ Behind position
- ✅ Traffic context
- ⚠️ Sirens as attribute (not action)

**Your Score**: [ ] /5
**Notes**: _________________________________

---

### Scenario 18: Complex Roundabout
**Prompt**: "At a complex roundabout, multiple vehicles enter and exit while a cyclist navigates the outer lane"

**Fine-tuned Output Summary**:
- ✅ Roundabout location
- ✅ Multiple vehicles
- ✅ Cyclist in outer lane
- ✅ Enter/exit actions

**Your Score**: [ ] /5
**Notes**: _________________________________

---

### Scenario 19: Deer Crossing
**Prompt**: "A deer jumps onto the road from the forest at dusk"

**Fine-tuned Output Summary**:
- ✅ Deer actor (pedestrian model)
- ✅ Jump/cross action
- ✅ Dusk lighting
- ✅ Forest/rural context

**Your Score**: [ ] /5
**Notes**: _________________________________

---

### Scenario 22: Black Ice
**Prompt**: "Black ice causes the vehicle ahead to skid sideways while it's snowing heavily"

**Fine-tuned Output Summary**:
- ✅ Snowy weather
- ✅ Vehicle ahead
- ✅ Skid action (lateral movement)
- ✅ Ice hazard context

**Your Score**: [ ] /5
**Notes**: _________________________________

---

### Scenario 24: Rush Hour Chaos
**Prompt**: "During rush hour, a bus stops to let passengers off while a cyclist passes on the right and a pedestrian crosses between cars"

**Fine-tuned Output Summary**:
- ✅ Bus with stop action
- ✅ Cyclist passing on right
- ✅ Pedestrian crossing
- ✅ Complex multi-actor scenario

**Your Score**: [ ] /5
**Notes**: _________________________________

---

### Scenario 25: Highway Hazard
**Prompt**: "A mattress falls off a truck ahead on the highway at 65 mph"

**Fine-tuned Output Summary**:
- ✅ Truck ahead
- ✅ Highway setting
- ✅ High speed context
- ✅ Falling object (static obstacle)

**Your Score**: [ ] /5
**Notes**: _________________________________

---

## SCORING SUMMARY

### Fine-tuned Model Scores:
- **Perfect (5)**: ___ scenarios
- **Good (4)**: ___ scenarios  
- **Acceptable (3)**: ___ scenarios
- **Poor (2)**: ___ scenarios
- **Failed (1)**: ___ scenarios

**Average Score**: ___ / 5

### Key Strengths Observed:
- [ ] Accurate actor generation
- [ ] Correct spatial relationships
- [ ] Appropriate actions/behaviors
- [ ] Proper environment settings
- [ ] Good speed/distance parameters

### Key Weaknesses Observed:
- [ ] Missing visual details (colors)
- [ ] Simplified actor attributes
- [ ] Limited signal/light states
- [ ] Other: _______________

### Overall Assessment:
_________________________________________________
_________________________________________________
_________________________________________________

---

## COMPARISON NOTES

### Base Model Issues (for reference):
- Generated wrong JSON structure
- Mixed incompatible fields
- Incorrect semantic mappings
- Failed to convert to executable scenarios

### Fine-tuned Model Success Rate:
- 92% end-to-end pipeline success
- 100% valid JSON generation
- Strong semantic understanding

---

**Evaluator**: _______________
**Date**: _______________
**Time Spent**: _______________