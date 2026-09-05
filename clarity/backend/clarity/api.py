"""HTTP API.

Standard library only, on purpose. The analytics layer returns plain
dictionaries, so the serving framework is an implementation detail -- swapping
this for FastAPI is a mechanical change and the payloads do not move. What it
buys on a hackathon weekend is that ``python -m clarity.api`` works on any
laptop with Python, with no install step and nothing to go wrong at the demo.

Run:
    python -m clarity.api            # serves on http://127.0.0.1:8000

Routes:
    GET  /api/health
    GET  /api/meta
    GET  /api/book
    GET  /api/clients/<client_id>
    GET  /api/clients/<client_id>/scenario-templates
    GET  /api/clients/<client_id>/scenarios
    GET  /api/clients/<client_id>/meeting-packages
    GET  /api/meeting-packages/<package_id>
    GET  /api/events
    GET  /api/audit
    POST /api/insights/<insight_id>/readiness
    POST /api/insights/<insight_id>/decision
    POST /api/clients/<client_id>/scenarios/evaluate
    POST /api/clients/<client_id>/scenarios
    POST /api/insights/<insight_id>/meeting-packages
    POST /api/meeting-packages/<package_id>/(versions|regenerate|restore|preflight|handoff|ai-drafts)
    POST /api/meeting-packages/<package_id>/ai-drafts/<draft_id>/apply
    POST /api/reset
Anything else is served from ../frontend/dist if it has been built, so the
whole product runs from one process.
"""

from __future__ import annotations

import hmac
import json
import mimetypes
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import config
from .ai_adapter import draft_insight_narrative
from .actions import options_for
from .analytics.attribution import attribute, detect_meaningful_changes
from .analytics.event_impact import event_impact_view
from .attribution_ai import generate_client_attribution
from .contracts import Category, MeetingHandoffEvent, Severity
from .dossier import all_events, book_view, client_dossier
from .gates import evaluate_readiness
from .loaders import get_book
from .meeting import create_package, preflight, regenerate_section, restore_version, update_section
from .meeting_store import get_meeting_store, new_id, now as meeting_now
from .meeting_draft_store import get_meeting_draft_store
from .review import InvalidTransitionError, VALID_STATUSES, get_store
from .scenario_store import get_scenario_store
from .scenarios import evaluate_scenario, templates_for_client
from .audit import timeline
from .calibration import create_policy, evaluate as evaluate_policy, validate_feedback, validate_weights
from .calibration_store import TEMPLATES, get_calibration_store
from .followthrough import (
    actor as follow_actor, ensure_create, ensure_update, evidence_record, outcome_record,
    reevaluation_update, required_text, status_update, work_record,
)
from .followthrough_store import get_followthrough_store
from .knowledge_store import get_knowledge_repository
from .ai_drafting import get_ai_drafting_service
from .integration_store import get_integration_store
from .signals.base import SignalContext, run_for_client
from .signals.holding_explain import explain_holding

FRONTEND_DIST = config.REPO_ROOT / "clarity" / "frontend" / "dist"
CALIBRATION_ACTORS = {"rm": "RM-SG-014", "compliance_audit": "COMPLIANCE-SG-001"}


def _calibration_actor(role: str) -> str:
    if role not in CALIBRATION_ACTORS:
        raise PermissionError("This simulated role cannot change priority calibration.")
    return CALIBRATION_ACTORS[role]


def _meta() -> dict:
    book = get_book()
    return {
        "as_of": config.AS_OF,
        "snapshots": [
            {"date": d, "label": config.SNAPSHOT_LABELS.get(d, d)}
            for d in config.SNAPSHOTS
        ],
        "asset_classes": list(config.ASSET_CLASSES),
        "liquidity_tiers": list(config.LIQUIDITY_TIERS),
        "categories": [c.value for c in Category],
        "severities": [s.value for s in Severity],
        "statuses": list(VALID_STATUSES),
        "thresholds": {
            "mandate_tolerance_pct": config.MANDATE_TOLERANCE_PCT,
            "concentration_warn_pct": config.HOUSEHOLD_CONCENTRATION_WARN_PCT,
            "concentration_high_pct": config.HOUSEHOLD_CONCENTRATION_HIGH_PCT,
            "ltv_warn_headroom_pp": config.LTV_WARN_HEADROOM_PP,
            "ltv_critical_headroom_pp": config.LTV_CRITICAL_HEADROOM_PP,
            "near_term_months": config.NEAR_TERM_MONTHS,
            "liquidity_cover_warn": config.LIQUIDITY_COVER_WARN,
        },
        "data_warnings": book.warnings,
    }


def _decision_subject(client_id: str, insight_id: str):
    """Resolve the deterministic Task 1/2 payload used by Task 3's gates."""
    book = get_book()
    if client_id not in book.clients:
        raise ValueError(f"Unknown client {client_id}")
    ctx = SignalContext(book=book, client_id=client_id)
    insight = next(
        (item for item in run_for_client(client_id, book) if item.id == insight_id),
        None,
    )
    if insight is None:
        raise ValueError(f"Unknown insight {insight_id} for client {client_id}")
    return insight, options_for(ctx, insight)


def _client_id_for(insight_id: str, payload: dict) -> str:
    return payload.get("client_id") or "-".join(insight_id.split("-")[:2])


