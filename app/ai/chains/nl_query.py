import os
import json
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException
from sqlalchemy.orm import Session

from app.ai.prompts.nl_query_prompt import NL_QUERY_SYSTEM
from app.models.asset import Asset


class NLQueryChain:
    def __init__(self, db: Session):
        self.db = db
        self.llm = ChatGroq(
            model="openai/gpt-oss-120b",
            groq_api_key=os.getenv("GROQ_API_KEY"),
            temperature=0,
        )

    def run(self, question: str) -> dict:
        if not question or not question.strip():
            return {"error": "Empty question provided"}

        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", NL_QUERY_SYSTEM),
                ("human", "{question}"),
            ])
            chain = prompt | self.llm | JsonOutputParser()
            filters = chain.invoke({"question": question})
        except (OutputParserException, Exception) as e:
            return {"error": f"Failed to parse query: {str(e)}"}

        # Apply filters to real DB only — no hallucination possible
        query = self.db.query(Asset)

        if filters.get("type"):
            query = query.filter(Asset.type == filters["type"])
        if filters.get("status"):
            query = query.filter(Asset.status == filters["status"])
        if filters.get("value_contains"):
            query = query.filter(Asset.value.ilike(f"%{filters['value_contains']}%"))
        if filters.get("tags"):
            for tag in filters["tags"]:
                query = query.filter(Asset.tags.any(tag))

        assets = query.limit(50).all()

        return {
            "question": question,
            "filters_used": filters,
            "count": len(assets),
            "results": [
                {
                    "id": a.id,
                    "type": a.type,
                    "value": a.value,
                    "status": a.status,
                    "tags": a.tags or [],
                    "metadata": a.metadata_ or {},
                }
                for a in assets
            ],
        }
