# Architecture decisions

1. **I chose document-grounded comparison.** The assistant explains the supplied KIDs against stated preferences. Its instructions exclude investment recommendations, allocations, overall rankings and outside financial knowledge, keeping the employee responsible for the choice.

2. **I chose deterministic ingestion before conversation.** PDFs are parsed locally once at startup, without model-generated extraction. Text fragments are reconstructed into lines and grouped by known Polish headings, preserving context around costs and risks. This fits the supplied layout; other layouts may produce gaps and document changes require Looka restart.

3. **I retained original evidence and provenance.** Each section keeps its Polish text, product identity, document date, unit class, pages and document hash. Product figures come from the PDFs rather than code. Unreadable or ambiguous sections become explicit gaps, and evidence with duplicate product identifiers is withheld.

4. **I chose separate, read-only tool calls for each evidence topic.** Strategy, risks, costs, holding terms and scenarios have dedicated retrieval tools accepting product identifiers. The model produces a structured retrieval plan, and the application executes one call per selected topic, collecting evidence and gaps before generating the answer. Comparisons always retrieve the four core topics, adding scenarios when requested. This keeps retrieval bounded and traceable while preserving complete sections for the small catalogue.

5. **I separated conversation planning from answer generation.** One model call identifies intent, preferences and retrieval scope; another explains the retrieved evidence. Preferences are stored explicitly alongside recent conversation history, with instructions to preserve revisions and cleared values. Missing preferences remain unknown, and factual questions require no questionnaire.

6. **I made findings structured and checkable.** Findings use the brief's Documented, Interpreted, Assumed and Not supported labels. Documented and interpreted findings require retrieved citations and matching Polish quotes; interpretations also require reasoning. One repair is allowed before returning an error. These checks verify quote presence, while claim support still needs evaluation.

7. **I kept English explanations alongside Polish sources.** The model translates and explains evidence during the conversation, while product names, quotations and original PDFs remain available for checking. Instructions preserve numerical qualifications, distinguish illustrations from forecasts and expose missing information. Quote validation does not verify translation accuracy.

8. **I chose optional tracing with limited content retention.** MLflow records conversation stages, document versions and retrieved evidence IDs. Questions, evidence and answers are retained only with explicit content-tracing opt-in; tracing failures do not block conversations.
