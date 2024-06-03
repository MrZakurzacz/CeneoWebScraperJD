from flask import Flask

def create_app():
    app = Flask(__name__)
    return app

# Create the Flask application instance
app = create_app()

# Import routes after creating the app to avoid circular import issues
from app import routes