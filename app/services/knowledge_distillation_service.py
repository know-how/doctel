"""
knowledge_distillation_service.py – Proactively distill ZETDC knowledge
from cloud API models (Gemini, DeepSeek) into local model training data.

This service generates diverse ZETDC-specific Q&A pairs using cloud models,
then saves them as JSONL training samples for LoRA fine-tuning of local models.

This is the ACTIVE distillation pipeline (vs the passive one in teacher_service
which only captures samples when the fallback router hits the teacher tier).
"""
import json
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict

from app.config import settings

logger = logging.getLogger(__name__)

ZETDC_TOPICS = [
    "ZETDC electricity transmission infrastructure and grid management",
    "ZETDC distribution network operations and maintenance procedures",
    "ZETDC substation safety protocols and high-voltage procedures",
    "ZETDC outage reporting, restoration, and incident management",
    "ZETDC net metering policy for solar and renewable installations",
    "ZETDC SCADA systems and real-time grid monitoring",
    "ZETDC transformer maintenance and oil level inspection procedures",
    "ZETDC load shedding protocols and demand-side management",
    "ZETDC metering systems: prepaid, postpaid, and smart meters",
    "ZETDC ZERA compliance and regulatory requirements",
    "ZETDC HSE (Health Safety Environment) standards for field workers",
    "ZETDC customer service and billing dispute resolution",
    "ZETDC feeder line inspection and fault detection procedures",
    "ZETDC power quality monitoring and voltage regulation",
    "ZETDC procurement and supply chain for electrical equipment",
    "ZETDC emergency response procedures for electrical accidents",
    "ZETDC corporate governance and organizational structure",
    "ZETDC project management for infrastructure upgrades",
    "ZETDC environmental impact assessments for new substations",
    "ZETDC workforce training and competency development programs",
    "ZETDC revenue protection and anti-theft of electricity measures",
    "ZETDC rural electrification programs and off-grid solutions",
    "ZETDC protection relay settings and coordination studies",
    "ZETDC cable fault locating and underground cable management",
    "ZETDC switchgear operation and maintenance standards",
]

ZETDC_INSTRUCTION_STYLES = [
    "question_answer",
    "instruction_output",
    "few_shot",
]

SYSTEM_PROMPT_SUFFIX = (
    " You are answering as DocTel, ZETDC's AI assistant. "
    "Use precise ZETDC terminology: transmission, distribution, substations, "
    "feeders, SCADA, HSE, ZERA compliance, ZUMS, prepaid meters, load shedding. "
    "Be specific to Zimbabwe's electricity infrastructure context."
)


async def generate_zetdc_qa_from_gemini(
    topic: str,
    num_examples: int = 5,
    instruction_style: str = "question_answer",
) -> List[Dict[str, str]]:
    from app.services.gemini_service import generate as gemini_generate, is_configured as gemini_ok
    if not gemini_ok():
        return []

    if instruction_style == "question_answer":
        prompt = (
            f"Generate {num_examples} high-quality question-answer pairs about: {topic}\n\n"
            "Each Q&A should be specific to ZETDC (Zimbabwe Electricity Transmission and "
            "Distribution Company) operations. Include practical details, procedures, and "
            "ZETDC-specific terminology.\n\n"
            "Format each as JSON:\n"
            '{"instruction": "specific question about ZETDC", "output": "detailed answer with ZETDC context"}\n\n'
            "Return ONLY a valid JSON array, no markdown."
        )
    elif instruction_style == "instruction_output":
        prompt = (
            f"Generate {num_examples} instruction-output pairs for: {topic}\n\n"
            "Each pair should represent a task a ZETDC employee would ask DocTel AI.\n\n"
            "Format each as JSON:\n"
            '{"instruction": "task description for ZETDC staff", "output": "step-by-step result"}\n\n'
            "Return ONLY a valid JSON array, no markdown."
        )
    else:
        prompt = (
            f"Generate {num_examples} few-shot examples about: {topic}\n\n"
            "Each example should demonstrate ZETDC domain knowledge.\n\n"
            "Format each as JSON:\n"
            '{"instruction": "context or query", "output": "knowledgeable response"}\n\n'
            "Return ONLY a valid JSON array, no markdown."
        )

    system = "You are a ZETDC domain expert generating training data for an AI assistant." + SYSTEM_PROMPT_SUFFIX
    try:
        raw = await gemini_generate(prompt, system=system)
        return _parse_jsonl_response(raw)
    except Exception as e:
        logger.warning("Gemini distillation failed for topic '%s': %s", topic, e)
        return []


