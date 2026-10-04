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

from agents.writer.prompts import WRITER_SYSTEM_PROMPT
from core.llm import generate_text


class WriterAgent:
    """Core writer logic."""

    async def invoke(self, research: str) -> str:
        return await generate_text(
            prompt=research,
            system_prompt=WRITER_SYSTEM_PROMPT,
            temperature=0.3,
        )


class WriterAgentExecutor(AgentExecutor):
    """A2A executor for the Writer Agent."""

    def __init__(self) -> None:
        self.agent = WriterAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
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
                "Writer Agent is preparing the final response..."
            ),
        )

        research = get_message_text(context.message)

        if not research or not research.strip():
            result = "No research content was provided."
        else:
            result = await self.agent.invoke(
                research.strip()
            )

        await updater.add_artifact(
            parts=[
                new_text_part(
                    text=result,
                    media_type="text/plain",
                )
            ],
            name="written-response",
        )

        await updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message(
                "Writing completed."
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
