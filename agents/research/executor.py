from a2a.helpers import (
    get_message_text,
    new_task_from_user_message,
    new_text_message,
    new_text_part,
)
from a2a.server.agent_execution import (
    AgentExecutor,
    RequestContext,
)
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState

from core.llm import generate_text
from agents.research.prompts import RESEARCH_SYSTEM_PROMPT


class ResearchAgent:
    """Core research logic."""

    async def invoke(self, topic: str) -> str:
        return await generate_text(
            prompt=topic,
            system_prompt=RESEARCH_SYSTEM_PROMPT,
            temperature=0.2,
        )


class ResearchAgentExecutor(AgentExecutor):
    """A2A executor for the Research Agent."""

    def __init__(self) -> None:
        self.agent = ResearchAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        # Reuse an existing task when present.
        if context.current_task:
            task = context.current_task
        else:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=task.id,
            context_id=task.context_id,
        )

        await updater.update_status(
            state=TaskState.TASK_STATE_WORKING,
            message=new_text_message(
                "Research Agent is analyzing the topic..."
            ),
        )

        user_input = get_message_text(context.message)

        if not user_input or not user_input.strip():
            result = "No research topic was provided."
        else:
            result = await self.agent.invoke(user_input.strip())

        await updater.add_artifact(
            parts=[
                new_text_part(
                    text=result,
                    media_type="text/plain",
                )
            ],
            name="research-brief",
        )

        await updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message(
                "Research completed."
            ),
        )

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        raise NotImplementedError(
            "Cancellation is not supported yet."
        )
