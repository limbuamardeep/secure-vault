from flask import Flask, jsonify
from config import Config

def create_app():
    app=Flask(__name__)
    app.config.from_object(Config)
    @app.get("/")
    def health():
        return jsonify({"status":"ok"})
    return app