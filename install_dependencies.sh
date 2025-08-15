#!/bin/bash

echo "======================================"
echo "CARLA Llama Training - Dependency Installer"
echo "======================================"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | grep -Po '(?<=Python )\d+\.\d+')
echo "Python version: $python_version"

# Check for CUDA
echo ""
echo "Checking for CUDA..."
if command_exists nvidia-smi; then
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
    cuda_available=true
else
    echo "CUDA not detected. CPU-only installation will be used."
    cuda_available=false
fi

echo ""
echo "======================================"
echo "Step 1: Installing PyTorch"
echo "======================================"

if [ "$cuda_available" = true ]; then
    echo "Installing PyTorch with CUDA support..."
    # CUDA 11.8 version (most compatible)
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
else
    echo "Installing PyTorch CPU version..."
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
fi

echo ""
echo "======================================"
echo "Step 2: Installing Core Dependencies"
echo "======================================"

# Install transformers and related packages
pip install transformers==4.36.2
pip install datasets==2.14.0
pip install accelerate==0.25.0
pip install peft==0.7.1

echo ""
echo "======================================"
echo "Step 3: Installing Utilities"
echo "======================================"

pip install scikit-learn tqdm numpy sentencepiece protobuf

echo ""
echo "======================================"
echo "Step 4: Installing Optional Dependencies"
echo "======================================"

# Try to install bitsandbytes (may fail on some systems)
if [ "$cuda_available" = true ]; then
    echo "Attempting to install bitsandbytes for 4-bit quantization..."
    pip install bitsandbytes==0.41.3 || echo "Warning: bitsandbytes installation failed. 4-bit quantization will not be available."
fi

# Install wandb for logging
pip install wandb || echo "Warning: wandb installation failed. Logging will not be available."

echo ""
echo "======================================"
echo "Installation Complete!"
echo "======================================"

# Verify installation
echo ""
echo "Verifying installation..."
python3 -c "
import sys
print('Python:', sys.version)
try:
    import torch
    print(f'PyTorch: {torch.__version__}')
    print(f'CUDA available: {torch.cuda.is_available()}')
    if torch.cuda.is_available():
        print(f'CUDA version: {torch.version.cuda}')
        print(f'GPU: {torch.cuda.get_device_name(0)}')
except ImportError:
    print('ERROR: PyTorch not installed correctly')
    
try:
    import transformers
    print(f'Transformers: {transformers.__version__}')
except ImportError:
    print('ERROR: Transformers not installed')
    
try:
    import peft
    print(f'PEFT: {peft.__version__}')
except ImportError:
    print('ERROR: PEFT not installed')
    
try:
    import accelerate
    print(f'Accelerate: {accelerate.__version__}')
except ImportError:
    print('ERROR: Accelerate not installed')
    
try:
    import bitsandbytes
    print(f'Bitsandbytes: {bitsandbytes.__version__} (4-bit support available)')
except ImportError:
    print('Warning: Bitsandbytes not available (4-bit quantization disabled)')
"

echo ""
echo "======================================"
echo "Next Steps:"
echo "======================================"
echo "1. If installation succeeded, you can now run:"
echo "   python prepare_training_data.py"
echo "   python train_llama_carla.py --model meta-llama/Llama-3.2-1B-Instruct"
echo ""
echo "2. If you encountered errors, try:"
echo "   - Create a virtual environment: python -m venv venv"
echo "   - Activate it: source venv/bin/activate"
echo "   - Re-run this script"
echo "======================================="