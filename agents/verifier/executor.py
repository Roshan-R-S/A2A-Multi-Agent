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

from agents.verifier.context import (
    parse_verification_request,
)
from agents.verifier.generator import (
    EvidenceAwareVerifier,
)


class VerifierAgent:
    """
    Evidence-aware Verifier Agent.

    Input:
        Structured VerificationRequest JSON

    Output:
        Structured VerificationResult JSON
    """

    def __init__(
        self,
        verifier: EvidenceAwareVerifier | None = None,
    ) -> None:
        self.verifier = (
            verifier
            or EvidenceAwareVerifier()
        )

    async def invoke(
        self,
        payload: str,
    ) -> str:
        request = parse_verification_request(
            payload
        )

        result = await self.verifier.verify(
            request
        )

        return result.model_dump_json(
            indent=2
        )


class VerifierAgentExecutor(AgentExecutor):
    def __init__(
        self,
        agent: VerifierAgent | None = None,
    ) -> None:
        self.agent = (
            agent
            or VerifierAgent()
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
                "Verifier Agent is checking "
                "the draft against evidence..."
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
                '"No verification request was provided."}'
            )
        else:
            result = await self.agent.invoke(
                user_input
            )

        await updater.add_artifact(
            parts=[
                new_text_part(
                    text=result,
                    media_type="application/json",
                )
            ],
            name="verification-result",
        )

        await updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message(
                "Evidence verification completed."
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