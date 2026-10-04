"""Content management API (CM E1): open, edit, submit, approve and publish any source; versions, comments, activity."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..content.service import ContentError, ContentService, NotFound
from ..iam.visibility import visible
from .access import need


class DraftBody(BaseModel):
    text: str
    base_sha: str | None = None


class NoteBody(BaseModel):
    note: str = ""


class ReturnBody(BaseModel):
    """A return to the author names the draft returned (REF S23, S8), as a publish does."""

    draft_sha: str
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


class AcceptBody(BaseModel):
    key: str
    note: str = ""


class TitleBody(BaseModel):
    title: str


class ParentBody(BaseModel):
    parent: str | None = None


class GroupBody(BaseModel):
    title: str
    parent: str | None = None


class MoveBody(BaseModel):
    node: str
    parent: str | None = None
    before: str | None = None


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
        overview = content.suggestion_overview()
        notes = overview["notes"]
        notes = {k: v for k, v in notes.items() if visible(k)}  # REF S13: nothing about a document the person may not read
        documents = {k: v for k, v in content.summary().items() if visible(k)}
        return {"documents": documents, "suggestions": {k: len(v) for k, v in notes.items()}, "suggestion_notes": notes,
                "settled": overview["settled"], "operator": {"name": content.operator.name, "role": content.operator.role}}

    @router.get("/documents/{source_id}")
    def document(source_id: str) -> dict:
        return _guard(lambda: content.document(source_id))

    @router.put("/documents/{source_id}/draft", dependencies=[need("documents.edit")])
    def save_draft(source_id: str, body: DraftBody) -> dict:
        return _guard(lambda: content.save_draft(source_id, body.text, body.base_sha))

    @router.delete("/documents/{source_id}/draft", dependencies=[need("documents.edit")])
    def discard_draft(source_id: str) -> dict:
        return _guard(lambda: content.discard_draft(source_id))

    @router.post("/documents/{source_id}/submit", dependencies=[need("documents.submit")])
    def submit(source_id: str, body: NoteBody) -> dict:
        return _guard(lambda: content.submit(source_id, body.note))

    @router.post("/documents/{source_id}/return", dependencies=[need("documents.reject")])
    def return_to_draft(source_id: str, body: ReturnBody) -> dict:
        return _guard(lambda: content.return_to_draft(source_id, body.note, body.draft_sha))

    @router.post("/documents/{source_id}/publish", dependencies=[need("documents.publish")])
    def publish(source_id: str, body: PublishBody) -> dict:
        return _guard(lambda: content.publish(source_id, body.draft_sha, body.note))

    @router.post("/documents/{source_id}/approve", dependencies=[need("documents.approve"), need("documents.publish")])
    def approve(source_id: str, body: DecideBody) -> dict:
        return _guard(lambda: content.decide(source_id, body.expected_sha, True))

    @router.post("/documents/{source_id}/reject", dependencies=[need("documents.reject")])
    def reject(source_id: str, body: DecideBody) -> dict:
        return _guard(lambda: content.decide(source_id, body.expected_sha, False))

    @router.get("/documents/{source_id}/versions", dependencies=[need("documents.versions.read")])
    def versions(source_id: str) -> dict:
        return {"versions": _guard(lambda: content.versions(source_id))}

    @router.get("/documents/{source_id}/versions/{n}", dependencies=[need("documents.versions.read")])
    def version(source_id: str, n: int) -> dict:
        return _guard(lambda: content.version(source_id, n))

    @router.post("/documents/{source_id}/versions/{n}/restore", dependencies=[need("documents.versions.restore")])
    def restore(source_id: str, n: int) -> dict:
        return _guard(lambda: content.restore(source_id, n))

    @router.get("/documents/{source_id}/diff", dependencies=[need("documents.draft.read")])
    def diff(source_id: str, base: str = "published", target: str = "draft") -> dict:
        return _guard(lambda: content.diff(source_id, base, target))

    @router.get("/documents/{source_id}/comments", dependencies=[need("comments.read")])
    def comments(source_id: str) -> dict:
        return {"comments": _guard(lambda: content.comments(source_id))}

    @router.post("/documents/{source_id}/comments", dependencies=[need("comments.create")])
    def add_comment(source_id: str, body: CommentBody) -> dict:
        return _guard(lambda: content.add_comment(source_id, body.quote, body.text, body.prefix, body.suffix))

    @router.post("/comments/{comment_id}/replies", dependencies=[need("comments.create")])
    def reply(comment_id: str, body: ReplyBody) -> dict:
        return _guard(lambda: content.reply(comment_id, body.text))

    @router.post("/comments/{comment_id}/resolve", dependencies=[need("comments.create")])
    def resolve(comment_id: str) -> dict:
        return _guard(lambda: content.set_comment_status(comment_id, True))

    @router.post("/comments/{comment_id}/reopen", dependencies=[need("comments.create")])
    def reopen(comment_id: str) -> dict:
        return _guard(lambda: content.set_comment_status(comment_id, False))

    @router.delete("/comments/{comment_id}", dependencies=[need("comments.moderate")])
    def delete_comment(comment_id: str) -> dict:
        _guard(lambda: content.delete_comment(comment_id))
        return {"deleted": comment_id}

    @router.get("/documents/{source_id}/activity")
    def activity(source_id: str) -> dict:
        return {"activity": _guard(lambda: content.activity(source_id))}

    @router.get("/documents/{source_id}/suggestions", dependencies=[need("documents.draft.read")])
    def suggestions(source_id: str) -> dict:
        return _guard(lambda: content.suggestion_state(source_id))

    @router.post("/documents/{source_id}/suggestions/accept", dependencies=[need("documents.edit")])
    def accept_suggestion(source_id: str, body: AcceptBody) -> dict:
        return _guard(lambda: content.accept_suggestion(source_id, body.key, body.note))

    @router.post("/documents/{source_id}/suggestions/settled/{settled_id}/reopen", dependencies=[need("documents.edit")])
    def reopen_suggestion(source_id: str, settled_id: str) -> dict:
        return _guard(lambda: content.reopen_suggestion(source_id, settled_id))

    @router.patch("/documents/{source_id}/details", dependencies=[need("sources.metadata.update")])
    def details(source_id: str, body: DetailsBody) -> dict:
        return _guard(lambda: content.update_details(source_id, body.fields))

    @router.post("/documents/{source_id}/rename", dependencies=[need("sources.metadata.update")])
    def rename(source_id: str, body: TitleBody) -> dict:
        return _guard(lambda: content.rename(source_id, body.title))

    @router.put("/documents/{source_id}/parent", dependencies=[need("collections.move")])
    def set_parent(source_id: str, body: ParentBody) -> dict:
        return _guard(lambda: content.set_parent(source_id, body.parent))

    @router.get("/library", dependencies=[need("collections.read")])
    def library() -> dict:
        tree = content.library()
        return {**tree, "placements": {sid: place for sid, place in tree["placements"].items() if visible(sid)}}  # REF S13

    @router.post("/library/move", dependencies=[need("collections.move")])
    def move(body: MoveBody) -> dict:
        return _guard(lambda: content.move(body.node, body.parent, body.before))

    @router.post("/groups", dependencies=[need("collections.create")])
    def create_group(body: GroupBody) -> dict:
        return _guard(lambda: content.create_group(body.title, body.parent))

    @router.patch("/groups/{group_id}", dependencies=[need("collections.update")])
    def update_group(group_id: str, body: DetailsBody) -> dict:
        return _guard(lambda: content.update_group(group_id, body.fields))

    @router.delete("/groups/{group_id}", dependencies=[need("collections.delete")])
    def delete_group(group_id: str) -> dict:
        return _guard(lambda: content.delete_group(group_id))

    @router.post("/assets", dependencies=[need("assets.upload")])
    async def upload_image(file: UploadFile = File(...)) -> dict:
        data = await file.read()
        return _guard(lambda: content.save_image(data, file.content_type or ""))

    return router


def build_content_assets_router(content: ContentService, dependencies: list | None = None) -> APIRouter:
    """Images inserted into documents. An <img> sends the session cookie, so the route is guarded like the document
    it belongs to (IAM F5); names are content hashes, so nothing is guessable either."""
    router = APIRouter(prefix="/api/content", tags=["content"], dependencies=dependencies or [])

    @router.get("/assets/{name}")
    def image(name: str) -> FileResponse:
        path, media = _guard(lambda: content.image(name))
        return FileResponse(path, media_type=media, headers={"Cache-Control": "private, max-age=31536000, immutable"})

    return router
