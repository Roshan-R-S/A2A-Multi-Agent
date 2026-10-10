"""Run the independent Planner A2A service on port 8004."""

import uvicorn

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from agents.planner.card import planner_agent_card
from agents.planner.executor import PlannerAgentExecutor
from agents.planner.settings import planner_agent_host, planner_agent_port, planner_agent_url


async def health(request):
    return JSONResponse({"status": "ok", "agent": "Planner Agent", "version": "0.2.0"})


request_handler = DefaultRequestHandler(
    agent_executor=PlannerAgentExecutor(),
    task_store=InMemoryTaskStore(),
    agent_card=planner_agent_card,
)

routes = [Route("/health", endpoint=health, methods=["GET"])]
routes.extend(create_agent_card_routes(planner_agent_card))
routes.extend(create_jsonrpc_routes(request_handler, "/"))
app = Starlette(routes=routes)

if __name__ == "__main__":
    print(f"Starting Planner Agent at {planner_agent_url}")
    print(f"Agent Card: {planner_agent_url}/.well-known/agent-card.json")
    uvicorn.run(app, host=planner_agent_host, port=planner_agent_port)
