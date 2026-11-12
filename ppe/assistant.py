"""One retrieval plan, read-only section tools, and a validated answer."""

import json
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI
from langsmith import tracing_context
from openai import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import Field, SecretStr

from ppe.config import Settings
from ppe.evidence import Answer, Catalogue, Preferences, Record, Section
from ppe.ingestion import normalize
from ppe.prompts import FINAL_ANSWER, POLICY, REPAIR, ROUTE
from ppe.tools import build_tools
from ppe.tracing import (
    annotate,
    trace_error,
    trace_output,
    trace_span,
    tracing_settings,
)

CORE_SECTIONS = ("strategy", "risks", "costs", "holding_terms")


class RequestPlan(Record):
    language: Literal["English", "non-English", "ambiguous"]
    intent: Literal["factual", "comparison", "clarification", "unsupported"]
    preferences: Preferences
    all_options: bool
    fund_ids: list[str] = Field(max_length=25)
    sections: list[Section] = Field(max_length=5)


def create_model(settings: Settings) -> AzureChatOpenAI:
    if not settings.model_ready:
        raise ValueError(
            "Azure endpoint, deployment, API version and key are required."
        )
    return AzureChatOpenAI(
        azure_endpoint=settings.azure_endpoint,
        azure_deployment=settings.azure_deployment,
        api_version=settings.api_version,
        api_key=SecretStr(settings.api_key),
        base_url=None,
        azure_ad_token=None,
        timeout=180,
        max_retries=0,
        max_completion_tokens=5000,
        reasoning_effort=settings.reasoning_effort,
    )


def model_error_message(exc: Exception) -> str:
    """Expose actionable categories without displaying API payloads or secrets."""
    body = getattr(exc, "body", None)
    error = body.get("error", body) if isinstance(body, dict) else {}
    error = error if isinstance(error, dict) else {}
    if error.get("code") in {"credit_balance_exhausted", "insufficient_quota"}:
        return "Model API credits or quota are exhausted. Restore access before trying again."
    if isinstance(exc, APITimeoutError):
        return "The model request timed out. Try again."
    if isinstance(exc, APIConnectionError):
        return "Could not connect to the model. Check the Azure endpoint and network connection."
    if isinstance(exc, APIStatusError):
        if exc.status_code in {401, 403}:
            return (
                "Model access was denied. Check the Azure resource key and permissions."
            )
        if exc.status_code == 404:
            return "Model deployment was not found. Check the Azure endpoint and deployment name."
        if exc.status_code == 429:
            return "The model rate limit was reached. Wait briefly and try again; check Azure quota if it persists."
        if exc.status_code == 400:
            return (
                "The model rejected the request settings. Check the API version and "
                "native JSON-schema output and reasoning-effort support, then "
                "restart the app."
            )
    return "A verified answer could not be produced. Check model access and try again."


def validate_answer(answer: Answer, evidence: dict) -> None:
    if answer.status == "answered" and not answer.findings:
        raise ValueError("An answered response requires findings.")
    for finding in answer.findings:
        for citation in finding.citations:
            source = evidence.get(citation.evidence_id)
            if source is None:
                raise ValueError("Citation was not retrieved in this request.")
            quote = normalize(citation.quote)
            if not quote or quote not in normalize(source.text):
                raise ValueError("Quote does not match retained Polish evidence.")


