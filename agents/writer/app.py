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

from agents.writer.card import writer_agent_card
from agents.writer.executor import WriterAgentExecutor
from core.config import settings


async def health(request):
    return JSONResponse(
        {
            "status": "ok",
            "agent": "Writer Agent",
            "version": "0.1.0",
        }
    )


request_handler = DefaultRequestHandler(
    agent_executor=WriterAgentExecutor(),
    task_store=InMemoryTaskStore(),
    agent_card=writer_agent_card,
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
        writer_agent_card
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
        "Starting Writer Agent at "
        f"{settings.writer_agent_url}"
    )

    print(
        "Health: "
        f"{settings.writer_agent_url}/health"
    )

    print(
        "Agent Card: "
        f"{settings.writer_agent_url}"
        "/.well-known/agent-card.json"
    )

    uvicorn.run(
        app,
        host=settings.writer_agent_host,
        port=settings.writer_agent_port,
    )
