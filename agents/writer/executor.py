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

from agents.writer.context import (
    parse_research_result,
)
from agents.writer.generator import (
    CitationAwareWriter,
)


class WriterAgent:
    """
    Citation-aware Writer Agent.

    Input:
        Structured ResearchResult JSON

    Output:
        User-facing prose with [src_n] citations.
    """

    def __init__(
        self,
        writer: CitationAwareWriter | None = None,
    ) -> None:
        self.writer = (
            writer
            or CitationAwareWriter()
        )

    async def invoke(
        self,
        research_payload: str,
    ) -> str:
        research = parse_research_result(
            research_payload
        )

        return await self.writer.write(
            research
        )


class WriterAgentExecutor(AgentExecutor):
    def __init__(
        self,
        agent: WriterAgent | None = None,
    ) -> None:
        self.agent = (
            agent
            or WriterAgent()
        )

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:

        if context.current_task:
            task = context.current_task

        else:
            task = new_task_from_user_message(
                context.message
            )

            await event_queue.enqueue_event(
                task
            )

        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=task.id,
            context_id=task.context_id,
        )

        await updater.update_status(
            state=TaskState.TASK_STATE_WORKING,
            message=new_text_message(
                "Writer Agent is creating a "
                "citation-backed response..."
            ),
        )

        user_input = get_message_text(
            context.message
        )

        if (
            not user_input
            or not user_input.strip()
        ):
            result = (
                "No structured research result "
                "was provided."
            )

        else:
            result = await self.agent.invoke(
                user_input
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
                "Citation-backed response completed."
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
