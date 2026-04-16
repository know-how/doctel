"""
Training configuration – extends the main app config for LoRA/QLoRA settings.
All paths are resolved relative to settings.base_dir (default: C:\\LocalAI).
"""
from pathlib import Path
from typing import Optional
from pydantic import BaseModel


class LoraConfig(BaseModel):
    """LoRA adapter hyper-parameters."""
    r: int = 8                         # LoRA rank
    lora_alpha: int = 16               # LoRA alpha scaling
    lora_dropout: float = 0.05
    target_modules: list[str] = ["q_proj", "v_proj"]
    bias: str = "none"
    task_type: str = "CAUSAL_LM"


class TrainingRunConfig(BaseModel):
    """Runtime training parameters – safe for an i7-10510U + 16GB RAM."""
    num_train_epochs: int = 1
    per_device_train_batch_size: int = 1
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-4
    max_steps: int = 200              # cap to keep jobs short
    save_steps: int = 50
    logging_steps: int = 10
    fp16: bool = False                 # CPU – always False
    bf16: bool = False
    optim: str = "adamw_torch"
    warmup_ratio: float = 0.05
    lr_scheduler_type: str = "cosine"
    max_seq_length: int = 512          # keep low for 16 GB RAM


class TrainingSettings(BaseModel):
    """Overall training module settings."""
    # Folder layout (relative to base_dir)
    training_room_subdir: str = "training_room"
    inbox_subdir: str = "inbox"
    batches_subdir: str = "batches"
    teacher_samples_subdir: str = "teacher_samples"
    web_samples_subdir: str = "web_samples"
    model_state_subdir: str = "model_state"

    # Base models for transfer learning (multiple model support)
    # All three models will be trained on the same dataset using LoRA adapters
    base_models: list[str] = [
        "meta-llama/Llama-3.2-3B-Instruct",
        "meta-llama/Llama-3.2-8B-Instruct",
        "Qwen/Qwen2.5-7B-Instruct",
    ]

    # Primary base model (the .gguf is for inference; PEFT works on HF safetensors)
    # Switched to Meta-Llama 3.2 3B Instruct as the core local model
    hf_base_model: str = "meta-llama/Llama-3.2-3B-Instruct"

    # Minimum free RAM (MB) before an idle-training job starts
    min_free_ram_for_training_mb: int = 4096

    # LoRA and run settings
    lora: LoraConfig = LoraConfig()
    run: TrainingRunConfig = TrainingRunConfig()

    # If True, quantise the base model with BitsAndBytes (requires bitsandbytes)
    use_4bit_qlora: bool = False


# Default singleton used across the training module
default_training_settings = TrainingSettings()


def get_training_paths(base_dir: str, ts: TrainingSettings | None = None) -> dict[str, Path]:
    """Return resolved absolute paths for all training_room sub-folders."""
    if ts is None:
        ts = default_training_settings
    
    # Resolve the physical Doctel project directory
    project_root = Path(__file__).resolve().parent.parent.parent
    
    # doctel/training/ workspace
    root = project_root / "training"
    
    # doctel/models/llama_local/
    llama_local_dir = project_root / "models" / "llama_local"
    
    paths = {
        "root": root,
        "inbox": root / ts.inbox_subdir,
        "batches": root / ts.batches_subdir,
        "teacher_samples": root / ts.teacher_samples_subdir,
        "web_samples": root / ts.web_samples_subdir,
        "model_state": llama_local_dir / "adapters",
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return paths
