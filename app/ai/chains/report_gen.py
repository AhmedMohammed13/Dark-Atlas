import os
import json
from collections import Counter
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from sqlalchemy.orm import Session

from app.ai.prompts.report_prompt import REPORT_SYSTEM
from app.models.asset import Asset


class ReportGenChain:
    def __init__(self, db: Session):
        self.db = db
        self.llm = ChatGroq(
            model="openai/gpt-oss-120b",
            groq_api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.2,
        )

    def run(self, filters: dict = None) -> dict:
        query = self.db.query(Asset)

        if filters:
            if filters.get("type"):
                query = query.filter(Asset.type == filters["type"])
            if filters.get("status"):
                query = query.filter(Asset.status == filters["status"])

        assets = query.limit(100).all()

        if not assets:
            return {"error": "No assets found for report generation"}

        assets_data = [
            {
                "type": a.type,
                "value": a.value,
                "status": a.status,
                "tags": a.tags or [],
                "metadata": a.metadata_ or {},
            }
            for a in assets
        ]

        type_counts = dict(Counter(a.type.value for a in assets))
        status_counts = dict(Counter(a.status.value for a in assets))

        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", REPORT_SYSTEM),
                ("human", """
Total assets: {total}
By type: {by_type}
By status: {by_status}

Assets data (first 30):
{assets_json}
"""),
            ])
            chain = prompt | self.llm | StrOutputParser()
            report_text = chain.invoke({
                "total": len(assets),
                "by_type": json.dumps(type_counts),
                "by_status": json.dumps(status_counts),
                "assets_json": json.dumps(assets_data[:30], indent=2),
            })

            return {
                "total_assets": len(assets),
                "by_type": type_counts,
                "by_status": status_counts,
                "report": report_text,
            }
        except Exception as e:
            return {"error": f"Report generation failed: {str(e)}"}