def _follow_links(payload: dict) -> str:
    """Validate stable collaboration links without changing source records."""
    client_id = required_text(payload, "client_id")
    if client_id not in get_book().clients:
        raise KeyError(f"Unknown client {client_id}")
    insight_id = payload.get("insight_id")
    if insight_id:
        _decision_subject(client_id, insight_id)
    package_id = payload.get("meeting_package_id")
    if package_id:
        package = get_meeting_store().get(package_id)
        if not package or package["client_id"] != client_id or (insight_id and package["insight_id"] != insight_id):
            raise ValueError("Meeting package link does not belong to this client/finding.")
    return client_id


def _integration_work_link(payload: dict) -> dict:
    """Resolve a stable local work-record link without contacting an external system."""
    client_id = required_text(payload, "client_id")
    if client_id not in get_book().clients:
        raise KeyError(f"Unknown client {client_id}")
    kind, record_id = required_text(payload, "work_record_type"), required_text(payload, "work_record_id")
    if kind in {"task", "referral"}:
        collection = "tasks" if kind == "task" else "referrals"
        record = get_followthrough_store().data[collection].get(record_id)
        if not record or record.get("client_id") != client_id:
            raise ValueError("The linked follow-through record does not belong to this client.")
        return {"work_record_version": str(len(record.get("history", []))), "insight_id": record.get("insight_id"), "meeting_package_id": record.get("meeting_package_id"), "evidence_refs": record.get("evidence_refs") or []}
    if kind == "meeting_package":
        package = get_meeting_store().get(record_id)
        if not package or package.get("client_id") != client_id:
            raise ValueError("The linked meeting package does not belong to this client.")
        evidence = [f"{item.get('source_file')}:{item.get('row_or_id')}" for item in package.get("source", {}).get("evidence", [])]
        return {"work_record_version": str(package["current_version"]), "insight_id": package["insight_id"], "meeting_package_id": package["id"], "evidence_refs": evidence}
    if kind == "client_ready_finding":
        insight, _ = _decision_subject(client_id, record_id)
        if get_store().status_of(record_id) != "client_ready":
            raise ValueError("Only a client-ready finding can be handed off as a work order.")
        return {"work_record_version": str(len(get_store().audit(client_id, limit=1000))), "insight_id": insight.id, "meeting_package_id": None, "evidence_refs": [f"{item.source_file}:{item.row_or_id}" for item in insight.evidence]}
    raise ValueError("Unknown work_record_type.")


def _readiness(insight_id: str, payload: dict):
    client_id = _client_id_for(insight_id, payload)
    insight, options = _decision_subject(client_id, insight_id)
    readiness = evaluate_readiness(
        insight,
        options,
        selected_option_id=payload.get("selected_option_id"),
        rm_note=payload.get("rm_note", ""),
        edited_next_step=payload.get("edited_next_step"),
    )
    return client_id, readiness


def _saved_scenario(payload: dict, client_id: str, insight_id: str) -> dict | None:
    scenario_id = payload.get("selected_scenario_id")
    if not scenario_id:
        return None
    scenario = get_scenario_store().get(scenario_id)
    if scenario is None:
        raise ValueError(f"Unknown saved scenario {scenario_id}")
    result = scenario.get("result", {})
    if result.get("client_id") != client_id or result.get("insight_id") != insight_id:
        raise ValueError("Saved scenario does not belong to this client finding.")
    selected_option_id = payload.get("selected_option_id")
    if selected_option_id and result.get("option_id") != selected_option_id:
        raise ValueError("Saved scenario does not match the selected action option.")
    return scenario


