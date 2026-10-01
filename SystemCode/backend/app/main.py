from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.knowledge.mind_ontology import get_mind_knowledge_graph


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Backend API for resume parsing and explainable job recommendations.",
    )
    # 本地前端（Vite dev server）跨域调用需要放行
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.mind_knowledge_graph = get_mind_knowledge_graph()
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
