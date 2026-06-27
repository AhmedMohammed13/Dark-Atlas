import os
import json
from datetime import datetime, timezone
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from sqlalchemy.orm import Session

from app.ai.prompts.enrichment_prompt import ENRICHMENT_SYSTEM
from app.models.asset import Asset


class EnrichmentChain:
    def __init__(self, db: Session):
        self.db = db
        self.llm = ChatGroq(
            model="openai/gpt-oss-120b",
            groq_api_key=os.getenv("GROQ_API_KEY"),
            temperature=0,
        )

    def run(self, asset_id: str) -> dict:
        asset = self.db.query(Asset).filter(Asset.id == asset_id).first()
        if not asset:
            return {"error": "Asset not found"}

        asset_data = {
            "id": asset.id,
            "type": asset.type,
            "value": asset.value,
            "status": asset.status,
            "tags": asset.tags or [],
            "metadata": asset.metadata_ or {},
        }

        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", ENRICHMENT_SYSTEM),
                ("human", "Classify this asset:\n{asset_json}"),
            ])
            chain = prompt | self.llm | JsonOutputParser()
            enrichment = chain.invoke({"asset_json": json.dumps(asset_data, indent=2)})

            # Merge tags (union — never drop existing)
            existing_tags = list(asset.tags or [])
            new_tags = enrichment.get("suggested_tags", [])
            merged_tags = list(set(existing_tags + new_tags))

            # Merge metadata
            existing_meta = dict(asset.metadata_ or {})
            existing_meta.update({
                "environment": enrichment.get("environment"),
                "category": enrichment.get("category"),
                "criticality": enrichment.get("criticality"),
                "enriched_at": datetime.now(timezone.utc).isoformat(),
            })

            asset.tags = merged_tags
            asset.metadata_ = existing_meta
            asset.last_seen = datetime.now(timezone.utc)
            self.db.commit()

            return {
                "asset_id": asset_id,
                "enrichment": enrichment,
                "updated_tags": merged_tags,
                "updated_metadata": existing_meta,
            }
        except Exception as e:
            self.db.rollback()
            return {"error": f"Enrichment failed: {str(e)}"}
