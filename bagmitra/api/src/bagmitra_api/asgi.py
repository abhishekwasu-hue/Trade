"""ASGI entrypoint: `uvicorn bagmitra_api.asgi:app`."""

from bagmitra_api.main import create_app

app = create_app()
