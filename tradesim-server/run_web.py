#!/usr/bin/env python3
"""Web service entrypoint. Render starts this for the dashboard:
    uvicorn run_web:app --host 0.0.0.0 --port $PORT
"""
from app.web import app  # noqa: F401

if __name__ == "__main__":
    import os
    import uvicorn

    uvicorn.run("app.web:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
