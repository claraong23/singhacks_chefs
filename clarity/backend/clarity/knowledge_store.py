"""Local, citation-first retrieval over approved synthetic reference documents."""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import config

PATH = config.REPO_ROOT / "clarity" / "state" / "knowledge.json"
SEED_PATH = config.REPO_ROOT / "clarity" / "fixtures" / "knowledge_documents.json"
PUBLIC_ROLES = {"rm", "credit", "wealth_planning", "investment", "compliance_audit", "operations"}
AUTHOR_ROLES = {"operations"}
REVIEWER_ROLES = {"compliance_audit"}
BLOCKED_SOURCE_PARTS = (".csv", "rm_notes", "transactions", "event_log", "http://", "https://")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return str(uuid4())


def actor_for(role: str) -> str:
    actors = {"rm": "RM-SG-014", "credit": "CREDIT-HK-001", "wealth_planning": "PLANNING-SG-001",
              "investment": "INVESTMENT-SG-001", "compliance_audit": "COMPLIANCE-SG-001", "operations": "OPS-SG-001"}
    if role not in actors:
        raise ValueError("Unknown simulated role.")
    return actors[role]


def tokens(value: str) -> list[str]:
    return [item.lower() for item in re.findall(r"[a-zA-Z][a-zA-Z0-9_/-]*", value) if len(item) > 1]


def _safe_sources(values: Any) -> list[str]:
    if not isinstance(values, list) or not values or not all(isinstance(item, str) and item.strip() for item in values):
        raise ValueError("source_refs must be a non-empty list of controlled local references.")
    refs = [item.strip() for item in values]
    if any(any(blocked in item.lower() for blocked in BLOCKED_SOURCE_PARTS) for item in refs):
        raise ValueError("Knowledge documents cannot cite client data files, RM notes, or external sources.")
    return refs


