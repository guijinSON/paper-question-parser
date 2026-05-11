# train.py

from datasets import load_dataset
from trl import SFTConfig, SFTTrainer
from utils import generate_conversation
from datasets import load_dataset, Dataset
from transformers import AutoTokenizer
from tqdm import tqdm


MODEL_NAME = "Qwen/Qwen3-0.6B-Base"
OUTPUT_DIR = "qwen3-sft-fsdp"
NUM_PROC = 4
sample_train = 100
MAX_LENGTH = 32768

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)


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
    model=MODEL_NAME,
    train_dataset=combined_dataset,
    args=SFTConfig(
        output_dir=OUTPUT_DIR,
        dataset_num_proc=4,
        
        # Training
        max_length = MAX_LENGTH,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=5e-5,
        warmup_ratio=0.03,
        max_steps=100,
        lr_scheduler_type="cosine",
        optim = "adamw_torch_fused",
        
        # Memory
        gradient_checkpointing=False,

        # Precision
        bf16=True,

        # Logging and saving
        logging_steps=1,
        save_strategy="steps",
        save_steps=50,
        save_total_limit=2,

        # FSDP/Trainer stability
        ddp_find_unused_parameters=False,

        report_to="wandb",

        # Speed up
        model_init_kwargs={"attn_implementation": "kernels-community/flash-attn2"},
        use_liger_kernel=True,
        loss_type="chunked_nll"
    ),
)

trainer.train()
trainer.save_model(OUTPUT_DIR)