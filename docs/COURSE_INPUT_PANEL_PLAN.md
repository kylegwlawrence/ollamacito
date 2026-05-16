# Plan: Show original create-form inputs on course outline page

## Context

When a course is generated, the user lands on the course detail page (`/courses/{id}`) and sees the outline (modules, lessons, etc.) — but nothing on this page tells them what they originally entered to produce it. After a regenerate, after returning to an old course later, or just while comparing two courses, the user has no way to recall the topic, audience, expertise levels, hours, resources, RAG corpus, or model overrides that drove the output. The user wants a small always-visible card at the bottom of the page that surfaces the full set of inputs that were used.

All the data is already loaded — no backend or API changes are needed:
- `course.input` (a `CourseGenerationRequest`) carries topic, expertise levels, audience, hours, resources, learner context.
- `course` columns carry `rag_server_id`, `rag_top_k`, `override_model`, `override_temperature`, `override_num_ctx`.
- The RAG server name can be resolved via `useRagServersStore` (already mounted by the create form).

## Confirmed scope (from clarifying questions)

- **Fields**: ALL form inputs, including the technical settings (RAG server + top_k, model override, temperature, context window).
- **Display**: Always-visible compact card. No collapse/expand interaction.
- **When to show**: Only when an outline exists (`gen.outline || course.outline`). Hidden during pending/generating states.

## Approach

Inline the card directly in `CourseDetail.tsx` (below `<OutlineRenderer />`). Render it conditionally on `outline` being truthy. Pull labels from the existing exports in `@/types`. Resolve the RAG server name from `useRagServersStore`. Style with a smaller, more muted look than the outline sections.

Keep this inline rather than a separate component — it's read-only, has no internal state, and the existing pattern in `CourseDetail.tsx` already inlines several sections (banners, action bars, etc.).

## Files to modify

1. **`frontend/src/components/courses/CourseDetail.tsx`** — new JSX block at the bottom of `<div className="course-detail__body">`, conditionally rendered.
   - Subscribe to `useRagServersStore((s) => s.servers)` to resolve the RAG server name.
   - Use existing `AGE_CATEGORY_LABELS` and `RESOURCE_LABELS` from `@/types`.
   - Render sections matching the create form layout: Topic & Audience, Course Length, Optional Notes, RAG Source, Model Overrides.
   - For each section, render two-column key→value pairs.
   - Empty `included_resources` → display "(none)". Null/empty `learner_context` → "(none provided)". Null `override_model` → "(global default)".

2. **`frontend/src/components/courses/courses.css`** — add styles for the new card:
   - `.course-detail__inputs-summary` (the card shell — `surf-1` background, `border-subtle`, `r-md`, padding)
   - `.course-detail__inputs-summary-group` (per-section spacing)
   - `.course-detail__inputs-summary-title` (uppercase mini-heading, same treatment as `__section-title`)
   - `.course-detail__inputs-summary-row` (two-column grid for label/value)
   - `.course-detail__inputs-summary-label` (muted, `on-surf-2`, `fs-caption`)
   - `.course-detail__inputs-summary-value` (default text, `fs-body-sm`)

## Verification

1. `make dev` to start the stack.
2. Create a new course via `/courses/new` with distinctive values (e.g. topic "Photosynthesis", elementary audience, hours 4–6, resources Readings + Quizzes, learner context "Show diagrams").
3. After the outline finishes generating on `/courses/{id}`, scroll to the bottom. Verify the "Original Inputs" card appears with every value matching what was entered.
4. Confirm the card is HIDDEN before generation finishes (`status === pending`, mid-stream).
5. Reload the page — confirm the card still renders correctly (data loaded from `loadOne`, not just stream frames).
6. Click "Regenerate" — confirm the card disappears while regenerating, then reappears with values once the new outline arrives.
7. Edge cases:
   - A course where `override_model` is null → shows "(global default)".
   - A course with `learner_context` null/empty → shows "(none provided)".
   - A course with `included_resources` empty → shows "(none)".
   - RAG server name resolves (servers store loaded). If lookup is undefined, fall back to showing the server ID.
8. `make lint` — confirm no eslint errors.
9. `docker exec ollama_frontend npm test` — confirm Vitest suite still passes.

## Out of scope

- No new Vitest tests added. The change is presentational and the existing test suite covers the data flow.
- No backend or schema changes.
- No edit/back-to-form action — the panel is read-only.
- No collapse/expand interaction (per user clarification).
