from flask import Flask, jsonify
from flask_swagger_ui import get_swaggerui_blueprint

from .route import router
from .swagger import open_api_spec


def create_app() -> Flask:
    app = Flask(__name__)

    # -- Swagger UI --------------------------------------------------------
    SWAGGER_URL = "/docs"
    API_URL = "/openapi.json"

    swagger_ui = get_swaggerui_blueprint(
        SWAGGER_URL,
        API_URL,
        config={"app_name": "Idempotency Gateway API"},
    )
    app.register_blueprint(swagger_ui, url_prefix=SWAGGER_URL)

    @app.route("/openapi.json")
    def openapi_spec():
        return jsonify(open_api_spec), 200

    # -- Application routes ------------------------------------------------
    app.register_blueprint(router)

    return app


app = create_app()
