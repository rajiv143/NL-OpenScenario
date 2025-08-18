# debug_raw_output.py
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

print("Loading model...")
base_model = AutoModelForCausalLM.from_pretrained(
    "meta-llama/Llama-3.2-3B-Instruct", 
    torch_dtype=torch.float16, 
    device_map="auto"
)
model = PeftModel.from_pretrained(base_model, "./llama-carla-model/final_model")
tokenizer = AutoTokenizer.from_pretrained("./llama-carla-model/final_model")

# Set pad token
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

prompt = """<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are an expert CARLA simulator scenario designer. Generate valid JSON scenarios based on natural language descriptions. The JSON should follow the exact CARLA scenario format with proper structure for actors, actions, spawn criteria, and triggers.<|eot_id|><|start_header_id|>user<|end_header_id|>

Generate a CARLA scenario JSON based on this description:

A blue car ahead of ego stops suddenly<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""

print(f"Prompt length: {len(prompt)} characters")

# Tokenize and move to correct device
inputs = tokenizer(prompt, return_tensors="pt")
inputs = {k: v.to(model.device) for k, v in inputs.items()}  # 🔑 FIX: Move to GPU

print(f"Input tokens: {inputs['input_ids'].shape[1]}")

print("Generating...")
with torch.no_grad():
    outputs = model.generate(
        **inputs,
        max_new_tokens=1500,
        min_new_tokens=500,
        temperature=0.7,
        do_sample=True,
        repetition_penalty=1.1,
        pad_token_id=tokenizer.eos_token_id,
        eos_token_id=tokenizer.eos_token_id
    )

print(f"Generated {outputs.shape[1] - inputs['input_ids'].shape[1]} tokens")

# Decode full response
full_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
result = full_text[len(prompt):].strip()

print("="*60)
print("COMPLETE RAW OUTPUT:")
print("="*60)
print(result)
print("="*60)
print(f"Length: {len(result)} characters")

# Try to identify if it's valid JSON
if result.startswith('{') and result.endswith('}'):
    try:
        import json
        parsed = json.loads(result)
        print(f"\n✅ VALID JSON with keys: {list(parsed.keys())}")
    except json.JSONDecodeError as e:
        print(f"\n❌ JSON parse error: {e}")
else:
    print(f"\n⚠️  Output doesn't look like pure JSON")
    print(f"Starts with: {repr(result[:50])}")
    print(f"Ends with: {repr(result[-50:])}")