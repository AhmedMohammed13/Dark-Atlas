from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.schemas import AnalyzeRequest
from app.ai.chains.nl_query import NLQueryChain
from app.ai.chains.risk_scoring import RiskScoringChain
from app.ai.chains.enrichment import EnrichmentChain
from app.ai.chains.report_gen import ReportGenChain
from app.ai.agent.darkatlas_agent import DarkAtlasAgent

router = APIRouter()


@router.post("/analyze")
def analyze(request: AnalyzeRequest, db: Session = Depends(get_db)):
    mode = request.mode

    if mode == "nl_query":
        if not request.input:
            raise HTTPException(status_code=400, detail="'input' is required for nl_query mode")
        return NLQueryChain(db).run(request.input)

    elif mode == "risk_score":
        return RiskScoringChain(db).run(asset_id=request.asset_id)

    elif mode == "enrich":
        if not request.asset_id:
            raise HTTPException(status_code=400, detail="'asset_id' is required for enrich mode")
        return EnrichmentChain(db).run(request.asset_id)

    elif mode == "report":
        return ReportGenChain(db).run(filters=request.filters)

    elif mode == "agent":
        if not request.input:
            raise HTTPException(status_code=400, detail="'input' is required for agent mode")
        return DarkAtlasAgent(db).run(request.input)

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown mode '{mode}'. Valid modes: nl_query | risk_score | enrich | report | agent",
        )