def _text(value: Any, name: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError(f"{name} is required.")
    return value


class KnowledgeRepository:
    def __init__(self, path: Path = PATH) -> None:
        self.path = path
        self.lock = threading.Lock()
        self.data: dict[str, Any] = {"documents": {}, "audit": []}
        self._load()
        self._seed()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            self.data.update({key: saved.get(key, self.data[key]) for key in self.data})
        except (OSError, json.JSONDecodeError):
            pass

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _seed(self) -> None:
        if self.data["documents"]:
            return
        seeds = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        for item in seeds:
            version = {"version": 1, "status": "approved", "body": item["body"], "source_refs": item["source_refs"],
                       "effective_date": item["effective_date"], "created_at": config.AS_OF,
                       "created_by": "Clarity synthetic corpus", "rationale": "Seeded fictional prototype reference."}
            self.data["documents"][item["id"]] = {"id": item["id"], "title": item["title"], "category": item["category"],
                "tags": item["tags"], "owner": item["owner"], "current_version": 1, "approved_version": 1,
                "seeded": True, "versions": [version]}
        self._save()

    def _event(self, *, origin: str, object_id: str, action: str, actor: str, role: str,
               detail: dict[str, Any] | None = None) -> None:
        self.data["audit"].append({"id": new_id(), "timestamp": now(), "origin": origin,
            "object_type": "knowledge_document", "object_id": object_id, "action": action, "actor": actor,
            "client_id": None, "insight_id": None, "detail": {"role": role, **(detail or {})}})

    def _version(self, document: dict[str, Any], number: int | None = None) -> dict[str, Any]:
        target = number if number is not None else document["current_version"]
        version = next((item for item in document["versions"] if item["version"] == target), None)
        if not version:
            raise KeyError("Unknown document version.")
        return version

    def _public(self, document: dict[str, Any]) -> dict[str, Any]:
        version = self._version(document, document["approved_version"])
        return {**{key: document[key] for key in ("id", "title", "category", "tags", "owner", "approved_version")},
                "current_version": version["version"], "version": version}

    def list(self, role: str) -> list[dict[str, Any]]:
        if role not in PUBLIC_ROLES:
            raise ValueError("Unknown simulated role.")
        rows = list(self.data["documents"].values())
        if role not in AUTHOR_ROLES | REVIEWER_ROLES:
            return sorted([self._public(item) for item in rows if item.get("approved_version")], key=lambda item: item["title"])
        return sorted(rows, key=lambda item: item["title"])

    def get(self, document_id: str, role: str) -> dict[str, Any]:
        document = self.data["documents"].get(document_id)
        if not document:
            raise KeyError("Unknown knowledge document.")
        if role in AUTHOR_ROLES | REVIEWER_ROLES:
            return document
        if role not in PUBLIC_ROLES or not document.get("approved_version"):
            raise KeyError("Unknown approved knowledge document.")
        return self._public(document)

    def create(self, payload: dict[str, Any], role: str) -> dict[str, Any]:
        if role not in AUTHOR_ROLES:
            raise PermissionError("Only Product Operations can create knowledge drafts.")
        with self.lock:
            document_id = "KN-" + new_id()
            version = {"version": 1, "status": "draft", "body": _text(payload.get("body"), "body"),
                "source_refs": _safe_sources(payload.get("source_refs")), "effective_date": _text(payload.get("effective_date"), "effective_date"),
                "created_at": now(), "created_by": actor_for(role), "rationale": _text(payload.get("rationale"), "rationale")}
            document = {"id": document_id, "title": _text(payload.get("title"), "title"),
                "category": _text(payload.get("category"), "category"), "tags": tokens(" ".join(payload.get("tags") or [])),
                "owner": _text(payload.get("owner"), "owner"), "current_version": 1, "approved_version": None,
                "seeded": False, "versions": [version]}
            if not document["tags"]:
                raise ValueError("At least one tag is required.")
            self.data["documents"][document_id] = document
            self._event(origin="source_data", object_id=document_id, action="draft_created", actor=actor_for(role), role=role, detail={"version": 1})
            self._save()
            return document

    def revise(self, document_id: str, payload: dict[str, Any], role: str) -> dict[str, Any]:
        if role not in AUTHOR_ROLES:
            raise PermissionError("Only Product Operations can revise knowledge drafts.")
        with self.lock:
            document = self.data["documents"].get(document_id)
            if not document:
                raise KeyError("Unknown knowledge document.")
            current = self._version(document)
            if current["status"] == "draft":
                raise ValueError("Revise the existing draft before creating another version.")
            number = max(item["version"] for item in document["versions"]) + 1
            version = {"version": number, "status": "draft", "body": _text(payload.get("body"), "body"),
                "source_refs": _safe_sources(payload.get("source_refs")), "effective_date": _text(payload.get("effective_date"), "effective_date"),
                "created_at": now(), "created_by": actor_for(role), "rationale": _text(payload.get("rationale"), "rationale")}
            document["versions"].append(version); document["current_version"] = number
            self._event(origin="source_data", object_id=document_id, action="revision_drafted", actor=actor_for(role), role=role, detail={"version": number})
            self._save()
            return document

    def submit(self, document_id: str, rationale: str, role: str) -> dict[str, Any]:
        if role not in AUTHOR_ROLES:
            raise PermissionError("Only Product Operations can submit a knowledge draft.")
        return self._change(document_id, "draft", "submitted", rationale, role, "submitted")

    def review(self, document_id: str, approve: bool, rationale: str, role: str) -> dict[str, Any]:
        if role not in REVIEWER_ROLES:
            raise PermissionError("Only Compliance/Audit can approve or reject a knowledge draft.")
        document = self._change(document_id, "submitted", "approved" if approve else "rejected", rationale, role, "approved" if approve else "rejected")
        if approve:
            with self.lock:
                for item in document["versions"]:
                    if item["version"] != document["current_version"] and item["status"] == "approved":
                        item["status"] = "superseded"
                        self._event(origin="user_decision", object_id=document_id, action="superseded", actor=actor_for(role), role=role, detail={"version": item["version"]})
                document["approved_version"] = document["current_version"]
                self._save()
        return document

    def _change(self, document_id: str, expected: str, target: str, rationale: str, role: str, action: str) -> dict[str, Any]:
        rationale = _text(rationale, "rationale")
        with self.lock:
            document = self.data["documents"].get(document_id)
            if not document:
                raise KeyError("Unknown knowledge document.")
            version = self._version(document)
            if version["status"] != expected:
                raise ValueError(f"Only {expected} documents can be {target}.")
            version["status"] = target; version["reviewed_by"] = actor_for(role); version["reviewed_at"] = now(); version["review_rationale"] = rationale
            self._event(origin="user_decision", object_id=document_id, action=action, actor=actor_for(role), role=role, detail={"version": version["version"], "rationale": rationale})
            self._save()
            return document

    def search(self, *, query: str, category: str | None, tag: str | None, role: str, location: str) -> list[dict[str, Any]]:
        if role not in PUBLIC_ROLES:
            raise ValueError("Unknown simulated role.")
        terms = tokens(query)
        results: list[dict[str, Any]] = []
        for document in self.data["documents"].values():
            version = self._version(document, document["approved_version"]) if document["approved_version"] else None
            if not version or version["status"] != "approved":
                continue
            if category and document["category"] != category:
                continue
            if tag and tag not in document["tags"]:
                continue
            fields = {"title": tokens(document["title"]), "category": tokens(document["category"]), "tags": tokens(" ".join(document["tags"])), "body": tokens(version["body"])}
            matched_terms = [term for term in terms if any(term in words for words in fields.values())]
            matched_fields = [field for field, words in fields.items() if any(term in words for term in matched_terms)]
            if terms and not matched_fields:
                continue
            score = sum((12 if field == "title" else 7 if field == "tags" else 4 if field == "category" else 1) * sum(term in words for term in matched_terms) for field, words in fields.items())
            excerpt = _excerpt(version["body"], terms)
            results.append({"citation": {"document_id": document["id"], "version": version["version"], "title": document["title"], "effective_date": version["effective_date"], "source_refs": version["source_refs"]},
                "category": document["category"], "tags": document["tags"], "excerpt": excerpt, "matched_terms": matched_terms, "matched_fields": matched_fields, "score": score})
        results.sort(key=lambda item: (-item["score"], item["citation"]["title"]))
        self._event(origin="system", object_id="knowledge-search", action="retrieval_served", actor=actor_for(role), role=role, detail={"location": location, "query": query, "category": category, "tag": tag, "document_versions": [f"{item['citation']['document_id']}:v{item['citation']['version']}" for item in results]})
        self._save()
        return results[:10]

    def audit(self, client_id: str | None = None) -> list[dict[str, Any]]:
        return list(reversed(self.data["audit"]))

    def reset(self) -> None:
        with self.lock:
            self.data = {"documents": {}, "audit": []}
            self._seed()


def _excerpt(body: str, terms: list[str]) -> str:
    lowered = body.lower()
    first = next((lowered.find(term) for term in terms if lowered.find(term) >= 0), 0)
    start = max(0, first - 90); end = min(len(body), first + 220)
    return ("…" if start else "") + body[start:end].strip() + ("…" if end < len(body) else "")


_STORE: KnowledgeRepository | None = None


def get_knowledge_repository() -> KnowledgeRepository:
    global _STORE
    if _STORE is None:
        _STORE = KnowledgeRepository()
    return _STORE
