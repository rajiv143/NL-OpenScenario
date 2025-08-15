#!/usr/bin/env python3
"""
Train Llama model for CARLA scenario generation using LoRA
Compatible with Python 3.7 and older package versions
"""

import json
import torch
import os
from pathlib import Path
from datasets import Dataset, DatasetDict
from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import LoraConfig, get_peft_model, TaskType
import wandb
from typing import Dict, List, Optional
import argparse

class CarlaScenarioTrainer:
    def __init__(self, 
                 model_name: str = "gpt2",  # Use GPT-2 as fallback for Python 3.7
                 output_dir: str = "./carla-model",
                 use_4bit: bool = False,  # 4-bit not available in older versions
                 lora_r: int = 16,
                 lora_alpha: int = 32):
        """
        Initialize the trainer with model configuration
        
        Args:
            model_name: HuggingFace model name or path
            output_dir: Directory to save the trained model
            use_4bit: Whether to use 4-bit quantization (disabled for Python 3.7)
            lora_r: LoRA rank parameter
            lora_alpha: LoRA alpha parameter
        """
        self.model_name = model_name
        self.output_dir = Path(output_dir)
        self.use_4bit = False  # Disable 4-bit for compatibility
        self.lora_r = lora_r
        self.lora_alpha = lora_alpha
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Set device
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")
        if self.device.type == "cuda":
            print(f"GPU: {torch.cuda.get_device_name()}")
            print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    
    def format_prompt(self, example: Dict) -> Dict:
        """Format training examples as prompts"""
        # Use simpler format for GPT-2 or older models
        prompt = f"""### Instruction:
{example['instruction']}

### Input:
{example['input']}

### Response:
{example['output']}"""
        
        return {"text": prompt}
    
    def setup_model_and_tokenizer(self):
        """Setup model with LoRA and tokenizer"""
        print(f"\nLoading model: {self.model_name}")
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name, 
            trust_remote_code=True
        )
        
        # Set padding token if not exists
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
        
        # Load model
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=torch.float16,
            device_map="auto" if torch.cuda.is_available() else None,
            trust_remote_code=True
        )
        
        if torch.cuda.is_available():
            self.model = self.model.cuda()
        
        # Configure LoRA (simplified for older PEFT version)
        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=self.lora_r,
            lora_alpha=self.lora_alpha,
            lora_dropout=0.1,
            target_modules=["c_attn", "c_proj"] if "gpt2" in self.model_name.lower() else ["q_proj", "v_proj"]
        )
        
        # Apply LoRA
        self.model = get_peft_model(self.model, lora_config)
        self.model.print_trainable_parameters()
    
    def load_and_prepare_datasets(self, train_file: str = "train_dataset.json",
                                 val_file: str = "val_dataset.json"):
        """Load and prepare datasets for training"""
        print("\nLoading datasets...")
        
        # Load JSON files
        with open(train_file, 'r') as f:
            train_data = json.load(f)
        with open(val_file, 'r') as f:
            val_data = json.load(f)
        
        print(f"Loaded {len(train_data)} training examples")
        print(f"Loaded {len(val_data)} validation examples")
        
        # Create datasets and format prompts
        train_dataset = Dataset.from_list(train_data).map(self.format_prompt)
        val_dataset = Dataset.from_list(val_data).map(self.format_prompt)
        
        # Tokenize function
        def tokenize_function(examples):
            return self.tokenizer(
                examples["text"], 
                truncation=True, 
                padding="max_length",
                max_length=1024,  # Reduced for memory efficiency
                return_tensors="pt"
            )
        
        # Tokenize datasets
        print("Tokenizing datasets...")
        self.train_dataset = train_dataset.map(
            tokenize_function, 
            batched=True,
            remove_columns=train_dataset.column_names
        )
        self.val_dataset = val_dataset.map(
            tokenize_function, 
            batched=True,
            remove_columns=val_dataset.column_names
        )
        
        print(f"Tokenized {len(self.train_dataset)} training examples")
        print(f"Tokenized {len(self.val_dataset)} validation examples")
    
    def get_training_args(self, num_epochs: int = 3, batch_size: int = 2,
                         learning_rate: float = 5e-4, use_wandb: bool = False):
        """Get training arguments"""
        # Calculate gradient accumulation steps
        effective_batch_size = 8
        gradient_accumulation_steps = max(1, effective_batch_size // batch_size)
        
        training_args = TrainingArguments(
            output_dir=str(self.output_dir),
            overwrite_output_dir=True,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            gradient_accumulation_steps=gradient_accumulation_steps,
            num_train_epochs=num_epochs,
            learning_rate=learning_rate,
            fp16=torch.cuda.is_available(),  # Only use fp16 if CUDA available
            logging_steps=10,
            evaluation_strategy="steps",
            eval_steps=50,
            save_strategy="steps",
            save_steps=100,
            save_total_limit=2,
            load_best_model_at_end=True,
            metric_for_best_model="loss",
            greater_is_better=False,
            warmup_steps=50,
            logging_dir=str(self.output_dir / "logs"),
            report_to="wandb" if use_wandb else "none",
            remove_unused_columns=False,
        )
        
        return training_args
    
    def train(self, num_epochs: int = 3, batch_size: int = 2, 
             learning_rate: float = 5e-4, use_wandb: bool = False):
        """Run the training"""
        # Setup model and tokenizer
        self.setup_model_and_tokenizer()
        
        # Load datasets
        self.load_and_prepare_datasets()
        
        # Get training arguments
        training_args = self.get_training_args(
            num_epochs=num_epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
            use_wandb=use_wandb
        )
        
        # Initialize wandb if requested
        if use_wandb:
            wandb.init(
                project="carla-scenarios",
                name=f"{self.model_name.split('/')[-1]}-lora",
                config={
                    "model": self.model_name,
                    "lora_r": self.lora_r,
                    "lora_alpha": self.lora_alpha,
                    "epochs": num_epochs,
                    "batch_size": batch_size,
                    "learning_rate": learning_rate
                }
            )
        
        # Create data collator
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer,
            mlm=False,  # Causal LM, not masked LM
        )
        
        # Setup trainer
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=self.train_dataset,
            eval_dataset=self.val_dataset,
            tokenizer=self.tokenizer,
            data_collator=data_collator,
        )
        
        # Train
        print("\n" + "="*50)
        print("Starting training...")
        print("="*50)
        
        trainer.train()
        
        # Save the final model
        print("\nSaving model...")
        trainer.save_model(str(self.output_dir / "final_model"))
        self.tokenizer.save_pretrained(str(self.output_dir / "final_model"))
        
        # Save training metrics
        metrics = trainer.evaluate()
        with open(self.output_dir / "training_metrics.json", 'w') as f:
            json.dump(metrics, f, indent=2)
        
        print(f"\n✓ Training complete! Model saved to {self.output_dir / 'final_model'}")
        print(f"Final validation loss: {metrics.get('eval_loss', 'N/A'):.4f}")
        
        if use_wandb:
            wandb.finish()

