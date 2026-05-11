curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"

uv venv trl_env --python 3.11
source trl_env/bin/activate

uv pip install trl transformers accelerate datasets peft bitsandbytes wandb

uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
uv pip install -U kernels

#accelerate launch --config_file fsdp_config.yaml train.py