async def generate_zetdc_qa_from_deepseek(
    topic: str,
    num_examples: int = 5,
    instruction_style: str = "question_answer",
) -> List[Dict[str, str]]:
    from app.services.deepseek_service import generate as deepseek_generate, is_configured as deepseek_ok
    if not deepseek_ok():
        return []

    if instruction_style == "question_answer":
        prompt = (
            f"Generate {num_examples} high-quality question-answer pairs about: {topic}\n\n"
            "Each Q&A should be specific to ZETDC (Zimbabwe Electricity Transmission and "
            "Distribution Company) operations. Include practical details, procedures, and "
            "ZETDC-specific terminology.\n\n"
            "Format each as JSON:\n"
            '{"instruction": "specific question about ZETDC", "output": "detailed answer with ZETDC context"}\n\n'
            "Return ONLY a valid JSON array, no markdown."
        )
    elif instruction_style == "instruction_output":
        prompt = (
            f"Generate {num_examples} instruction-output pairs for: {topic}\n\n"
            "Each pair should represent a task a ZETDC employee would ask DocTel AI.\n\n"
            "Format each as JSON:\n"
            '{"instruction": "task description for ZETDC staff", "output": "step-by-step result"}\n\n'
            "Return ONLY a valid JSON array, no markdown."
        )
    else:
        prompt = (
            f"Generate {num_examples} few-shot examples about: {topic}\n\n"
            "Each example should demonstrate ZETDC domain knowledge.\n\n"
            "Format each as JSON:\n"
            '{"instruction": "context or query", "output": "knowledgeable response"}\n\n'
            "Return ONLY a valid JSON array, no markdown."
        )

    system = "You are a ZETDC domain expert generating training data for an AI assistant." + SYSTEM_PROMPT_SUFFIX
    try:
        raw = await deepseek_generate(prompt, system=system)
        return _parse_jsonl_response(raw)
    except Exception as e:
        logger.warning("DeepSeek distillation failed for topic '%s': %s", topic, e)
        return []


def _parse_jsonl_response(raw: str) -> List[Dict[str, str]]:
    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            data = json.loads(raw[start:end])
            if isinstance(data, list):
                valid = []
                for item in data:
                    if isinstance(item, dict) and "instruction" in item and "output" in item:
                        valid.append({
                            "instruction": str(item["instruction"]),
                            "output": str(item["output"]),
                        })
                return valid
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse distillation JSON: %s", e)
    return []


async def distill_zetdc_knowledge(
    topics: Optional[List[str]] = None,
    num_per_topic: int = 5,
    max_concurrent: int = 3,
    output_dir: Optional[Path] = None,
) -> Dict[str, int]:
    """
    Main entry: distill ZETDC knowledge from cloud APIs into training data.

    Queries both Gemini and DeepSeek in parallel (rate-limited) with diverse
    ZETDC topics, captures Q&A pairs as JSONL for LoRA fine-tuning.

    Returns dict with stats: {"total_samples": N, "gemini_samples": N, "deepseek_samples": N, "topics_covered": N}
    """
    if topics is None:
        topics = ZETDC_TOPICS

    if output_dir is None:
        output_dir = Path(settings.base_dir) / "training" / "distilled"
    output_dir.mkdir(parents=True, exist_ok=True)

    from app.services.gemini_service import is_configured as gemini_ok
    from app.services.deepseek_service import is_configured as deepseek_ok

    gemini_available = gemini_ok()
    deepseek_available = deepseek_ok()

    if not gemini_available and not deepseek_available:
        logger.warning("No cloud APIs configured for knowledge distillation")
        return {"total_samples": 0, "gemini_samples": 0, "deepseek_samples": 0, "topics_covered": 0}

    all_samples: List[Dict] = []
    gemini_count = 0
    deepseek_count = 0

    sem = asyncio.Semaphore(max_concurrent)

    async def _distill_one(topic: str, provider: str, style: str):
        nonlocal gemini_count, deepseek_count
        async with sem:
            try:
                if provider == "gemini":
                    samples = await generate_zetdc_qa_from_gemini(topic, num_per_topic, style)
                    gemini_count += len(samples)
                else:
                    samples = await generate_zetdc_qa_from_deepseek(topic, num_per_topic, style)
                    deepseek_count += len(samples)

                for s in samples:
                    s["topic"] = topic
                    s["provider"] = provider
                    s["style"] = style
                    s["distilled_at"] = datetime.now(timezone.utc).isoformat()
                all_samples.extend(samples)
            except Exception as e:
                logger.warning("Distillation failed for '%s' via %s: %s", topic, provider, e)

    tasks = []
    for topic in topics:
        style = ZETDC_INSTRUCTION_STYLES[hash(topic) % len(ZETDC_INSTRUCTION_STYLES)]
        if gemini_available:
            tasks.append(_distill_one(topic, "gemini", style))
        if deepseek_available:
            tasks.append(_distill_one(topic, "deepseek", style))

    if tasks:
        await asyncio.gather(*tasks)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    outfile = output_dir / f"distilled_zetdc_{ts}.jsonl"
    with open(outfile, "w", encoding="utf-8") as f:
        for s in all_samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    logger.info(
        "Distillation complete: %d samples (%d gemini, %d deepseek) from %d topics → %s",
        len(all_samples), gemini_count, deepseek_count, len(topics), outfile,
    )

    return {
        "total_samples": len(all_samples),
        "gemini_samples": gemini_count,
        "deepseek_samples": deepseek_count,
        "topics_covered": len(topics),
        "output_file": str(outfile),
    }


