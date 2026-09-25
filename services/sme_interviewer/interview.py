"""Session routes and cancellable local planning; all publication is absent."""

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from .answer_check import AnswerCheck
from .dialogue import QUESTIONS, LocalPlanner, allowed_questions, question_for_segment, retained_coverage
from .evidence import FixtureEvidence
from .ledger import Conflict, Ledger
from .planner_runtime import PLANNING_TIMEOUT_SECONDS
from .review import markdown
from .timing import TimingStore


class Interviews:
    def __init__(self, runtime, planner=None, evidence=None):
        self.store = Ledger(runtime / "interviews.sqlite")
        self.planner = planner or LocalPlanner()
        self.timings = TimingStore(runtime / "timings.sqlite")
        self.evidence = evidence or FixtureEvidence()
        self.tasks = {}
        self.events = None
        self.answer_check = AnswerCheck()

    async def cancel(self, identifier):
        task = self.tasks.get(identifier)
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def close(self):
        for identifier in list(self.tasks):
            await self.cancel(identifier)
        self.store.recover()

    def view(self, session):
        pending = next((s for s in session["segments"] if s["state"] == "provisional"), None)
        review_question = question_for_segment(session, pending) if pending else None
        result = {**session, "review_question": review_question, "evidence_current": self.evidence.current(session["evidence"])}
        if self.events:
            self.events.publish("session", result)
        return result

    async def plan(self, identifier, data):
        if any(not task.done() for task in self.tasks.values()):
            raise Conflict("A local question is already being prepared. Pause it or wait.")
        self.tasks = {key: task for key, task in self.tasks.items() if not task.done()}
        session = self.store.mutate(identifier, data.get("expected_revision"), data.get("request_id"), "plan_requested", {})
        # An idempotent replay of an already completed request must not plan again.
        if session["plan_state"] != "planning":
            return self.view(session)

        async def work():
            try:
                try:
                    plan = await asyncio.wait_for(
                        self.planner.plan(session, self.evidence.current(session["evidence"])), PLANNING_TIMEOUT_SECONDS
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    observations, assessed_ids = retained_coverage(session)
                    key = "review"
                    plan = {
                        "question": key,
                        "text": QUESTIONS[key][1],
                        "observations": observations,
                        "coverage_context": ((session.get("analysis") or {}).get("coverage_context")
                                             if assessed_ids else None),
                        "mode": "guided",
                        "reason": ("Follow-up is pending: local planning did not complete. "
                                   "Your wording is saved; retry Ask next question or review the draft."),
                        "policy": session["policy"],
                        "evidence_status": "unchecked",
                        "checks": "Factual validation pending.",
                    }
                if not self.evidence.current(session["evidence"]):
                    plan["evidence_status"] = "stale_or_unavailable"
                    if plan["question"] == "compare":
                        key = allowed_questions(session, False)[0]
                        plan.update(question=key, text=QUESTIONS[key][1], detail=None, anchor=None, mode="guided",
                                    reason="Evidence changed; comparison deferred.")
                if self.store.apply_plan(identifier, session["revision"], plan):
                    self.view(self.store.get(identifier))
            except asyncio.CancelledError:
                # The caller records pause/correction/restart; a late question is never applied.
                return

        self.tasks[identifier] = asyncio.create_task(work())
        return self.view(session)


def routes(interviews, read_body, audio):
    router = APIRouter(prefix="/api/interviews")
    store = interviews.store

    def protect(action):
        try:
            return action()
        except KeyError as exc:
            raise HTTPException(404, "Saved session not found") from exc
        except Conflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get("")
    async def listing():
        return {"sessions": store.list(), "evidence": interviews.evidence.snapshot()}

    @router.post("")
    async def create(request: Request):
        data = await read_body(request)
        sales = interviews.evidence.snapshot().get("mode") == "sales_rehearsal"
        if data.get("accept_local_storage" if sales else "accept_synthetic_storage") is not True:
            message = ("Confirm local storage before starting" if sales else
                       "Confirm synthetic-only content and local transcript storage before starting")
            raise HTTPException(400, message)
        evidence = interviews.evidence.snapshot()
        if sales and data.get('product_interview') is not None:
            from services.opsatlas_sales.foundation import topics
            TOPICS = topics()
            settings = data['product_interview']
            if (not isinstance(settings, dict) or set(settings) != {'contributor', 'topic'}
                    or settings['contributor'] not in ('Chris', 'Dan') or settings['topic'] not in TOPICS):
                raise HTTPException(400, 'Choose Chris or Dan and a product topic')
            evidence = {**evidence, 'product_interview': settings}
        return interviews.view(protect(lambda: store.create(evidence, data.get("scope"), data.get("request_id"))))

    @router.get("/{identifier}")
    async def get(identifier: str):
        return interviews.view(protect(lambda: store.get(identifier)))

    @router.get("/{identifier}/events")
    async def events(identifier: str):
        return protect(lambda: store.events(identifier))

    @router.post("/{identifier}/timings")
    async def timing_save(identifier: str, request: Request):
        data = await read_body(request)
        protect(lambda: store.get(identifier))
        return protect(lambda: interviews.timings.save(identifier, data))

    @router.get("/{identifier}/timings")
    async def timing_export(identifier: str):
        protect(lambda: store.get(identifier))
        return Response(json.dumps(interviews.timings.export(identifier), indent=2), media_type="application/json",
                        headers={"Content-Disposition": 'attachment; filename="interview-timings.json"'})

    @router.post("/{identifier}/assess")
    async def assess(identifier: str, request: Request):
        data = await read_body(request)
        session = protect(lambda: store.get(identifier))
        if data.get("expected_revision") != session["revision"]:
            raise HTTPException(409, "Session changed before answer assessment")
        answer = data.get("text")
        if not isinstance(answer, str) or not 1 <= len(answer.strip()) <= 6000:
            raise HTTPException(400, "Enter 1–6000 characters")
        segment_id = data.get("segment_id")
        target = next((s for s in session["segments"] if s["id"] == segment_id), None) if segment_id else next(
            (s for s in session["segments"] if s["state"] == "provisional"), None)
        if segment_id and target is None:
            raise HTTPException(400, "Unknown contribution")
        question = (question_for_segment(session, target) if target else session.get("current_question")) or {}
        history = "\n".join(s["text"] for s in session["segments"] if s["state"] == "confirmed" and s is not target)[-6000:]
        capture_id = data.get("audio_sequence")
        capture = audio.jobs.get(capture_id) if isinstance(capture_id, str) else None
        return await interviews.answer_check.check(question.get("text", "Describe the process"), answer, history, capture)

    @router.post("/{identifier}/segments")
    async def segment(identifier: str, request: Request):
        data = await read_body(request)
        # Optimistic mutation first, then stop the now-stale planner. A rejected
        # edit must not cancel otherwise valid work.
        result = protect(
            lambda: store.mutate(
                identifier, data.get("expected_revision"), data.get("request_id"), "segment_saved", data.get("segment", {})
            )
        )
        await interviews.cancel(identifier)
        return interviews.view(result)

    @router.post("/{identifier}/discard")
    async def discard(identifier: str, request: Request):
        data = await read_body(request)
        result = protect(
            lambda: store.mutate(
                identifier,
                data.get("expected_revision"),
                data.get("request_id"),
                "segment_discarded",
                {"segment_id": data.get("segment_id")},
            )
        )
        await interviews.cancel(identifier)
        return interviews.view(result)

    @router.post("/{identifier}/scope")
    async def scope(identifier: str, request: Request):
        data = await read_body(request)
        result = protect(
            lambda: store.mutate(identifier, data.get("expected_revision"), data.get("request_id"), "scope_changed", data.get("scope", {}))
        )
        await interviews.cancel(identifier)
        return interviews.view(result)

    @router.post("/{identifier}/plan")
    async def plan(identifier: str, request: Request):
        data = await read_body(request)
        try:
            return await interviews.plan(identifier, data)
        except (Conflict, KeyError, ValueError, TypeError) as exc:

            def fail(error=exc):
                raise error

            return protect(fail)

    @router.post("/{identifier}/pause")
    async def pause(identifier: str, request: Request):
        data = await read_body(request)
        reason = "disconnect" if data.get("reason") == "disconnect" else "operator_pause"
        result = protect(lambda: store.pause(identifier, reason))
        await interviews.cancel(identifier)
        # Speech transport is single-operator: Pause stops every outstanding audio job.
        for job in list(audio.jobs):
            await audio.cancel(job)
        return interviews.view(result)

    @router.post("/{identifier}/resume")
    async def resume(identifier: str, request: Request):
        data = await read_body(request)
        return interviews.view(
            protect(lambda: store.mutate(identifier, data.get("expected_revision"), data.get("request_id"), "resumed", {}))
        )

    @router.post("/{identifier}/finish")
    async def finish(identifier: str, request: Request):
        data = await read_body(request)
        session = protect(lambda: store.get(identifier))
        result = protect(lambda: store.finish(identifier, data.get("expected_revision"), interviews.evidence.current(session["evidence"])))
        await interviews.cancel(identifier)
        for job in list(audio.jobs):
            await audio.cancel(job)
        return interviews.view(result)

    @router.get("/{identifier}/draft/{format}")
    async def export(identifier: str, format: str):
        session = protect(lambda: store.get(identifier))
        if session["status"] != "finished" or not session["review"]:
            raise HTTPException(409, "Finish the draft before exporting")
        if not interviews.evidence.current(session["evidence"]):
            raise HTTPException(409, "The pinned evidence changed or was revoked; this draft needs revalidation before export")
        if format not in ("json", "md"):
            raise HTTPException(404, "Choose JSON or Markdown")
        packet = session["review"]
        content = json.dumps(packet, indent=2, ensure_ascii=False) if format == "json" else markdown(packet)
        return Response(
            content,
            media_type="application/json" if format == "json" else "text/markdown",
            headers={"Content-Disposition": f'attachment; filename="synthetic-interview-{identifier}.{format}"'},
        )

    return router
