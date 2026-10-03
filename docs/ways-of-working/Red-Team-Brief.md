# Red-team brief

The red team of the Definition of Done (3 October 2026, item 5): a separate agent of Claude's that tries to break an
item's promises before Codex reviews it. It gets the promises and the code, not Claude's tests, notes or reasoning, so
it does not inherit the same blind spots.

## How Claude runs it

One agent per item, with a budget (about 30 tool calls), in the background, on a worktree it may not change. Its prompt:

> You are the red team for one OpsAtlas change. Your only job is to find a way to break one of its promises.
>
> **Promises:** (the promises, copied from the ADO item)
>
> **Code:** (the files and functions that keep them)
>
> Do not read the existing tests or any notes; reason from the promises and the code. Try every line of the list of
> what can go wrong in docs/ways-of-working/Definition-of-Done.md against every promise. For each break you find, write
> a failing test in a new file under `tests/redteam/` (hermetic: no network, no live services, no models) and explain in
> two lines what input or interleaving breaks which promise. Do not fix the code. Report: the breaks found (each with
> its test), the lines of the list you tried without success, and anything you could not test.

## What happens to its findings

Each break is fixed, and becomes a scenario kind in the item's random suite (item 6). Its tests move into the ordinary
suite. A promise it could not test is either given a test by Claude or stated as untestable with a reason on the item.
