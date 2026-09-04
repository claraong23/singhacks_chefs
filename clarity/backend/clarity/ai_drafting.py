"""Optional, bounded AI rewriting for one Meeting Studio surface at a time.

This module deliberately has no access to CSV loaders, dossier payloads, RM
notes, retrieval, or decision mutation.  A configured provider receives only
the already-approved text of one immutable meeting-package version.  Candidate
text is held in memory until the RM explicitly applies it; the durable log
contains provenance and guardrail outcomes, never prompts, candidate text, or
credentials.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from . import config
from .contracts import AIDraftCandidate, AIDraftGuardrail, AIDraftProvenance, AIDraftingProviderStatus
from .meeting import CHANNELS, SECTION_TITLES, current_version, preflight, update_section
from .meeting_store import get_meeting_store

PROMPT_VERSION = "meeting-rewrite-v1"
EXPIRY_MINUTES = 15
STATE_PATH = config.REPO_ROOT / "clarity" / "state" / "ai_drafting_audit.json"
STYLES = {
    "clear_concise": "Clear and concise",
    "warm_respectful": "Warm and respectful",
    "formal_concise": "Formal and concise",
}
_PROHIBITED = (
    r"\bwe recommend\b",
    r"\byou should (buy|sell)\b",
    r"\bwill (buy|sell|execute|trade)\b",
    r"\bguarantee(?:d)?\b",
    r"\btax (payable|rate|outcome|liability)\b",
    r"\bredemption (will|date|is guaranteed)\b",
)
_PRODUCT_TERMS = ("structured product", "fund", "bond", "share", "security", "instrument", "product")
_NUMBER_TOKEN = re.compile(r"\b(?:[A-Z]{3}\s*)?\d[\d,./-]*(?:\.\d+)?%?(?:[kmb])?\b", re.IGNORECASE)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(value: datetime | None = None) -> str:
    return (value or _now()).isoformat(timespec="seconds")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _actor(role: str) -> str:
    if role != "rm":
        raise PermissionError("Only the RM role can generate or apply an AI meeting draft.")
    return "RM-SG-014"


def provider_status() -> dict[str, Any]:
    """Return only safe configuration metadata; never expose a key or endpoint."""
    provider = os.environ.get("CLARITY_AI_PROVIDER", "disabled").strip().lower()
    if provider == "gemini":
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        model = os.environ.get("CLARITY_GEMINI_MODEL", "gemini-2.5-flash").strip()
        if key and model:
            return AIDraftingProviderStatus(True, "gemini", model, "Gemini drafting is configured for this local process.").to_dict()
        return AIDraftingProviderStatus(False, "disabled", None, "Gemini is selected but its server-side key is unavailable.").to_dict()
    if provider == "openai_compatible":
        key = os.environ.get("CLARITY_OPENAI_COMPATIBLE_API_KEY", "").strip()
        base = os.environ.get("CLARITY_OPENAI_COMPATIBLE_BASE_URL", "").strip()
        model = os.environ.get("CLARITY_OPENAI_COMPATIBLE_MODEL", "").strip()
        if key and base and model:
            return AIDraftingProviderStatus(True, "openai_compatible", model, "OpenAI-compatible drafting is configured for this local process.").to_dict()
        return AIDraftingProviderStatus(False, "disabled", None, "OpenAI-compatible drafting requires server-side base URL, key, and model configuration.").to_dict()
    return AIDraftingProviderStatus(False, "disabled", None, "AI drafting is optional and disabled. Use deterministic wording or configure a server-side provider.").to_dict()


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=12.0) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("The configured AI provider did not return a usable draft.") from exc


def _provider_rewrite(prompt: str) -> tuple[str, str, str]:
    status = provider_status()
    if not status["available"]:
        raise PermissionError(status["detail"])
    provider, model = status["provider"], str(status["model"])
    if provider == "gemini":
        key = os.environ["GEMINI_API_KEY"]
        data = _post_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            {"Content-Type": "application/json", "x-goog-api-key": key},
            {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.1, "maxOutputTokens": 800}},
        )
        try:
            content = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("The configured AI provider did not return a usable draft.") from exc
        return str(content).strip(), provider, model
    base = os.environ["CLARITY_OPENAI_COMPATIBLE_BASE_URL"].rstrip("/")
    data = _post_json(
        f"{base}/chat/completions",
        {"Content-Type": "application/json", "Authorization": f"Bearer {os.environ['CLARITY_OPENAI_COMPATIBLE_API_KEY']}"},
        {"model": model, "temperature": 0.1, "messages": [{"role": "system", "content": "Return only the requested rewrite."}, {"role": "user", "content": prompt}]},
    )
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("The configured AI provider did not return a usable draft.") from exc
    return str(content).strip(), provider, model


def rewrite_with_configured_provider(prompt: str) -> tuple[str, str, str]:
    """Run a bounded text rewrite through the provider configured for Clarity.

    Other controlled drafting surfaces use this entry point so one server-side
    provider configuration powers the application without exposing credentials
    to the browser.
    """
    return _provider_rewrite(prompt)


def _target(package: dict[str, Any], key: str) -> tuple[dict[str, Any], bool]:
    current = current_version(package)
    for item in current["sections"]:
        if item["key"] == key:
            return item, False
    for item in current["communications"]:
        if item["channel"] == key:
            return item, True
    raise ValueError("Unknown meeting section or communication channel.")


def _prompt(*, key: str, source: str, client_facing: bool, style: str) -> str:
    label = CHANNELS.get(key) or SECTION_TITLES.get(key) or key
    channel_rule = (
        "This is client-facing. Preserve the exact phrases 'not a recommendation' and 'as at'. "
        "Do not include internal evidence IDs."
        if client_facing else "This is an internal RM section, not client communication."
    )
    return (
        "You rewrite exactly one already-approved private-bank meeting-package surface. "
        "Return plain text only—no heading, explanation, citations, markdown, tools, or JSON. "
        "Do not add, infer, omit, or change facts, numbers, dates, currencies, product references, tax statements, "
        "recommendations, execution language, guarantees, or redemption timing. Preserve all caveats. "
        f"Style: {STYLES[style]}. Target: {label}. {channel_rule}\n\n"
        f"Approved source text:\n{source}"
    )


def _numeric_tokens(value: str) -> set[str]:
    return {token.lower().replace(" ", "") for token in _NUMBER_TOKEN.findall(value)}


def _guardrails(package: dict[str, Any], key: str, content: str, preflight_runner=preflight) -> list[dict[str, Any]]:
    target, client_facing = _target(package, key)
    source = target["content"]
    checks: list[dict[str, Any]] = []
    source_control = next((item for item in preflight_runner(package)["checks"] if item["id"] == "client_ready"), None)
    checks.append({"id": "client_ready", "label": "Client-ready source", "status": "pass" if source_control and source_control["status"] == "pass" else "block", "detail": "The linked decision and gate snapshot still match." if source_control and source_control["status"] == "pass" else "The linked client-ready decision or gate snapshot cannot be reconstructed."})
    allowed = {f"{item['source_file']}:{item['row_or_id']}" for item in package["source"]["evidence"]}
    refs = set(target.get("evidence_refs") or [])
    checks.append({"id": "evidence_refs", "label": "Allowed package evidence", "status": "pass" if refs and refs.issubset(allowed) else "block", "detail": "The target retains its package evidence references." if refs and refs.issubset(allowed) else "The target is missing permitted package evidence references."})
    lower = content.lower()
    prohibited = next((pattern for pattern in _PROHIBITED if re.search(pattern, lower)), None)
    checks.append({"id": "prohibited_claims", "label": "No prohibited advice or execution claim", "status": "block" if prohibited else "pass", "detail": "Remove prohibited advice, execution, guarantee, tax-outcome, or redemption language." if prohibited else "No prohibited advice, execution, guarantee, tax-outcome, or redemption language was detected."})
    new_tokens = _numeric_tokens(content) - _numeric_tokens(source)
    checks.append({"id": "facts", "label": "No new numerical or dated claim", "status": "block" if new_tokens else "pass", "detail": "Remove numerical, date, currency, or percentage claims absent from the approved source text." if new_tokens else "No new numerical, date, currency, or percentage claim was detected."})
    new_product = next((term for term in _PRODUCT_TERMS if term in lower and term not in source.lower()), None)
    checks.append({"id": "products", "label": "No new product claim", "status": "block" if new_product else "pass", "detail": "Remove a product claim absent from the approved source text." if new_product else "No new product claim was detected."})
    if client_facing:
        caveats = "not a recommendation" in lower and "as at" in lower
        checks.append({"id": "client_caveats", "label": "Required client caveats", "status": "pass" if caveats else "block", "detail": "The client-facing wording retains the required caveats." if caveats else "Retain the exact 'not a recommendation' and 'as at' caveats."})
    return checks


class AIDraftAuditStore:
    """Durable audit metadata; deliberately never stores prompt or candidate text."""

    def __init__(self, path: Path = STATE_PATH) -> None:
        self.path, self.lock, self.events = path, threading.Lock(), []
        try:
            self.events = json.loads(path.read_text(encoding="utf-8")).get("events", []) if path.exists() else []
        except (OSError, json.JSONDecodeError):
            self.events = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"events": self.events}, indent=2), encoding="utf-8")

    def record(self, *, origin: str, action: str, package: dict[str, Any], actor: str, detail: dict[str, Any]) -> None:
        with self.lock:
            self.events.append({"id": str(uuid4()), "timestamp": _stamp(), "origin": origin, "object_type": "ai_draft", "object_id": package["id"], "action": action, "actor": actor, "client_id": package["client_id"], "insight_id": package["insight_id"], "detail": detail})
            self._save()

    def audit(self, client_id: str | None = None) -> list[dict[str, Any]]:
        rows = [item for item in self.events if client_id is None or item["client_id"] == client_id]
        return list(reversed(rows))

    def reset(self) -> None:
        with self.lock:
            self.events = []
            self._save()


class AIDraftingService:
    def __init__(self, audit_store: AIDraftAuditStore | None = None, preflight_runner=None) -> None:
        self.audit = audit_store or get_ai_draft_audit_store()
        self.preflight_runner = preflight_runner or preflight
        self.lock = threading.Lock()
        self.candidates: dict[str, dict[str, Any]] = {}

    def status(self) -> dict[str, Any]:
        return provider_status()

    def generate(self, package: dict[str, Any], *, key: str, style: str, role: str) -> dict[str, Any]:
        actor = _actor(role)
        if style not in STYLES:
            raise ValueError("Unknown AI drafting style.")
        target, client_facing = _target(package, key)
        source_version = package["current_version"]
        try:
            content, provider, model = _provider_rewrite(_prompt(key=key, source=target["content"], client_facing=client_facing, style=style))
        except RuntimeError:
            self.audit.record(origin="system", action="ai_draft_provider_failed", package=package, actor=actor, detail={"target_key": key, "source_version": source_version, "prompt_version": PROMPT_VERSION})
            raise
        if not content or len(content) > 4000:
            raise ValueError("AI output was empty or exceeded the controlled draft length.")
        checks = _guardrails(package, key, content, self.preflight_runner)
        digest = _digest(content)
        expiry = _now() + timedelta(minutes=EXPIRY_MINUTES)
        provenance = AIDraftProvenance(provider, model, PROMPT_VERSION, source_version, key, digest).to_dict()
        candidate = AIDraftCandidate(str(uuid4()), package["id"], key, style, content if all(item["status"] == "pass" for item in checks) else None, all(item["status"] == "pass" for item in checks), [AIDraftGuardrail(**item) for item in checks], _stamp(expiry), AIDraftProvenance(**provenance)).to_dict()
        detail = {"target_key": key, "style": style, "source_version": source_version, "provider": provider, "model": model, "prompt_version": PROMPT_VERSION, "candidate_digest": digest, "guardrails": [{"id": item["id"], "status": item["status"]} for item in checks], "expires_at": candidate["expires_at"]}
        if not candidate["can_apply"]:
            self.audit.record(origin="system", action="ai_draft_blocked", package=package, actor=actor, detail=detail)
            return candidate
        with self.lock:
            self.candidates[candidate["id"]] = candidate
        self.audit.record(origin="system", action="ai_draft_generated", package=package, actor=actor, detail=detail)
        return candidate

    def apply(self, package: dict[str, Any], *, draft_id: str, rationale: str, role: str) -> dict[str, Any]:
        actor = _actor(role)
        rationale = str(rationale or "").strip()
        if not rationale:
            raise ValueError("An RM rationale is required to apply an AI meeting draft.")
        with self.lock:
            candidate = self.candidates.get(draft_id)
        if not candidate or candidate["package_id"] != package["id"]:
            raise KeyError("Unknown AI draft candidate.")
        if _now() >= datetime.fromisoformat(candidate["expires_at"]):
            with self.lock:
                self.candidates.pop(draft_id, None)
            self.audit.record(origin="system", action="ai_draft_expired", package=package, actor=actor, detail={"target_key": candidate["target_key"], "source_version": candidate["provenance"]["source_version"], "candidate_digest": candidate["provenance"]["candidate_digest"]})
            raise PermissionError("This AI draft preview expired. Generate a fresh draft.")
        if package["current_version"] != candidate["provenance"]["source_version"]:
            raise PermissionError("The meeting package changed after this AI preview. Generate a fresh draft.")
        checks = _guardrails(package, candidate["target_key"], str(candidate["content"] or ""), self.preflight_runner)
        if not candidate["can_apply"] or not all(item["status"] == "pass" for item in checks):
            self.audit.record(origin="system", action="ai_draft_blocked_on_apply", package=package, actor=actor, detail={"target_key": candidate["target_key"], "candidate_digest": candidate["provenance"]["candidate_digest"], "guardrails": [{"id": item["id"], "status": item["status"]} for item in checks]})
            raise PermissionError("The AI draft no longer passes the controlled checks.")
        target, _ = _target(package, candidate["target_key"])
        version = update_section(package, candidate["target_key"], candidate["content"], target["evidence_refs"], actor=actor, reason=f"ai_applied:{candidate['style']}", provenance={**candidate["provenance"], "draft_id": draft_id, "rm_rationale": rationale})
        with self.lock:
            self.candidates.pop(draft_id, None)
        self.audit.record(origin="user_decision", action="ai_draft_applied", package=package, actor=actor, detail={"target_key": candidate["target_key"], "style": candidate["style"], "source_version": candidate["provenance"]["source_version"], "provider": candidate["provenance"]["provider"], "model": candidate["provenance"]["model"], "prompt_version": PROMPT_VERSION, "candidate_digest": candidate["provenance"]["candidate_digest"], "rationale": rationale})
        return version

    def reset(self) -> None:
        with self.lock:
            self.candidates = {}
        self.audit.reset()


_AUDIT_STORE: AIDraftAuditStore | None = None
_SERVICE: AIDraftingService | None = None


def get_ai_draft_audit_store() -> AIDraftAuditStore:
    global _AUDIT_STORE
    if _AUDIT_STORE is None:
        _AUDIT_STORE = AIDraftAuditStore()
    return _AUDIT_STORE


def get_ai_drafting_service() -> AIDraftingService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = AIDraftingService()
    return _SERVICE