class ClarityHandler(BaseHTTPRequestHandler):
    server_version = "Clarity/0.1"

    # -- helpers ------------------------------------------------------------

    def _send_json(self, payload, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        content_type, _ = mimetypes.guess_type(str(path))
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _authorized(self) -> bool:
        """Optional bearer protection for mutations; disabled for local demos."""
        if not config.API_TOKEN:
            return True
        supplied = self.headers.get("Authorization", "")
        return hmac.compare_digest(supplied, f"Bearer {config.API_TOKEN}")

    def log_message(self, fmt: str, *args) -> None:  # quieter console
        print(f"  {self.command} {self.path} -> {args[1] if len(args) > 1 else ''}")

    # -- routing ------------------------------------------------------------

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json({}, 204)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)
        try:
            if path == "/api/health":
                return self._send_json({"status": "ok", "as_of": config.AS_OF})
            if path == "/api/meta":
                return self._send_json(_meta())
            if path == "/api/book":
                return self._send_json(book_view())
            if path == "/api/priority-policies":
                store = get_calibration_store()
                return self._send_json({"active_policy": store.active(), "policies": store.list(), "templates": TEMPLATES})
            if path == "/api/ai-drafting/status":
                return self._send_json(get_ai_drafting_service().status())
            if path == "/api/integrations/capabilities":
                return self._send_json(get_integration_store().capabilities())
            if path == "/api/integrations":
                role = query.get("role", ["rm"])[0]
                return self._send_json(get_integration_store().list(role, query.get("client_id", [None])[0]))
            if path == "/api/knowledge-documents":
                role = query.get("role", ["rm"])[0]
                return self._send_json({"documents": get_knowledge_repository().list(role)})
            if path == "/api/knowledge/search":
                role = query.get("role", ["rm"])[0]
                results = get_knowledge_repository().search(
                    query=query.get("q", [""])[0], category=query.get("category", [None])[0],
                    tag=query.get("tag", [None])[0], role=role, location=query.get("location", ["knowledge_library"])[0],
                )
                return self._send_json({"results": results})
            if path.startswith("/api/knowledge-documents/"):
                document_id = path[len("/api/knowledge-documents/") :]
                if "/" not in document_id:
                    role = query.get("role", ["rm"])[0]
                    return self._send_json({"document": get_knowledge_repository().get(document_id, role)})
            if path.startswith("/api/priority-policies/") and path.endswith("/evaluation"):
                policy_id = path[len("/api/priority-policies/") : -len("/evaluation")]
                return self._send_json({"evaluation": evaluate_policy(policy_id)})
            if path == "/api/events":
                return self._send_json({"events": all_events()})
            if path.startswith("/api/events/") and path.endswith("/impact"):
                event_id = path[len("/api/events/") : -len("/impact")].strip("/")
                if event_id not in get_book().events_by_id:
                    return self._send_json({"error": f"Unknown event {event_id}"}, 404)
                return self._send_json(event_impact_view(get_book(), event_id))
            if path == "/api/audit":
                audit = timeline(query.get("client_id", [None])[0])
                for field in ("origin", "actor", "object_type", "insight_id"):
                    value = query.get(field, [None])[0]
                    if value:
                        audit = [item for item in audit if item.get(field) == value]
                return self._send_json({"audit": audit})
            if path == "/api/follow-through":
                client_id = query.get("client_id", [None])[0]
                role = query.get("role", ["rm"])[0]
                store = get_followthrough_store()
                payload = {key: store.list(key, client_id=client_id) for key in ("tasks", "referrals", "outcomes", "evidence_updates", "reevaluations")}
                if role in {"credit", "wealth_planning", "investment"}:
                    for key in ("tasks", "referrals"):
                        payload[key] = [item for item in payload[key] if item.get("owner_role") == role]
                    payload["outcomes"], payload["evidence_updates"], payload["reevaluations"] = [], [], []
                elif role == "operations":
                    payload["tasks"], payload["referrals"], payload["outcomes"] = [], [], []
                elif role == "compliance_audit":
                    payload = {key: [] for key in payload}
                return self._send_json(payload)
            if path.startswith("/api/clients/") and path.endswith("/scenario-templates"):
                client_id = path[len("/api/clients/") : -len("/scenario-templates")]
                return self._send_json(
                    {"templates": [item.to_dict() for item in templates_for_client(client_id)]}
                )
            if path.startswith("/api/clients/") and path.endswith("/scenarios"):
                client_id = path[len("/api/clients/") : -len("/scenarios")]
                if client_id not in get_book().clients:
                    return self._send_json({"error": f"Unknown client {client_id}"}, 404)
                return self._send_json({"scenarios": get_scenario_store().list_for_client(client_id)})
            if path.startswith("/api/clients/") and path.endswith("/meeting-packages"):
                client_id = path[len("/api/clients/") : -len("/meeting-packages")]
                if client_id not in get_book().clients:
                    return self._send_json({"error": f"Unknown client {client_id}"}, 404)
                return self._send_json({"packages": get_meeting_store().list_for_client(client_id)})
            if path.startswith("/api/clients/") and path.endswith("/meeting-drafts"):
                client_id = path[len("/api/clients/") : -len("/meeting-drafts")]
                if client_id not in get_book().clients:
                    return self._send_json({"error": f"Unknown client {client_id}"}, 404)
                return self._send_json({"drafts": get_meeting_draft_store().list_for_client(client_id)})
            if path.startswith("/api/meeting-packages/"):
                package_id = path[len("/api/meeting-packages/") :].strip("/")
                package = get_meeting_store().get(package_id)
                if package is None:
                    return self._send_json({"error": f"Unknown meeting package {package_id}"}, 404)
                return self._send_json({"package": package})
            if path.startswith("/api/clients/") and "/changes" in path:
                client_id = (
                    path.split("/api/clients/", 1)[1].split("/changes", 1)[0].strip("/")
                )
                if client_id not in get_book().clients:
                    return self._send_json({"error": f"Unknown client {client_id}"}, 404)
                query = parse_qs(urlparse(self.path).query)
                start = query.get("from", [config.BASELINE_SNAPSHOT])[0]
                end = query.get("to", [config.AS_OF])[0]
                portfolio_id = query.get("portfolio", [None])[0]
                if portfolio_id in ("", "all", "undefined", "null"):
                    portfolio_id = None
                changes = detect_meaningful_changes(
                    get_book(), client_id, start, end, portfolio_id
                )
                attr = attribute(get_book(), client_id, start, end, portfolio_id)
                return self._send_json(
                    {
                        "client_id": client_id,
                        "start": start,
                        "end": end,
                        "portfolio_id": portfolio_id,
                        "changes": [c.to_dict() for c in changes],
                        "attribution": attr.to_dict(),
                    }
                )
            if path.startswith("/api/clients/"):
                client_id = path.split("/api/clients/", 1)[1].strip("/")
                if client_id not in get_book().clients:
                    return self._send_json({"error": f"Unknown client {client_id}"}, 404)
                return self._send_json(client_dossier(client_id))
            if path.startswith("/api/"):
                return self._send_json({"error": "Not found"}, 404)
            return self._serve_static(path)
        except Exception as exc:  # keep the demo alive, show the cause
            traceback.print_exc()
            return self._send_json({"error": str(exc)}, 500)

    def do_POST(self) -> None:  # noqa: N802
        path = unquote(urlparse(self.path).path)
        try:
            if not self._authorized():
                return self._send_json({"error": "Unauthorized"}, 401)
            if path == "/api/reset":
                get_store().reset()
                get_scenario_store().reset()
                get_meeting_store().reset()
                get_followthrough_store().reset()
                get_calibration_store().reset()
                get_knowledge_repository().reset()
                get_ai_drafting_service().reset()
                get_integration_store().reset()
                return self._send_json({"status": "reset"})
            if path == "/api/integrations/inbound":
                payload = self._read_json(); role = payload.get("role") or "operations"
                client_id = _follow_links({"client_id": payload.get("client_id"), "insight_id": (payload.get("affected_insight_ids") or [None])[0]})
                for insight_id in payload.get("affected_insight_ids") or []:
                    _decision_subject(client_id, insight_id)
                event, replayed = get_integration_store().receive(payload, role)
                return self._send_json({"event": event, "replayed": replayed}, 200 if replayed else 201)
            if path.startswith("/api/integrations/inbound/"):
                remainder = path[len("/api/integrations/inbound/") :].strip("/")
                event_id, _, action = remainder.partition("/")
                if action not in {"accept", "reject"}:
                    return self._send_json({"error": "Unknown inbound integration action."}, 404)
                payload = self._read_json(); role = payload.get("role") or "operations"
                if role != "operations":
                    raise PermissionError("Only Product Operations can accept or reject inbound integration events.")
                integration = get_integration_store(); event = integration.data["inbound"].get(event_id)
                if event is None:
                    return self._send_json({"error": "Unknown inbound integration event."}, 404)
                rationale = payload.get("rationale", "")
                if not isinstance(rationale, str) or not rationale.strip():
                    raise ValueError("An Operations rationale is required.")
                if event.get("operations_disposition") is not None:
                    if event["operations_disposition"] == ("accepted" if action == "accept" else "rejected"):
                        return self._send_json({"event": event, "replayed": True})
                    return self._send_json({"error": "Inbound event already has an Operations disposition."}, 409)
                if action == "reject":
                    return self._send_json({"event": integration.disposition(event_id, accepted=False, rationale=rationale, role=role)})
                update_payload = {"client_id": event["client_id"], "source_type": "document", "source_ref": event["source_ref"], "summary": event["summary"], "received_at": event["occurred_at"], "affected_insight_ids": event["affected_insight_ids"]}
                update = get_followthrough_store().create("evidence_updates", evidence_record(update_payload, follow_actor(role)), origin="source_data", actor=follow_actor(role))
                reeval = get_followthrough_store().create("reevaluations", {"kind": "reevaluation", "client_id": event["client_id"], "evidence_update_id": update["id"], "affected_insight_ids": update["affected_insight_ids"], "owner_role": "operations", "status": "queued"}, origin="source_data", actor=follow_actor(role))
                saved = integration.disposition(event_id, accepted=True, rationale=rationale, role=role, evidence_update_id=update["id"], reevaluation_id=reeval["id"])
                return self._send_json({"event": saved, "evidence_update": update, "reevaluation": reeval})
            if path == "/api/integrations/work-orders":
                payload = self._read_json(); role = payload.get("role") or "rm"
                order, replayed = get_integration_store().prepare_work_order({**payload, **_integration_work_link(payload)}, role)
                return self._send_json({"work_order": order, "replayed": replayed}, 200 if replayed else 201)
            if path.startswith("/api/integrations/work-orders/"):
                remainder = path[len("/api/integrations/work-orders/") :].strip("/")
                order_id, _, action = remainder.partition("/")
                payload = self._read_json(); role = payload.get("role") or "rm"; integration = get_integration_store()
                if action == "dispatch":
                    order, replayed = integration.dispatch(order_id, role)
                    return self._send_json({"work_order": order, "replayed": replayed})
                if action == "acknowledge":
                    return self._send_json({"work_order": integration.acknowledge(order_id, role)})
                return self._send_json({"error": "Unknown work-order action."}, 404)
            if path == "/api/knowledge-documents":
                payload = self._read_json(); role = payload.get("role", "operations")
                return self._send_json({"document": get_knowledge_repository().create(payload, role)}, 201)
            if path.startswith("/api/knowledge-documents/"):
                remainder = path[len("/api/knowledge-documents/") :].strip("/")
                document_id, _, action = remainder.partition("/")
                payload = self._read_json(); role = payload.get("role", "rm")
                repository = get_knowledge_repository()
                if action == "revise":
                    return self._send_json({"document": repository.revise(document_id, payload, role)})
                if action == "submit":
                    return self._send_json({"document": repository.submit(document_id, payload.get("rationale"), role)})
                if action == "approve":
                    return self._send_json({"document": repository.review(document_id, True, payload.get("rationale"), role)})
                if action == "reject":
                    return self._send_json({"document": repository.review(document_id, False, payload.get("rationale"), role)})
                return self._send_json({"error": "Unknown knowledge document action."}, 404)
            if path == "/api/priority-policies":
                payload = self._read_json()
                if payload.get("role", "rm") != "rm":
                    raise PermissionError("Only the RM role can propose a priority policy.")
                policy = create_policy(payload, _calibration_actor("rm"))
                return self._send_json({"policy": policy, "evaluation": evaluate_policy(policy["id"])}, 201)
            if path.startswith("/api/priority-policies/"):
                remainder = path[len("/api/priority-policies/") :].strip("/")
                policy_id, _, action = remainder.partition("/")
                payload = self._read_json()
                role = payload.get("role", "rm")
                store = get_calibration_store()
                if action == "revise":
                    if role != "rm":
                        raise PermissionError("Only the RM role can revise a priority policy.")
                    name = str(payload.get("name") or "").strip()
                    rationale = str(payload.get("rationale") or "").strip()
                    if not name or not rationale:
                        raise ValueError("A policy name and RM rationale are required.")
                    saved = store.revise(policy_id, name=name, weights=validate_weights(payload.get("weights")), rationale=rationale, actor=_calibration_actor(role))
                    return self._send_json({"policy": saved, "evaluation": evaluate_policy(policy_id)})
                if action == "submit":
                    if role != "rm":
                        raise PermissionError("Only the RM role can submit a priority policy.")
                    rationale = str(payload.get("rationale") or "").strip()
                    if not rationale:
                        raise ValueError("An RM submission rationale is required.")
                    return self._send_json({"policy": store.transition(policy_id, status="submitted", actor=_calibration_actor(role), rationale=rationale)})
                if action in {"approve", "reject"}:
                    if role != "compliance_audit":
                        raise PermissionError("Only Compliance/Audit can approve or reject a priority policy.")
                    rationale = str(payload.get("rationale") or "").strip()
                    if not rationale:
                        raise ValueError("A Compliance/Audit rationale is required.")
                    if action == "approve":
                        evaluation = evaluate_policy(policy_id)
                        if not evaluation["activation_eligible"]:
                            return self._send_json({"error": "Priority policy lacks the required feedback coverage.", "evaluation": evaluation}, 409)
                        saved = store.activate(policy_id, actor=_calibration_actor(role), rationale=rationale)
                    else:
                        saved = store.transition(policy_id, status="rejected", actor=_calibration_actor(role), rationale=rationale)
                    return self._send_json({"policy": saved})
            if path == "/api/follow-through/tasks" or path == "/api/follow-through/referrals":
                payload = self._read_json()
                role = payload.get("role") or "rm"
                kind = "task" if path.endswith("tasks") else "referral"
                ensure_create(role, kind)
                _follow_links(payload)
                record = work_record(payload, kind=kind)
                saved = get_followthrough_store().create(
                    "tasks" if kind == "task" else "referrals", record,
                    origin="user_decision", actor=follow_actor(role),
                )
                return self._send_json({kind: saved}, 201)
            if path == "/api/follow-through/outcomes":
                payload = self._read_json(); role = payload.get("role") or "rm"
                ensure_create(role, "outcome"); _follow_links(payload)
                saved = get_followthrough_store().create("outcomes", outcome_record(payload, follow_actor(role)), origin="user_decision", actor=follow_actor(role))
                return self._send_json({"outcome": saved}, 201)
            if path == "/api/follow-through/evidence-updates":
                payload = self._read_json(); role = payload.get("role") or "operations"
                ensure_create(role, "evidence_update"); client_id = _follow_links(payload)
                for insight_id in payload.get("affected_insight_ids") or []:
                    _decision_subject(client_id, insight_id)
                store = get_followthrough_store()
                update = store.create("evidence_updates", evidence_record(payload, follow_actor(role)), origin="source_data", actor=follow_actor(role))
                reeval = store.create("reevaluations", {
                    "kind": "reevaluation", "client_id": client_id, "evidence_update_id": update["id"],
                    "affected_insight_ids": update["affected_insight_ids"], "owner_role": "operations", "status": "queued",
                }, origin="source_data", actor=follow_actor(role))
                return self._send_json({"evidence_update": update, "reevaluation": reeval}, 201)
            if path.startswith("/api/follow-through/") and path.endswith("/update"):
                remainder = path[len("/api/follow-through/") : -len("/update")].strip("/")
                collection, _, record_id = remainder.partition("/")
                if collection not in {"tasks", "referrals", "reevaluations"} or not record_id:
                    return self._send_json({"error": "Unknown follow-through record."}, 404)
                payload = self._read_json(); role = payload.get("role") or "rm"
                store = get_followthrough_store(); record = store.data[collection].get(record_id)
                if record is None:
                    return self._send_json({"error": "Unknown follow-through record."}, 404)
                ensure_update(role, record)
                changes, reason = reevaluation_update(payload) if collection == "reevaluations" else status_update(record, payload)
                saved = store.update(collection, record_id, changes, actor=follow_actor(role), action="status_updated", reason=reason)
                return self._send_json({collection[:-1]: saved})
            if path.startswith("/api/clients/") and path.endswith("/scenarios/evaluate"):
                client_id = path[len("/api/clients/") : -len("/scenarios/evaluate")]
                payload = self._read_json()
                result = evaluate_scenario(
                    client_id=client_id,
                    template_id=payload.get("template_id", ""),
                    insight_id=payload.get("insight_id", ""),
                    option_id=payload.get("option_id", ""),
                    inputs=payload.get("inputs"),
                )
                return self._send_json({"scenario": result.to_dict()})
            if path.startswith("/api/clients/") and path.endswith("/scenarios"):
                client_id = path[len("/api/clients/") : -len("/scenarios")]
                payload = self._read_json()
                result = evaluate_scenario(
                    client_id=client_id,
                    template_id=payload.get("template_id", ""),
                    insight_id=payload.get("insight_id", ""),
                    option_id=payload.get("option_id", ""),
                    inputs=payload.get("inputs"),
                )
                scenario = get_scenario_store().save(
                    name=payload.get("name", ""),
                    result=result.to_dict(),
                    saved_by=payload.get("actor") or "RM-SG-014",
                )
                return self._send_json({"scenario": scenario}, 201)
            if path.startswith("/api/insights/") and path.endswith("/meeting-packages"):
                insight_id = path[len("/api/insights/") : -len("/meeting-packages")]
                payload = self._read_json()
                client_id = _client_id_for(insight_id, payload)
                package = create_package(client_id, insight_id, actor=payload.get("actor") or "RM-SG-014")
                get_meeting_store().create(package)
                return self._send_json({"package": package}, 201)
            if path.startswith("/api/meeting-packages/"):
                remainder = path[len("/api/meeting-packages/") :].strip("/")
                package_id, _, action = remainder.partition("/")
                package = get_meeting_store().get(package_id)
                if package is None:
                    return self._send_json({"error": f"Unknown meeting package {package_id}"}, 404)
                payload = self._read_json()
                actor = payload.get("actor") or "RM-SG-014"
                if action.startswith("ai-drafts/"):
                    draft_id = action[len("ai-drafts/") :].removesuffix("/apply")
                    if not action.endswith("/apply"):
                        return self._send_json({"error": "Unknown AI draft action."}, 404)
                    version = get_ai_drafting_service().apply(package, draft_id=draft_id, rationale=payload.get("rationale", ""), role=payload.get("role", "rm"))
                    return self._send_json({"package": get_meeting_store().append_version(package_id, version)})
                if action == "ai-drafts":
                    candidate = get_ai_drafting_service().generate(package, key=payload.get("target_key", ""), style=payload.get("style", ""), role=payload.get("role", "rm"))
                    return self._send_json({"draft": candidate})
                if action == "versions":
                    version = update_section(
                        package, payload.get("key", ""), payload.get("content", ""),
                        payload.get("evidence_refs", []), actor=actor,
                        reason=payload.get("reason") or "RM edit",
                    )
                    return self._send_json({"package": get_meeting_store().append_version(package_id, version)})
                if action == "regenerate":
                    version = regenerate_section(package, key=payload.get("key", ""), actor=actor)
                    return self._send_json({"package": get_meeting_store().append_version(package_id, version)})
                if action == "restore":
                    version = restore_version(package, int(str(payload.get("version", ""))), actor=actor)
                    return self._send_json({"package": get_meeting_store().append_version(package_id, version)})
                if action == "preflight":
                    result = preflight(package)
                    get_meeting_store().mark_preflight(package_id, result)
                    return self._send_json({"preflight": result})
                if action == "handoff":
                    channel = payload.get("channel")
                    result = preflight(package)
                    get_meeting_store().mark_preflight(package_id, result)
                    if not result["can_hand_off"]:
                        return self._send_json({"error": "Communication hand-off is blocked by preflight.", "preflight": result}, 409)
                    if channel not in {"email", "formal_briefing", "call_notes", "client_app"}:
                        return self._send_json({"error": "Unknown communication channel."}, 400)
                    event = MeetingHandoffEvent(new_id(), package_id, channel, actor, meeting_now(), package["current_version"]).to_dict()
                    return self._send_json({"package": get_meeting_store().append_handoff(package_id, event), "handoff": event})
                return self._send_json({"error": "Unknown meeting package action."}, 404)
            if path.startswith("/api/insights/") and path.endswith("/readiness"):
                insight_id = path[len("/api/insights/") : -len("/readiness")]
                payload = self._read_json()
                _, readiness = _readiness(insight_id, payload)
                return self._send_json(readiness.to_dict())
            if path == "/api/explain-holding":
                payload = self._read_json()
                client_id = payload.get("client_id")
                instrument_id = payload.get("instrument_id")
                start = payload.get("from") or config.BASELINE_SNAPSHOT
                end = payload.get("to") or config.AS_OF
                portfolio_id = payload.get("portfolio")
                if portfolio_id in ("", "all", "undefined", "null"):
                    portfolio_id = None
                if not client_id or not instrument_id:
                    return self._send_json(
                        {"error": "client_id and instrument_id are required"}, 400
                    )
                explanation = explain_holding(
                    get_book(), client_id, instrument_id, start, end, portfolio_id
                )
                return self._send_json({"explanation": explanation.to_dict()})
            if path == "/api/client-attribution":
                payload = self._read_json()
                client_id = payload.get("client_id")
                instrument_id = payload.get("instrument_id")
                start = payload.get("from") or config.BASELINE_SNAPSHOT
                end = payload.get("to") or config.AS_OF
                portfolio_id = payload.get("portfolio")
                highlighted_claim = payload.get("highlighted_claim")
                if portfolio_id in ("", "all", "undefined", "null"):
                    portfolio_id = None
                if not client_id or not instrument_id:
                    return self._send_json(
                        {"error": "client_id and instrument_id are required"}, 400
                    )
                explanation = explain_holding(
                    get_book(), client_id, instrument_id, start, end, portfolio_id
                )
                client = get_book().clients.get(client_id, {})
                draft = generate_client_attribution(
                    explanation, client, highlighted_claim
                )
                return self._send_json({"draft": draft.to_dict()})
            if path.startswith("/api/clients/") and path.endswith("/notes"):
                client_id = path[len("/api/clients/") : -len("/notes")].strip("/")
                payload = self._read_json()
                note = payload.get("note", "").strip()
                channel = payload.get("channel", "Meeting")
                if not note:
                    return self._send_json({"error": "note cannot be empty"}, 400)
                entry = get_store().add_note(
                    client_id=client_id, note=note, channel=channel
                )
                return self._send_json({"note": entry})
            if path.startswith("/api/clients/") and path.endswith("/propose-objective"):
                client_id = path[
                    len("/api/clients/") : -len("/propose-objective")
                ].strip("/")
                payload = self._read_json()
                proposed = payload.get("proposed_objective", "").strip()
                rationale = payload.get("rationale", "")
                if not proposed:
                    return self._send_json(
                        {"error": "proposed_objective cannot be empty"}, 400
                    )
                entry = get_store().propose_objective(
                    client_id=client_id,
                    proposed_objective=proposed,
                    rationale=rationale,
                )
                return self._send_json({"objective": entry})
            if path == "/api/meeting-brief/add-draft":
                payload = self._read_json()
                client_id = payload.get("client_id")
                draft = payload.get("draft", {})
                if not client_id or not draft:
                    return self._send_json(
                        {"error": "client_id and draft are required"}, 400
                    )
                entry = get_meeting_draft_store().save(
                    client_id=client_id, draft=draft
                )
                return self._send_json({"status": "added", "draft": entry, "entry": entry, "brief": {"status": "saved"}}, 201)
            if path.startswith("/api/clients/") and "/meeting-drafts/" in path and path.endswith("/update"):
                parts = path[len("/api/clients/") : -len("/update")].split("/meeting-drafts/")
                client_id, draft_id = parts[0], parts[1]
                payload = self._read_json()
                draft = payload.get("draft") or payload
                entry = get_meeting_draft_store().update(client_id, draft_id, draft)
                if not entry:
                    return self._send_json({"error": "Draft not found"}, 404)
                return self._send_json({"draft": entry})
            if path.startswith("/api/clients/") and "/meeting-drafts/" in path and path.endswith("/delete"):
                parts = path[len("/api/clients/") : -len("/delete")].split("/meeting-drafts/")
                client_id, draft_id = parts[0], parts[1]
                deleted = get_meeting_draft_store().delete(client_id, draft_id)
                return self._send_json({"ok": deleted})
            if path.startswith("/api/insights/") and path.endswith("/narrative"):
                payload = self._read_json()
                if payload.get("role", "rm") != "rm":
                    raise PermissionError("Only the RM role can generate an AI insight preview.")
                insight_id = path[len("/api/insights/") : -len("/narrative")]
                client_id = "-".join(insight_id.split("-")[:2])
                if client_id not in get_book().clients:
                    return self._send_json({"error": f"Unknown client {client_id}"}, 400)
                insight = next(
                    (item for item in run_for_client(client_id, get_book()) if item.id == insight_id),
                    None,
                )
                if insight is None:
                    return self._send_json({"error": "Unknown insight"}, 404)
                try:
                    draft = draft_insight_narrative(insight)
                except (RuntimeError, PermissionError) as exc:
                    return self._send_json({"error": str(exc)}, 503)
                return self._send_json({"insight_id": insight_id, **draft})
            if path.startswith("/api/insights/") and path.endswith("/decision"):
                insight_id = path[len("/api/insights/") : -len("/decision")]
                payload = self._read_json()
                status = payload.get("status")
                if status not in VALID_STATUSES:
                    return self._send_json(
                        {"error": f"status must be one of {list(VALID_STATUSES)}"}, 400
                    )
                client_id = _client_id_for(insight_id, payload)
                if payload.get("role", "rm") != "rm":
                    raise PermissionError("Only the RM role can change RM decisions.")
                actor = payload.get("actor") or "RM-SG-014"
                saved_scenario = _saved_scenario(payload, client_id, insight_id)
                readiness = None
                if status == "client_ready":
                    client_id, readiness = _readiness(insight_id, payload)
                    if not readiness.can_mark_client_ready:
                        get_store().record_blocked_transition(
                            insight_id=insight_id,
                            client_id=client_id,
                            target_status=status,
                            actor=actor,
                            gate_results=[gate.to_dict() for gate in readiness.gates],
                            evidence_version=(
                                f"{readiness.evidence_version}:{saved_scenario['result']['calculation_version']}"
                                if saved_scenario
                                else readiness.evidence_version
                            ),
                            selected_scenario_id=saved_scenario["id"] if saved_scenario else None,
                            scenario_calculation_version=(
                                saved_scenario["result"]["calculation_version"] if saved_scenario else None
                            ),
                        )
                        return self._send_json(
                            {
                                "error": "Client-ready transition is blocked by required controls.",
                                **readiness.to_dict(),
                            },
                            409,
                        )
                feedback = validate_feedback(payload, status)
                feedback_readiness = readiness
                if feedback and feedback_readiness is None:
                    _, feedback_readiness = _readiness(insight_id, payload)
                # Resolve every decision against the current deterministic
                # source payload, even where readiness is not required.
                decision_insight, _ = _decision_subject(client_id, insight_id)
                decision = get_store().record(
                    insight_id=insight_id,
                    client_id=client_id,
                    status=status,
                    actor=actor,
                    rm_note=payload.get("rm_note") if "rm_note" in payload else None,
                    selected_option_id=payload.get("selected_option_id"),
                    edited_headline=payload.get("edited_headline"),
                    edited_next_step=payload.get("edited_next_step"),
                    gate_results=[gate.to_dict() for gate in readiness.gates]
                    if readiness
                    else None,
                    evidence_version=(
                        f"{readiness.evidence_version}:{saved_scenario['result']['calculation_version']}"
                        if readiness and saved_scenario
                        else readiness.evidence_version if readiness else None
                    ),
                    selected_scenario_id=saved_scenario["id"] if saved_scenario else None,
                    scenario_calculation_version=(
                        saved_scenario["result"]["calculation_version"] if saved_scenario else None
                    ),
                    feedback=feedback or None,
                    insight=decision_insight,
                )
                saved_feedback = None
                if feedback:
                    saved_feedback = get_calibration_store().feedback(
                        client_id=client_id,
                        insight_id=insight_id,
                        decision_status=status,
                        usefulness=feedback["usefulness"],
                        urgency_assessment=feedback["urgency_assessment"],
                        rationale=feedback["rationale"],
                        actor=actor,
                        evidence_version=feedback_readiness.evidence_version if feedback_readiness else None,
                        policy_id=get_calibration_store().active()["id"],
                    )
                return self._send_json({"decision": decision.to_dict(), "feedback": saved_feedback})
            if path.startswith("/api/insights/") and path.endswith("/reset"):
                insight_id = path[len("/api/insights/") : -len("/reset")]
                payload = self._read_json() if self.headers.get("content-length") else {}
                actor = payload.get("actor") or "RM-SG-014"
                get_store().reset_decision(insight_id, actor=actor)
                return self._send_json({"status": "reset", "insight_id": insight_id})
            return self._send_json({"error": "Not found"}, 404)
        except PermissionError as exc:
            return self._send_json({"error": str(exc)}, 409)
        except KeyError as exc:
            return self._send_json({"error": str(exc)}, 404)
        except InvalidTransitionError as exc:
            return self._send_json({"error": str(exc)}, 409)
        except ValueError as exc:
            return self._send_json({"error": str(exc)}, 400)
        except Exception as exc:
            traceback.print_exc()
            return self._send_json({"error": str(exc)}, 500)

    def do_PUT(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        try:
            if path.startswith("/api/clients/") and "/meeting-drafts/" in path:
                parts = path[len("/api/clients/") :].split("/meeting-drafts/")
                client_id, draft_id = parts[0], parts[1]
                payload = self._read_json()
                draft = payload.get("draft") or payload
                entry = get_meeting_draft_store().update(client_id, draft_id, draft)
                if not entry:
                    return self._send_json({"error": "Draft not found"}, 404)
                return self._send_json({"draft": entry})
            return self._send_json({"error": "Not found"}, 404)
        except Exception as exc:
            traceback.print_exc()
            return self._send_json({"error": str(exc)}, 500)

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        try:
            if path.startswith("/api/clients/") and "/meeting-drafts/" in path:
                parts = path[len("/api/clients/") :].split("/meeting-drafts/")
                client_id, draft_id = parts[0], parts[1]
                deleted = get_meeting_draft_store().delete(client_id, draft_id)
                return self._send_json({"ok": deleted})
            return self._send_json({"error": "Not found"}, 404)
        except Exception as exc:
            traceback.print_exc()
            return self._send_json({"error": str(exc)}, 500)

    # -- static -------------------------------------------------------------

    def _serve_static(self, path: str) -> None:
        if not FRONTEND_DIST.exists():
            return self._send_json(
                {
                    "message": "Clarity API is running.",
                    "hint": (
                        "Build the frontend with 'npm install && npm run build' in "
                        "clarity/frontend, or run 'npm run dev' for hot reload."
                    ),
                    "routes": [
                        "/api/health",
                        "/api/meta",
                        "/api/book",
                        "/api/clients/CL-0014",
                        "/api/events",
                        "/api/audit",
                    ],
                }
            )
        relative = path.lstrip("/") or "index.html"
        candidate = (FRONTEND_DIST / relative).resolve()
        if not str(candidate).startswith(str(FRONTEND_DIST.resolve())):
            return self._send_json({"error": "Forbidden"}, 403)
        if not candidate.is_file():
            candidate = FRONTEND_DIST / "index.html"  # SPA fallback
        if not candidate.is_file():
            return self._send_json({"error": "Not found"}, 404)
        return self._send_file(candidate)


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    get_book()  # warm the cache before the first request
    server = ThreadingHTTPServer((host, port), ClarityHandler)
    print(f"Clarity API on http://{host}:{port}  (dataset as of {config.AS_OF})")
    print(f"  data:     {config.DATA_DIR}")
    print(f"  frontend: {FRONTEND_DIST if FRONTEND_DIST.exists() else 'not built'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the Clarity API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    serve(args.host, args.port)
