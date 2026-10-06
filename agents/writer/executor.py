import json

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
from agents.writer.revision import (
    parse_revision_request,
)


class WriterAgent:
    """
    Citation-aware Writer Agent.

    Supports:

    1. Normal writing:
       ResearchResult JSON -> final answer

    2. Revision:
       WriterRevisionRequest JSON -> revised answer
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
        payload: str,
    ) -> str:
        payload = payload.strip()

        if not payload:
            raise ValueError(
                "Writer request cannot be empty."
            )

        try:
            data = json.loads(
                payload
            )

        except json.JSONDecodeError:
            # Preserve the existing structured
            # research validation behaviour.
            research = parse_research_result(
                payload
            )

            return await self.writer.write(
                research
            )

        if (
            isinstance(data, dict)
            and data.get("mode") == "revise"
        ):
            request = parse_revision_request(
                payload
            )

            return await self.writer.revise(
                request
            )

        research = parse_research_result(
            payload
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
                "Writer Agent is creating or "
                "revising a citation-backed response..."
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
                "No structured writer request "
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