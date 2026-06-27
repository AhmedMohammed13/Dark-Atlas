import os
import json
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.prebuilt import create_react_agent
from sqlalchemy.orm import Session

from app.models.asset import Asset


AGENT_SYSTEM_PROMPT = """
You are DarkAtlas Security Agent — an expert in Attack Surface Monitoring.

You have access to two tools:
1. search_assets — searches the internal asset database (always use this first)
2. tavily_search_results_json — searches the internet for CVEs and threat intelligence

Rules:
- ALWAYS query the internal database first before searching the internet
- NEVER invent asset data; only reference what search_assets returns
- Use web search to enrich findings with real-world threat intelligence
- Be concise and professional in your final answer
- If no assets match, say so clearly
"""


class DarkAtlasAgent:
    def __init__(self, db: Session):
        self.db = db

    def run(self, question: str) -> dict:
        if not question or not question.strip():
            return {"error": "Empty question provided"}

        if not os.getenv("TAVILY_API_KEY"):
            return {"error": "TAVILY_API_KEY is not set in environment variables"}

        db = self.db

        @tool
        def search_assets(query: str) -> str:
            """
            Search the internal DarkAtlas asset database.
            Use this to find domains, subdomains, certificates, IPs, services, and technologies.
            Input: a keyword like 'certificate', 'expired', 'prod', or a domain name.
            """
            assets = db.query(Asset).filter(
                Asset.value.ilike(f"%{query}%")
            ).limit(20).all()

            if not assets:
                assets = db.query(Asset).filter(
                    Asset.type.ilike(f"%{query}%")
                ).limit(20).all()

            if not assets:
                return "No assets found matching that query in the internal database."

            results = [
                {
                    "id": a.id,
                    "type": str(a.type),
                    "value": a.value,
                    "status": str(a.status),
                    "tags": a.tags or [],
                    "metadata": a.metadata_ or {},
                }
                for a in assets
            ]
            return json.dumps(results, indent=2)

        tavily_tool = TavilySearchResults(
            max_results=3,
            tavily_api_key=os.getenv("TAVILY_API_KEY"),
        )

        tools = [search_assets, tavily_tool]

        llm = ChatGroq(
            model="openai/gpt-oss-120b",
            groq_api_key=os.getenv("GROQ_API_KEY"),
            temperature=0,
        )

        try:
            agent = create_react_agent(
                model=llm,
                tools=tools,
                prompt=AGENT_SYSTEM_PROMPT,
            )

            result = agent.invoke({"messages": [("human", question)]})

            final_answer = ""
            steps = []

            for msg in result.get("messages", []):
                msg_type = type(msg).__name__
                if msg_type == "AIMessage":
                    if msg.content:
                        final_answer = msg.content
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            steps.append({
                                "tool": tc.get("name", ""),
                                "input": str(tc.get("args", "")),
                            })

            return {
                "question": question,
                "answer": final_answer,
                "steps_taken": steps,
                "total_steps": len(steps),
            }

        except Exception as e:
            return {"error": f"Agent execution failed: {str(e)}"}