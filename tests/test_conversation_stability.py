"""
test_conversation_stability.py -- Long-horizon conversation stability test.

Measures **hallucination drift**, **citation relevance**, and **topic retention**
over a 50-turn conversation by calling the live DocTel API endpoints.

Usage
-----
    python tests/test_conversation_stability.py [--url URL] [--ec EC_NUMBER] [--password PASSWORD]

The script will:
  1. Authenticate via /auth/login
  2. Create a new conversation session
  3. Run 50 sequential questions covering a mix of browsing, definition,
     procedure, policy, comparison, and follow-up queries
  4. For each turn, record grounding score, citation quality, and topic relevance
  5. Output a detailed CSV + summary report

Environment variables
---------------------
    DOCTEL_API_URL        Base URL (default: http://127.0.0.1:8000)
    DOCTEL_EC_NUMBER      EC number for login (default: "admin")
    DOCTEL_PASSWORD       Password (default: "admin")
    DOCTEL_TOP_K          Number of chunks to retrieve (default: 6)

Exit codes
----------
    0 -- all metrics pass
    1 -- some metrics below threshold
    2 -- setup / auth failure
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

try:
    import httpx
except ImportError:
    print("Missing httpx -- install with:  pip install httpx")
    sys.exit(2)

# ---------------------------------------------------------------------------
# Constants & defaults
# ---------------------------------------------------------------------------

DEFAULT_URL = os.environ.get("DOCTEL_API_URL", "http://127.0.0.1:8000")
DEFAULT_EC = os.environ.get("DOCTEL_EC_NUMBER", "admin")
DEFAULT_PASSWORD = os.environ.get("DOCTEL_PASSWORD", "admin")
DEFAULT_TOP_K = int(os.environ.get("DOCTEL_TOP_K", "6"))

GROUNDING_THRESHOLD = 0.30  # Minimum grounding fraction (matches answer_validator)

# ---------------------------------------------------------------------------
# Per-turn measurement
# ---------------------------------------------------------------------------


@dataclass
class TurnMetrics:
    turn: int
    question: str
    retrieval_question: str = ""
    is_follow_up: bool = False
    answer_length: int = 0
    citation_count: int = 0
    avg_distance: float = 0.0
    min_distance: float = 0.0
    max_distance: float = 0.0
    documents_used: list[str] = field(default_factory=list)
    total_claims: int = 0
    grounded_claims: int = 0
    grounding_score: float = 0.0
    grounding_rejected: bool = False
    topic_keywords_found: int = 0
    topic_keywords_total: int = 0
    topic_retention: float = 0.0
    has_answer: bool = False
    elapsed_ms: int = 0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Claim extraction (mirrors answer_validator for drift measurement)
# ---------------------------------------------------------------------------

_FUNCTION_ID_RE = re.compile(r"\b[A-Z]-[A-Z]{3,}-\d{3,}\b")
_ACRONYM_RE = re.compile(r"\b[A-Z]{2,8}\d?\b")
_NUMBER_RE = re.compile(r"\b\d{2,}(?:[.,]\d+)?%?\b")
_QUOTED_RE = re.compile(r'"([^"]{3,})"')
_SKIP_ACRONYMS = {"THE", "AND", "FOR", "ARE", "WAS", "NOT", "BUT", "ALL",
                   "CAN", "HAS", "ITS", "MAY", "PER", "YOU", "OUR", "YOUR"}


def extract_claims(text: str) -> list[str]:
    """Extract verifiable claims from *text* (mirrors answer_validator)."""
    if not text:
        return []
    claims: list[str] = []
    seen: set[str] = set()

    def _add(claim: str) -> None:
        n = claim.strip().lower()
        if n and len(n) >= 2 and n not in seen:
            seen.add(n)
            claims.append(n)

    for m in _FUNCTION_ID_RE.finditer(text):
        _add(m.group())
    for m in _ACRONYM_RE.finditer(text):
        tok = m.group()
        if tok.upper() not in _SKIP_ACRONYMS:
            _add(tok)
    for m in _NUMBER_RE.finditer(text):
        _add(m.group())
    for m in _QUOTED_RE.finditer(text):
        p = m.group(1).strip()
        if len(p) >= 5:
            _add(p)
    for phrase in re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,5}\b", text):
        if len(phrase) >= 8:
            _add(phrase)

    return claims[:25]


def check_claim_in_text(claim: str, chunk_text: str) -> bool:
    """Return True if *claim* appears in *chunk_text* (boundary-aware for short claims)."""
    if not chunk_text:
        return False
    lower = chunk_text.lower()
    is_number = bool(re.match(r"^\d{2,}(?:[.,]\d+)?%?$", claim))
    is_short = len(claim) <= 5

    if is_number:
        return claim in set(lower.split())
    elif is_short:
        return bool(re.search(r"\b" + re.escape(claim) + r"\b", lower))
    else:
        return claim in lower


def measure_grounding(answer_text: str, chunk_texts: list[str]) -> dict:
    """Measure what fraction of the answer's claims are grounded in chunks."""
    result = {"total_claims": 0, "grounded_claims": 0,
              "score": 1.0, "ungrounded": []}

    if len(answer_text.strip()) < 50:
        return result

    claims = extract_claims(answer_text)
    result["total_claims"] = len(claims)
    if not claims:
        return result

    grounded = 0
    ungrounded = []
    for c in claims:
        if any(check_claim_in_text(c, ct) for ct in chunk_texts):
            grounded += 1
        else:
            ungrounded.append(c)

    result["grounded_claims"] = grounded
    result["ungrounded"] = ungrounded
    result["score"] = round(grounded / len(claims), 4) if claims else 1.0
    return result


