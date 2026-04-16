"""
multi_model_trainer.py – Train multiple base models with the same dataset using LoRA.

Orchestrates parallel/sequential training runs across Llama, Qwen, and other models
from a single training batch file. Reports progress and errors per model.
"""
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any

from app.config import settings
from app.training.training_config import default_training_settings, get_training_paths
from app.training.lora_trainer import run_lora_training, is_available as lora_available

logger = logging.getLogger(__name__)


class MultiModelTrainer:
    """Orchestrate training across multiple base models."""
    
    def __init__(self):
        self.base_models = default_training_settings.base_models
        self.training_config = default_training_settings
        self.results: Dict[str, Dict[str, Any]] = {}
    
    async def train_all_models(
        self,
        batch_path: Path,
        sequential: bool = False,
        on_progress: Optional[callable] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Train all configured base models on the provided batch.
        
        Args:
            batch_path: Path to JSONL training batch file
            sequential: If True, train models one-at-a-time; else train in parallel
            on_progress: Optional callback(model_name, progress_0_to_1, message)
        
        Returns:
            Dictionary mapping model names to their training result dicts
            {
                "meta-llama/Llama-3.2-3B-Instruct": {"ok": True, "adapter_path": "...", ...},
                "Qwen/Qwen2.5-7B-Instruct": {"ok": False, "error": "OOM", ...},
            }
        """
        if not lora_available():
            return {
                "error": "PEFT/Transformers not installed. Run: pip install peft transformers datasets"
            }
        
        batch_path = Path(batch_path)
        if not batch_path.exists():
            raise FileNotFoundError(f"Batch file not found: {batch_path}")
        
        logger.info(f"Starting multi-model training on {len(self.base_models)} models")
        logger.info(f"Batch file: {batch_path}")
        logger.info(f"Sequential mode: {sequential}")
        
        if sequential:
            await self._train_sequential(batch_path, on_progress)
        else:
            await self._train_parallel(batch_path, on_progress)
        
        return self.results
    
    async def _train_sequential(
        self,
        batch_path: Path,
        on_progress: Optional[callable] = None,
    ) -> None:
        """Train models one at a time."""
        for i, model in enumerate(self.base_models):
            model_idx = i + 1
            logger.info(f"[{model_idx}/{len(self.base_models)}] Training {model}...")
            
            if on_progress:
                on_progress(model, 0.0, f"Initializing {model}")
            
            result = await self._train_single_model(model, batch_path, on_progress)
            self.results[model] = result
            
            status = "✅ OK" if result.get("ok") else "❌ FAILED"
            logger.info(f"[{model_idx}/{len(self.base_models)}] {model}: {status}")
            
            if not result.get("ok"):
                logger.error(f"  Error: {result.get('error')}")
    
    async def _train_parallel(
        self,
        batch_path: Path,
        on_progress: Optional[callable] = None,
    ) -> None:
        """Train models in parallel (resource-constrained, may OOM)."""
        logger.warning("Parallel training may cause OOM; consider sequential mode")
        
        tasks = [
            self._train_single_model(model, batch_path, on_progress)
            for model in self.base_models
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for model, result in zip(self.base_models, results):
            if isinstance(result, Exception):
                self.results[model] = {"ok": False, "error": str(result)}
            else:
                self.results[model] = result
    
    async def _train_single_model(
        self,
        model: str,
        batch_path: Path,
        on_progress: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Train a single model.
        
        Args:
            model: HuggingFace model identifier
            batch_path: Path to JSONL batch
            on_progress: Optional progress callback
        
        Returns:
            Result dict with 'ok', 'adapter_path', 'samples', 'steps', 'error'
        """
        try:
            # Determine adapter output directory
            model_short = model.split("/")[-1]
            paths = get_training_paths(settings.base_dir, self.training_config)
            
            adapter_dir = (
                Path(paths.get("model_state_subdir") or settings.base_dir)
                / model_short
                / "adapter"
            )
            adapter_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"  Adapter output: {adapter_dir}")
            
            # Wrapper progress callback
            def _wrapped_progress(progress: float, message: str) -> None:
                if on_progress:
                    on_progress(model, progress, message)
            
            # Train with PEFT/Transformers
            result = run_lora_training(
                batch_path=batch_path,
                adapter_output_dir=adapter_dir,
                hf_base_model=model,
                lora_r=self.training_config.lora.r,
                lora_alpha=self.training_config.lora.lora_alpha,
                lora_dropout=self.training_config.lora.lora_dropout,
                max_steps=self.training_config.run.max_steps,
                per_device_batch=self.training_config.run.per_device_train_batch_size,
                grad_acc=self.training_config.run.gradient_accumulation_steps,
                learning_rate=self.training_config.run.learning_rate,
                max_seq_length=self.training_config.run.max_seq_length,
                use_4bit=self.training_config.use_4bit_qlora,
                progress_cb=__import__("app.training.lora_trainer", fromlist=["ProgressCallback"]).ProgressCallback(_wrapped_progress),
            )
            
            return result
        
        except Exception as e:
            logger.exception(f"Training failed for {model}")
            return {
                "ok": False,
                "error": str(e),
            }
    
    async def get_trained_adapters(self) -> Dict[str, Path]:
        """
        List all successfully trained adapters.
        
        Returns:
            Mapping of model names to adapter directories
        """
        adapters = {}
        paths = get_training_paths(settings.base_dir, self.training_config)
        model_state_dir = Path(paths.get("model_state_subdir") or settings.base_dir)
        
        for model in self.base_models:
            model_short = model.split("/")[-1]
            adapter_path = model_state_dir / model_short / "adapter"
            
            if adapter_path.exists() and (adapter_path / "adapter_config.json").exists():
                adapters[model] = adapter_path
        
        logger.info(f"Found {len(adapters)} trained adapters")
        return adapters


async def train_models_from_project(
    project_ids: List[int],
    db: Optional[object] = None,
) -> Dict[str, Any]:
    """
    Convenience function: export documents from projects → train all models.
    
    Args:
        project_ids: List of project IDs to use for training
        db: AsyncSession (optional, will create one if not provided)
    
    Returns:
        Result dict with batch_file and per-model results
    """
    from app.services.training_export_service import export_documents_for_training
    from app.db.database import AsyncSessionLocal
    
    if db is None:
        db = AsyncSessionLocal()
    
    try:
        # Export documents as training batch
        logger.info(f"Exporting documents from projects {project_ids}...")
        batch_file = await export_documents_for_training(
            project_ids=project_ids,
            db=db,
        )
        
        # Train all models
        logger.info(f"Starting multi-model training run...")
        trainer = MultiModelTrainer()
        results = await trainer.train_all_models(
            batch_path=Path(batch_file),
            sequential=True,  # Safe for constrained hardware
        )
        
        return {
            "status": "complete",
            "batch_file": batch_file,
            "results": results,
        }
    
    finally:
        try:
            await db.close()
        except Exception:
            pass
