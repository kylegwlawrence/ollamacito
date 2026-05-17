"""
Tests for the course-generator endpoints + service.

Strategy:
- CRUD endpoints (create / list / get / patch / delete) exercise real DB rows
  against the FastAPI app via httpx.ASGITransport (same pattern as test_projects).
- Generation flows mock `course_service.run_agent` (the research-phase entry
  point) AND `course_service.ollama_service.chat_structured` (the assembly
  call) so we can deterministically drive each phase end-to-end without
  hitting Ollama or RAG.
- `validate_outline` is tested directly with hand-crafted CourseOutline
  fixtures — no HTTP needed.
"""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import uuid4

import httpx
import pytest

from app.db.models import RagServer
from app.schemas.course import CourseGenerationRequest, CourseOutline
from app.services import course_service
from tests.conftest import create_rag_server

# ---------- helpers ----------


async def _make_rag_server(async_client: httpx.AsyncClient) -> str:
    """Create a RAG server for the current user. Returns the rag_server id.

    Mirrors the original `_make_rag_project` helper but doesn't create a
    Project — courses are standalone now.
    """
    server = await create_rag_server(
        async_client,
        name=f"course-test-{uuid4().hex[:8]}",
    )
    return server["id"]


def _valid_request_payload(**overrides: Any) -> Dict[str, Any]:
    body = {
        "topic": "Photosynthesis",
        "current_expertise": "novice",
        "target_expertise": "competent",
        "age_category": "elementary",
        "hours_min": 4,
        "hours_max": 6,
        "included_resources": ["readings", "quizzes"],
    }
    body.update(overrides)
    return body


def _valid_outline_dict() -> Dict[str, Any]:
    """Hand-crafted small CourseOutline that passes Pydantic + the validator."""
    return {
        "title": "Photosynthesis 101",
        "summary": "Intro to photosynthesis for elementary students.",
        "target_audience": "Elementary school students (grade 4-7)",
        "total_hours": 5.0,
        "course_outcomes": [
            {
                "id": "out-c-1",
                "text": "Explain how plants convert sunlight into food.",
                "bloom_level": "understand",
            }
        ],
        "modules": [
            {
                "id": "mod-1",
                "title": "What is photosynthesis?",
                "summary": "Basic concept.",
                "estimated_hours": 2.5,
                "outcomes": [
                    {
                        "id": "out-m-1-1",
                        "text": "Identify the inputs and outputs of photosynthesis.",
                        "bloom_level": "remember",
                    }
                ],
                "lessons": [
                    {
                        "id": "les-1-1",
                        "title": "Inputs and outputs",
                        "summary": "Sunlight + water + CO2 -> sugar + O2.",
                        "estimated_hours": 2.5,
                        "objectives": [
                            {
                                "id": "obj-1-1-1",
                                "text": "List the inputs and outputs.",
                                "bloom_level": "remember",
                            }
                        ],
                        "prerequisite_ids": [],
                        "readings": [
                            {
                                "title": "Photosynthesis",
                                "url": "https://simple.wikipedia.org/wiki/Photosynthesis",
                                "snippet": None,
                            }
                        ],
                        "assessments": [
                            {
                                "id": "asm-1-1-1",
                                "type": "quiz",
                                "prompt": "Match each input to its output.",
                                "assesses_outcome_ids": ["out-c-1", "out-m-1-1"],
                            }
                        ],
                    }
                ],
            },
            {
                "id": "mod-2",
                "title": "Why it matters",
                "summary": "Connection to ecosystems.",
                "estimated_hours": 2.5,
                "outcomes": [
                    {
                        "id": "out-m-2-1",
                        "text": "Explain why photosynthesis matters.",
                        "bloom_level": "understand",
                    }
                ],
                "lessons": [
                    {
                        "id": "les-2-1",
                        "title": "Food chains",
                        "summary": "Plants feed everyone.",
                        "estimated_hours": 2.5,
                        "objectives": [
                            {
                                "id": "obj-2-1-1",
                                "text": "Describe how photosynthesis supports life.",
                                "bloom_level": "understand",
                            }
                        ],
                        "prerequisite_ids": ["mod-1"],
                        "readings": [],
                        "assessments": [
                            {
                                "id": "asm-2-1-1",
                                "type": "quiz",
                                "prompt": "Explain in one sentence why plants matter to animals.",
                                "assesses_outcome_ids": ["out-m-2-1"],
                            }
                        ],
                    }
                ],
            },
        ],
    }