# ---------------------------------------------------------------------------
# Topic keywords for retention measurement
# ---------------------------------------------------------------------------

# Each scenario has a primary topic with associated keywords.
# Retention is measured by how many of these keywords appear in the answer.

SCENARIO_KEYWORDS: list[dict[str, Any]] = [
    {
        "name": "Billing System Overview",
        "keywords": {"billing", "customer", "account", "payment", "invoice",
                      "tariff", "meter", "collection", "FRS", "ZETDC"},
    },
    {
        "name": "OMS (Outage Management)",
        "keywords": {"OMS", "outage", "fault", "incident", "restoration",
                      "crew", "dispatch", "notification", "CRM", "ticket"},
    },
    {
        "name": "CRM (Customer Relations)",
        "keywords": {"CRM", "customer", "complaint", "case", "service",
                      "request", "omnichannel", "omnichannel", "interaction"},
    },
    {
        "name": "NDPM (New Connections)",
        "keywords": {"NDPM", "connection", "application", "approval",
                      "inspection", "commissioning", "workflow", "feeder"},
    },
    {
        "name": "ZUMS Mobile",
        "keywords": {"ZUMS", "mobile", "app", "FWA", "payment", "self-service",
                      "notification", "micro-app", "portal"},
    },
    {
        "name": "Policy & Compliance",
        "keywords": {"policy", "compliance", "regulation", "ZERA", "governance",
                      "security", "standard", "requirement", "audit"},
    },
    {
        "name": "ICT & Cloud",
        "keywords": {"ICT", "cloud", "security", "acceptable use", "data",
                      "infrastructure", "system", "access", "control"},
    },
]

# 50-turn question sequence
CONVERSATION_SCRIPT: list[str] = [
    # Turns 1-7: Billing System (definition + exploration)
    "What is the ZETDC Billing System?",
    "What are the main modules of the billing system?",
    "How does the billing lifecycle work?",
    "What payment methods are supported?",
    "How are customer accounts managed?",
    "What happens when a payment is reversed?",
    "Explain the collections process in detail.",

    # Turns 8-14: OMS (new topic with follow-up resolution)
    "What is OMS?",
    "How does OMS integrate with the billing system?",
    "What types of outages does OMS manage?",
    "How are customers notified during an outage?",
    "What is the escalation process?",
    "How does OMS track restoration progress?",
    "What reports does OMS generate?",

    # Turns 15-21: CRM (third topic, follow-up continuity)
    "Explain the CRM system.",
    "How is CRM related to OMS?",
    "What are the Omni Channel capabilities?",
    "How are customer complaints managed in CRM?",
    "What integration does CRM have with billing?",
    "How are service requests tracked?",
    "What reporting is available in CRM?",

    # Turns 22-28: NDPM (procedure questions)
    "What is NDPM?",
    "What is the process for a new connection application?",
    "What documents are required for a new connection?",
    "How are inspections scheduled?",
    "What happens after inspection approval?",
    "How long does the connection process typically take?",
    "Who is responsible for commissioning?",

    # Turns 29-35: ZUMS Mobile (definition + features)
    "What is ZUMS Mobile?",
    "What features does the mobile app provide?",
    "How do customers pay via the mobile app?",
    "Can customers check their account balance on ZUMS?",
    "What notifications does the app send?",
    "How is ZUMS Mobile different from the web portal?",
    "Is ZUMS Mobile available for all customer types?",

    # Turns 36-42: Policy questions (new domain)
    "What does the ICT policy cover?",
    "What are the acceptable use guidelines?",
    "How is data security handled?",
    "What happens if policy is violated?",
    "Who enforces the ICT policy?",
    "How often is the policy reviewed?",
    "What cloud services are permitted under policy?",

    # Turns 43-50: Mixed follow-ups + cross-domain
    "Compare OMS and NDPM workflows.",
    "How do mobile, web, and CRM interact for customer service?",
    "What systems are involved in a new electricity connection?",
    "Explain the end-to-end customer journey from application to billing.",
    "What role does ZERA play in ZETDC systems?",
    "How are system changes governed?",
    "What business continuity measures exist?",
    "Summarise the key enterprise systems and their relationships.",
]


