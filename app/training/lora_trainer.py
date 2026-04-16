"""
lora_trainer.py – LoRA/QLoRA fine-tuning using HuggingFace PEFT + Transformers.

Gracefully degrades if peft/transformers are not installed:
  - The _peft_available flag is set to False
  - Training endpoints return a descriptive error instead of crashing

Hardware target: Intel i7-10510U, 16 GB RAM, 2 GB GPU
Safe defaults: TinyLlama-1.1B or Llama-3.2-3B, batch=1, grad_acc=4, max_steps=200
"""
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# ── soft-import peft / transformers ───────────────────────────────────────────
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, TrainerCallback
    from peft import LoraConfig as PeftLoraConfig, get_peft_model, TaskType
    _peft_available = True
    logger.info("PEFT + Transformers available – LoRA training enabled")
except ImportError:
    _peft_available = False
    logger.warning(
        "peft / transformers not installed. LoRA training is disabled. "
        "Install with: pip install peft transformers datasets"
    )

try:
    from datasets import Dataset as HFDataset
    _datasets_available = True
except ImportError:
    _datasets_available = False


# ── progress callback ─────────────────────────────────────────────────────────

class ProgressCallback:
    """Thread-safe progress reporter."""
    def __init__(self, on_progress: Optional[Callable[[float, str], None]] = None):
        self.progress = 0.0
        self.message = "initialising"
        self._on_progress = on_progress
        self._lock = threading.Lock()

    def update(self, progress: float, message: str = "") -> None:
        with self._lock:
            self.progress = min(1.0, max(0.0, progress))
            self.message = message
        if self._on_progress:
            self._on_progress(self.progress, self.message)


# ── main trainer ──────────────────────────────────────────────────────────────

def is_available() -> bool:
    return _peft_available and _datasets_available


def run_lora_training(
    batch_path: Path,
    adapter_output_dir: Path,
    hf_base_model: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    lora_r: int = 8,
    lora_alpha: int = 16,
    lora_dropout: float = 0.05,
    max_steps: int = 200,
    per_device_batch: int = 1,
    grad_acc: int = 4,
    learning_rate: float = 2e-4,
    max_seq_length: int = 512,
    use_4bit: bool = False,
    progress_cb: Optional[ProgressCallback] = None,
) -> dict:
    """
    Fine-tune hf_base_model on batch_path using LoRA.
    Returns a result dict with 'ok', 'adapter_path', 'samples', 'steps', 'error'.
    """
    if not is_available():
        return {
            "ok": False,
            "error": (
                "peft/transformers/datasets not installed. "
                "Run: pip install peft transformers datasets"
            ),
        }

    if progress_cb is None:
        progress_cb = ProgressCallback()

    # ── load dataset ──────────────────────────────────────────────────────────
    progress_cb.update(0.02, "loading dataset")
    try:
        raw = []
        with open(batch_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    raw.append(json.loads(line))
        if not raw:
            return {"ok": False, "error": "Batch file is empty"}
        dataset = HFDataset.from_list(raw)
        samples = len(dataset)
        logger.info("Loaded %d training pairs from %s", samples, batch_path.name)
    except Exception as e:
        return {"ok": False, "error": f"Dataset load failed: {e}"}

    # ── load tokeniser ────────────────────────────────────────────────────────
    progress_cb.update(0.05, "loading tokeniser")
    try:
        tokenizer = AutoTokenizer.from_pretrained(hf_base_model, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
    except Exception as e:
        return {"ok": False, "error": f"Tokeniser load failed: {e}"}

    # ── tokenise ──────────────────────────────────────────────────────────────
    progress_cb.update(0.10, "tokenising")
    def tokenise(example):
        text = f"{example['prompt']}\n{example['completion']}"
        enc = tokenizer(
            text,
            truncation=True,
            max_length=max_seq_length,
            padding="max_length",
        )
        enc["labels"] = enc["input_ids"].copy()
        return enc

    try:
        tokenised = dataset.map(tokenise, remove_columns=["prompt", "completion"])
    except Exception as e:
        return {"ok": False, "error": f"Tokenisation failed: {e}"}

    # ── load base model ───────────────────────────────────────────────────────
    progress_cb.update(0.15, "loading base model")
    try:
        load_kwargs: dict = {"trust_remote_code": True, "torch_dtype": torch.float32}
        if use_4bit:
            try:
                from transformers import BitsAndBytesConfig
                bnb_cfg = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )
                load_kwargs["quantization_config"] = bnb_cfg
            except ImportError:
                logger.warning("bitsandbytes not installed – running without 4-bit quantisation")
        model = AutoModelForCausalLM.from_pretrained(hf_base_model, **load_kwargs)
    except Exception as e:
        return {"ok": False, "error": f"Base model load failed: {e}"}

    # ── apply LoRA ────────────────────────────────────────────────────────────
    progress_cb.update(0.20, "applying LoRA")
    try:
        lora_cfg = PeftLoraConfig(
            r=lora_r,
            lora_alpha=lora_alpha,
            lora_dropout=lora_dropout,
            target_modules=["q_proj", "v_proj"],
            task_type=TaskType.CAUSAL_LM,
            bias="none",
        )
        model = get_peft_model(model, lora_cfg)
        model.print_trainable_parameters()
    except Exception as e:
        return {"ok": False, "error": f"LoRA setup failed: {e}"}

    # ── training arguments ────────────────────────────────────────────────────
    progress_cb.update(0.22, "starting training")
    adapter_output_dir.mkdir(parents=True, exist_ok=True)
    try:
        from transformers import Trainer, DataCollatorForLanguageModeling

        training_args = TrainingArguments(
            output_dir=str(adapter_output_dir),
            num_train_epochs=1,
            per_device_train_batch_size=per_device_batch,
            gradient_accumulation_steps=grad_acc,
            learning_rate=learning_rate,
            max_steps=max_steps,
            save_steps=max(50, max_steps // 4),
            logging_steps=10,
            fp16=False,
            bf16=False,
            optim="adamw_torch",
            warmup_ratio=0.05,
            lr_scheduler_type="cosine",
            report_to="none",
            no_cuda=not torch.cuda.is_available(),
            dataloader_num_workers=0,
        )

        class _ProgressHook(TrainerCallback):
            def __init__(self, cb: ProgressCallback, total_steps: int):
                self._cb = cb
                self._total = max(1, total_steps)

            def on_step_end(self, args, state, control, **kwargs):
                frac = 0.22 + (state.global_step / self._total) * 0.70
                self._cb.update(frac, f"step {state.global_step}/{self._total}")

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=tokenised,
            data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
            callbacks=[_ProgressHook(progress_cb, max_steps)],
        )
        trainer.train()
    except Exception as e:
        logger.exception("Training loop failed")
        return {"ok": False, "error": f"Training failed: {e}"}

    # ── save adapter ──────────────────────────────────────────────────────────
    progress_cb.update(0.95, "saving adapter")
    try:
        model.save_pretrained(str(adapter_output_dir))
        tokenizer.save_pretrained(str(adapter_output_dir))
        logger.info("Adapter saved to %s", adapter_output_dir)
    except Exception as e:
        return {"ok": False, "error": f"Save failed: {e}"}

    progress_cb.update(1.0, "done")
    return {
        "ok": True,
        "adapter_path": str(adapter_output_dir),
        "samples": samples,
        "steps": max_steps,
    }