class Assistant:
    def __init__(self, catalogue: Catalogue, model, settings: Settings):
        self.catalogue, self.model, self.settings = catalogue, model, settings
        self.tools = build_tools(catalogue)

    def answer(
        self, question: str, history: list[dict], preferences: Preferences
    ) -> Answer:
        question = question.strip()
        if not question or len(question) > 6000:
            return Answer.message(
                "clarification",
                "Enter an English question of 1-6,000 characters.",
                preferences,
            )
        if not self.catalogue.documents:
            return Answer.message(
                "incomplete", "No KID documents were available at startup.", preferences
            )
        tracing = tracing_settings(self.settings)
        data = {
            "question": question,
            "previous_turns_untrusted": history[-6:],
            "remembered_preferences_untrusted": preferences.model_dump(),
        }
        versions = {d.filename: d.document_hash for d in self.catalogue.documents}
        with (
            tracing_context(enabled=False),
            trace_span(
                tracing,
                "ppe.question",
                "CHAIN",
                data,
                deployment=self.settings.azure_deployment,
                documents=versions,
            ) as span,
        ):
            try:
                answer = self._answer(data, tracing, span)
            except Exception as exc:
                annotate(span, error_code=type(exc).__name__)
                answer = Answer.message("error", model_error_message(exc), preferences)
            if answer.status == "error":
                trace_error(span)
                answer = answer.model_copy(update={"preferences": preferences})
            trace_output(tracing, span, answer)
            return answer

    def _answer(self, data, tracing, request_span):
        plan = self._invoke(
            RequestPlan,
            ROUTE,
            {**data, "catalogue_untrusted": self.catalogue.options()},
            tracing,
            "model.route",
        )
        if plan.language == "non-English":
            return Answer.message(
                "english_required",
                "Please resubmit in English; Polish names and quotes are welcome.",
                plan.preferences,
            )
        if plan.intent in {"clarification", "unsupported"}:
            message = (
                "What would you like to compare about the supplied options?"
                if plan.intent == "clarification"
                else "The KIDs cannot establish this. Ask about documented strategy, risks, costs or holding terms."
            )
            return Answer.message(plan.intent, message, plan.preferences)
        known = [d.fund_id for d in self.catalogue.documents]
        selected = known if plan.all_options else list(dict.fromkeys(plan.fund_ids))
        if not selected or any(f not in known for f in selected):
            return Answer.message(
                "clarification",
                "Identify the supplied options, or ask to compare all options.",
                plan.preferences,
            )
        sections = list(
            dict.fromkeys(
                CORE_SECTIONS if plan.intent == "comparison" else plan.sections
            )
        )
        if "scenarios" in plan.sections and "scenarios" not in sections:
            sections.append("scenarios")
        if not sections:
            return Answer.message(
                "unsupported",
                "That topic is outside the retained KID evidence.",
                plan.preferences,
            )
        evidence, gaps = {}, list(self.catalogue.startup_gaps)
        for section in sections:
            name, arguments = "get_" + section, {"fund_ids": selected}
            with trace_span(tracing, name, "TOOL", arguments) as span:
                result = self.tools[name].invoke(arguments)
                trace_output(tracing, span, result)
            evidence.update(
                {r["id"]: self.catalogue.by_id[r["id"]] for r in result["records"]}
            )
            gaps.extend(result["gaps"])
        gaps = list(dict.fromkeys(gaps))
        annotate(request_span, evidence_ids=sorted(evidence))
        final_data = {
            **data,
            "preferences": plan.preferences.model_dump(),
            "selected_fund_ids": selected,
            "coverage_gaps": gaps,
            "evidence": [r.model_dump(mode="json") for r in evidence.values()],
        }
        instruction = FINAL_ANSWER
        for attempt in range(2):
            try:
                answer = self._invoke(
                    Answer,
                    instruction,
                    final_data,
                    tracing,
                    "model.repair" if attempt else "model.final",
                )
                validate_answer(answer, evidence)
                if answer.status == "error":
                    return answer
                answer = answer.model_copy(update={"preferences": plan.preferences})
                if gaps:
                    answer = answer.model_copy(
                        update={
                            "status": "incomplete",
                            "gaps": list(dict.fromkeys([*gaps, *answer.gaps]))[:30],
                        }
                    )
                return answer
            except ValueError:
                instruction += REPAIR
        return Answer.message(
            "error",
            "Answer validation failed after one repair. No unverified prose is displayed.",
            plan.preferences,
        )

    def _invoke(self, schema, instruction, data, tracing, stage):
        messages = [
            SystemMessage(POLICY),
            SystemMessage(instruction),
            HumanMessage(json.dumps(data, ensure_ascii=False)),
        ]
        with trace_span(
            tracing, stage, "LLM", [m.model_dump(mode="json") for m in messages]
        ) as span:
            result = self.model.with_structured_output(
                schema, method="json_schema", strict=True
            ).invoke(messages)
            trace_output(tracing, span, result)
            return result
