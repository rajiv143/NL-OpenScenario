# continue_training.py
from train_llama_carla import CarlaScenarioTrainer
import argparse

def continue_training(existing_model_path: str, **kwargs):
    """Continue training from existing model"""
    
    # Create trainer with lower learning rate for continued training
    trainer = CarlaScenarioTrainer(
        model_name=kwargs.get('base_model', 'meta-llama/Llama-3.2-3B-Instruct'),
        output_dir=kwargs.get('output_dir', './llama-carla-model-v2'),
        use_4bit=kwargs.get('use_4bit', True),
        lora_r=kwargs.get('lora_r', 16),
        lora_alpha=kwargs.get('lora_alpha', 32)
    )
    
    # Use the modified setup method
    trainer.setup_model_and_tokenizer_continue(existing_model_path)
    
    # Load new datasets
    trainer.load_and_prepare_datasets()
    
    # Continue training with lower learning rate
    trainer.train(
        num_epochs=kwargs.get('epochs', 2),
        batch_size=kwargs.get('batch_size', 2),
        learning_rate=kwargs.get('learning_rate', 1e-5),  # Lower LR for continued training
        use_wandb=kwargs.get('use_wandb', False)
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--existing-model", required=True, help="Path to existing LoRA model")
    parser.add_argument("--base-model", default="meta-llama/Llama-3.2-3B-Instruct")
    parser.add_argument("--output-dir", default="./llama-carla-model-v2")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    
    args = parser.parse_args()
    
    continue_training(
        existing_model_path=args.existing_model,
        base_model=args.base_model,
        output_dir=args.output_dir,
        epochs=args.epochs,
        learning_rate=args.learning_rate
    )