#!/usr/bin/env python3
"""
Export LLM LoRA Model - Flexible Version
Supports command line arguments and interactive mode
"""

from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import os
import argparse
import sys

def export_lora_adapters(model_name, base_model_name, models_base_path="./llm/models"):
    """Export just the LoRA adapters (lightweight approach)"""
    
    print("🚀 Starting LoRA adapter export...")
    print(f"📁 Model: {model_name}")
    print(f"🤖 Base Model: {base_model_name}")
    
    # Step 1: Load the base model first
    print(f"📥 Loading base model: {base_model_name}")
    
    try:
        base_model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            torch_dtype=torch.float16,
            device_map="auto",
            low_cpu_mem_usage=True
        )
        print("✅ Base model loaded successfully")
    except Exception as e:
        print(f"❌ Error loading base model: {e}")
        return False
    
    # Step 2: Load LoRA adapters on top of base model
    adapter_path = os.path.join(models_base_path, model_name, "final_model")
    print(f"📥 Loading LoRA adapters from: {adapter_path}")
    
    if not os.path.exists(adapter_path):
        print(f"❌ Adapter path not found: {adapter_path}")
        print("Available models:")
        list_available_models(models_base_path)
        return False
    
    try:
        model = PeftModel.from_pretrained(base_model, adapter_path)
        print("✅ LoRA adapters loaded successfully")
    except Exception as e:
        print(f"❌ Error loading LoRA adapters: {e}")
        return False
    
    # Step 3: Export adapter-only (small size)
    export_path = os.path.join("./llm/exported_models", model_name, "exported_model_adapters")
    print(f"💾 Saving LoRA adapters to: {export_path}")
    
    try:
        model.save_pretrained(export_path)
        print("✅ LoRA adapters exported successfully")
        
        # Also save tokenizer
        tokenizer = AutoTokenizer.from_pretrained(base_model_name)
        tokenizer.save_pretrained(export_path)
        print("✅ Tokenizer saved")
        
        # Save model info
        save_model_info(export_path, model_name, base_model_name, "adapters")
        
    except Exception as e:
        print(f"❌ Error saving adapters: {e}")
        return False
    
    return True

def export_merged_model(model_name, base_model_name, models_base_path="./llm/models"):
    """Export full merged model (larger size but standalone)"""
    
    print("\n🔄 Starting merged model export...")
    
    # Step 1: Load base model
    print(f"📥 Loading base model: {base_model_name}")
    
    try:
        base_model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            torch_dtype=torch.float16,
            device_map="auto",
            low_cpu_mem_usage=True
        )
    except Exception as e:
        print(f"❌ Error loading base model: {e}")
        return False
    
    # Step 2: Load LoRA adapters
    adapter_path = os.path.join(models_base_path, model_name, "final_model")
    print(f"📥 Loading LoRA adapters from: {adapter_path}")
    
    try:
        model = PeftModel.from_pretrained(base_model, adapter_path)
    except Exception as e:
        print(f"❌ Error loading LoRA adapters: {e}")
        return False
    
    # Step 3: Merge adapters into base model
    print("🔗 Merging LoRA adapters with base model...")
    try:
        merged_model = model.merge_and_unload()
        print("✅ Models merged successfully")
    except Exception as e:
        print(f"❌ Error merging models: {e}")
        return False
    
    # Step 4: Save merged model
    export_path = os.path.join(models_base_path, model_name, "exported_full_model")
    print(f"💾 Saving merged model to: {export_path}")
    
    try:
        merged_model.save_pretrained(
            export_path,
            torch_dtype=torch.float16,
            safe_serialization=True
        )
        
        # Save tokenizer
        tokenizer = AutoTokenizer.from_pretrained(base_model_name)
        tokenizer.save_pretrained(export_path)
        
        # Save model info
        save_model_info(export_path, model_name, base_model_name, "merged")
        
        print("✅ Full merged model exported successfully")
        
    except Exception as e:
        print(f"❌ Error saving merged model: {e}")
        return False
    
    return True

def save_model_info(export_path, model_name, base_model_name, export_type):
    """Save model information for future reference"""
    
    info_content = f"""# Model Export Information

## Export Details
- **Original Model**: {model_name}
- **Base Model**: {base_model_name}
- **Export Type**: {export_type}
- **Export Date**: {torch.utils.data.get_worker_info() or 'Unknown'}

## Usage Instructions

### For Adapter Export:
```python
from peft import PeftModel
from transformers import AutoModelForCausalLM

base_model = AutoModelForCausalLM.from_pretrained("{base_model_name}")
model = PeftModel.from_pretrained(base_model, "{export_path}")
```

### For Merged Model Export:
```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model = AutoModelForCausalLM.from_pretrained("{export_path}")
tokenizer = AutoTokenizer.from_pretrained("{export_path}")
```
"""
    
    try:
        with open(os.path.join(export_path, "MODEL_INFO.md"), "w") as f:
            f.write(info_content)
    except Exception as e:
        print(f"⚠️ Could not save model info: {e}")

def list_available_models(models_base_path):
    """List available models in the models directory"""
    
    if not os.path.exists(models_base_path):
        print(f"Models directory not found: {models_base_path}")
        return []
    
    models = []
    for item in os.listdir(models_base_path):
        model_path = os.path.join(models_base_path, item)
        if os.path.isdir(model_path):
            final_model_path = os.path.join(model_path, "final_model")
            if os.path.exists(final_model_path):
                models.append(item)
                print(f"  📁 {item}")
    
    return models

