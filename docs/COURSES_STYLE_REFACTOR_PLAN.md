# Course pages — styling refactor to match AppSettings

> Canonical location post-approval: `docs/COURSES_STYLE_REFACTOR_PLAN.md`.
> Predecessor: `docs/COURSES_STANDALONE_RAG_PLAN.md` (the previous refactor; complete and shipped).

## Context

The course pages (`/courses`, `/courses/new`, `/courses/:id`) use a narrow centered layout — `max-width: 720px` for the form, `max-width: 960px` for list/detail, all with `margin: 0 auto` — that visually doesn't match the rest of the app. The reference page (`/settings`, `AppSettings`) uses a left-aligned canvas-coloured shell with `ViewHeader` + a `__body` scroll region at `max-width: 800px`, and groups fields into `.card` blocks (white-ish surface against the page canvas).

This change brings the three course pages onto the same pattern: page canvas underneath, left-aligned 800px body, fields grouped in four named cards.

## Locked decisions (confirmed via clarifying questions)

| Axis | Decision |
| --- | --- |
| Sectioning (NewCourseForm) | **Four cards**: RAG Source · Topic & Audience · Course Length · Optional Notes |
| Scope | **All three course pages** (CourseList, NewCourseForm, CourseDetail) |
| Max width | **800px** (exactly matches `.app-settings__body`, `AppSettings.css:55`) |
| Alignment | **Left** (no `margin: 0 auto`; body sits at the left edge of the pane up to 800px wide) |
| Card surface | `.card` utility from `frontend/src/styles/globals.css:69` (`var(--surf-1)` background + `var(--border-subtle)` border + rounded) |
| Page canvas | `var(--surf-0)` (matches AppSettings) |
| Field styling | Mirror `.app-settings__field/__label/__input/__hint`: `var(--surf-0)` inputs against `var(--surf-1)` cards, brand focus ring |

## Files to modify

- `frontend/src/components/courses/courses.css` — substantial rewrite
- `frontend/src/components/courses/NewCourseForm.tsx` — wrap fields in `.card .new-course__section` blocks with `__section-title`
- `frontend/src/components/courses/CourseList.tsx` — wrap in outer + `__body` shell
- `frontend/src/components/courses/CourseDetail.tsx` — wrap in outer + `__body` shell

No test file changes expected (tests query by role/label, not class name) — `NewCourseForm.test.tsx`'s assertions like `getByRole('button', { name: /Create course/ })` and `getByLabelText('Topic')` keep working.

## Approach

### 1. CSS rewrite — `courses.css`

Three layout shells share one rule (mirrors `.app-settings`):
```css
.new-course,
.course-list,
.course-detail {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--surf-0);
  overflow: hidden;
}

.new-course__body,
.course-list__body,
.course-detail__body {
  flex: 1;
  overflow-y: auto;
  padding: var(--s-4) var(--s-6) var(--s-6);
  display: flex;
  flex-direction: column;
  gap: var(--s-4);
  max-width: 800px;
  /* deliberately no margin: 0 auto — body is left-aligned */
}
```

