"""Streamlit presentation; catalogue/model initialization is shared across reruns."""

import streamlit as st

from ppe.assistant import Assistant, create_model
from ppe.config import Settings
from ppe.evidence import Answer, Catalogue, Preferences
from ppe.ingestion import load_catalogue

st.set_page_config(page_title="PPE comparison", page_icon="📄", layout="centered")


@st.cache_resource(show_spinner="Reading the supplied KID documents…")
def startup():
    settings = Settings.from_env()
    catalogue = load_catalogue(settings.pdf_dir)
    assistant = None
    if settings.model_ready:
        assistant = Assistant(catalogue, create_model(settings), settings)
    return settings, catalogue, assistant


def render_answer(answer: Answer, catalogue: Catalogue, turn: int):
    if answer.status == "incomplete":
        st.warning("Evidence coverage is incomplete. See the gaps below.")
    elif answer.status == "error":
        st.error("An answer could not be verified.")
    if answer.gaps:
        st.markdown("**Evidence and answer limits**")
        for gap in answer.gaps:
            st.text(gap)
    for number, finding in enumerate(answer.findings, 1):
        st.caption(finding.label)
        # Plain text prevents model-generated links, HTML, or images from running.
        st.text(finding.statement)
        if finding.reasoning:
            st.text("Reasoning: " + finding.reasoning)
        sources_by_fund = {}
        for citation in finding.citations:
            source = catalogue.by_id.get(citation.evidence_id)
            if source is None:
                continue
            sources_by_fund.setdefault(source.fund_id, []).append((source, citation))
        for index, references in enumerate(sources_by_fund.values(), 1):
            source = references[0][0]
            sections = ", ".join(
                dict.fromkeys(
                    record.section.replace("_", " ") for record, _ in references
                )
            )
            st.caption(f"Source: {source.fund_name} — {sections}.")
            with st.expander("Supporting quotes and original PDF"):
                metadata = [
                    source.filename,
                    f"Document date: {source.document_date or 'unknown'}",
                    source.unit_class or "Unit class unknown.",
                ]
                st.text("\n".join(metadata))
                seen = set()
                for record, citation in references:
                    reference = (record.id, citation.quote)
                    if reference in seen:
                        continue
                    seen.add(reference)
                    st.text(
                        f"{record.heading} | page(s) "
                        + ", ".join(map(str, record.pages))
                    )
                    st.text(citation.quote)
                pdf = catalogue.pdfs.get(source.fund_id)
                if pdf:
                    st.download_button(
                        "Open original PDF",
                        pdf,
                        file_name=source.filename,
                        mime="application/pdf",
                        key=f"pdf-{turn}-{number}-{index}",
                    )
    if answer.assumptions:
        st.markdown("**Assumptions**")
        for assumption in answer.assumptions:
            st.text(assumption)
    supplied = {
        key: value for key, value in answer.preferences.model_dump().items() if value
    }
    if supplied:
        with st.expander("Your stated preferences"):
            for key, value in supplied.items():
                st.text(f"{key.replace('_', ' ').capitalize()}: {value}")
    if answer.follow_up:
        st.text(answer.follow_up)


def main():
    st.title("PPE comparison")
    st.write(
        "Understand the supplied investment options through their documented trade-offs."
    )
    st.caption("Ask in English. Product names and source evidence remain Polish.")
    try:
        settings, catalogue, assistant = startup()
    except Exception:
        st.error(
            "Startup failed. Check the local PDF configuration, then restart the app."
        )
        return
    with st.expander(f"Available documents ({len(catalogue.documents)})"):
        for document in catalogue.documents:
            st.text(f"{document.name} · {document.date or 'date unknown'}")
            for gap in document.gaps:
                st.text(gap)
        for gap in catalogue.startup_gaps:
            st.text(gap)
    if not settings.model_ready:
        st.info(
            "Set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, "
            "AZURE_OPENAI_DEPLOYMENT and AZURE_OPENAI_API_VERSION "
            "in your local .env, then restart the app."
        )
    if settings.trace_content:
        st.caption(
            "Full-content tracing is enabled by local configuration; questions and evidence are saved to MLflow."
        )
    if "turns" not in st.session_state:
        st.session_state.turns = []
    if "preferences" not in st.session_state:
        st.session_state.preferences = Preferences.unknown()
    for index, turn in enumerate(st.session_state.turns):
        with st.chat_message("user"):
            st.text(turn["question"])
        with st.chat_message("assistant"):
            render_answer(Answer.model_validate(turn["answer"]), catalogue, index)
    question = st.chat_input(
        "Ask about the options or describe your preferences…",
        max_chars=6000,
        disabled=assistant is None or not catalogue.documents,
    )
    if question and assistant:
        with st.chat_message("user"):
            st.text(question)
        with st.chat_message("assistant"):
            with st.spinner("Checking the document evidence…"):
                answer = assistant.answer(
                    question,
                    st.session_state.turns,
                    st.session_state.preferences,
                )
            render_answer(answer, catalogue, len(st.session_state.turns))
        st.session_state.preferences = answer.preferences
        st.session_state.turns.append(
            {"question": question, "answer": answer.model_dump(mode="json")}
        )


if __name__ == "__main__":
    main()
