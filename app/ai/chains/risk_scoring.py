import os
import json
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from sqlalchemy.orm import Session

from app.ai.prompts.risk_prompt import RISK_SYSTEM
from app.models.asset import Asset


class RiskScoringChain:
    def __init__(self, db: Session):
        self.db = db
        self.llm = ChatGroq(
            model="openai/gpt-oss-120b",
            groq_api_key=os.getenv("GROQ_API_KEY"),
            temperature=0,
        )

    def run(self, asset_id: str = None) -> dict:
        if asset_id:
            assets = self.db.query(Asset).filter(Asset.id == asset_id).all()
            if not assets:
                return {"error": "Asset not found"}
        else:
            assets = self.db.query(Asset).limit(100).all()

        if not assets:
            return {"error": "No assets found to analyze"}

        assets_data = [
            {
                "id": a.id,
                "type": a.type,
                "value": a.value,
                "status": a.status,
                "tags": a.tags or [],
                "metadata": a.metadata_ or {},
            }
            for a in assets
        ]

        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", RISK_SYSTEM),
                ("human", "Analyze these assets:\n{assets_json}"),
            ])
            chain = prompt | self.llm | JsonOutputParser()
            result = chain.invoke({"assets_json": json.dumps(assets_data, indent=2)})
            return result
        except Exception as e:
            return {"error": f"Risk analysis failed: {str(e)}"}
