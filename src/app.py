import hmac
import logging
import re
from functools import wraps

from flask import Flask, jsonify, render_template, request

from src.config.config import Config
from src.errors import GraphError, SignatureManagerError
from src.signature_manager import OutlookSignatureManager
from src.signatures import SIGNATURE_TEMPLATES, personalize, sanitize_html

logger = logging.getLogger(__name__)

# Covers normal and guest (#EXT#) user principal names.
UPN_RE = re.compile(r"^[A-Za-z0-9._%+'#-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
MAX_SIGNATURE_BYTES = 64 * 1024


def _error(message: str, status: int):
    return jsonify({"error": message}), status


def _json_body() -> dict | None:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _valid_upn(value) -> bool:
    return isinstance(value, str) and len(value) <= 256 and bool(UPN_RE.match(value))


def _template_from(data: dict) -> tuple[str | None, str | None]:
    """Return (template, error) from either a template name or raw HTML."""
    if "template" in data:
        template = SIGNATURE_TEMPLATES.get(data["template"])
        return (template, None) if template else (None, "Unknown template")
    template = data.get("templateHtml")
    if not isinstance(template, str) or not template.strip():
        return None, "Provide 'template' (a name) or 'templateHtml'"
    if len(template.encode()) > MAX_SIGNATURE_BYTES:
        return None, "Template is too large"
    return template, None


def require_api_key(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        supplied = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(supplied.encode(), Config.API_KEY.encode()):
            return _error("Unauthorized", 401)
        return view(*args, **kwargs)
    return wrapper


def create_app(manager: OutlookSignatureManager | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.secret_key = Config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = 2 * MAX_SIGNATURE_BYTES
    manager = manager or OutlookSignatureManager()

    @app.errorhandler(SignatureManagerError)
    def handle_upstream_error(e):
        logger.exception("Upstream call failed")
        if isinstance(e, GraphError) and e.status_code == 404:
            return _error("User not found", 404)
        return _error("Request to Microsoft 365 failed; see server logs", 502)

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' https: data:; style-src 'self' 'unsafe-inline'; "
            "frame-src 'self'",
        )
        return response

    @app.route("/")
    def dashboard():
        return render_template("dashboard.html", templates=sorted(SIGNATURE_TEMPLATES))

    @app.route("/api/health")
    def health_check():
        return jsonify({"status": "ok"})

    @app.route("/api/health/graph")
    @require_api_key
    def graph_health():
        manager.graph.get_access_token()
        return jsonify({"status": "ok", "message": "Token acquired"})

    @app.route("/api/templates")
    @require_api_key
    def get_templates():
        return jsonify({"templates": SIGNATURE_TEMPLATES})

    @app.route("/api/users")
    @require_api_key
    def get_users():
        fields = ("displayName", "userPrincipalName", "mail", "jobTitle", "department")
        users = [
            {field: user.get(field) or "" for field in fields}
            for user in manager.get_all_users()
        ]
        return jsonify({"users": users})

    @app.route("/api/signature/<path:user_principal_name>")
    @require_api_key
    def get_user_signature(user_principal_name):
        if not _valid_upn(user_principal_name):
            return _error("Invalid userPrincipalName", 400)
        return jsonify({"signature": manager.get_user_signature(user_principal_name)})

    @app.route("/api/signature", methods=["POST"])
    @require_api_key
    def set_user_signature():
        data = _json_body()
        if data is None:
            return _error("Expected a JSON object", 400)
        upn = data.get("userPrincipalName")
        if not _valid_upn(upn):
            return _error("A valid userPrincipalName is required", 400)

        if "signature" in data:
            signature = data["signature"]
            if not isinstance(signature, str) or not signature.strip():
                return _error("signature must be a non-empty string", 400)
            if len(signature.encode()) > MAX_SIGNATURE_BYTES:
                return _error("Signature is too large", 400)
            manager.set_user_signature(upn, signature)
            applied = sanitize_html(signature)
        else:
            template, err = _template_from(data)
            if err:
                return _error(err, 400)
            applied = manager.apply_template_to_user(upn, template)

        return jsonify({"success": True, "message": "Signature updated", "signature": applied})

    @app.route("/api/signature/preview", methods=["POST"])
    @require_api_key
    def preview_signature():
        data = _json_body()
        if data is None:
            return _error("Expected a JSON object", 400)
        upn = data.get("userPrincipalName")
        if not _valid_upn(upn):
            return _error("A valid userPrincipalName is required", 400)
        template, err = _template_from(data)
        if err:
            return _error(err, 400)
        return jsonify({"signature": personalize(template, manager.graph.get_user(upn))})

    @app.route("/api/signature/bulk", methods=["POST"])
    @require_api_key
    def bulk_signature():
        data = _json_body()
        if data is None:
            return _error("Expected a JSON object", 400)
        template, err = _template_from(data)
        if err:
            return _error(err, 400)
        results = manager.apply_standard_signature_to_all(template)
        return jsonify({
            "succeeded": len(results["success"]),
            "failed": results["failed"],
        })

    return app
