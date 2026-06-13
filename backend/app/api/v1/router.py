from fastapi import APIRouter

from app.api.v1.endpoints import alerts, analysis, audit_logs, auth, cases, collectors, content, dashboard, export, health, graph, search, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(content.router, prefix="/content", tags=["content"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(collectors.router, prefix="/collectors", tags=["collectors"])
api_router.include_router(graph.router, prefix="/graph", tags=["graph"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(audit_logs.router, prefix="/audit_log", tags=["audit_logs"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
