# 13. AI-assisted development and Azure DevOps operating model

The solution is too broad to build efficiently through manual coding alone within a constrained project window. A controlled AI-assisted development approach is therefore appropriate. Codex is one example of the type of coding agent that may be used; equivalent tools such as other AI coding assistants could also support implementation. The important architectural point is not the specific tool name, but the control model around its use.

AI coding agents should accelerate boilerplate, test creation, refactoring and module implementation, but they should not be allowed to operate as uncontrolled editors across the whole solution. Each AI-assisted task should be tied to a backlog item, restricted to a defined module, reviewed through source control and evidenced through tests. The use of such tools should also be logged so that there is a transparent record of how AI supported the build.

| Control | Expected practice |
| --- | --- |
| Backlog control | Every coding-agent task should link to an Azure DevOps epic, feature, user story or task. |
| Scope control | Each task should state which module and files may be edited and which areas are out of scope. |
| Repository control | All changes should be committed through source control with clear messages and reviewable diffs. |
| Pipeline control | Automated tests and linting should run before a change is accepted. |
| Documentation control | Architecture decisions, module status and known limitations should be updated when meaningful behaviour changes. |
| AI usage log | The project should record where AI coding agents were used, for what purpose, and how outputs were checked. |
| Policy alignment | The use of AI development tools should remain transparent, proportionate and consistent with training provider and organisational expectations. |
