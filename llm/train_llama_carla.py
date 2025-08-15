import json
import torch
from datasets import Dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model, TaskType

def format_prompt(example):
    """Format training examples as chat prompts"""
    prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are an expert CARLA simulator scenario designer. Generate valid JSON scenarios based on natural language descriptions.<|eot_id|>

<|start_header_id|>user<|end_header_id|>
{example['instruction']}

{example['input']}<|eot_id|>

<|start_header_id|>assistant<|end_header_id|>
{example['output']}<|eot_id|>"""
    return {"text": prompt}

def train_model():
    # Load tokenizer and model
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True
    )
    
    # Apply LoRA
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    
    # Load and format datasets
    with open('train_dataset.json', 'r') as f:
        train_data = json.load(f)
    with open('val_dataset.json', 'r') as f:
        val_data = json.load(f)
    
    train_dataset = Dataset.from_list(train_data).map(format_prompt)
    val_dataset = Dataset.from_list(val_data).map(format_prompt)
    
    # Tokenize
    def tokenize_function(examples):
        return tokenizer(examples["text"], truncation=True, padding=True, max_length=2048)
    
    train_dataset = train_dataset.map(tokenize_function, batched=True)
    val_dataset = val_dataset.map(tokenize_function, batched=True)
    
    # Setup trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        tokenizer=tokenizer,
    )
    
    # Train!
    trainer.train()
    
    # Save the model
    trainer.save_model("./llama-carla-final")
    tokenizer.save_pretrained("./llama-carla-final")

if __name__ == "__main__":
    train_model()