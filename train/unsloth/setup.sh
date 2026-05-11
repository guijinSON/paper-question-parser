
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv unsloth_env --python 3.13
source unsloth_env/bin/activate
uv pip install unsloth --torch-backend=auto

python -m ensurepip --upgrade
python -m pip install -U pip setuptools wheel
python -m pip install -U wandb

#torchrun --standalone --nproc_per_node=2 run.py