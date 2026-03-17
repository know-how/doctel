import asyncio
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

from app.config import settings
from app.utils.ollama_client import ollama
from app.utils.model_cache import set_pull_state, update_installed_models, load_model_cache


@dataclass
class _LayerProgress:
    completed: int = 0
    total: int = 0


@dataclass
class PullStatus:
    model: str
    state: str = "idle"  # pending|downloading|verifying|success|failed|retrying
    percent: int = 0
    bytes_completed: int = 0
    bytes_total: int = 0
    eta_seconds: Optional[int] = None
    attempt: int = 0
    last_event: str = ""
    error: str = ""
    resume_supported: bool = False
    started_at: float = 0.0
    updated_at: float = 0.0
    layers: dict[str, _LayerProgress] = field(default_factory=dict)
    _samples: list[tuple[float, int]] = field(default_factory=list, repr=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("_samples", None)
        d["layers"] = {k: asdict(v) for k, v in self.layers.items()}
        return d

    def _recompute(self) -> None:
        total = 0
        done = 0
        for lp in self.layers.values():
            if lp.total and lp.total > 0:
                total += int(lp.total)
                done += int(min(lp.completed, lp.total))
        self.bytes_total = total
        self.bytes_completed = done
        if total > 0:
            self.percent = int(min(100, (done / total) * 100))
        self.resume_supported = bool(done > 0 and total > 0 and self.state not in ("success", "failed"))
        now = time.time()
        self.updated_at = now
        self._samples.append((now, done))
        cutoff = now - 10.0
        self._samples = [(t, b) for (t, b) in self._samples if t >= cutoff]
        if len(self._samples) >= 2 and total > done:
            t0, b0 = self._samples[0]
            t1, b1 = self._samples[-1]
            dt = max(0.1, t1 - t0)
            rate = max(1.0, (b1 - b0) / dt)
            self.eta_seconds = int((total - done) / rate)


_lock = asyncio.Lock()
_statuses: dict[str, PullStatus] = {}
_tasks: dict[str, asyncio.Task] = {}


def _friendly_error(msg: str) -> str:
    m = (msg or "").strip()
    low = m.lower()
    if "file does not exist" in low or "manifest" in low:
        return "Model not found. Check the model name (try :latest) and retry."
    if "no such host" in low or "name resolution" in low or "dns" in low:
        return "Network/DNS error reaching Ollama registry. Check internet/DNS and retry."
    if "connection reset" in low or "connection refused" in low:
        return "Connection error talking to Ollama. Ensure Ollama is running (ollama serve)."
    if "timeout" in low:
        return "Network timeout while downloading model. Please retry."
    return m or "Pull failed. Please retry."


def get_pull_status(model: str) -> PullStatus:
    key = model.strip()
    st = _statuses.get(key)
    if st:
        return st
    st = PullStatus(model=key, state="idle", percent=0)
    _statuses[key] = st
    return st


async def start_pull(model: str, *, resume: bool = True) -> PullStatus:
    key = model.strip()
    async with _lock:
        st = get_pull_status(key)
        task = _tasks.get(key)
        if task and not task.done():
            return st
        st.state = "pending"
        st.attempt = 0
        st.error = ""
        st.last_event = "queued"
        st.started_at = time.time()
        st.updated_at = st.started_at
        st.layers = {}
        st.bytes_total = 0
        st.bytes_completed = 0
        st.percent = 0
        st.eta_seconds = None
        st.resume_supported = False
        set_pull_state(key, "in_progress", last_line="queued")
        _tasks[key] = asyncio.create_task(_run_pull(key, resume=resume))
        return st


async def _run_pull(model: str, *, resume: bool) -> None:
    st = get_pull_status(model)
    retries = int(settings.pull.max_retries or 0)
    backoffs = list(settings.pull.backoff_seconds or [2, 4, 8])
    attempt = 0
    current_model = model
    used_latest_fallback = False

    while True:
        attempt += 1
        st.attempt = attempt
        st.state = "downloading" if attempt == 1 else "retrying"
        st.last_event = f"attempt {attempt}"
        st.error = ""
        st.updated_at = time.time()
        set_pull_state(current_model, "in_progress", last_line=st.last_event)
        try:
            async for line in ollama.pull_stream(current_model, resume=resume):
                st.updated_at = time.time()
                raw = (line or "").strip()
                if not raw:
                    continue
                st.last_event = raw
                try:
                    ev = json.loads(raw)
                except Exception:
                    continue
                if not isinstance(ev, dict):
                    continue
                if ev.get("error"):
                    raise RuntimeError(str(ev.get("error")))

                status = str(ev.get("status") or "").lower()
                digest = str(ev.get("digest") or "").strip() or None
                completed = ev.get("completed")
                total = ev.get("total")
                if digest:
                    lp = st.layers.get(digest) or _LayerProgress()
                    if isinstance(completed, (int, float)):
                        lp.completed = int(completed)
                    if isinstance(total, (int, float)) and int(total) > 0:
                        lp.total = int(total)
                    st.layers[digest] = lp
                    st._recompute()

                if status in ("pulling", "downloading"):
                    st.state = "downloading"
                elif status in ("verifying", "extracting"):
                    st.state = "verifying"
                elif status == "success":
                    st.state = "success"
                    st.percent = 100
                    st.eta_seconds = 0

            st.state = "success"
            st.percent = 100
            st.eta_seconds = 0
            st.updated_at = time.time()
            set_pull_state(current_model, "complete", last_line=st.last_event)
            try:
                installed = await ollama.list_models()
                update_installed_models(installed)
            except Exception:
                pass
            return
        except Exception as e:
            msg = str(e)
            low = msg.lower()
            if (
                "pull model manifest" in low
                and "file does not exist" in low
                and not used_latest_fallback
            ):
                base = current_model.split(":")[0].strip() if ":" in current_model else current_model
                alt = f"{base}:latest"
                used_latest_fallback = True
                if alt and alt != current_model:
                    current_model = alt
                    st.last_event = f"retry_latest {current_model}"
                    continue

            st.error = _friendly_error(msg)
            st.state = "failed" if attempt > retries else "retrying"
            st.updated_at = time.time()
            set_pull_state(current_model, "failed", last_line=msg)
            if attempt > retries:
                return
            wait_s = backoffs[min(attempt - 1, len(backoffs) - 1)] if backoffs else 2
            st.last_event = f"retrying in {wait_s}s"
            st.updated_at = time.time()
            await asyncio.sleep(float(wait_s))


async def get_status_payload(model: str) -> dict:
    key = model.strip()
    st = get_pull_status(key)
    installed = set((load_model_cache().get("installed") or []))
    payload = st.to_dict()
    payload["installed"] = key in installed
    return payload
