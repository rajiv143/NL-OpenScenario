# 🚀 Quick Start Guide - Python 3.7 Setup

## ✅ Installation Complete!

Your system is now ready for CARLA scenario model training with:
- **Python 3.7.5** 
- **NVIDIA RTX 3090** (24GB VRAM)
- **CUDA 11.7** support
- All required packages installed

## 🎯 Recommended Training Commands

### Option 1: GPT-2 (Fast, Proven)
```bash
# Train with GPT-2 - most compatible and reliable
python train_llama_carla_py37.py --model gpt2 --epochs 3 --batch-size 4
```

### Option 2: GPT-2 Medium (Better Quality)
```bash
# Larger model, better results
python train_llama_carla_py37.py --model gpt2-medium --epochs 3 --batch-size 2
```

### Option 3: GPT-Neo (Advanced)
```bash
# Modern architecture, good performance
python train_llama_carla_py37.py --model EleutherAI/gpt-neo-125M --epochs 3 --batch-size 4
```

## 📋 Step-by-Step Training Process

### 1. Verify Training Data
```bash
# Your data is already prepared (443 examples)
ls train_dataset.json val_dataset.json test_dataset.json
```

### 2. Start Training
```bash
# Recommended for your setup:
python train_llama_carla_py37.py \
    --model gpt2-medium \
    --epochs 5 \
    --batch-size 2 \
    --learning-rate 5e-4 \
    --output-dir ./carla-gpt2-model
```

### 3. Monitor Progress
Training will show:
- Loss decreasing over time
- Validation metrics
- GPU memory usage
- ETA for completion

### 4. Expected Training Time
- **GPT-2**: ~45 minutes
- **GPT-2 Medium**: ~90 minutes  
- **GPT-Neo 125M**: ~60 minutes

## 📊 Your System Specs
```
GPU: NVIDIA RTX 3090 (24GB) ✅
CUDA: 11.7 ✅
Python: 3.7.5 ✅
PyTorch: 1.13.1+cu117 ✅
Memory: Excellent for training ✅
```

## 🛠️ Troubleshooting

### If Training Runs Out of Memory:
```bash
# Reduce batch size
python train_llama_carla_py37.py --model gpt2 --batch-size 1

# Or use smaller model
python train_llama_carla_py37.py --model distilgpt2 --batch-size 4
```

### If Training is Slow:
```bash
# Use smaller model for faster training
python train_llama_carla_py37.py --model gpt2 --epochs 3
```

## 🎉 After Training

### Test Your Model:
```bash
# Create simple inference script
python -c "
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

# Load your trained model
base_model = AutoModelForCausalLM.from_pretrained('gpt2')
model = PeftModel.from_pretrained(base_model, './carla-gpt2-model/final_model')
tokenizer = AutoTokenizer.from_pretrained('./carla-gpt2-model/final_model')

# Test generation
prompt = 'Generate a CARLA scenario JSON based on this description: A red car stops ahead'
inputs = tokenizer(prompt, return_tensors='pt')
outputs = model.generate(**inputs, max_length=200)
print(tokenizer.decode(outputs[0]))
"
```

## 💡 Tips for Best Results

1. **Start with GPT-2 Medium** - Good balance of quality/speed
2. **Use batch size 2-4** - Optimal for your 24GB GPU
3. **Train for 3-5 epochs** - Usually sufficient
4. **Monitor validation loss** - Should decrease steadily
5. **Save checkpoints** - Automatically saved every 100 steps

## 🔧 Alternative Models Available

| Model | Size | Training Time | Quality | Memory |
|-------|------|---------------|---------|---------|
| `distilgpt2` | 82M | 30 min | Good | 2GB |
| `gpt2` | 124M | 45 min | Better | 3GB |
| `gpt2-medium` | 355M | 90 min | Best | 6GB |
| `EleutherAI/gpt-neo-125M` | 125M | 60 min | Better | 4GB |

## 🎯 Ready to Start!

Your setup is optimized and ready. Run this command to begin:

```bash
python train_llama_carla_py37.py --model gpt2-medium --epochs 5 --batch-size 2
```

Training will begin automatically and save your model to `./carla-gpt2-model/final_model/`