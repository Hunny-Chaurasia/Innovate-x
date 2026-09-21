import reflex as rx

import os

from app.api_runtime import API

from app.api_auth import router as identity_router
from app.api_projects import router as projects_router
from app.api_workflows import router as workflows_router
from app.api_uploads import router as uploads_router

api = API(
    title="InnovateX API",
    version="1.0.0",
    allow_origins=[
        origin.strip()
        for origin in os.environ.get(
            "INNOVATEX_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip() and origin.strip() != "*"
    ],
)
api.include_router(identity_router)
api.include_router(projects_router)
api.include_router(workflows_router)
api.include_router(uploads_router)
