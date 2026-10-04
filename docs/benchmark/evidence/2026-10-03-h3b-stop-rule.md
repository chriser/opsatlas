# REF H3b #2126: the stop rule, second time (3 October 2026)

**Decision (the Human, 3 October 2026): the simpler design below, with no site guessing.** The promises were restated
on #2126 before the build (P1–P8).

The second red-team round on the today-only design (commit 1023c60) found eight breaks. The tests are in
`tests/redteam/test_scope_h3b_today_redteam.py`. Each one is marked as an expected failure until the design below is
decided and built.

The Definition of Done's stop rule applies again. Patching has stopped. This note records the design flaws and
proposes a simpler design. Nothing is measured on scope set v3 until the Human decides.

## Faults by area and round

| Area | F10 red team | H3b round 1 | H3b round 2 |
|---|---|---|---|
| Reading a date in the metadata | loose dates ("2027-1-1"), date objects | an unreadable `KP_SCOPE_TODAY` crashed the answer | "2026-12-311" read as 31 December (the pattern reads only the start); "20261231" accepted by the details editor but unreadable to scope |
| Rechecking before the answer is given | (no recheck yet) | a supersede approved mid-answer was not caught (recheck added) | the facts-map path returns before the recheck; a label that appears mid-answer is not compared; an unrelated approval mid-answer withholds the answer |
| Naming a site from the question | substring ("bathroom" named Bath), a shared word, case | none | a common word in a site name ("Returns", "Reading"), a name ending in punctuation ("DC (A)"), a month ("in March" names a site called March) |

The first two areas have faults in consecutive rounds. Site naming does not, by the letter of the rule. It has the
same flaw as the date guessing that triggered the rule the first time: it reads structured meaning out of free text.

## The flaws

1. **Two readers of one date.** The details editor reads a date one way (`date.fromisoformat`). Scope reads it
   another way (a prefix pattern). Each new difference between them is a new fault.
2. **The recheck sits at one exit and compares the wrong thing.** The answer service has several exits. The recheck
   is at one of them, and it compares everything scope allows across the space, not what this answer rests on. So it
   misses changes to what the answer used (its labels, the facts path) and stops answers for changes elsewhere.
3. **Site naming guesses.** Any rule for spotting a site in free text has false matches: common words, months, place
   names that are also ordinary words. Each fix moves the false matches somewhere else.

## The simpler design (proposed)

1. **One date reader.** `date.fromisoformat` on text, or a date object. Anything else is unreadable and the source is
   left out. The details editor, scope and `KP_SCOPE_TODAY` all use the same reader, so whatever the editor accepts,
   scope reads. Loose forms the editor already rejects ("2027-1-1") become unreadable, which fails closed.
2. **One recheck, of what the answer rests on, at every exit.**
   - Before any answer is given, scope is judged again on the register as it is now.
   - The answer is given only if each source it used is still allowed with the same label.
   - For a facts-map or process-registry answer, the facts must still be open (`closes_facts` still false).
   - A change to a source the answer did not use does not stop it, as with scope off.
3. **Sites: no guessing (recommended).** No site is read from the question. Every site-specific passage says its site
   ("Applies to: Leeds distribution centre"), whatever the question says. A site's guidance is never left out for
   being another site's. The facts map stays closed whenever any approved source has a site, as it is today when no
   site is named.

   Measured basis, from phase 2 (`evaluation/results/evidence/2026-10-03-scope-*.json`): on the five questions that
   name one site, site filtering changed nothing. There was one violation with scope off and the same one (sc-016) with
   it on. Retrieval and the model already pick the site asked about. What failed was the three questions that name no
   site, which need each site's answer side by side. The labels are for those.

   The alternative is an explicit site the asker chooses (a field on `/api/ask` and a picker), with no guessing from
   text. That is more work and a separate item. It is not needed to keep any promise measured so far.

## What changes in the promises

- Promise 1 loses "another site's guidance is left out when the question names exactly one site the space knows".
- Promise 2 gains "every site-specific passage says its site".
- The other promises stand.
- The H3 mark is unchanged: violations 5% of scope questions at most; correct in-scope answers down 2 points at most,
  on set v3's 24 questions.

## Round 3, and the stop rule a third time

The red team's third round, on 39f149c, found eleven breaks. Tests: `tests/redteam/test_scope_h3b_round3_redteam.py`.

- **The recheck** had faults again: it judged on the day the answer began, even past midnight; the avatar route gives
  its answer after a second model call; there is a window between the recheck and delivery; it did not notice a
  replacing source withdrawn mid-answer. This is the same flaw as in round 2: a recheck can only be as late as the code
  it sits in, and delivery happens later, in several routes.
- **The editor's dates** had faults again: 0, false or an empty list cleared a date; an end before the start was
  accepted when the two came in separate edits. The flaw: the editor still turned the value into "no date" before the
  shared reader saw it, and checked the pair within one edit only.

