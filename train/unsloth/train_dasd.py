import torch
from unsloth import FastLanguageModel
from unsloth.chat_templates import (
    get_chat_template,
)
import pandas as pd
from utils import generate_conversation
from datasets import load_dataset, Dataset
from trl import SFTTrainer, SFTConfig
from transformers import TextStreamer
from tqdm import tqdm
import os
import torch

local_rank = int(os.environ.get("LOCAL_RANK", 0))
torch.cuda.set_device(local_rank)

MAX_LENGTH = 32768
NUM_PROC = 16
sample_train = None #100

HF_TOKEN = os.environ.get("HF_TOKEN")
HF_USER_NAME = "amphora"

MODEL_NAME = "Qwen/Qwen3-4B-Instruct-2507"
save_to = "Qwen3-4B-DASD-32K"

generate_after_train = True

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = MODEL_NAME,
    max_seq_length = MAX_LENGTH,   # Context length - can be longer, but uses more memory
    load_in_4bit = False,     # 4bit uses much less memory
    load_in_8bit = False,    # A bit more accurate, uses 2x memory
    full_finetuning = True, # We have full finetuning now!
    # device_map = "balanced", # Uses 2x Telsa T4s
     # unsloth_tiled_mlp = True,
    use_gradient_checkpointing="unsloth",
    device_map={"": local_rank}
)

tokenizer = get_chat_template(tokenizer, chat_template = "qwen3")


reasoning_dataset = load_dataset("Alibaba-Apsara/Superior-Reasoning-SFT-gpt-oss-120b", "stage1",split='train')
mapped_dataset = reasoning_dataset.map(generate_conversation, batched=True)

reasoning_conversations = [
    tokenizer.apply_chat_template(
        conversation,
        tokenize=False,
    )
    for conversation in tqdm(mapped_dataset["conversations"])
]

text_dataset = Dataset.from_dict({
    "text": reasoning_conversations
})
    
if sample_train:
    text_dataset = text_dataset.select(range(sample_train))

def tokenize_batch(batch):
    tokenized = tokenizer(
        batch["text"],
        add_special_tokens=False,
        truncation=False,
    )
    tokenized["num_tokens"] = [len(ids) for ids in tokenized["input_ids"]]
    return tokenized

tokenized_dataset = text_dataset.map(
    tokenize_batch,
    batched=True,
    num_proc=NUM_PROC,
    remove_columns=["text"],
    desc="Tokenizing dataset",
)

before = len(tokenized_dataset)

tokenized_dataset = tokenized_dataset.filter(
    lambda example: example["num_tokens"] <= MAX_LENGTH,
    num_proc=NUM_PROC,
    desc=f"Dropping examples longer than {MAX_LENGTH}",
)

after = len(tokenized_dataset)

print('='*80)
print(f"Dropped {before - after} examples longer than {MAX_LENGTH} tokens")
print(f"Kept {after} examples")
print('='*80)
      
tokenized_dataset = tokenized_dataset.remove_columns(["num_tokens"])

combined_dataset = tokenized_dataset.shuffle(seed=1210)

print(combined_dataset[0])
print("data loaded")

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = combined_dataset,
    eval_dataset = None, # Can set up evaluation!
    args = SFTConfig(
        dataset_text_field = "text",
        max_length = MAX_LENGTH,
        dataset_num_proc=4,
        per_device_train_batch_size = 1,
        gradient_accumulation_steps = 64, # Use GA to mimic batch size!
        # warmup_steps = 5,
        warmup_ratio = 0.05,
        num_train_epochs = 3, # Set this for 1 full training run.
        # max_steps = 100,
        learning_rate = 5e-5,
        logging_steps = 1,
        optim = "adamw_torch_fused",
        weight_decay = 0.001,
        lr_scheduler_type = "cosine",
        seed = 1210,
        # packing = True,
        report_to = "wandb", # Use TrackIO/WandB etc
        save_strategy = "steps",
        save_steps = 300,
        save_total_limit = 2,
    ),
)


trainer.train()

if generate_after_train:
    messages = [
        {"role" : "user", "content" : "Solve (x + 2)^2 = 0."}
    ]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize = False,
        add_generation_prompt = True, # Must add for generation
        enable_thinking = False, # Disable thinking
    )
    
    from transformers import TextStreamer
    _ = model.generate(
        **tokenizer(text, return_tensors = "pt").to("cuda"),
        max_new_tokens = 256, # Increase for longer outputs!
        temperature = 0.7, top_p = 0.8, top_k = 20, # For non thinking
        streamer = TextStreamer(tokenizer, skip_prompt = True),
    )
    
    
    messages = [
        {"role" : "user", "content" : "Solve (x + 2)^2 = 0."}
    ]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize = False,
        add_generation_prompt = True, # Must add for generation
        enable_thinking = True, # Disable thinking
    )
    
    from transformers import TextStreamer
    _ = model.generate(
        **tokenizer(text, return_tensors = "pt").to("cuda"),
        max_new_tokens = 1024, # Increase for longer outputs!
        temperature = 0.6, top_p = 0.95, top_k = 20, # For thinking
        streamer = TextStreamer(tokenizer, skip_prompt = True),
    )


model.push_to_hub(f'{HF_USER_NAME}/{save_to}',token=HF_TOKEN)
model.save_pretrained(save_to)
tokenizer.save_pretrained(save_to)
