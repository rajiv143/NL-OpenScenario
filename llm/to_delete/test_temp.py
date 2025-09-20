from inference_carla_model import CarlaScenarioGenerator
import json, torch

gen = CarlaScenarioGenerator(
    "./models/llama-carla-model-v5-improved/final_model",
    use_4bit=False,
    merge_lora=True
)

# Generate with low temperature
prompt = "A single blue car parked ahead"
formatted = gen.format_prompt(prompt)
inputs = gen.tokenizer(formatted, return_tensors="pt").to(gen.model.device)

with torch.no_grad():
    outputs = gen.model.generate(
        **inputs,
        max_new_tokens=500,
        temperature=0.3,
        use_cache=True,
    )

raw = gen.tokenizer.decode(outputs[0], skip_special_tokens=True)
response = raw[len(formatted):].strip()
print("RAW OUTPUT:")
print(response)
print("raw as well"+raw)