Form sections inside the body (each wrapped in `.card`):
```css
.new-course__section {
  display: flex;
  flex-direction: column;
  gap: var(--s-4);
}

.new-course__section-title {
  font-size: var(--fs-body-sm);
  font-weight: var(--fw-semibold);
  color: var(--on-surf-1);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.new-course__field { display: flex; flex-direction: column; gap: var(--s-1); }
.new-course__row { display: grid; grid-template-columns: 1fr 1fr; gap: var(--s-4); }

.new-course__label {
  font-size: var(--fs-body-sm);
  font-weight: var(--fw-semibold);
  color: var(--on-surf-1);
}

.new-course__input,
.new-course__textarea {
  height: var(--h-control);
  padding: 0 var(--s-3);
  background: var(--surf-0);     /* canvas-coloured against surf-1 cards */
  color: var(--on-surf-0);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-sm);
  font-size: var(--fs-body-sm);
  font-family: inherit;
  transition: border-color var(--dur-fast) var(--ease-std);
}
.new-course__textarea { height: auto; min-height: 96px; padding: var(--s-2) var(--s-3); line-height: 1.5; resize: vertical; }
.new-course__input:focus,
.new-course__textarea:focus {
  outline: none;
  border-color: var(--brand);
  box-shadow: 0 0 0 2px var(--brand-tint);
}

.new-course__hint { font-size: var(--fs-caption); color: var(--on-surf-2); }
.new-course__warning { font-size: var(--fs-caption); color: var(--warning); }
.new-course__error { font-size: var(--fs-caption); color: var(--danger); }

.new-course__resources { display: flex; flex-wrap: wrap; gap: var(--s-2); }
.new-course__resource-chip {
  display: flex; align-items: center; gap: var(--s-2);
  padding: var(--s-1) var(--s-3);
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-pill);
  background: var(--surf-0);
  color: var(--on-surf-1);
  cursor: pointer; user-select: none;
}
.new-course__resource-chip--on { background: var(--brand-tint); border-color: var(--brand); color: var(--brand); }

.new-course__actions { display: flex; gap: var(--s-3); padding-top: var(--s-2); }
```

