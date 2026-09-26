"""Local Flask entry point. Production uses backend.wsgi:app."""
from backend.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