def check_file_sizes(model_name, models_base_path="./llm/models"):
    """Check and display file sizes of exports"""
    
    print("\n📊 File Size Summary:")
    print("-" * 50)
    
    base_path = os.path.join(models_base_path, model_name)
    paths_to_check = [
        os.path.join(base_path, "exported_model_adapters"),
        os.path.join(base_path, "exported_full_model"),
        os.path.join(base_path, "final_model")
    ]
    
    for path in paths_to_check:
        if os.path.exists(path):
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
            
            size_mb = total_size / (1024 * 1024)
            size_gb = size_mb / 1024
            
            if size_gb > 1:
                print(f"{os.path.basename(path)}: {size_gb:.2f} GB")
            else:
                print(f"{os.path.basename(path)}: {size_mb:.2f} MB")
        else:
            print(f"{os.path.basename(path)}: Not found")

def interactive_mode():
    """Interactive mode for selecting model and base model"""
    
    print("🔍 Interactive Mode")
    print("=" * 30)
    
    # Get models base path
    models_base_path = input("📁 Models base path (default: ./llm/models): ").strip()
    if not models_base_path:
        models_base_path = "./llm/models"
    
    # List available models
    print(f"\n📋 Available models in {models_base_path}:")
    available_models = list_available_models(models_base_path)
    
    if not available_models:
        print("❌ No models found with final_model directory")
        return None, None, None
    
    # Get model name
    while True:
        model_name = input(f"\n🎯 Enter model name: ").strip()
        if model_name in available_models:
            break
        elif model_name == "":
            print("❌ Model name cannot be empty")
        else:
            print(f"❌ Model '{model_name}' not found. Available: {', '.join(available_models)}")
    
    # Get base model name
    common_base_models = [
        "meta-llama/Llama-3.2-3B-Instruct",
        "meta-llama/Llama-3.2-1B-Instruct", 
        "meta-llama/Llama-2-7b-hf",
        "meta-llama/Llama-2-7b-chat-hf"
    ]
    
    print(f"\n🤖 Common base models:")
    for i, model in enumerate(common_base_models, 1):
        print(f"  {i}. {model}")
    
    base_model_name = input(f"\n🎯 Enter base model name (or number 1-{len(common_base_models)}): ").strip()
    
    # Handle numeric selection
    if base_model_name.isdigit():
        idx = int(base_model_name) - 1
        if 0 <= idx < len(common_base_models):
            base_model_name = common_base_models[idx]
        else:
            print("❌ Invalid selection, using default")
            base_model_name = common_base_models[0]
    elif not base_model_name:
        base_model_name = common_base_models[0]
    
    return model_name, base_model_name, models_base_path

def main():
    parser = argparse.ArgumentParser(
        description="Export LLM LoRA models with flexible parameters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python export_model_llm.py
  
  # Command line mode
  python export_model_llm.py --model continued-llama-carla --base-model meta-llama/Llama-3.2-3B-Instruct
  
  # With custom models path
  python export_model_llm.py --model my-model --base-model meta-llama/Llama-2-7b-hf --models-path /path/to/models
  
  # Export both adapters and merged model
  python export_model_llm.py --model continued-llama-carla --base-model meta-llama/Llama-3.2-3B-Instruct --export-merged
        """
    )
    
    parser.add_argument(
        "--model", "-m",
        type=str,
        help="Name of the model directory (e.g., 'continued-llama-carla')"
    )
    
    parser.add_argument(
        "--base-model", "-b",
        type=str,
        help="Base model name (e.g., 'meta-llama/Llama-3.2-3B-Instruct')"
    )
    
    parser.add_argument(
        "--models-path", "-p",
        type=str,
        default="./llm/models",
        help="Base path to models directory (default: ./llm/models)"
    )
    
    parser.add_argument(
        "--export-merged",
        action="store_true",
        help="Also export the full merged model (in addition to adapters)"
    )
    
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available models and exit"
    )
    
    args = parser.parse_args()
    
    print("🎯 LLM Model Export Tool")
    print("=" * 50)
    
    # Handle list models command
    if args.list_models:
        print(f"📋 Available models in {args.models_path}:")
        list_available_models(args.models_path)
        return
    
    # Get parameters (command line or interactive)
    if args.model and args.base_model:
        model_name = args.model
        base_model_name = args.base_model
        models_base_path = args.models_path
        print(f"📁 Using command line parameters:")
        print(f"   Model: {model_name}")
        print(f"   Base Model: {base_model_name}")
        print(f"   Models Path: {models_base_path}")
    else:
        model_name, base_model_name, models_base_path = interactive_mode()
        if not model_name:
            print("❌ Exiting...")
            return
    
    # Export LoRA adapters (always)
    print(f"\n🔧 STEP 1: Export LoRA Adapters (Lightweight)")
    success_adapters = export_lora_adapters(model_name, base_model_name, models_base_path)
    
    # Export merged model (if requested or user confirms)
    export_merged = args.export_merged
    if success_adapters and not export_merged:
        print(f"\n❓ Do you also want to export the full merged model? (y/n): ", end="")
        user_input = input().strip().lower()
        export_merged = user_input in ['y', 'yes']
    
    if export_merged and success_adapters:
        print(f"\n🔧 STEP 2: Export Full Merged Model (Larger)")
        export_merged_model(model_name, base_model_name, models_base_path)
    
    # Show file size summary
    check_file_sizes(model_name, models_base_path)
    
    print(f"\n🎉 Export process completed!")
    print(f"\nNext steps:")
    print(f"1. Use the 'exported_model_adapters' for lightweight deployment")
    print(f"2. The adapter files are only a few MB vs GB for full model")
    print(f"3. Check MODEL_INFO.md in export directories for usage instructions")

if __name__ == "__main__":
    main()