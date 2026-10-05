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

from agents.research.factory import (
    create_research_pipeline,
)
from agents.research.pipeline import (
    ResearchPipeline,
)


class ResearchAgent:
    """
    Web-backed Research Agent.

    The agent returns a structured ResearchResult JSON document
    containing claims, evidence, sources, and caveats.
    """

    def __init__(
        self,
        pipeline: ResearchPipeline | None = None,
    ) -> None:
        self.pipeline = (
            pipeline
            or create_research_pipeline()
        )

    async def invoke(
        self,
        question: str,
    ) -> str:
        question = question.strip()

        if not question:
            raise ValueError(
                "Research question cannot be empty."
            )

        result = await self.pipeline.run(
            question,
            max_results=5,
            max_evidence=10,
            max_claims=8,
        )

        return result.model_dump_json(
            indent=2
        )


class ResearchAgentExecutor(AgentExecutor):
    def __init__(
        self,
        agent: ResearchAgent | None = None,
    ) -> None:
        self.agent = (
            agent
            or ResearchAgent()
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
                "Research Agent is searching "
                "and analyzing sources..."
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
                '{"error": '
                '"No research question was provided."}'
            )

        else:
            result = await self.agent.invoke(
                user_input.strip()
            )

        await updater.add_artifact(
            parts=[
                new_text_part(
                    text=result,
                    media_type="application/json",
                )
            ],
            name="research-result",
        )

        await updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message(
                "Web-backed research completed."
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
