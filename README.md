# CARLA Scenario Generation Pipeline

A comprehensive pipeline for generating CARLA simulation scenarios from natural language descriptions using fine-tuned Large Language Models (LLMs).

## Overview

This project provides an end-to-end pipeline that:
1. Takes natural language descriptions of driving scenarios
2. Generates structured JSON scenario definitions using LLM (base or fine-tuned)
3. Converts JSON to OpenSCENARIO (XOSC) format for CARLA simulator
4. Validates outputs at each stage

## Features

- **Natural Language Input**: Describe scenarios in plain English
- **LLM-Powered Generation**: Uses Llama 3.2 models (base or fine-tuned)
- **JSON to XOSC Conversion**: Automatic conversion to CARLA-compatible format
- **Multiple Operation Modes**: Interactive, batch processing, testing, and benchmarking
- **Validation Pipeline**: Ensures valid JSON structure and XOSC compliance
- **Weather Recognition**: Automatically extracts and applies weather conditions from descriptions

## Prerequisites

- Python 3.10 (specifically 3.10.18 for best compatibility with llm310 environment)
- CUDA-capable GPU (recommended for performance)
- CUDA 11.8+ runtime
- 8GB+ GPU memory for 4-bit quantization
- CARLA Simulator (optional, for running generated scenarios)

## Installation

### Using Conda Environment (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd Rajiv
```

2. Create and activate the conda environment:
```bash
conda env create -f llm310_environment.yml
conda activate llm310
```

This environment includes all necessary dependencies with specific versions for compatibility.

### Manual Installation

If you prefer pip installation:
```bash
pip install -r requirements.txt
```

### Model Setup

Download model files (if using pre-trained models):
- Place fine-tuned model in: `./llm/exported_models/llama-carla-model-v5-improved/`
- Base model will be downloaded automatically from HuggingFace

## Project Structure

```
Rajiv/
├── carla_scenario_pipeline.py    # Main pipeline orchestrator
├── llm/
│   ├── inference_carla_model.py  # LLM inference engine
│   └── exported_models/          # Fine-tuned model storage
├── xosc_json.py                  # JSON to XOSC converter
├── pipeline_output/              # Generated outputs (auto-created)
│   ├── json/                     # Generated JSON scenarios
│   ├── xosc/                     # Converted XOSC files
│   └── logs/                     # Processing logs and results
└── requirements.txt              # Python dependencies
```

## Usage

### 1. Using the Complete Pipeline (carla_scenario_pipeline.py)

The pipeline script provides a unified interface for the entire generation process.

#### Interactive Mode (Default)
```bash
python carla_scenario_pipeline.py --model finetuned
```
Enter scenario descriptions interactively. Type 'quit' to exit.

#### Single Scenario Generation
```bash
python carla_scenario_pipeline.py --mode single \
    --description "A red car stops suddenly ahead in heavy rain" \
    --model finetuned
```

#### Batch Processing
Create a JSON file with multiple scenarios:
```json
{
  "test_scenarios": [
    {"id": "test1", "description": "A vehicle ahead brakes suddenly"},
    {"id": "test2", "description": "Pedestrian crossing in foggy conditions"}
  ]
}
```

Process the batch:
```bash
python carla_scenario_pipeline.py --mode batch \
    --batch-file scenarios.json \
    --model finetuned
```

#### Test Mode
Run predefined test scenarios:
```bash
python carla_scenario_pipeline.py --mode test --model finetuned
```

#### Command-line Options
- `--model`: Choose between 'finetuned' or 'base' model
- `--mode`: Operation mode (interactive/single/batch/test)
- `--description`: Scenario description for single mode
- `--batch-file`: Input file for batch processing
- `--output-dir`: Directory for outputs (default: pipeline_output)
- `--no-save`: Skip saving output files

### 2. Using the JSON to XOSC Converter (xosc_json.py)

The `xosc_json.py` module provides the `JsonToXoscConverter` class for converting JSON scenario definitions to OpenSCENARIO (XOSC) format.

#### Standalone Usage

While typically used through the pipeline, you can use the converter directly in Python:

```python
from xosc_json import JsonToXoscConverter
import json

# Initialize converter
converter = JsonToXoscConverter()

# Load your JSON scenario
with open('scenario.json', 'r') as f:
    scenario_data = json.load(f)

# Convert to XOSC
xosc_output = converter.convert(scenario_data)

# Save XOSC file
with open('scenario.xosc', 'w') as f:
    f.write(xosc_output)
