import hmac
import json
import logging
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from flask import Flask, g, jsonify, request
from flask_cors import CORS
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException

from backend.ai import GeminiService
from backend.crm import log_consultation
from backend.data import GeoResolver, load_communities
from backend.models import ClientProfile, CRMRequest, RecommendationRequest, completeness
from backend.ranking import filter_communities, load_config, rank
from src.budget import regex_budget_fallback
from src.data_loader import DEMO_PREFERENCES, DEMO_TRANSCRIPT

LOGGER = logging.getLogger("placement")
MIME = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "m4a": "audio/mp4",
    "webm": "audio/webm",
    "ogg": "audio/ogg",
    "flac": "audio/flac",
}


def valid_audio(data, ext):
    return {
        "mp3": data.startswith(b"ID3") or (len(data) > 1 and data[0] == 255 and data[1] & 224 == 224),
        "wav": data[:4] == b"RIFF" and data[8:12] == b"WAVE",
        "m4a": data[4:8] == b"ftyp",
        "webm": data[:4] == b"\x1aE\xdf\xa3",
        "ogg": data[:4] == b"OggS",
        "flac": data[:4] == b"fLaC",
    }.get(ext, False)


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.update(
        DEMO_MODE=os.getenv("DEMO_MODE", "true").lower() == "true",
        GEMINI_MODEL=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        GEMINI_LIVE_MODEL=os.getenv("GEMINI_LIVE_MODEL", "gemini-3.8-live"),
        GEMINI_API_KEY=os.getenv("GEMINI_API_KEY", ""),
        ADVISOR_ACCESS_TOKEN=os.getenv("ADVISOR_ACCESS_TOKEN", ""),
        SIGNING_SECRET=os.getenv("SIGNING_SECRET", ""),
        CORS_ORIGINS=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
        COMMUNITIES_FILE=os.getenv("COMMUNITIES_FILE", ""),
        GEO_LOOKUP_FILE=os.getenv("GEO_LOOKUP_FILE") or None,
        GOOGLE_SERVICE_ACCOUNT_JSON=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", ""),
        COMMUNITIES_SHEET_ID=os.getenv("COMMUNITIES_SHEET_ID", ""),
        COMMUNITIES_WORKSHEET=os.getenv("COMMUNITIES_WORKSHEET", "Communities"),
        CRM_SHEET_ID=os.getenv("CRM_SHEET_ID", ""),
        CRM_WORKSHEET=os.getenv("CRM_WORKSHEET", "Consultations"),
        MAX_CONTENT_LENGTH=12 * 1024 * 1024,
        RATE_LIMIT=30,
    )
    app.config.update(overrides or {})
    if not app.config["DEMO_MODE"]:
        if any(len(app.config[key]) < 32 for key in ("ADVISOR_ACCESS_TOKEN", "SIGNING_SECRET")):
            raise ValueError(
                "Production requires distinct access and signing secrets of at least 32 characters"
            )
        if app.config["ADVISOR_ACCESS_TOKEN"] == app.config["SIGNING_SECRET"]:
            raise ValueError("Use distinct access and signing secrets")
        if "*" in app.config["CORS_ORIGINS"]:
            raise ValueError("Production CORS must use explicit origins")
    CORS(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        allow_headers=["Authorization", "Content-Type"],
        methods=["GET", "POST", "OPTIONS"],
    )
    geo = GeoResolver(app.config["GEO_LOOKUP_FILE"])
    config = load_config(os.getenv("RANKING_CONFIG") or None)
    ai = app.config.get("AI_SERVICE") or GeminiService(app.config)
    serializer = URLSafeTimedSerializer(
        app.config["SIGNING_SECRET"] or "offline-demo-only", salt="consultation-v2"
    )
    limits, lock = defaultdict(deque), Lock()

    @app.before_request
    def before():
        g.start, g.request_id = time.perf_counter(), str(uuid4())
        if request.path in {"/api/health", "/api/config"} or request.method == "OPTIONS":
            return None
        if not app.config["DEMO_MODE"]:
            provided = request.headers.get("Authorization", "")
            if not hmac.compare_digest(provided, "Bearer " + app.config["ADVISOR_ACCESS_TOKEN"]):
                return jsonify(
                    error={"code": "unauthorized", "message": "Enter your advisor access token."}
                ), 401
        if request.method == "POST":
            # A per-process safety bound. No proxy header is trusted as an identity.
            now, key = time.monotonic(), request.remote_addr or "unknown"
            with lock:
                for stale in [k for k, v in limits.items() if not v or v[-1] < now - 60]:
                    del limits[stale]
                hits = limits[key]
                while hits and hits[0] < now - 60:
                    hits.popleft()
                if len(hits) >= app.config["RATE_LIMIT"]:
                    return jsonify(
                        error={"code": "rate_limit", "message": "Please wait a minute before trying again."}
                    ), 429
                hits.append(now)

    @app.after_request
    def after(response):
        if response.status_code >= 400 and response.is_json:
            body = response.get_json()
            if isinstance(body, dict) and isinstance(body.get("error"), dict):
                body["error"].setdefault("code", f"HTTP_{response.status_code}")
                response.set_data(app.json.dumps(body))
        response.headers["X-Request-ID"] = g.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        LOGGER.info(
            json.dumps(
                {
                    "event": "request",
                    "request_id": g.request_id,
                    "endpoint": request.endpoint,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - g.start) * 1000, 2),
                }
            )
        )
        return response

    @app.errorhandler(Exception)
    def error(exc):
        if isinstance(exc, ValidationError):
            return jsonify(
                error={
                    "code": "validation",
                    "message": "Please review the highlighted profile fields.",
                    "fields": [".".join(map(str, e["loc"])) for e in exc.errors()],
                }
            ), 422
        if isinstance(exc, HTTPException):
            return jsonify(error={"code": exc.name, "message": exc.description}), exc.code
        LOGGER.warning(
            json.dumps({"event": "request_failed", "request_id": g.request_id, "type": type(exc).__name__})
        )
        return jsonify(
            error={
                "code": "service_unavailable",
                "message": "Service unavailable. Please retry or contact your administrator.",
            }
        ), 503

    def intake(profile, calls=0, warnings=None, metrics=None):
        metrics = metrics or {}
        validation_start = time.perf_counter()
        validation = completeness(profile)
        metrics["completeness_ms"] = round((time.perf_counter() - validation_start) * 1000, 3)
        LOGGER.info(
            json.dumps(
                {
                    "event": "intake",
                    "request_id": g.request_id,
                    "mode": request.endpoint,
                    "complete": validation["is_complete"],
                    "ai_calls": calls,
                }
            )
        )
        return jsonify(
            profile=profile.model_dump(),
            intake=validation,
            warnings=warnings or [],
            metrics={
                **metrics,
                "ai_calls": calls,
                "intake_ms": round((time.perf_counter() - g.start) * 1000, 2),
            },
        )

    @app.get("/api/health")
    def health():
        return jsonify(status="ok", version="2.0")

    @app.get("/api/config")
    def public_config():
        return jsonify(
            demo_mode=app.config["DEMO_MODE"],
            auth_required=not app.config["DEMO_MODE"],
            max_audio_bytes=10 * 1024 * 1024,
            audio_formats=list(MIME),
        )

    @app.get("/api/demo")
    def demo():
        if not app.config["DEMO_MODE"]:
            return jsonify(error={"message": "Demo is disabled."}), 404
        p = DEMO_PREFERENCES
        profile = ClientProfile(
            patient_name=p["name_of_patient"],
            age=p["age_of_patient"],
            care_level=p["care_level"],
            max_budget=p["max_budget"],
            preferred_locations=p["preferred_location"],
            enhanced_required=True,
            move_in_window="Immediate",
            primary_contact_name="Sarah Johnson",
            primary_contact_phone="585-555-0142",
        )
        return jsonify(profile=profile.model_dump(), transcript=DEMO_TRANSCRIPT, intake=completeness(profile))

    @app.post("/api/intake/manual")
    def manual():
        return intake(ClientProfile.model_validate(request.get_json()))

    @app.post("/api/intake/text")
    def text_intake():
        payload = request.get_json()
        text = payload.get("text") if isinstance(payload, dict) else None
        if not isinstance(text, str) or not text.strip() or len(text) > 50000:
            return jsonify(error={"message": "Enter 1–50,000 characters of consultation notes."}), 422
        if app.config["DEMO_MODE"]:
            return intake(
                ClientProfile(max_budget=regex_budget_fallback(text)),
                warnings=[
                    "Offline mode extracts budget only. Load the sample consultation or complete fields manually."
                ],
            )
        metrics = {}
        profile, calls, warnings = ai.extract(text=text, metrics=metrics)
        return intake(profile, calls, warnings, metrics)

    @app.post("/api/intake/audio")
    def audio_intake():
        upload = request.files.get("audio")
        if not upload or not upload.filename:
            return jsonify(error={"message": "Choose an audio file."}), 422
        ext = Path(upload.filename).suffix.lower().lstrip(".")
        data = upload.read(10 * 1024 * 1024 + 1)
        if ext not in MIME or not data or len(data) > 10 * 1024 * 1024 or not valid_audio(data, ext):
            return jsonify(error={"message": "Invalid audio. Use a supported audio file up to 10 MB."}), 422
        if app.config["DEMO_MODE"]:
            return jsonify(
                error={"message": "Audio understanding requires Gemini. Use the offline sample consultation."}
            ), 409
        metrics = {}
        started = time.perf_counter()
        profile, calls, warnings = ai.extract(audio=data, mime=MIME[ext], metrics=metrics)
        metrics["audio_processing_ms"] = round((time.perf_counter() - started) * 1000, 2)
        return intake(profile, calls, warnings, metrics)

    @app.post("/api/live/token")
    def live_token():
        if app.config["DEMO_MODE"]:
            return jsonify(
                error={"message": "Live voice requires Gemini. Use the labeled offline simulation."}
            ), 409
        payload = request.get_json()
        mode = payload.get("mode") if isinstance(payload, dict) else None
        if mode not in {"assist", "conversation"}:
            return jsonify(error={"message": "Invalid consultation mode."}), 422
        return jsonify(ai.live_token(mode))

    @app.get("/api/communities")
    def communities():
        return jsonify(communities=[c.model_dump() for c in load_communities(app.config, geo)])

    @app.post("/api/recommend")
    def recommend():
        data = RecommendationRequest.model_validate(request.get_json())
        resolved = [(loc, geo.resolve(loc)) for loc in data.profile.preferred_locations]
        refs = [coords for _, coords in resolved if coords]
        started = time.perf_counter()
        communities = load_communities(app.config, geo) if completeness(data.profile)["is_complete"] else []
        load_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        prepared = filter_communities(data.profile, communities)
        filter_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        result = rank(data.profile, communities, refs, config, prepared=prepared)
        ranking_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        usage = {}
        explanations, calls, source = ai.explain(data.profile, result["recommendations"], metrics=usage)
        for item in result["recommendations"]:
            item.update(explanation=explanations[item["community_id"]], explanation_source=source)
        metrics = {
            **usage,
            "load_ms": round(load_ms, 2),
            "hard_filter_ms": round(filter_ms, 2),
            "ranking_ms": round(ranking_ms, 2),
            "explanation_ms": round((time.perf_counter() - started) * 1000, 2),
            "ai_calls": calls,
            "total_ms": round((time.perf_counter() - g.start) * 1000, 2),
            "total_communities": result["total_communities"],
            "eligible_count": result["eligible_count"],
        }
        record = {
            "consultation_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "profile": data.profile.model_dump(),
            "input_mode": data.input_mode,
            "processing_ms": metrics["total_ms"],
            "scores": {r["community_id"]: r["final_score"] for r in result["recommendations"]},
        }
        result.update(
            client_profile=data.profile.model_dump(),
            metrics=metrics,
            consultation_id=record["consultation_id"],
            receipt=serializer.dumps(record) if result["recommendations"] else None,
            warnings=[
                f"Location unresolved: {loc}. Distance uses only resolved locations."
                for loc, coords in resolved
                if coords is None
            ],
        )
        LOGGER.info(json.dumps({"event": "recommendation", "request_id": g.request_id, **metrics}))
        return jsonify(result)

    @app.post("/api/consultations/log")
    def crm():
        data = CRMRequest.model_validate(request.get_json())
        try:
            record = serializer.loads(data.receipt, max_age=86400)
        except BadSignature:
            return jsonify(
                error={"message": "Recommendation receipt is invalid or expired. Rank again."}
            ), 422
        if any(key not in record["scores"] for key in data.selected_community_ids):
            return jsonify(error={"message": "Choose only communities from these recommendations."}), 422
        started = time.perf_counter()
        result = log_consultation(app.config, record, data.selected_community_ids, data.advisor_notes)
        latency = round((time.perf_counter() - started) * 1000, 2)
        LOGGER.info(
            json.dumps(
                {
                    "event": "crm",
                    "request_id": g.request_id,
                    "logged": result["crm_logged"],
                    "crm_ms": latency,
                }
            )
        )
        return jsonify(consultation_id=record["consultation_id"], crm_ms=latency, **result)

    return app
