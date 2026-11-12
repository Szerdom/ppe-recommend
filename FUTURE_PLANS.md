# Future plans

1. **Real scenario evaluation dataset.** I will use reviewed MLflow conversations, with content-tracing opt-in and personal details removed. I will cover conflicting or changed preferences, all-option comparisons, missing evidence and unsupported questions, with labelled expectations and a held-out regression set.

2. **Answer quality evaluation.** I will involve reviewers in checking claim support, numerical context, preference handling and useful trade-offs without investment recommendations. I will replay trace-based cases after changes, comparing quality, repair rate, latency and cost against a baseline with recorded prompt, model and document versions.

3. **Code cleanup.** I will clean up the code to improve readability, reduce duplication and simplify maintenance.

4. **Deterministic code tests.** I will cover PDF parsing, section boundaries, duplicate identifiers, retrieval coverage and citation validation with fixed inputs and expected outputs, without live model calls.

5. **Evidence presentation.** I will place each finding beside its supporting quote, document section and page reference, with clear labels for interpretation and missing evidence. I will check whether users can verify claims and compare trade-offs easily.

6. **Semantic search.** I will test multilingual embeddings and a vector database to connect English questions to Polish evidence, using metadata filters and source-linked chunks. I will retain complete coverage for broad comparisons and adopt the approach only if trace-based evaluation demonstrates improvements.

7. **Ingestion and document updates.** I will test changed headings, cost tables and unreadable PDFs against original documents, and add catalogue refresh with stale evidence and embeddings replaced.

8. **Plain English and verified translations.** I will arrange bilingual human review of Polish-to-English translations against the KIDs, checking financial terms, figures and qualifications. I will use basic English while preserving the source meaning and Polish quotations, and require human verification rather than relying on automated translation checks alone.
