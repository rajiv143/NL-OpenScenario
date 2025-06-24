# CARLA Scenario JSON → OpenSCENARIO Converter

This project provides a Python-based tool to convert flat, LLM-friendly JSON scenario descriptions into valid OpenSCENARIO (XOSC) files for use with the CARLA simulator.

## Repository Structure

```bash
├── xosc_json.py        # Main converter script
├── example-json-*.json # Sample scenario definitions in JSON
├── *.xosc              # Generated OpenSCENARIO XML files
└── README.md           # This documentation file
```

## Features

* **JSON-to-XOSC conversion**: Transforms a simplified JSON schema into a fully compliant OpenSCENARIO XML.
* **Schema validation**: Optional JSON Schema integration to catch errors early.
* **CARLA integration**: Supports CARLA vehicle/pedestrian catalogs, map validation, and weather presets.
* **Action & trigger support**: Implements common action types (`speed`, `stop`, `wait`, `lane_change`, etc.) and trigger types (`time`, `distance_to_ego`, `after_previous`).
* **Customizable dynamics**: Fine-tune `dynamics_dimension`, `dynamics_shape`, and `dynamics_value` for smooth transitions.

## Prerequisites

* Python 3.7+ (tested on 3.7)
* `xmlschema`, `jsonschema`, `lxml` (for XML validation, optional)

Install dependencies with:

```bash
pip install jsonschema xmlschema
```

## JSON Schema Template

A simplified excerpt of the schema (`$schema: http://json-schema.org/draft-07/schema#`):

```json
{
  "type": "object",
  "required": ["scenario_name", "map_name", "ego_start_position"],
  "properties": {
    "scenario_name": { "type": "string" },
    "map_name":    { "type": "string", "enum": ["Town01","Town02",... ] },
    "ego_start_position": { "type": "string", "pattern": "^-?[0-9]+(\\.[0-9]+)?,...$" },
    "actors": { "type": "array", "items": { /* id, type, model, start_position */ } },
    "actions": { "type": "array", "items": { /* actor_id, action_type, trigger_type, ... */ } },
    "success_distance": { "type": "number" },
    "timeout": { "type": "number" },
    "collision_allowed": { "type": "boolean" }
  }
}
```

Refer to the full JSON schema in the `docs/` folder (if available) or adapt from the included template in this repository.

## Usage

1. **Prepare a JSON scenario**

   * Write your scenario JSON following the schema (e.g., `example-json-pedestrian.json`).

2. **Generate the XOSC file**

   ```bash
   python xosc_json.py example-json-pedestrian.json -o example-pedestrian.xosc
   ```

   This will validate the JSON (if a schema is provided) and output a pretty-printed XOSC file.

3. **Run in CARLA**

   ```bash
   ./scenario_runner.py --openscenario example-pedestrian.xosc --reloadWorld --output
   ```

   Ensure CARLA server is running on port `2000`.

## Example

**JSON input (`example-pedestrian.json`):**

```json
{
  "scenario_name": "PedestrianCrossingFront",
  "map_name": "Town01",
  "ego_start_position": "150,55,0,180",
  "actors": [{"id":"adversary","type":"pedestrian","model":"walker.pedestrian.0001","start_position":"110,52,0.3,90"}],
  "actions": [
    {"actor_id":"adversary","action_type":"speed","trigger_type":"distance_to_ego","trigger_value":40,"speed_value":10.0},
    {"actor_id":"adversary","action_type":"stop","trigger_type":"after_previous"}
  ],
  "success_distance":200,
  "timeout":60,
  "collision_allowed":false
}
```

**Generated XOSC snippet:**

```xml
<Story name="MyStory">
  <Act name="Behavior">
    <ManeuverGroup maximumExecutionCount="1" name="adversaryManeuverGroup">
      <Actors selectTriggeringEntities="false">
        <EntityRef entityRef="adversary"/>
      </Actors>
      <Maneuver name="adversaryManeuver">
        <Event name="adversaryEvent0" priority="overwrite">
          <Action name="adversaryAction0">
            <PrivateAction>
              <LongitudinalAction>
                <SpeedAction>
                  <SpeedActionDynamics dynamicsDimension="time" dynamicsShape="step" value="0"/>
                  <SpeedActionTarget>
                    <AbsoluteTargetSpeed value="10.0"/>
                  </SpeedActionTarget>
                </SpeedAction>
              </LongitudinalAction>
            </PrivateAction>
          </Action>
          <StartTrigger>…</StartTrigger>
        </Event>
      </Maneuver>
    </ManeuverGroup>
  </Act>
</Story>
```

## Limitations & Future Work

* **Partial trigger/action support**: Only common types implemented. Extended triggers (e.g., `reach_position`) need to be added.
* **No scene-graph validation**: Assumes correct map and catalog files exist in CARLA.
* **LLM Integration**: Future work includes synthetic dataset generation via GPT APIs and LLM fine-tuning for JSON synthesis.

## Contributing

Feel free to submit issues or pull requests for new action types, trigger conditions, or improved schema validation.

---

*Generated on* `$(date)`
