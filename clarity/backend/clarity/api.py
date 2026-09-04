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
    GET  /api/events
    GET  /api/audit
    POST /api/insights/<insight_id>/readiness
    POST /api/insights/<insight_id>/decision
    POST /api/reset
Anything else is served from ../frontend/dist if it has been built, so the
whole product runs from one process.
"""

from __future__ import annotations

import json
import mimetypes
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import config
from .actions import options_for
from .contracts import Category, Severity
from .dossier import all_events, book_view, client_dossier
from .gates import evaluate_readiness
from .loaders import get_book
from .review import InvalidTransitionError, VALID_STATUSES, get_store
from .signals.base import SignalContext, run_for_client

FRONTEND_DIST = config.REPO_ROOT / "clarity" / "frontend" / "dist"


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


class ClarityHandler(BaseHTTPRequestHandler):
    server_version = "Clarity/0.1"

    # -- helpers ------------------------------------------------------------

    def _send_json(self, payload, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
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

    def log_message(self, fmt: str, *args) -> None:  # quieter console
        print(f"  {self.command} {self.path} -> {args[1] if len(args) > 1 else ''}")

    # -- routing ------------------------------------------------------------

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json({}, 204)

    def do_GET(self) -> None:  # noqa: N802
        path = unquote(urlparse(self.path).path)
        try:
            if path == "/api/health":
                return self._send_json({"status": "ok", "as_of": config.AS_OF})
            if path == "/api/meta":
                return self._send_json(_meta())
            if path == "/api/book":
                return self._send_json(book_view())
            if path == "/api/events":
                return self._send_json({"events": all_events()})
            if path == "/api/audit":
                return self._send_json(
                    {"audit": [e.to_dict() for e in get_store().audit()]}
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
            if path == "/api/reset":
                get_store().reset()
                return self._send_json({"status": "reset"})
            if path.startswith("/api/insights/") and path.endswith("/readiness"):
                insight_id = path[len("/api/insights/") : -len("/readiness")]
                payload = self._read_json()
                _, readiness = _readiness(insight_id, payload)
                return self._send_json(readiness.to_dict())
            if path.startswith("/api/insights/") and path.endswith("/decision"):
                insight_id = path[len("/api/insights/") : -len("/decision")]
                payload = self._read_json()
                status = payload.get("status")
                if status not in VALID_STATUSES:
                    return self._send_json(
                        {"error": f"status must be one of {list(VALID_STATUSES)}"}, 400
                    )
                client_id = _client_id_for(insight_id, payload)
                actor = payload.get("actor") or "RM-SG-014"
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
                            evidence_version=readiness.evidence_version,
                        )
                        return self._send_json(
                            {
                                "error": "Client-ready transition is blocked by required controls.",
                                **readiness.to_dict(),
                            },
                            409,
                        )
                # Resolve every decision against the current deterministic
                # source payload, even where readiness is not required.
                _decision_subject(client_id, insight_id)
                decision = get_store().record(
                    insight_id=insight_id,
                    client_id=client_id,
                    status=status,
                    actor=actor,
                    rm_note=payload.get("rm_note", ""),
                    selected_option_id=payload.get("selected_option_id"),
                    edited_headline=payload.get("edited_headline"),
                    edited_next_step=payload.get("edited_next_step"),
                    gate_results=[gate.to_dict() for gate in readiness.gates]
                    if readiness
                    else None,
                    evidence_version=readiness.evidence_version if readiness else None,
                )
                return self._send_json({"decision": decision.to_dict()})
            return self._send_json({"error": "Not found"}, 404)
        except InvalidTransitionError as exc:
            return self._send_json({"error": str(exc)}, 409)
        except ValueError as exc:
            return self._send_json({"error": str(exc)}, 400)
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
