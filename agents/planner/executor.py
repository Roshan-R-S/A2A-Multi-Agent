"""A2A execution adapter for Planner Agent."""

from a2a.helpers import (
    get_message_text,
    new_task_from_user_message,
    new_text_message,
    new_text_part,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState

from agents.planner.router import LLMTaskPlanner


class PlannerAgent:
    def __init__(self, planner: LLMTaskPlanner | None = None) -> None:
        self.planner = planner or LLMTaskPlanner()

    async def invoke(self, question: str) -> str:
        decision = await self.planner.plan(question)
        return decision.model_dump_json(indent=2)


class PlannerAgentExecutor(AgentExecutor):
    def __init__(self, agent: PlannerAgent | None = None) -> None:
        self.agent = agent or PlannerAgent()

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        task = context.current_task
        if task is None:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=task.id,
            context_id=task.context_id,
        )
        await updater.update_status(
            state=TaskState.TASK_STATE_WORKING,
            message=new_text_message("Planner is selecting a route..."),
        )

        question = (get_message_text(context.message) or "").strip()
        if not question:
            result = '{"error":"No planning question was provided."}'
        else:
            result = await self.agent.invoke(question)

        await updater.add_artifact(
            parts=[new_text_part(text=result, media_type="application/json")],
            name="routing-decision",
        )
        await updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message("Planning completed."),
        )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise NotImplementedError("Cancellation is not supported yet.")