Existing rules that stay (already use the right tokens; verify they aren't tied to the old `.course-form` selector and update if so):
- `.course-status-badge*` (status pills)
- `.course-card`, `.course-card__title`, `.course-card__meta` (list rows) — already use `--surf-1` + border
- `.course-list__empty`
- `.course-detail__banner*`
- `.outline*` (OutlineRenderer blocks)
- `.research-trace*`

Remove the old `.course-form*` selectors. They're being renamed to `.new-course*` (or replaced by `.card`/`.app-settings`-style equivalents).

### 2. `NewCourseForm.tsx`

Wrap in the new shell and split fields into four `.card .new-course__section` blocks:

```tsx
<div className="new-course">
  <ViewHeader title="New course" />
  <div className="new-course__body">

    {ragServers.length === 0 ? (
      <div className="card new-course__section">
        <h3 className="new-course__section-title">RAG Source</h3>
        <p>No RAG servers configured. Add one before creating a course.</p>
        <Button onClick={() => navigate('/rag-servers')} variant="primary" size="sm" leadingIcon="add">
          Manage RAG servers
        </Button>
      </div>
    ) : (
      <>
        <div className="card new-course__section">
          <h3 className="new-course__section-title">RAG Source</h3>
          <div className="new-course__field">
            <label className="new-course__label">RAG server</label>
            <Select ... />
            <span className="new-course__hint">Pick the corpus the research agent will search.</span>
          </div>
          <div className="new-course__field">
            <label className="new-course__label" htmlFor="topk">Retrieval top_k</label>
            <input id="topk" className="new-course__input" type="number" min={1} max={50} ... />
            <span className="new-course__hint">How many results per query (1–50, default 5).</span>
          </div>
        </div>

        <div className="card new-course__section">
          <h3 className="new-course__section-title">Topic & Audience</h3>
          <div className="new-course__field"><label htmlFor="topic" className="new-course__label">Topic</label><input id="topic" className="new-course__input" ... /></div>
          <div className="new-course__field"><label className="new-course__label">Audience age</label><Select ... /></div>
          {audienceWarning && <span className="new-course__warning" role="alert">{audienceWarning}</span>}
          <div className="new-course__row">
            <div className="new-course__field"><label className="new-course__label">Current expertise</label><Select ... /></div>
            <div className="new-course__field"><label className="new-course__label">Target expertise</label><Select ... /></div>
          </div>
        </div>

        <div className="card new-course__section">
          <h3 className="new-course__section-title">Course Length</h3>
          <div className="new-course__row">
            <div className="new-course__field"><label htmlFor="hmin" className="new-course__label">Hours (min)</label><input id="hmin" className="new-course__input" type="number" ... /></div>
            <div className="new-course__field"><label htmlFor="hmax" className="new-course__label">Hours (max)</label><input id="hmax" className="new-course__input" type="number" ... /></div>
          </div>
          <div className="new-course__field">
            <span className="new-course__label">Included resources</span>
            <div className="new-course__resources">
              {RESOURCE_TYPES.map((r) => (<button className="new-course__resource-chip[--on]" ... />))}
            </div>
          </div>
        </div>

        <div className="card new-course__section">
          <h3 className="new-course__section-title">Optional Notes</h3>
          <div className="new-course__field">
            <label htmlFor="ctx" className="new-course__label">Learner context</label>
            <textarea id="ctx" className="new-course__textarea" ... />
            <span className="new-course__hint">{learnerContext.length} / 1000</span>
          </div>
        </div>

        {submitError && <span className="new-course__error" role="alert">{submitError}</span>}

        <div className="new-course__actions">
          <Button onClick={handleSubmit} disabled={submitting || !!formError} variant="primary">
            {submitting ? 'Creating…' : 'Create course'}
          </Button>
          <Button onClick={() => navigate('/courses')} variant="ghost" disabled={submitting}>
            Cancel
          </Button>
        </div>
      </>
    )}
  </div>
</div>
```

### 3. `CourseList.tsx`

```tsx
<div className="course-list">
  <ViewHeader title="Courses" actions={...} />
  <div className="course-list__body">
    {loading && !loaded && <LoadingSpinner />}
    {loaded && courses.length === 0 && (
      <div className="course-list__empty"><p>No courses yet. Click "New Course" to generate one.</p></div>
    )}
    {courses.map((c) => (<CourseCard ... />))}
  </div>
</div>
```

`.course-card` is unchanged.

### 4. `CourseDetail.tsx`

```tsx
<div className="course-detail">
  <ViewHeader ... />
  <div className="course-detail__body">
    {course.status === 'pending' && !isStreaming && (<Button ...>Generate now</Button>)}
    {showResearchTrace && (<ResearchTrace ... />)}
    {gen.error && (<div className="course-detail__banner course-detail__banner--error">{gen.error}</div>)}
    {validationErrors && validationErrors.length > 0 && (<div className="course-detail__banner course-detail__banner--warn">...</div>)}
    {outline ? (<OutlineRenderer outline={outline} />) : (...empty state...)}
  </div>
</div>
```

`.research-trace`, `.outline*`, and the banners stay as-is.

## Existing utilities reused

- `.card` from `frontend/src/styles/globals.css:69`
- AppSettings field pattern (`AppSettings.css:80-127`) — referenced for the visual target
- `<ViewHeader>`, `<Select>`, `<Button>`, `<LoadingSpinner>` primitives from `frontend/src/components/common/`
- Theme tokens (`--surf-0/1/2`, `--on-surf-*`, `--brand*`, `--border-subtle`, `--h-control`, `--s-*`, `--r-*`, `--fs-*`) from `frontend/src/styles/theme.css`

## Verification

- `docker exec ollama_frontend npx tsc --noEmit` — clean (class names are strings, no TS impact)
- `docker exec ollama_frontend npm run lint` — zero warnings
- `docker exec ollama_frontend npm test -- --run` — 42/42 green (tests query by role/label, not class)
- Manual:
  1. `/courses/new` — four named cards (RAG Source / Topic & Audience / Course Length / Optional Notes) on the page canvas, left-aligned at 800px, with white-ish card surfaces and canvas-coloured inputs
  2. Inputs show a brand-coloured focus ring on focus
  3. `/courses` list — left-aligned at 800px, course cards as before
  4. `/courses/:id` detail — left-aligned at 800px, research trace + outline render against the canvas
  5. Toggle light/dark mode — surfaces invert correctly; in light mode cards are white, canvas is off-white

## Out of scope

- Restyling the `OutlineRenderer` internals (its own card-like blocks already use `--surf-1`)
- Changing the status/Bloom badge colour palette
- Re-bucketing which fields go in which section beyond the four-group split chosen above
- Light-mode tuning beyond what the existing theme tokens give us

## Commit

Single commit at the end:

`style(courses): match AppSettings layout — cards, 800px, left-aligned`