# ---------------------------------------------------------------------------
# Main test runner
# ---------------------------------------------------------------------------


class ConversationStabilityTest:
    """Run a 50-turn conversation and measure per-turn metrics."""

    def __init__(
        self,
        base_url: str = DEFAULT_URL,
        ec_number: str = DEFAULT_EC,
        password: str = DEFAULT_PASSWORD,
        top_k: int = DEFAULT_TOP_K,
    ):
        self.base_url = base_url.rstrip("/")
        self.ec_number = ec_number
        self.password = password
        self.top_k = top_k
        self.client = httpx.Client(timeout=120.0, follow_redirects=True)
        self.token: Optional[str] = None
        self.session_id: Optional[str] = None
        self.metrics: list[TurnMetrics] = []
        self._current_topic_idx: int = 0

    # ── Authentication ──────────────────────────────────────────────────

    def authenticate(self) -> None:
        """Log in and store the bearer token."""
        url = f"{self.base_url}/auth/login"
        payload = {"ec_number": self.ec_number, "password": self.password}
        resp = self.client.post(url, json=payload)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Auth failed ({resp.status_code}): {resp.text[:200]}"
            )
        data = resp.json()
        self.token = data.get("access_token") or data.get("token")
        if not self.token:
            raise RuntimeError(f"No token in auth response: {data}")
        # Set default auth header for subsequent requests
        self.client.headers["Authorization"] = f"Bearer {self.token}"
        print(f"  [OK] Authenticated as {data.get('display_name', self.ec_number)}")

    # ── Single ask call ─────────────────────────────────────────────────

    def ask(self, question: str, turn_number: int) -> dict[str, Any]:
        """Send a question to the API and return the parsed response.

        Also records a RAG trace for detailed retrieval metrics.
        """
        # ── Send question ──────────────────────────────────────────────
        ask_url = f"{self.base_url}/api/ask"
        payload: dict[str, Any] = {
            "question": question,
            "scope": "all",
        }
        if self.session_id:
            payload["session_id"] = self.session_id

        t0 = time.monotonic()
        resp = self.client.post(ask_url, json=payload)
        elapsed = int((time.monotonic() - t0) * 1000)

        if resp.status_code != 200:
            return {
                "error": f"API error ({resp.status_code}): {resp.text[:300]}",
                "answer": "",
                "citations": [],
                "session_id": self.session_id or "",
                "elapsed_ms": elapsed,
                "used_model": "unknown",
            }

        data = resp.json()
        # Capture session ID for follow-up continuity
        if data.get("session_id"):
            self.session_id = data["session_id"]

        # ── Also fetch RAG trace for detailed retrieval data ────────────
        # This gives us the rewritten question, conversation history, and
        # raw ChromaDB results.
        try:
            trace_url = f"{self.base_url}/api/ask/debug/trace"
            trace_resp = self.client.post(trace_url, json={
                "question": question,
                "session_id": self.session_id or "",
                "scope": "project",
            })
            if trace_resp.status_code == 200:
                trace_data = trace_resp.json()
                data["_trace"] = trace_data
        except Exception:
            pass

        data.setdefault("elapsed_ms", elapsed)
        return data

    # ── Per-turn measurement ────────────────────────────────────────────

    def measure_turn(
        self, turn: int, question: str, response: dict[str, Any]
    ) -> TurnMetrics:
        """Compute metrics for a single turn."""
        answer = response.get("answer", "") or ""
        citations = response.get("citations", []) or []
        trace = response.get("_trace", {})

        m = TurnMetrics(
            turn=turn,
            question=question[:120],
            retrieval_question=(trace.get("retrieval_question") or question)[:120],
            is_follow_up=trace.get("is_follow_up", False),
            answer_length=len(answer),
            citation_count=len(citations),
            has_answer=bool(answer.strip()),
            elapsed_ms=response.get("elapsed_ms", 0),
        )

        # ── Citation relevance ──────────────────────────────────────────
        distances = []
        doc_set: set[str] = set()
        for c in citations:
            d = c.get("distance")
            if d is not None:
                try:
                    distances.append(float(d))
                except (ValueError, TypeError):
                    pass
            fn = c.get("filename", "")
            if fn:
                doc_set.add(fn)
        m.documents_used = sorted(doc_set)
        if distances:
            m.avg_distance = round(sum(distances) / len(distances), 4)
            m.min_distance = round(min(distances), 4)
            m.max_distance = round(max(distances), 4)

        # ── Hallucination drift (grounding) ─────────────────────────────
        chunks_text = [c.get("text", "") or "" for c in citations]
        grounding = measure_grounding(answer, chunks_text)
        m.total_claims = grounding["total_claims"]
        m.grounded_claims = grounding["grounded_claims"]
        m.grounding_score = grounding["score"]
        m.grounding_rejected = (
            grounding["total_claims"] >= 3
            and grounding["score"] < GROUNDING_THRESHOLD
        )

        # ── Topic retention ─────────────────────────────────────────────
        topic_keywords = self._resolve_topic_keywords(question)
        if topic_keywords:
            answer_lower = answer.lower()
            found = sum(
                1 for kw in topic_keywords
                if kw.lower() in answer_lower
            )
            m.topic_keywords_found = found
            m.topic_keywords_total = len(topic_keywords)
            m.topic_retention = round(found / len(topic_keywords), 4)

        if response.get("error"):
            m.error = response["error"][:200]

        return m

    def _resolve_topic_keywords(self, question: str) -> set[str]:
        """Return the keyword set for the topic most relevant to *question*."""
        q_lower = question.lower()
        best_score = 0
        best_keywords: set[str] = set()
        for scenario in SCENARIO_KEYWORDS:
            score = sum(1 for kw in scenario["keywords"] if kw.lower() in q_lower)
            if score > best_score:
                best_score = score
                best_keywords = scenario["keywords"]
        return best_keywords

    # ── Run all turns ──────────────────────────────────────────────────

    def run(self) -> list[TurnMetrics]:
        """Run the complete 50-turn conversation."""
        total = len(CONVERSATION_SCRIPT)
        print(f"\n  Running {total} turns...")

        for i, question in enumerate(CONVERSATION_SCRIPT, start=1):
            try:
                response = self.ask(question, i)
                m = self.measure_turn(i, question, response)
                self.metrics.append(m)

                status = "[OK]" if m.has_answer else "[FAIL]"
                drift = "[WARN]" if m.grounding_rejected else " "
                ret = f"R={m.topic_retention:.0%}" if m.topic_keywords_total > 0 else ""
                cite = f"C={m.citation_count}"
                print(
                    f"    [{status}] Turn {i:2d}/{total} | "
                    f"{drift}{cite} | "
                    f"G={m.grounding_score:.0%} | "
                    f"{ret} | "
                    f"{m.elapsed_ms}ms"
                )
            except Exception as exc:
                m = TurnMetrics(
                    turn=i, question=question[:120], error=str(exc)[:200]
                )
                self.metrics.append(m)
                print(f"    [[FAIL]] Turn {i:2d}/{total} -- ERROR: {exc}")

        return self.metrics

    # ── Report ──────────────────────────────────────────────────────────

    def report(self) -> dict[str, Any]:
        """Generate a summary report from all metrics."""
        total = len(self.metrics)
        if total == 0:
            return {"error": "No metrics collected"}

        answered = sum(1 for m in self.metrics if m.has_answer)
        rejected = sum(1 for m in self.metrics if m.grounding_rejected)
        with_citations = sum(1 for m in self.metrics if m.citation_count > 0)
        avg_grounding = (
            sum(m.grounding_score for m in self.metrics)
            / total
        )
        avg_retention = (
            sum(m.topic_retention for m in self.metrics)
            / sum(1 for m in self.metrics if m.topic_keywords_total > 0)
            if sum(1 for m in self.metrics if m.topic_keywords_total > 0) > 0
            else 0.0
        )
        avg_citations = (
            sum(m.citation_count for m in self.metrics)
            / total
        )
        avg_distance = (
            sum(m.avg_distance for m in self.metrics if m.avg_distance > 0)
            / sum(1 for m in self.metrics if m.avg_distance > 0)
            if sum(1 for m in self.metrics if m.avg_distance > 0) > 0
            else 0.0
        )

        # Track drift by segment: early (1-10), mid (11-25), late (26-50)
        def _segment(lo: int, hi: int) -> dict:
            seg = [m for m in self.metrics if lo <= m.turn <= hi]
            return {
                "turns": f"{lo}-{hi}",
                "count": len(seg),
                "avg_grounding": round(
                    sum(m.grounding_score for m in seg) / len(seg), 4
                ) if seg else 0,
                "grounding_rejected": sum(1 for m in seg if m.grounding_rejected),
                "avg_citations": round(
                    sum(m.citation_count for m in seg) / len(seg), 2
                ) if seg else 0,
                "avg_retention": round(
                    sum(m.topic_retention for m in seg if m.topic_keywords_total > 0)
                    / max(sum(1 for m in seg if m.topic_keywords_total > 0), 1), 4
                ),
            }

        summary = {
            "total_turns": total,
            "answered": answered,
            "rejected_answers": rejected,
            "with_citations": with_citations,
            "avg_grounding_score": round(avg_grounding, 4),
            "avg_topic_retention": round(avg_retention, 4),
            "avg_citations_per_turn": round(avg_citations, 2),
            "avg_chunk_distance": round(avg_distance, 4),
            "segments": {
                "early": _segment(1, 10),
                "mid": _segment(11, 25),
                "late": _segment(26, 50),
            },
            "elapsed_seconds": round(
                sum(m.elapsed_ms for m in self.metrics) / 1000, 1
            ),
        }

        # Determine pass/fail
        passes = True
        failures = []
        if avg_grounding < GROUNDING_THRESHOLD:
            passes = False
            failures.append(
                f"Low grounding score: {avg_grounding:.1%} < {GROUNDING_THRESHOLD:.0%}"
            )
        if rejected > total * 0.3:
            passes = False
            failures.append(
                f"Too many rejected answers: {rejected}/{total} "
                f"({rejected/total:.0%})"
            )
        if avg_retention < 0.2:
            passes = False
            failures.append(
                f"Low topic retention: {avg_retention:.1%}"
            )

        summary["pass"] = passes
        summary["failures"] = failures
        return summary

    def print_report(self, summary: dict[str, Any]) -> None:
        """Pretty-print the summary report."""
        print("\n" + "=" * 65)
        print("  DOCTEL CONVERSATION STABILITY TEST REPORT")
        print("=" * 65)
        print(f"\n  Date:              {datetime.now(timezone.utc).isoformat()[:19]}")
        print(f"  API URL:           {self.base_url}")
        print(f"  Model:             (auto-resolved by API)")
        print(f"  Turns:             {summary['total_turns']}")
        print(f"  Answered:          {summary['answered']}/{summary['total_turns']}")
        print(f"  Rejected (low G):  {summary['rejected_answers']}")
        print(f"  With citations:    {summary['with_citations']}")
        print(f"  Elapsed:           {summary['elapsed_seconds']}s")
        print()

        # ── Overall scores ──────────────────────────────────────────────
        print(f"  {'SCORE':<30} {'VALUE':>10}  {'STATUS':>8}")
        print(f"  {'─'*30}  {'─'*10}  {'─'*8}")
        g = summary["avg_grounding_score"]
        print(f"  {'  Grounding (avg)':<30} {g:>10.1%}  "
              f"{'[OK] PASS' if g >= GROUNDING_THRESHOLD else '[FAIL] FAIL'}")
        r = summary["avg_topic_retention"]
        print(f"  {'  Topic retention (avg)':<30} {r:>10.1%}  "
              f"{'[OK] PASS' if r >= 0.20 else '[WARN] BORDERLINE'}")
        c = summary["avg_citations_per_turn"]
        print(f"  {'  Citations per turn (avg)':<30} {c:>10.2f}")
        d = summary["avg_chunk_distance"]
        print(f"  {'  Chunk distance (avg)':<30} {d:>10.4f}")
        print()

        # ── Segment comparison ──────────────────────────────────────────
        print("  DRIFT BY SEGMENT:")
        print(f"  {'Segment':<12} {'Grounding':>10} {'Rejected':>10} "
              f"{'Citations':>10} {'Retention':>10} {'Drift':>8}")
        print(f"  {'─'*8:<12} {'─'*8:>10} {'─'*6:>10} "
              f"{'─'*6:>10} {'─'*6:>10} {'─'*4:>8}")
        baseline_g = summary["segments"]["early"]["avg_grounding"]
        for seg_name in ("early", "mid", "late"):
            seg = summary["segments"][seg_name]
            drift = seg["avg_grounding"] - baseline_g
            print(f"  {seg['turns']:<12} "
                  f"{seg['avg_grounding']:>10.1%} "
                  f"{seg['grounding_rejected']:>10} "
                  f"{seg['avg_citations']:>10.2f} "
                  f"{seg['avg_retention']:>10.1%} "
                  f"{drift:>+8.1%}")

        # ── Top declining turns ──────────────────────────────────────────
        print()
        print("  TOP 5 LOWEST-GROUNDING TURNS:")
        sorted_by_g = sorted(
            [m for m in self.metrics if m.total_claims > 0],
            key=lambda m: m.grounding_score,
        )[:5]
        for m in sorted_by_g:
            print(f"    Turn {m.turn:2d} | G={m.grounding_score:.0%} "
                  f"({m.grounded_claims}/{m.total_claims}) | "
                  f"{m.question[:80]}")

        # ── Failures ────────────────────────────────────────────────────
        if summary["failures"]:
            print()
            print("  [FAIL] FAILURES:")
            for f in summary["failures"]:
                print(f"    • {f}")

        print()
        verdict = (
            "\033[32mALL CHECKS PASSED\033[0m"
            if summary["pass"]
            else "\033[31mSOME CHECKS FAILED\033[0m"
        )
        print(f"  VERDICT: {verdict}")
        print("=" * 65)

    def export_csv(self, path: str = "conversation_stability_report.csv") -> str:
        """Export per-turn metrics to CSV."""
        if not self.metrics:
            return ""
        fieldnames = list(TurnMetrics.__dataclass_fields__.keys())
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for m in self.metrics:
                row = {k: getattr(m, k) for k in fieldnames}
                # Convert list/dict fields to strings for CSV
                for k in ("documents_used",):
                    v = row.get(k)
                    if isinstance(v, (list, tuple)):
                        row[k] = "; ".join(str(x) for x in v)
                writer.writerow(row)
        print(f"\n  📄 CSV exported: {path}")
        return path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="DocTel Long-Horizon Conversation Stability Test"
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="API base URL")
    parser.add_argument("--ec", default=DEFAULT_EC, help="EC number")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Password")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K,
                        help="Chunks to retrieve")
    parser.add_argument("--csv", default="conversation_stability_report.csv",
                        help="CSV output path")
    parser.add_argument("--skip-auth", action="store_true",
                        help="Skip auth if token already set")
    args = parser.parse_args()

    print("\n" + "=" * 65)
    print("  DocTel Conversation Stability Test")
    print("=" * 65)
    print(f"\n  API:   {args.url}")
    print(f"  EC:    {args.ec}")

    runner = ConversationStabilityTest(
        base_url=args.url,
        ec_number=args.ec,
        password=args.password,
        top_k=args.top_k,
    )

    try:
        if not args.skip_auth:
            runner.authenticate()
    except Exception as exc:
        print(f"\n  [FAIL] Auth failed: {exc}")
        return 2

    metrics = runner.run()
    summary = runner.report()
    runner.print_report(summary)
    runner.export_csv(args.csv)

    return 0 if summary.get("pass", False) else 1


if __name__ == "__main__":
    sys.exit(main())