ZETDC_TRANSCRIPTION_SCENARIOS = [
    ("ZETDC field technician reporting a transformer oil leak at Harare Central substation", "Shona"),
    ("ZETDC control room operator announcing load shedding schedule for Bulawayo district", "Shona"),
    ("ZETDC safety officer briefing on high-voltage circuit breaker maintenance procedures", "English"),
    ("ZETDC customer service agent explaining net metering application process to a homeowner", "Shona"),
    ("ZETDC engineer discussing SCADA system alarm response protocol", "English"),
    ("ZETDC field crew reporting a downed power line on feeder 33KV-12 in Mutare", "Shona"),
    ("ZETDC training instructor teaching new apprentices about substation entry procedures", "Shona"),
    ("ZETDC manager presenting quarterly distribution loss reduction targets", "English"),
    ("ZETDC meter reader reporting irregular prepaid meter readings in Gweru", "Shona"),
    ("ZETDC HSE officer conducting a toolbox talk on working at heights near transmission towers", "English"),
    ("ZETDC dispatch operator coordinating emergency crew response to an outage in Chitungwiza", "Shona"),
    ("ZETDC procurement team discussing specifications for replacement 33KV transformers", "English"),
]


async def generate_transcription_training_data(
    output_dir: Optional[Path] = None,
) -> Dict[str, int]:
    """
    Generate transcription-specific training samples for local models.
    Uses cloud APIs to produce ZETDC audio transcription instruction/output pairs
    that teach the local model how to handle ZETDC audio content.
    """
    if output_dir is None:
        output_dir = Path(settings.base_dir) / "training" / "distilled"
    output_dir.mkdir(parents=True, exist_ok=True)

    from app.services.gemini_service import is_configured as gemini_ok, generate as gemini_generate
    from app.services.deepseek_service import is_configured as deepseek_ok, generate as deepseek_generate

    all_samples: List[Dict] = []

    for scenario, language in ZETDC_TRANSCRIPTION_SCENARIOS:
        prompt = (
            f"Generate a realistic ZETDC audio transcription training sample for this scenario: "
            f'"{scenario}" (language: {language}).\n\n'
            "Create TWO JSON objects:\n"
            "1. instruction/output where instruction asks to transcribe and output is the transcript\n"
            "2. instruction/output where instruction is the transcript and output is a ZETDC-specific summary/action\n\n"
            "The transcript should use ZETDC terminology: transmission, distribution, substations, "
            "feeders, SCADA, HSE, ZERA, ZUMS, load shedding, prepaid meters.\n\n"
            "Return ONLY a valid JSON array of {instruction, output} objects, no markdown."
        )
        system = "You are generating training data for a ZETDC AI transcription system." + SYSTEM_PROMPT_SUFFIX

        for provider, is_ok, gen_func in [
            ("gemini", gemini_ok(), gemini_generate),
            ("deepseek", deepseek_ok(), deepseek_generate),
        ]:
            if not is_ok:
                continue
            try:
                raw = await gen_func(prompt, system=system)
                samples = _parse_jsonl_response(raw)
                for s in samples:
                    s["topic"] = scenario[:80]
                    s["provider"] = provider
                    s["type"] = "transcription_training"
                    s["language"] = language
                    s["distilled_at"] = datetime.now(timezone.utc).isoformat()
                all_samples.extend(samples)
            except Exception as e:
                logger.warning("Transcription training generation failed via %s: %s", provider, e)

    if all_samples:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        outfile = output_dir / f"transcription_training_{ts}.jsonl"
        with open(outfile, "w", encoding="utf-8") as f:
            for s in all_samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        logger.info("Generated %d transcription training samples → %s", len(all_samples), outfile)
    else:
        outfile = None

    return {
        "total_samples": len(all_samples),
        "output_file": str(outfile) if outfile else "",
    }
