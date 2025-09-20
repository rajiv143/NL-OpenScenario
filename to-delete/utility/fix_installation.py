#!/usr/bin/env python3
"""
Diagnostic and fix script for installation issues
"""

import subprocess
import sys
import platform
import os

def run_command(cmd):
    """Run a command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.returncode
    except Exception as e:
        return str(e), 1

def check_system():
    """Check system configuration"""
    print("="*60)
    print("System Information")
    print("="*60)
    
    # Python version
    print(f"Python: {sys.version}")
    print(f"Platform: {platform.platform()}")
    print(f"Architecture: {platform.machine()}")
    
    # Check CUDA
    print("\nChecking CUDA...")
    cuda_output, cuda_code = run_command("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader")
    if cuda_code == 0:
        print(f"GPU detected: {cuda_output}")
        
        # Check CUDA version
        cuda_version, _ = run_command("nvcc --version | grep 'release' | sed 's/.*release //' | sed 's/,.*//'")
        if cuda_version:
            print(f"CUDA version: {cuda_version}")
    else:
        print("No CUDA/GPU detected - CPU only mode")
    
    print("\n" + "="*60)

def check_packages():
    """Check which packages are installed"""
    print("Checking installed packages...")
    print("="*60)
    
    packages = [
        "torch",
        "transformers", 
        "datasets",
        "accelerate",
        "peft",
        "bitsandbytes",
        "scikit-learn",
        "wandb"
    ]
    
    installed = []
    missing = []
    
    for package in packages:
        try:
            __import__(package.replace("-", "_"))
            installed.append(package)
            # Get version
            if package == "scikit-learn":
                import sklearn
                version = sklearn.__version__
            else:
                mod = __import__(package.replace("-", "_"))
                version = getattr(mod, "__version__", "unknown")
            print(f"✓ {package}: {version}")
        except ImportError:
            missing.append(package)
            print(f"✗ {package}: NOT INSTALLED")
    
    return installed, missing

def suggest_fixes(missing):
    """Suggest fixes for missing packages"""
    if not missing:
        print("\n✓ All packages installed successfully!")
        return
    
    print("\n" + "="*60)
    print("Suggested Fixes")
    print("="*60)
    
    print("\nOption 1: Manual Installation (Recommended)")
    print("-" * 40)
    
    # Check if CUDA is available
    try:
        import torch
        has_cuda = torch.cuda.is_available()
    except:
        has_cuda = False
    
    if "torch" in missing:
        print("\n# Install PyTorch first:")
        if has_cuda or "nvidia" in platform.platform().lower():
            print("pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")
        else:
            print("pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu")
    
    if "transformers" in missing or "peft" in missing:
        print("\n# Install Hugging Face packages:")
        print("pip install transformers==4.36.2 datasets==2.14.0 accelerate==0.25.0 peft==0.7.1")
    
    if "bitsandbytes" in missing:
        print("\n# For 4-bit quantization (optional, CUDA required):")
        print("pip install bitsandbytes==0.41.3")
        print("# If this fails, training will still work without 4-bit mode")
    
    print("\n\nOption 2: Use Virtual Environment")
    print("-" * 40)
    print("""
# Create fresh environment
python -m venv llama_env
source llama_env/bin/activate  # On Windows: llama_env\\Scripts\\activate

# Install packages
pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install transformers datasets accelerate peft scikit-learn
""")
    
    print("\nOption 3: Use Conda")
    print("-" * 40)
    print("""
# Create conda environment from provided file
conda env create -f install_conda.yml
conda activate carla-llama
""")
    
    print("\nOption 4: Google Colab")
    print("-" * 40)
    print("""
If local installation fails, use Google Colab:
1. Upload your files to Google Drive
2. Open Google Colab (colab.research.google.com)
3. Run this in a cell:

!pip install transformers datasets accelerate peft bitsandbytes
from google.colab import drive
drive.mount('/content/drive')
""")

def test_import():
    """Test if we can import and use the packages"""
    print("\n" + "="*60)
    print("Testing Package Imports")
    print("="*60)
    
    try:
        print("Testing PyTorch...")
        import torch
        print(f"✓ PyTorch {torch.__version__}")
        print(f"  CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"  GPU: {torch.cuda.get_device_name(0)}")
            print(f"  Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    except Exception as e:
        print(f"✗ PyTorch error: {e}")
        return False
    
    try:
        print("\nTesting Transformers...")
        from transformers import AutoTokenizer
        print("✓ Transformers import successful")
    except Exception as e:
        print(f"✗ Transformers error: {e}")
        return False
    
    try:
        print("\nTesting PEFT...")
        from peft import LoraConfig
        print("✓ PEFT import successful")
    except Exception as e:
        print(f"✗ PEFT error: {e}")
        return False
    
    print("\n✓ All critical imports successful!")
    return True

def main():
    print("\n" + "="*60)
    print("CARLA Llama Training - Installation Diagnostic")
    print("="*60)
    
    # Check system
    check_system()
    
    # Check packages
    installed, missing = check_packages()
    
    # Suggest fixes
    suggest_fixes(missing)
    
    # Test imports if possible
    if not missing or (len(missing) == 1 and "bitsandbytes" in missing):
        if test_import():
            print("\n" + "="*60)
            print("✓ Ready to train!")
            print("="*60)
            print("\nYou can now run:")
            print("  python prepare_training_data.py")
            print("  python train_llama_carla.py --model meta-llama/Llama-3.2-1B-Instruct")
            
            if "bitsandbytes" in missing:
                print("\nNote: 4-bit quantization unavailable. Add --no-4bit flag:")
                print("  python train_llama_carla.py --no-4bit")
    else:
        print("\n" + "="*60)
        print("⚠ Installation incomplete")
        print("="*60)
        print("Please follow the suggested fixes above.")

if __name__ == "__main__":
    main()