def main():
    parser = argparse.ArgumentParser(description="Train model for CARLA scenario generation (Python 3.7)")
    
    # Model choices for Python 3.7
    model_choices = [
        "gpt2",           # Default, works well
        "gpt2-medium",    # Larger GPT-2
        "distilgpt2",     # Smaller, faster
        "EleutherAI/gpt-neo-125M",  # Open alternative
        "EleutherAI/gpt-neo-1.3B",  # Larger alternative (needs more memory)
    ]
    
    parser.add_argument("--model", type=str, default="gpt2",
                       choices=model_choices,
                       help=f"Model to use. Options: {', '.join(model_choices)}")
    parser.add_argument("--output-dir", type=str, default="./carla-model-py37",
                       help="Output directory for the trained model")
    parser.add_argument("--epochs", type=int, default=3,
                       help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=2,
                       help="Batch size per device")
    parser.add_argument("--learning-rate", type=float, default=5e-4,
                       help="Learning rate")
    parser.add_argument("--lora-r", type=int, default=16,
                       help="LoRA rank parameter")
    parser.add_argument("--lora-alpha", type=int, default=32,
                       help="LoRA alpha parameter")
    parser.add_argument("--wandb", action="store_true",
                       help="Use Weights & Biases for logging")
    
    args = parser.parse_args()
    
    # Check for CUDA
    if not torch.cuda.is_available():
        print("WARNING: CUDA not available! Training will be slower on CPU.")
        print("Reducing batch size to 1 for CPU training...")
        args.batch_size = 1
    
    print(f"\nUsing model: {args.model}")
    print(f"This model is compatible with Python 3.7")
    
    # Initialize trainer
    trainer = CarlaScenarioTrainer(
        model_name=args.model,
        output_dir=args.output_dir,
        use_4bit=False,  # Not available for Python 3.7
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha
    )
    
    # Run training
    trainer.train(
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        use_wandb=args.wandb
    )

if __name__ == "__main__":
    main()