```

#### Converter Features

- **Vehicle Validation**: Validates against CARLA's vehicle catalog
- **Spawn Point Selection**: Intelligent spawn point selection based on criteria:
  - Lane type (Driving, Parking, etc.)
  - Distance to ego vehicle
  - Relative position (ahead, behind, adjacent)
  - Road relationship (same road, different road)
- **Weather Mapping**: Converts weather descriptions to CARLA parameters
- **Action Translation**: Converts high-level actions to XOSC maneuvers
- **Safety Checks**: Enforces minimum distances and prevents invalid spawns

#### Supported Spawn Criteria

```json
{
  "lane_type": "Driving",           // Lane type constraint
  "is_intersection": false,          // Intersection requirement
  "distance_to_ego": {               // Distance constraints
    "min": 20,
    "max": 60
  },
  "lane_relationship": "adjacent",   // same_lane, adjacent, opposite
  "relative_position": "ahead",      // ahead, behind, alongside
  "road_relationship": "same_road"   // same_road, different_road
}
```

#### Map Data

The converter uses pre-extracted spawn point data for various CARLA maps stored in JSON files. These include validated spawn points with road and lane information.

### 3. Using Direct LLM Inference (inference_carla_model.py)

For direct model interaction without the full pipeline:

#### Interactive Generation
```bash
python llm/inference_carla_model.py --mode interactive
```

#### Test Cases
```bash
python llm/inference_carla_model.py --mode test
```

#### Performance Benchmark
```bash
python llm/inference_carla_model.py --mode benchmark
```

#### Batch Generation from File
Create a text file with one scenario description per line:
```
A car stops at a red traffic light
Heavy rain reduces visibility on highway
Multiple vehicles at roundabout
```

Run batch generation:
```bash
python llm/inference_carla_model.py --mode batch \
    --input-file descriptions.txt \
    --output-dir generated_scenarios
```

#### Advanced Options
- `--model-path`: Path to fine-tuned model
- `--base-model`: Base model name (default: meta-llama/Llama-3.2-3B-Instruct)
- `--temperature`: Generation temperature (0.0-1.0, default: 0.3)
- `--max-tokens`: Maximum tokens to generate (default: 1500)
- `--no-4bit`: Disable 4-bit quantization
- `--merge-lora`: Merge LoRA weights for faster inference

## Example Scenarios

### Simple Scenario
```
Description: "A blue car stops 10 meters ahead"
```

### Weather-Specific Scenario
```
Description: "Heavy rain reduces visibility while following a truck on highway"
```

### Complex Multi-Actor Scenario
```
Description: "At a busy intersection, a pedestrian crosses while two cars approach from different directions in foggy conditions"
```

## Output Formats

### Generated JSON Structure
```json
{
  "scenario_name": "generated_scenario_001",
  "description": "A vehicle stops ahead",
  "weather": "clear",
  "ego_vehicle_model": "vehicle.audi.a2",
  "ego_spawn": {
    "criteria": {
      "lane_type": "Driving",
      "is_intersection": false
    }
  },
  "actors": [...],
  "actions": [...],
  "success_distance": 100,
  "timeout": 60,
  "collision_allowed": false
}
```

### XOSC Output
The pipeline automatically converts JSON to OpenSCENARIO format compatible with CARLA.

## Performance Considerations

### GPU Memory Requirements
- **4-bit Quantization** (default): ~4-6 GB VRAM
- **Full Precision**: ~12-16 GB VRAM

### Generation Speed
- **With 4-bit**: ~50-100 tokens/second on RTX 3090
- **Interactive Mode**: 2-5 seconds per scenario
- **Batch Mode**: Processes ~20-30 scenarios per minute

### Optimization Tips
1. Use 4-bit quantization (default) for faster inference
2. Batch process scenarios when possible
3. Lower temperature (0.1-0.3) for more consistent outputs
4. Increase temperature (0.7-0.9) for more creative scenarios

## Troubleshooting

### CUDA Out of Memory
- Ensure 4-bit quantization is enabled (default)
- Reduce `--max-tokens` parameter
- Close other GPU-intensive applications

### Model Loading Issues
- Verify model path exists: `./llm/exported_models/`
- Check CUDA availability: `python -c "import torch; print(torch.cuda.is_available())"`
- Ensure transformers version: `pip install transformers>=4.36.0`

### Invalid JSON Generation
- Use lower temperature (0.1-0.3) for more reliable outputs
- Increase `--max-tokens` if scenarios are truncated
- Check model is properly loaded (should show "✓ Model loaded successfully")

### Missing Dependencies
```bash
# Minimal installation
pip install -r requirements_minimal.txt

# For Python 3.7
pip install -r requirements_py37.txt
```

## Development

### Adding Custom Scenarios
Edit test cases in `inference_carla_model.py`:
```python
test_cases = [
    "Your custom scenario description here",
    # Add more test cases
]
```

### Modifying Generation Parameters
Adjust in `CarlaScenarioGenerator.generate_scenario()`:
- `temperature`: Controls randomness (0.0 = deterministic, 1.0 = creative)
- `top_p`: Nucleus sampling parameter
- `repetition_penalty`: Prevents repetitive text

### Custom Weather Mappings
Edit `_extract_weather_from_description()` in `inference_carla_model.py` to add new weather patterns.

## License

[Your License Here]

## Contributing

Contributions are welcome! Please submit pull requests or open issues for bugs and feature requests.

## Acknowledgments

- CARLA Simulator Team
- Meta Llama Team
- HuggingFace Transformers Library

## Contact

For questions or support, please open an issue on the GitHub repository.