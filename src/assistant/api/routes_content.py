"""Content management API (CM E1): open, edit, submit, approve and publish any source; versions, comments, activity."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..content.service import ContentError, ContentService, NotFound


class DraftBody(BaseModel):
    text: str
    base_sha: str | None = None


class NoteBody(BaseModel):
    note: str = ""


class PublishBody(BaseModel):
    draft_sha: str
    note: str = ""


class CommentBody(BaseModel):
    quote: str
    text: str
    prefix: str = ""
    suffix: str = ""


class ReplyBody(BaseModel):
    text: str


class DecideBody(BaseModel):
    expected_sha: str


class DetailsBody(BaseModel):
    fields: dict = Field(default_factory=dict)


def _guard(fn):
    try:
        return fn()
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=exc.args[0] if exc.args else "Not found") from exc
    except ContentError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def build_content_router(content: ContentService, dependencies: Sequence | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/content", tags=["content"], dependencies=list(dependencies or []))

    @router.get("/documents")
    def documents() -> dict:
        return {"documents": content.summary(), "suggestions": content.suggestion_counts(),
                "operator": {"name": content.operator.name, "role": content.operator.role}}

    @router.get("/documents/{source_id}")
    def document(source_id: str) -> dict:
        return _guard(lambda: content.document(source_id))

    @router.put("/documents/{source_id}/draft")
    def save_draft(source_id: str, body: DraftBody) -> dict:
        return _guard(lambda: content.save_draft(source_id, body.text, body.base_sha))

    @router.delete("/documents/{source_id}/draft")
    def discard_draft(source_id: str) -> dict:
        return _guard(lambda: content.discard_draft(source_id))

    @router.post("/documents/{source_id}/submit")
    def submit(source_id: str, body: NoteBody) -> dict:
        return _guard(lambda: content.submit(source_id, body.note))

    @router.post("/documents/{source_id}/return")
    def return_to_draft(source_id: str, body: NoteBody) -> dict:
        return _guard(lambda: content.return_to_draft(source_id, body.note))

    @router.post("/documents/{source_id}/publish")
    def publish(source_id: str, body: PublishBody) -> dict:
        return _guard(lambda: content.publish(source_id, body.draft_sha, body.note))

    @router.post("/documents/{source_id}/approve")
    def approve(source_id: str, body: DecideBody) -> dict:
        return _guard(lambda: content.decide(source_id, body.expected_sha, True))

    @router.post("/documents/{source_id}/reject")
    def reject(source_id: str, body: DecideBody) -> dict:
        return _guard(lambda: content.decide(source_id, body.expected_sha, False))

    @router.get("/documents/{source_id}/versions")
    def versions(source_id: str) -> dict:
        return {"versions": _guard(lambda: content.versions(source_id))}

    @router.get("/documents/{source_id}/versions/{n}")
    def version(source_id: str, n: int) -> dict:
        return _guard(lambda: content.version(source_id, n))

    @router.post("/documents/{source_id}/versions/{n}/restore")
    def restore(source_id: str, n: int) -> dict:
        return _guard(lambda: content.restore(source_id, n))

    @router.get("/documents/{source_id}/diff")
    def diff(source_id: str, base: str = "published", target: str = "draft") -> dict:
        return _guard(lambda: content.diff(source_id, base, target))

    @router.get("/documents/{source_id}/comments")
    def comments(source_id: str) -> dict:
        return {"comments": _guard(lambda: content.comments(source_id))}

    @router.post("/documents/{source_id}/comments")
    def add_comment(source_id: str, body: CommentBody) -> dict:
        return _guard(lambda: content.add_comment(source_id, body.quote, body.text, body.prefix, body.suffix))

    @router.post("/comments/{comment_id}/replies")
    def reply(comment_id: str, body: ReplyBody) -> dict:
        return _guard(lambda: content.reply(comment_id, body.text))

    @router.post("/comments/{comment_id}/resolve")
    def resolve(comment_id: str) -> dict:
        return _guard(lambda: content.set_comment_status(comment_id, True))

    @router.post("/comments/{comment_id}/reopen")
    def reopen(comment_id: str) -> dict:
        return _guard(lambda: content.set_comment_status(comment_id, False))

    @router.delete("/comments/{comment_id}")
    def delete_comment(comment_id: str) -> dict:
        _guard(lambda: content.delete_comment(comment_id))
        return {"deleted": comment_id}

    @router.get("/documents/{source_id}/activity")
    def activity(source_id: str) -> dict:
        return {"activity": _guard(lambda: content.activity(source_id))}

    @router.get("/documents/{source_id}/suggestions")
    def suggestions(source_id: str) -> dict:
        return {"suggestions": _guard(lambda: content.suggestions(source_id))}

    @router.patch("/documents/{source_id}/details")
    def details(source_id: str, body: DetailsBody) -> dict:
        return _guard(lambda: content.update_details(source_id, body.fields))

    @router.post("/assets")
    async def upload_image(file: UploadFile = File(...)) -> dict:
        data = await file.read()
        return _guard(lambda: content.save_image(data, file.content_type or ""))

    return router


def build_content_assets_router(content: ContentService) -> APIRouter:
    """Images inserted into documents. An <img> cannot send the sign-in header, so the route is open; names are
    content hashes, so an image can only be fetched by someone who already has the document."""
    router = APIRouter(prefix="/api/content", tags=["content"])

    @router.get("/assets/{name}")
    def image(name: str) -> FileResponse:
        path, media = _guard(lambda: content.image(name))
        return FileResponse(path, media_type=media, headers={"Cache-Control": "private, max-age=31536000, immutable"})

    return router
