#!/usr/bin/env python3
"""
Train Llama model for CARLA scenario generation using LoRA
Supports multiple Llama model sizes and configurations
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
    DataCollatorForLanguageModeling,
    EarlyStoppingCallback,
    BitsAndBytesConfig
)
from peft import LoraConfig, get_peft_model, TaskType
try:
    from peft import prepare_model_for_kbit_training
except ImportError:
    from peft import prepare_model_for_int8_training as prepare_model_for_kbit_training
import wandb
from typing import Dict, List, Optional
import argparse

class CarlaScenarioTrainer:
    def __init__(self, 
                 model_name: str = "meta-llama/Llama-3.2-1B-Instruct",
                 output_dir: str = "./llama-carla-model",
                 use_4bit: bool = True,
                 lora_r: int = 16,
                 lora_alpha: int = 32):
        """
        Initialize the trainer with model configuration
        
        Args:
            model_name: HuggingFace model name or path
            output_dir: Directory to save the trained model
            use_4bit: Whether to use 4-bit quantization for training
            lora_r: LoRA rank parameter
            lora_alpha: LoRA alpha parameter
        """
        self.model_name = model_name
        self.output_dir = Path(output_dir)
        self.use_4bit = use_4bit
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
        """Format training examples as chat prompts for Llama"""
        # Check if using Llama 3 format or older format
        if "3.2" in self.model_name or "3.1" in self.model_name:
            # Llama 3.x format
            prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are an expert CARLA simulator scenario designer. Generate valid JSON scenarios based on natural language descriptions. The JSON should follow the exact CARLA scenario format with proper structure for actors, actions, spawn criteria, and triggers.<|eot_id|><|start_header_id|>user<|end_header_id|>

{example['instruction']}

{example['input']}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

{example['output']}<|eot_id|>"""
        else:
            # Llama 2 or generic format
            prompt = f"""[INST] <<SYS>>
You are an expert CARLA simulator scenario designer. Generate valid JSON scenarios based on natural language descriptions.
<</SYS>>

{example['instruction']}

{example['input']} [/INST]

{example['output']}"""
        
        return {"text": prompt}
    
    def setup_model_and_tokenizer(self):
        """Setup model with LoRA and tokenizer"""
        print(f"\nLoading model: {self.model_name}")
        
        # Setup quantization config if using 4-bit
        bnb_config = None
        if self.use_4bit:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
            )
            print("Using 4-bit quantization")
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name, 
            trust_remote_code=True,
            padding_side="left"  # Important for generation
        )
        
        # Set padding token if not exists
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
        
        # Load model
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            quantization_config=bnb_config,
            torch_dtype=torch.float16 if not self.use_4bit else None,
            device_map="auto",
            trust_remote_code=True
        )
        
        # Prepare model for k-bit training if using quantization
        if self.use_4bit:
            self.model = prepare_model_for_kbit_training(self.model)
        
        # Configure LoRA
        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=self.lora_r,
            lora_alpha=self.lora_alpha,
            lora_dropout=0.1,
            target_modules=self._get_target_modules(),
            bias="none"
        )
        
        # Apply LoRA
        self.model = get_peft_model(self.model, lora_config)
        self.model.print_trainable_parameters()
        
        # Enable gradient checkpointing for memory efficiency
        self.model.enable_input_require_grads()
        if hasattr(self.model, "gradient_checkpointing_enable"):
            self.model.gradient_checkpointing_enable()

    def setup_model_and_tokenizer_continue(self, existing_model_path: str):
        """Setup model continuing from existing LoRA checkpoint"""
        from peft import PeftModel
        
        print(f"\nLoading existing model from: {existing_model_path}")
        
        # Setup quantization config if using 4-bit
        bnb_config = None
        if self.use_4bit:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
            )
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            existing_model_path, 
            trust_remote_code=True,
            padding_side="left"
        )
        
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
        
        # Load base model
        base_model = AutoModelForCausalLM.from_pretrained(
            self.model_name,  # Original base model
            quantization_config=bnb_config,
            torch_dtype=torch.float16 if not self.use_4bit else None,
            device_map="auto",
            trust_remote_code=True
        )
        
        # Load existing LoRA adapters
        self.model = PeftModel.from_pretrained(base_model, existing_model_path)
        
        # Prepare for additional training
        if self.use_4bit:
            self.model = prepare_model_for_kbit_training(self.model)
        
        self.model.train()  # Enable training mode
        self.model.print_trainable_parameters()
        
        # Enable gradient checkpointing
        self.model.enable_input_require_grads()
        if hasattr(self.model, "gradient_checkpointing_enable"):
            self.model.gradient_checkpointing_enable()

    def _get_target_modules(self) -> List[str]:
        """Get target modules for LoRA based on model architecture"""
        if "llama" in self.model_name.lower():
            # Llama architecture
            return ["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
        elif "codellama" in self.model_name.lower():
            # CodeLlama uses same as Llama
            return ["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
        else:
            # Default for other models
            return ["q_proj", "v_proj"]
    
    def load_and_prepare_datasets(self, train_file: str = "carla_correct_train.jsonl",
                                 val_file: str = "carla_correct_val.jsonl"):
        """Load and prepare datasets for training"""
        print("\nLoading datasets...")
        
        # Handle relative paths - check if files exist, if not try parent directory
        import os
        
        def find_file(filename):
            if os.path.exists(filename):
                return filename
            elif os.path.exists(f"../{filename}"):
                return f"../{filename}"
            elif os.path.exists(os.path.join(os.path.dirname(__file__), "..", filename)):
                return os.path.join(os.path.dirname(__file__), "..", filename)
            else:
                raise FileNotFoundError(f"Cannot find {filename} in current directory or parent directory")
        
        train_file = find_file(train_file)
        val_file = find_file(val_file)
        
        print(f"Using training file: {train_file}")
        print(f"Using validation file: {val_file}")
        
        # Load JSONL files (one JSON object per line)
        train_data = []
        val_data = []
        
        # Load training data
        with open(train_file, 'r') as f:
            for line in f:
                if line.strip():
                    train_data.append(json.loads(line))
        
        # Load validation data
        with open(val_file, 'r') as f:
            for line in f:
                if line.strip():
                    val_data.append(json.loads(line))
        
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
                max_length=2048,
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
                     learning_rate: float = 2e-4, use_wandb: bool = False):
        """Get training arguments with version compatibility"""
        effective_batch_size = 8
        gradient_accumulation_steps = max(1, effective_batch_size // batch_size)
        
        # Compatible training arguments
        training_args = TrainingArguments(
            output_dir=str(self.output_dir),
            overwrite_output_dir=True,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            gradient_accumulation_steps=gradient_accumulation_steps,
            num_train_epochs=num_epochs,
            learning_rate=learning_rate,
            fp16=True,
            logging_steps=10,
            save_steps=100,
            warmup_steps=50,
            remove_unused_columns=False,
            logging_dir=str(self.output_dir / "logs"),
            report_to="wandb" if use_wandb else "none",
        )
        return training_args
    
    def train(self, num_epochs: int = 3, batch_size: int = 2, 
             learning_rate: float = 2e-4, use_wandb: bool = False):
        """Run the training"""
        # Setup model and tokenizer
        self.setup_model_and_tokenizer()
        
        # Load datasets - use correct JSONL files (will auto-detect path)
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
                project="llama-carla-scenarios",
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
            pad_to_multiple_of=8
        )
        
        # Setup trainer
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=self.train_dataset,
            eval_dataset=self.val_dataset,
            tokenizer=self.tokenizer,
            data_collator=data_collator,
            #callbacks=[EarlyStoppingCallback(early_stopping_patience=3)]
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
    parser = argparse.ArgumentParser(description="Train Llama model for CARLA scenario generation")
    parser.add_argument("--model", type=str, default="meta-llama/Llama-3.2-3B-Instruct",
                       help="Model name or path (e.g., meta-llama/Llama-3.2-3B-Instruct)")
    parser.add_argument("--output-dir", type=str, default="./llama-carla-model",
                       help="Output directory for the trained model")
    parser.add_argument("--epochs", type=int, default=3,
                       help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=2,
                       help="Batch size per device")
    parser.add_argument("--learning-rate", type=float, default=2e-4,
                       help="Learning rate")
    parser.add_argument("--lora-r", type=int, default=16,
                       help="LoRA rank parameter")
    parser.add_argument("--lora-alpha", type=int, default=32,
                       help="LoRA alpha parameter")
    parser.add_argument("--no-4bit", action="store_true",
                       help="Disable 4-bit quantization")
    parser.add_argument("--wandb", action="store_true",
                       help="Use Weights & Biases for logging")
    
    args = parser.parse_args()
    
    # Check for CUDA
    if not torch.cuda.is_available():
        print("WARNING: CUDA not available! Training will be very slow on CPU.")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return
    
    # Initialize trainer
    trainer = CarlaScenarioTrainer(
        model_name=args.model,
        output_dir=args.output_dir,
        use_4bit=not args.no_4bit,
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