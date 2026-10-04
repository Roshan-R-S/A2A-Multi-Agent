import uvicorn

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from agents.research.card import research_agent_card
from agents.research.executor import ResearchAgentExecutor
from core.config import settings


async def health(request):
    return JSONResponse(
        {
            "status": "ok",
            "agent": "Research Agent",
            "version": "0.1.0",
        }
    )


request_handler = DefaultRequestHandler(
    agent_executor=ResearchAgentExecutor(),
    task_store=InMemoryTaskStore(),
    agent_card=research_agent_card,
)


routes = [
    Route(
        "/health",
        endpoint=health,
        methods=["GET"],
    )
]

routes.extend(
    create_agent_card_routes(
        research_agent_card
    )
)

routes.extend(
    create_jsonrpc_routes(
        request_handler,
        "/",
    )
)


app = Starlette(
    routes=routes,
)


if __name__ == "__main__":
    print(
        "Starting Research Agent at "
        f"{settings.research_agent_url}"
    )

    print(
        "Health: "
        f"{settings.research_agent_url}/health"
    )

    print(
        "Agent Card: "
        f"{settings.research_agent_url}"
        "/.well-known/agent-card.json"
    )

    uvicorn.run(
        app,
        host=settings.research_agent_host,
        port=settings.research_agent_port,
    )
