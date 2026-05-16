# Plan: Original-inputs panel on course outline page

## Context

When a course is generated, the user lands on `/courses/{id}` and sees the outline (modules, lessons) — but nothing tells them what they originally entered to produce it. After a regenerate, after returning to an old course later, or while comparing two courses, the user has no way to recall what drove the output.

This plan covers the original-inputs panel through its v2 layout (current shape).

All the data is already on the loaded course row — no backend or API changes are needed:
- `course.input` (a `CourseGenerationRequest`) carries topic, expertise levels, audience, hours, resources, learner context.
- `course` columns carry `rag_server_id`, `rag_top_k`, `override_model`, `override_temperature`, `override_num_ctx`.
- The RAG server name resolves via `useRagServersStore` (already mounted from `App.tsx`).

## Current shape (v2)

- **Position**: At the top of the course-detail body, above the (optional) "Generate now" button, research trace, banners, and outline. Visible on first paint.
- **Visibility**: Always visible when a course is loaded — including pending and generating states. (v1 only showed the panel once an outline existed.)
- **Layout**: Inline summary banner — 5 lines, each `label  value · value · value`. (v1 was a five-section vertical card ~20 lines tall.)
- **Width**: The detail body runs at 1200px max-width (other course pages remain at 800px to match AppSettings).

### Line composition

```
Original inputs

Topic     {topic} · {audience age label} · {current} → {target}
Length    {hours_min}–{hours_max} hours · {resources, comma-joined or "(none)"}
Context   {learner_context} or "(none provided)"
RAG       {server.name} ({server.corpus_id}) (k={rag_top_k})
Model     {model or "(global default)"} · temp {temperature or "(default)"} · {num_ctx or "(default)"} ctx
```

Fallbacks:
- Empty `included_resources` → `(none)`.
- Null/empty `learner_context` → `(none provided)`.
- Null `override_model` → `(global default)`.
- Null `override_temperature` → `temp (default)`.
- Null `override_num_ctx` → `(default) ctx`.
- RAG server not in store (e.g., deleted) → raw `rag_server_id`.

## Implementation notes

- **`frontend/src/components/courses/CourseDetail.tsx`** — `InputsSummary` + `SummaryLine` helpers above the main component. Rendered unconditionally inside `<div className="course-detail__body">` as the first child. RAG server is resolved via `useRagServersStore` selector + `Array.find`.
- **`frontend/src/components/courses/courses.css`** — `.course-detail__inputs-summary*` rules for the inline banner; `.course-detail__body { max-width: 1200px }` overriding the shared 800px rule.

## Verification

1. `make dev` is up. Open `/courses/{id}` on a completed course. Verify:
   - The "Original Inputs" card appears at the top of the body (above the outline).
   - 5 lines: Topic, Length, Context, RAG, Model — each on a single line.
   - The detail body is visibly wider than the create form / list pages.
2. Create a new course — verify the inputs panel is visible at the top during pending → research → assembling → complete (no longer gated on outline existing).
3. Edge cases (empty resources, null learner_context, null model overrides, missing RAG server in store) display the documented fallbacks.
4. `docker exec ollama_frontend npx tsc --noEmit`, `docker exec ollama_frontend npm run lint`, `docker exec ollama_frontend npm test` — all clean.

## Out of scope

- No new Vitest tests (presentational only).
- No backend or schema changes.
- No changes to create form or list page widths.
- No reflow of `OutlineRenderer` internals (just gets more horizontal room from the wider pane).

## Version history

- **v1** (commit `ddfae18`): five-section vertical card at the bottom of the page, gated on `outline` existing, body still 800px.
- **v2** (this iteration): compact 5-line inline banner at the top, always visible, body widened to 1200px.