def _patch_run_agent(
    monkeypatch: pytest.MonkeyPatch,
    *,
    chunks: Optional[List[str]] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    error: Optional[str] = None,
) -> None:
    """Monkeypatch course_service.run_agent to a deterministic generator.

    The fake mutates the AgentRunResult passed in by course_service so the
    orchestrator sees `final_content` populated.
    """

    async def fake_run_agent(
        *,
        model: str,
        initial_messages: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]],
        rag_server: RagServer,
        rag_top_k: int,
        result: Any,
        is_disconnected: Any,
        max_iters: int = 5,
        system_prompt: Optional[str] = None,
        min_tool_calls: int = 0,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if error is not None:
            result.error = error
            yield {"type": "error", "message": error}
            return
        for c in chunks or ["Research notes: module 1: ...\nmodule 2: ..."]:
            result.final_content = (result.final_content or "") + c
            yield {"type": "chunk", "content": c}
        for tc in tool_calls or []:
            yield {"type": "tool_call", **tc}
            yield {
                "type": "tool_result",
                "id": tc.get("id", "1"),
                "ok": True,
                "summary": "1 result",
            }

    monkeypatch.setattr(course_service, "run_agent", fake_run_agent)


def _patch_chat_structured(
    monkeypatch: pytest.MonkeyPatch,
    *,
    payload: Optional[Dict[str, Any]] = None,
    raw_text: Optional[str] = None,
    error: Optional[Exception] = None,
) -> List[Dict[str, Any]]:
    """Monkeypatch chat_structured. Returns a list that captures invocations."""
    calls: List[Dict[str, Any]] = []

    async def fake_chat_structured(
        *,
        model: str,
        messages: List[Dict[str, str]],
        json_schema: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        calls.append(
            {
                "model": model,
                "messages": messages,
                "schema_keys": list(json_schema.keys()),
                "options": options,
            }
        )
        if error is not None:
            raise error
        if raw_text is not None:
            return raw_text
        return json.dumps(payload if payload is not None else _valid_outline_dict())

    monkeypatch.setattr(
        course_service.ollama_service,
        "chat_structured",
        fake_chat_structured,
    )
    return calls


async def _delete_rag_server(
    async_client: httpx.AsyncClient, rag_server_id: str
) -> None:
    """Best-effort cleanup: delete every course pointing at this RAG server
    first (the courses_rag_server_id FK is ON DELETE RESTRICT), then delete
    the RAG server itself.
    """
    list_resp = await async_client.get("/api/v1/courses")
    if list_resp.status_code == 200:
        for course in list_resp.json():
            if course.get("rag_server_id") == rag_server_id:
                await async_client.delete(f"/api/v1/courses/{course['id']}")
    await async_client.delete(f"/api/v1/rag-servers/{rag_server_id}")


def _parse_ndjson(text: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


async def _read_stream(
    async_client: httpx.AsyncClient, url: str, *, json_body: Any = None
) -> tuple[int, List[Dict[str, Any]]]:
    async with async_client.stream("POST", url, json=json_body) as response:
        sc = response.status_code
        body = b""
        if sc == 200:
            async for chunk in response.aiter_bytes():
                body += chunk
    if sc != 200:
        return sc, []
    return sc, _parse_ndjson(body.decode("utf-8"))


# ---------- CRUD ----------


class TestCourseCRUD:
    @pytest.mark.asyncio
    async def test_create_course_persists_with_pending_status(
        self, async_client: httpx.AsyncClient
    ) -> None:
        rag_server_id = await _make_rag_server(async_client)
        try:
            r = await async_client.post(
                "/api/v1/courses",
                json={
                    "rag_server_id": rag_server_id,
                    "rag_top_k": 5,
                    "input": _valid_request_payload(),
                },
            )
            assert r.status_code == 201, r.text
            data = r.json()
            assert data["status"] == "pending"
            assert data["rag_server_id"] == rag_server_id
            assert data["rag_top_k"] == 5
            assert data["input"]["topic"] == "Photosynthesis"
            assert data["outline"] is None
            assert data["title"] == "Photosynthesis"
        finally:
            await _delete_rag_server(async_client, rag_server_id)

    @pytest.mark.asyncio
    async def test_create_course_fails_with_unowned_rag_server_id(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Submitting another user's (or a fake) rag_server_id is a 422."""
        bogus = str(uuid4())
        r = await async_client.post(
            "/api/v1/courses",
            json={
                "rag_server_id": bogus,
                "rag_top_k": 5,
                "input": _valid_request_payload(),
            },
        )
        assert r.status_code == 422, r.text

    @pytest.mark.asyncio
    async def test_create_course_fails_with_invalid_input(
        self, async_client: httpx.AsyncClient
    ) -> None:
        rag_server_id = await _make_rag_server(async_client)
        try:
            r = await async_client.post(
                "/api/v1/courses",
                json={
                    "rag_server_id": rag_server_id,
                    "rag_top_k": 5,
                    "input": _valid_request_payload(hours_min=10, hours_max=5),
                },
            )
            assert r.status_code == 422
        finally:
            await _delete_rag_server(async_client, rag_server_id)

    @pytest.mark.asyncio
    async def test_create_course_works_with_no_projects_in_db(
        self,
        async_client: httpx.AsyncClient,
    ) -> None:
        """The headline scenario for the standalone-RAG refactor.

        With ZERO projects in the DB, creating a course must still succeed
        — courses are first-class and only need a RAG server.
        """
        from sqlalchemy import delete

        from app.db.models import Course as CourseModel
        from app.db.models import Project as ProjectModel
        from app.db.session import AsyncSessionLocal

        # Nuke any pre-existing projects + courses from previous test runs.
        async with AsyncSessionLocal() as session:
            await session.execute(delete(CourseModel))
            await session.execute(delete(ProjectModel))
            await session.commit()

        rag_server_id = await _make_rag_server(async_client)
        try:
            r = await async_client.post(
                "/api/v1/courses",
                json={
                    "rag_server_id": rag_server_id,
                    "rag_top_k": 5,
                    "input": _valid_request_payload(),
                },
            )
            assert r.status_code == 201, r.text

            # And confirm projects really are empty.
            async with AsyncSessionLocal() as session:
                from sqlalchemy import func, select

                count = (
                    await session.execute(
                        select(func.count()).select_from(ProjectModel)
                    )
                ).scalar_one()
            assert count == 0
        finally:
            # Best-effort; will RESTRICT if a Course still references it
            await async_client.delete(f"/api/v1/courses/{r.json()['id']}")
            await _delete_rag_server(async_client, rag_server_id)

    @pytest.mark.asyncio
    async def test_list_returns_user_courses_only(
        self, async_client: httpx.AsyncClient
    ) -> None:
        rag_server_id = await _make_rag_server(async_client)
        try:
            await async_client.post(
                "/api/v1/courses",
                json={
                    "rag_server_id": rag_server_id,
                    "rag_top_k": 5,
                    "input": _valid_request_payload(),
                },
            )
            r = await async_client.get("/api/v1/courses")
            assert r.status_code == 200
            items = r.json()
            assert isinstance(items, list)
            assert any(
                i["rag_server_id"] == rag_server_id and i["topic"] == "Photosynthesis"
                for i in items
            )
        finally:
            await _delete_rag_server(async_client, rag_server_id)

    @pytest.mark.asyncio
    async def test_get_returns_course(self, async_client: httpx.AsyncClient) -> None:
        rag_server_id = await _make_rag_server(async_client)
        try:
            created = (
                await async_client.post(
                    "/api/v1/courses",
                    json={
                        "rag_server_id": rag_server_id,
                        "rag_top_k": 5,
                        "input": _valid_request_payload(),
                    },
                )
            ).json()
            r = await async_client.get(f"/api/v1/courses/{created['id']}")
            assert r.status_code == 200
            assert r.json()["id"] == created["id"]
        finally:
            await _delete_rag_server(async_client, rag_server_id)

    @pytest.mark.asyncio
    async def test_patch_title_updates_record(
        self, async_client: httpx.AsyncClient
    ) -> None:
        rag_server_id = await _make_rag_server(async_client)
        try:
            created = (
                await async_client.post(
                    "/api/v1/courses",
                    json={
                        "rag_server_id": rag_server_id,
                        "rag_top_k": 5,
                        "input": _valid_request_payload(),
                    },
                )
            ).json()
            r = await async_client.patch(
                f"/api/v1/courses/{created['id']}",
                json={"title": "Renamed"},
            )
            assert r.status_code == 200
            assert r.json()["title"] == "Renamed"
        finally:
            await _delete_rag_server(async_client, rag_server_id)

    @pytest.mark.asyncio
    async def test_delete_removes_record(self, async_client: httpx.AsyncClient) -> None:
        rag_server_id = await _make_rag_server(async_client)
        try:
            created = (
                await async_client.post(
                    "/api/v1/courses",
                    json={
                        "rag_server_id": rag_server_id,
                        "rag_top_k": 5,
                        "input": _valid_request_payload(),
                    },
                )
            ).json()
            r = await async_client.delete(f"/api/v1/courses/{created['id']}")
            assert r.status_code == 204
            r = await async_client.get(f"/api/v1/courses/{created['id']}")
            assert r.status_code == 404
        finally:
            await _delete_rag_server(async_client, rag_server_id)

    @pytest.mark.asyncio
    async def test_get_returns_404_for_unknown_id(
        self, async_client: httpx.AsyncClient
    ) -> None:
        r = await async_client.get(f"/api/v1/courses/{uuid4()}")
        assert r.status_code == 404


# ---------- Generation ----------


class TestCourseGeneration:
    @pytest.mark.asyncio
    async def test_generate_streams_phases_and_done(
        self,
        async_client: httpx.AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_run_agent(monkeypatch)
        _patch_chat_structured(monkeypatch)

        rag_server_id = await _make_rag_server(async_client)
        try:
            created = (
                await async_client.post(
                    "/api/v1/courses",
                    json={
                        "rag_server_id": rag_server_id,
                        "rag_top_k": 5,
                        "input": _valid_request_payload(),
                    },
                )
            ).json()
            sc, frames = await _read_stream(
                async_client, f"/api/v1/courses/{created['id']}/generate"
            )
            assert sc == 200, frames
            types = [f["type"] for f in frames]
            assert types[0] == "phase" and frames[0]["name"] == "research"
            assert any(
                t == "phase" and f["name"] == "assembling"
                for t, f in zip(types, frames, strict=False)
            )
            assert "outline" in types
            assert types[-1] == "done"
            assert frames[-1]["status"] == "complete"
        finally:
            await _delete_rag_server(async_client, rag_server_id)

    @pytest.mark.asyncio
    async def test_generate_persists_outline_on_success(
        self,
        async_client: httpx.AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_run_agent(monkeypatch)
        _patch_chat_structured(monkeypatch)

        rag_server_id = await _make_rag_server(async_client)
        try:
            created = (
                await async_client.post(
                    "/api/v1/courses",
                    json={
                        "rag_server_id": rag_server_id,
                        "rag_top_k": 5,
                        "input": _valid_request_payload(),
                    },
                )
            ).json()
            await _read_stream(
                async_client, f"/api/v1/courses/{created['id']}/generate"
            )
            r = await async_client.get(f"/api/v1/courses/{created['id']}")
            assert r.status_code == 200
            data = r.json()
            assert data["status"] == "complete"
            assert data["outline"] is not None
            assert data["outline"]["title"] == "Photosynthesis 101"
            assert data["model_used"] is not None
        finally:
            await _delete_rag_server(async_client, rag_server_id)

    @pytest.mark.asyncio
    async def test_generate_sets_needs_review_on_validation_failure(
        self,
        async_client: httpx.AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_run_agent(monkeypatch)

        # Mutate outline to break a prerequisite reference.
        broken = _valid_outline_dict()
        broken["modules"][0]["lessons"][0]["prerequisite_ids"] = ["les-99-99"]
        _patch_chat_structured(monkeypatch, payload=broken)

        rag_server_id = await _make_rag_server(async_client)
        try:
            created = (
                await async_client.post(
                    "/api/v1/courses",
                    json={
                        "rag_server_id": rag_server_id,
                        "rag_top_k": 5,
                        "input": _valid_request_payload(),
                    },
                )
            ).json()
            _, frames = await _read_stream(
                async_client, f"/api/v1/courses/{created['id']}/generate"
            )
            assert frames[-1]["status"] == "needs_review"
            validation_frames = [f for f in frames if f["type"] == "validation"]
            assert validation_frames
            assert any("les-99-99" in e["msg"] for e in validation_frames[0]["errors"])
        finally:
            await _delete_rag_server(async_client, rag_server_id)

    @pytest.mark.asyncio
    async def test_generate_sets_failed_on_parse_error(
        self,
        async_client: httpx.AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_run_agent(monkeypatch)
        _patch_chat_structured(monkeypatch, raw_text="{not valid json")

        rag_server_id = await _make_rag_server(async_client)
        try:
            created = (
                await async_client.post(
                    "/api/v1/courses",
                    json={
                        "rag_server_id": rag_server_id,
                        "rag_top_k": 5,
                        "input": _valid_request_payload(),
                    },
                )
            ).json()
            _, frames = await _read_stream(
                async_client, f"/api/v1/courses/{created['id']}/generate"
            )
            assert frames[-1]["status"] == "failed"
            r = await async_client.get(f"/api/v1/courses/{created['id']}")
            assert r.json()["status"] == "failed"
        finally:
            await _delete_rag_server(async_client, rag_server_id)

    @pytest.mark.asyncio
    async def test_generate_fails_if_research_errors(
        self,
        async_client: httpx.AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_run_agent(monkeypatch, error="RAG server down")
        _patch_chat_structured(monkeypatch)

        rag_server_id = await _make_rag_server(async_client)
        try:
            created = (
                await async_client.post(
                    "/api/v1/courses",
                    json={
                        "rag_server_id": rag_server_id,
                        "rag_top_k": 5,
                        "input": _valid_request_payload(),
                    },
                )
            ).json()
            _, frames = await _read_stream(
                async_client, f"/api/v1/courses/{created['id']}/generate"
            )
            assert any(f["type"] == "error" for f in frames)
            assert frames[-1]["status"] == "failed"
        finally:
            await _delete_rag_server(async_client, rag_server_id)

    # NOTE: We don't test "deleting a RAG server while a course references
    # it" here — that would exercise the rag-servers DELETE endpoint's
    # IntegrityError handling, which is out of scope for this refactor. The
    # FK RESTRICT is enforced at the DB level; the surface-level UX of how
    # the rag-servers endpoint reports that conflict is its own concern.


# ---------- Regenerate ----------


class TestRegenerate:
    @pytest.mark.asyncio
    async def test_regenerate_preserves_id_and_replaces_outline(
        self,
        async_client: httpx.AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_run_agent(monkeypatch)
        _patch_chat_structured(monkeypatch)

        rag_server_id = await _make_rag_server(async_client)
        try:
            created = (
                await async_client.post(
                    "/api/v1/courses",
                    json={
                        "rag_server_id": rag_server_id,
                        "rag_top_k": 5,
                        "input": _valid_request_payload(),
                    },
                )
            ).json()
            course_id = created["id"]
            # Initial generate
            await _read_stream(async_client, f"/api/v1/courses/{course_id}/generate")
            first = (await async_client.get(f"/api/v1/courses/{course_id}")).json()
            assert first["status"] == "complete"
            first_generated_at = first["generated_at"]

            # Regenerate
            _, frames = await _read_stream(
                async_client, f"/api/v1/courses/{course_id}/regenerate"
            )
            assert frames[-1]["status"] == "complete"
            second = (await async_client.get(f"/api/v1/courses/{course_id}")).json()
            assert second["id"] == course_id
            assert second["generated_at"] != first_generated_at
        finally:
            await _delete_rag_server(async_client, rag_server_id)

    @pytest.mark.asyncio
    async def test_regenerate_with_input_override_persists_new_input(
        self,
        async_client: httpx.AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_run_agent(monkeypatch)
        _patch_chat_structured(monkeypatch)

        rag_server_id = await _make_rag_server(async_client)
        try:
            created = (
                await async_client.post(
                    "/api/v1/courses",
                    json={
                        "rag_server_id": rag_server_id,
                        "rag_top_k": 5,
                        "input": _valid_request_payload(),
                    },
                )
            ).json()
            course_id = created["id"]

            new_input = _valid_request_payload(
                topic="Cellular Respiration", hours_max=10
            )
            await _read_stream(
                async_client,
                f"/api/v1/courses/{course_id}/regenerate",
                json_body={"input": new_input},
            )
            updated = (await async_client.get(f"/api/v1/courses/{course_id}")).json()
            assert updated["input"]["topic"] == "Cellular Respiration"
            assert updated["input"]["hours_max"] == 10
            assert updated["title"] == "Cellular Respiration"
        finally:
            await _delete_rag_server(async_client, rag_server_id)


# ---------- Validator ----------


class TestValidator:
    def _outline(self) -> CourseOutline:
        return CourseOutline.model_validate(_valid_outline_dict())

    def _request(self) -> CourseGenerationRequest:
        return CourseGenerationRequest.model_validate(_valid_request_payload())

    def test_returns_empty_on_valid_outline(self) -> None:
        errors = course_service.validate_outline(self._outline(), self._request())
        assert errors == []

    def test_allows_module_id_as_prerequisite(self) -> None:
        # The fixture already uses 'mod-1' as a prerequisite on les-2-1 — confirm.
        outline = self._outline()
        assert outline.modules[1].lessons[0].prerequisite_ids == ["mod-1"]
        assert course_service.validate_outline(outline, self._request()) == []

    def test_flags_unknown_prerequisite_id(self) -> None:
        outline_dict = _valid_outline_dict()
        outline_dict["modules"][0]["lessons"][0]["prerequisite_ids"] = ["les-99-99"]
        errors = course_service.validate_outline(
            CourseOutline.model_validate(outline_dict), self._request()
        )
        assert any("les-99-99" in e["msg"] for e in errors)

    def test_flags_unknown_outcome_id_in_assessment(self) -> None:
        outline_dict = _valid_outline_dict()
        outline_dict["modules"][0]["lessons"][0]["assessments"][0][
            "assesses_outcome_ids"
        ] = ["out-c-999"]
        errors = course_service.validate_outline(
            CourseOutline.model_validate(outline_dict), self._request()
        )
        assert any("out-c-999" in e["msg"] for e in errors)

    def test_flags_orphan_outcome_never_assessed(self) -> None:
        outline_dict = _valid_outline_dict()
        # Drop the assessment that covers out-m-2-1, making it an orphan.
        outline_dict["modules"][1]["lessons"][0]["assessments"] = []
        errors = course_service.validate_outline(
            CourseOutline.model_validate(outline_dict), self._request()
        )
        assert any(
            "out-m-2-1" in e["msg"] and "never exercised" in e["msg"]
            for e in errors
        )

    def test_flags_hours_out_of_range(self) -> None:
        # Request says 4-6h, outline above sums to 5h. Build a request with a
        # tighter band that excludes 5h.
        request = CourseGenerationRequest.model_validate(
            _valid_request_payload(hours_min=10, hours_max=20)
        )
        errors = course_service.validate_outline(self._outline(), request)
        assert any("not in" in e["msg"] for e in errors)


class TestMarkdown:
    def test_renderer_produces_expected_sections(self) -> None:
        from app.services.course_markdown import outline_to_markdown

        outline = CourseOutline.model_validate(_valid_outline_dict())
        md = outline_to_markdown(outline)

        assert md.startswith("# Photosynthesis 101")
        assert "**Audience:** Elementary school students (grade 4-7)" in md
        assert "## Course outcomes" in md
        assert "## Module 1: What is photosynthesis?" in md
        assert "## Module 2: Why it matters" in md
        assert "### Lesson 1.1: Inputs and outputs" in md
        assert "### Lesson 2.1: Food chains" in md
        # Bloom level prefixed on objectives and outcomes.
        assert "_remember_: List the inputs and outputs." in md
        assert "_understand_: Explain how plants convert sunlight into food." in md
        # Assessment prompt + resolved outcome text (not the raw id).
        assert "Match each input to its output." in md
        assert "Explain how plants convert sunlight into food." in md
        # Reading link.
        assert "[Photosynthesis](https://simple.wikipedia.org/wiki/Photosynthesis)" in md
        # Trailing newline, no double trailing.
        assert md.endswith("\n")
        assert not md.endswith("\n\n")

    @pytest.mark.asyncio
    async def test_endpoint_returns_404_when_no_outline(
        self, async_client: httpx.AsyncClient
    ) -> None:
        rag_server_id = await _make_rag_server(async_client)
        try:
            created = (
                await async_client.post(
                    "/api/v1/courses",
                    json={
                        "rag_server_id": rag_server_id,
                        "rag_top_k": 5,
                        "input": _valid_request_payload(),
                    },
                )
            ).json()
            r = await async_client.get(f"/api/v1/courses/{created['id']}/markdown")
            assert r.status_code == 404
        finally:
            await _delete_rag_server(async_client, rag_server_id)

    @pytest.mark.asyncio
    async def test_endpoint_returns_markdown_after_generation(
        self,
        async_client: httpx.AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _patch_run_agent(monkeypatch)
        _patch_chat_structured(monkeypatch)

        rag_server_id = await _make_rag_server(async_client)
        try:
            created = (
                await async_client.post(
                    "/api/v1/courses",
                    json={
                        "rag_server_id": rag_server_id,
                        "rag_top_k": 5,
                        "input": _valid_request_payload(),
                    },
                )
            ).json()
            await _read_stream(
                async_client, f"/api/v1/courses/{created['id']}/generate"
            )
            r = await async_client.get(f"/api/v1/courses/{created['id']}/markdown")
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/markdown")
            body = r.text
            assert body.startswith("# Photosynthesis 101")
            assert "## Module 1:" in body
        finally:
            await _delete_rag_server(async_client, rag_server_id)
