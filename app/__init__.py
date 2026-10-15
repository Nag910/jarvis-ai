import logging, secrets
from flask import Flask, jsonify, render_template, request, session
from config import Config
from . import db


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(Config)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    db.init_app(app)

    from .routes import api
    app.register_blueprint(api)

    @app.route("/")
    def index():
        session.setdefault("csrf", secrets.token_hex(16))
        return render_template("index.html", csrf=session["csrf"])

    @app.before_request
    def csrf_check():
        if request.path.startswith("/api/") and request.method in ("POST", "PUT", "PATCH", "DELETE"):
            sent = request.headers.get("X-CSRF-Token", "")
            if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
                return jsonify(error="Invalid or missing CSRF token. Reload the page."), 403

    @app.after_request
    def headers(resp):
        resp.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        return resp

    @app.errorhandler(404)
    def nf(e):
        return jsonify(error="Not found"), 404

    @app.errorhandler(405)
    def na(e):
        return jsonify(error="Method not allowed"), 405

    @app.errorhandler(413)
    def big(e):
        return jsonify(error="Request too large"), 413

    @app.errorhandler(500)
    def err(e):
        app.logger.exception("Server error")
        return jsonify(error="Internal server error"), 500

    return app
