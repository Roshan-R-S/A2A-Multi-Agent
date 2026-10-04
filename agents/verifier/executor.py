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

from agents.verifier.prompts import VERIFIER_SYSTEM_PROMPT
from core.llm import generate_text


class VerifierAgent:
    """Core verification logic."""

    async def invoke(
        self,
        verification_input: str,
    ) -> str:
        raw_result = await generate_text(
            prompt=verification_input,
            system_prompt=VERIFIER_SYSTEM_PROMPT,
            temperature=0.0,
        )

        return self._validate_result(
            raw_result
        )

    @staticmethod
    def _validate_result(
        raw_result: str,
    ) -> str:
        """
        Validate and normalize the Verifier's JSON response.
        """

        text = raw_result.strip()

        # Some models may still add Markdown fences despite
        # being instructed not to. Remove simple JSON fences
        # before parsing.
        if text.startswith("```json"):
            text = text[len("```json"):].strip()

        elif text.startswith("```"):
            text = text[len("```"):].strip()

        if text.endswith("```"):
            text = text[:-3].strip()

        try:
            data = json.loads(text)

        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Verifier returned invalid JSON."
            ) from exc

        if not isinstance(data, dict):
            raise RuntimeError(
                "Verifier response must be a JSON object."
            )

        verdict = data.get("verdict")

        if verdict not in {
            "PASS",
            "FAIL",
        }:
            raise RuntimeError(
                "Verifier verdict must be PASS or FAIL."
            )

        issues = data.get("issues")

        if not isinstance(issues, list):
            raise RuntimeError(
                "Verifier 'issues' must be a list."
            )

        feedback = data.get(
            "feedback",
            "",
        )

        if not isinstance(feedback, str):
            raise RuntimeError(
                "Verifier 'feedback' must be a string."
            )

        if verdict == "PASS":
            issues = []
            feedback = ""

        normalized = {
            "verdict": verdict,
            "issues": [
                str(issue)
                for issue in issues
            ],
            "feedback": feedback.strip(),
        }

        return json.dumps(
            normalized,
            ensure_ascii=False,
            indent=2,
        )


class VerifierAgentExecutor(AgentExecutor):
    """A2A executor for the Verifier Agent."""

    def __init__(self) -> None:
        self.agent = VerifierAgent()

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
                "Verifier Agent is reviewing the draft..."
            ),
        )

        verification_input = get_message_text(
            context.message
        )

        if (
            not verification_input
            or not verification_input.strip()
        ):
            result = json.dumps(
                {
                    "verdict": "FAIL",
                    "issues": [
                        "No verification input was provided."
                    ],
                    "feedback": (
                        "Provide the original question, "
                        "research brief, and draft answer."
                    ),
                },
                indent=2,
            )

        else:
            result = await self.agent.invoke(
                verification_input.strip()
            )

        await updater.add_artifact(
            parts=[
                new_text_part(
                    text=result,
                    media_type="text/plain",
                )
            ],
            name="verification-result",
        )

        await updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message(
                "Verification completed."
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
