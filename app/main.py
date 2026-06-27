from fastapi import FastAPI
from app.db.database import Base, engine
from app.api.routes import import_route, assets_route, analyze_route

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="DarkAtlas Asset Management API",
    description="AI-powered Attack Surface Monitoring",
    version="1.0.0",
)

app.include_router(import_route.router, prefix="/api/v1", tags=["Import"])
app.include_router(assets_route.router, prefix="/api/v1", tags=["Assets"])
app.include_router(analyze_route.router, prefix="/api/v1", tags=["Analyze"])


@app.get("/")
def root():
    return {
        "message": "DarkAtlas API is running",
        "docs": "/docs",
        "health": "ok",
    }
