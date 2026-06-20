# 15. Ethics, security and data controls

Because the assistant works with business knowledge and potentially SME-derived content, security and ethics cannot be separated from the architecture. The safe default is to use anonymised or synthetic data unless approved enterprise tooling and governance are available. Where real source material is used, it should be approved, catalogued, sanitised and access-controlled before processing.

| Control | Purpose |
| --- | --- |
| Data minimisation | Only include information required to prove the use case and produce meaningful analytics. |
| Anonymisation and generalisation | Remove names, personal identifiers, sensitive system IDs, commercially sensitive details and unnecessary market-specific labels. |
| Source approval | Record who owns each source, whether it is approved for use and what restrictions apply. |
| Access control | Restrict source material, processed data, indexes and logs to authorised users. |
| Prompt and response control | Prevent prompts from asking the model to answer from unapproved sources or external internet information. |
| Auditability | Keep logs of source processing, model configuration, retrieval evidence and evaluation results. |
| Human oversight | Use stakeholder review and test questions to validate usefulness, accuracy and risk before relying on outputs. |