**Decision (the Human, 3 October 2026):**
- **One reading, no recheck.** Each answer is judged on one reading of the register, and one day, both taken as it
  begins. An edit that lands while the answer is prepared applies from the next answer. The access and evidence
  checks at delivery (REF S16, S19) are unchanged.
- **The value as sent goes to the one reader.** Only null or "" clears a date. Anything scope cannot read is refused.
  The start-before-end rule is checked on the record as it will be stored.
- The site list is also validated: it must be a list of names, with ten at most. A list is no longer split into
  letters, and nothing is dropped.

Two wider findings were raised separately: REF S16b #2136 (the avatar route has neither S16 nor S19 at delivery) and
REF S19b #2137 (the delivery recheck does not check approval).

## Round 4, and the stop rule a fourth time

The red team's fourth round, on d9efe28, found seven breaks. Tests: `tests/redteam/test_scope_h3b_round4_redteam.py`.

- **Mid-answer consistency, again.** One reading applied to scope's judgement, but three other parts read the register
  again or were rebuilt from it during an answer: the search index, the facts map and the process registry. An
  approval landing mid-answer could bring in a source the reading never saw: a replacing source beside the one it
  replaces, or an expired process's facts.
- **Site names, again.** A name could forge a label ("Leeds; In force until …"), a comma made one site read as two,
  and blank or invisible entries were dropped or accepted.
- **Editor dates.** Two concurrent edits could store an end before the start, because the read, check and write were
  not one at a time.

**Decision (the Human, 3 October 2026):**
- **Hold every evidence path to the reading, keeping the facts map.** This was chosen over "documents only with scope
  on", which would have changed the design.
  - A passage is admitted only if its source is approved in the answer's reading.
  - With scope on, the process registry is derived from the reading.
  - The facts map is used only if it was built from exactly the sources the reading approves, at the same versions.
    This is checked before and after its facts are read; otherwise the answer uses documents only. The map records
    each source it was built from, with its approval and version, so no new provenance was needed.
- **Plain site names only.** Up to 60 letters, digits, spaces, hyphens, apostrophes and full stops, with at least one
  letter or digit; anything else is refused.
- The editor applies one edit at a time, under the project's file lock (`assistant.storage.locked`).

## Round 5, and the stop rule a fifth time

The red team's fifth round, on 6446fd8, found six breaks. Tests: `tests/redteam/test_scope_h3b_round5_redteam.py`.

- **Plain fix:** a facts map out of step fell through to the process registry, instead of documents only.
- **A document's text while a publish is in flight.** A publish wrote the new text before it marked the record pending
  at its new version. Passages do not record their version. So new text landing after the reading reached the answer.
  A failed publish restored the old text without rebuilding the facts map, which kept facts from text never approved.
  That second fault affects answers with scope off too.
- **Site names, a third round.** "Leeds. In force until 1 January 2020" passed the character set. Invisible Hangul
  fillers, "½" and "Ⅷ" passed as letters. Thai and Devanagari names were refused by accident.

**Decision (the Human, 3 October 2026):**
- **Fix the publish order (P9).**
  - A publish moves the record to its new version, pending, before it writes the new text.
  - A failed publish restores the old text and passages before the record, then rebuilds the facts map.
  - An answer uses a document's passages and process record only if, after they are read, the register still shows
    the reading's version and approval. A document whose new version lands mid-answer is left out of that answer.
- **Latin letters only in site names.** Up to 60 characters: A to Z with accented Latin letters, digits 0 to 9,
  spaces, hyphens and apostrophes, with at least one letter or digit. There are no full stops, so a name never ends
  its own label or starts another. Other scripts are refused.

## Round 6: a staged publish, as its own item

The red team's sixth round, on b52a33a, found four breaks with one cause. Tests:
`tests/redteam/test_scope_h3b_round6_redteam.py`, strict expected failures.

A failed publish puts the record back at the same version and fingerprint (A, then B, then A again). Text read while
it was in flight therefore passes every version check:
- text never approved reaches answers, with scope on or off;
- a facts map rebuilt in the race keeps its facts when the rebuild after the undo fails.

Scope's own rules (dates, labels, site names, the facts gate) found no break in this round.

**Decision (the Human, 3 October 2026):** a staged publish, as its own item: REF S23 #2140.
- A new version is prepared beside the live one and put in place only when approved.
- A failed publish never touches the live text, passages or facts map, so there is nothing to undo.
- H3b waits for S23 before Codex's review, and P9 moves to S23.

**Stated limit of P2:** the character rule cannot stop allowed words forming a site name, for example "In force until 1
January 2030". Site names are governed text written by editors, like the documents themselves.

## After S23 (4 October 2026)

REF S23 #2140 is built: the staged publish, the workspace's door and approvals decided in the register. Its red-team
loop ended at round 12 under the Human's exit rule (no break above low). Round 6's tests above pass under S23,
restated for the door (each says so). H3b goes to Codex with S23 and F10 in one review:
`2026-10-04-codex-review-brief.md`.
