# Model Export Information

## Export Details
- **Original Model**: llama-carla-model
- **Base Model**: meta-llama/Llama-3.2-3B-Instruct
- **Export Type**: adapters
- **Export Date**: Unknown

## Usage Instructions

### For Adapter Export:
```python
from peft import PeftModel
from transformers import AutoModelForCausalLM

base_model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-3.2-3B-Instruct")
model = PeftModel.from_pretrained(base_model, "./llm/exported_models/llama-carla-model/exported_model_adapters")
```

### For Merged Model Export:
```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model = AutoModelForCausalLM.from_pretrained("./llm/exported_models/llama-carla-model/exported_model_adapters")
tokenizer = AutoTokenizer.from_pretrained("./llm/exported_models/llama-carla-model/exported_model_adapters")
```
