# Frontend Visual Refactor — Gmail/Drive-flavored Google UI

## Context

The current Ollama GUI feels large and clunky:
- 300 px sidebar with quirky Trebuchet MS title, 2.5 rem main padding, native `<select>` everywhere
- Heavy borders, tall message bubbles (~28 px min), muted `#87ce87` accent
- Plain system fonts, no icon system, ad-hoc CSS variables that don't form a system

We're refactoring to a modern Google-product feel (Gmail/Drive flavor) with a coherent dark design system. The Ollama::cito logo image (`/green_logo_3.png`) is kept untouched; only its surrounding type and chrome change.

**Locked decisions (already discussed with user):**
1. Gmail/Drive feel — dense list rows, card-based content, contextual per-view headers (no app-wide top bar)
2. Compact 260 px text sidebar, sectioned (Actions / Projects / Chats / Settings-at-bottom)
3. Bubbles kept but softened — tighter padding, 20 px radius, no border on assistant, subtle elevation; user pill on right
4. Floating pill composer at the bottom of the chat view
5. Brand-green palette modernized: `#6FD18A` brand / `#5BB874` hover / `#1F2A22` tint, surface tiers 0-3, `rgba(255,255,255,0.08)` borders. Dark theme only (light theme stays out of scope per CLAUDE.md).
6. **Roboto Flex** + **Roboto Mono** + **Material Symbols Outlined** via Google Fonts (Google Sans itself isn't publicly licensed — Roboto Flex is its open VF sibling, visually equivalent)

---

## Phase 1 — Design system foundation

Goal: tokens, fonts, icons, base primitives. The app should already look noticeably greener/cleaner after this phase with the old layout intact.

**Modify** `frontend/index.html` — `preconnect` to `fonts.googleapis.com` + `fonts.gstatic.com` (crossorigin), `<link>` Roboto Flex (`opsz,wght@8..144,300..700`), Roboto Mono (`400;500`), Material Symbols Outlined (`opsz,wght,FILL,GRAD@24,400,0,0`).

**Rewrite** `frontend/src/styles/theme.css` — drop legacy tokens (`--bg-primary`, `--accent-color`, `--text-inverse`, `--accent-light`, `--user-message-*`, `--assistant-message-*`). Introduce the token system in the "Design tokens" section below. Retune scrollbar to `--surf-1` track + `--border-strong` thumb.

**Modify** `frontend/src/styles/globals.css` — body uses `'Roboto Flex', system-ui, sans-serif` with `font-variation-settings: 'opsz' 14, 'wght' 400`; code/pre use `'Roboto Mono', ui-monospace`. **Remove** the global `* { transition: ... }` rule — it animates every state change globally; replace with explicit per-component transitions. Keep the `.no-transition` escape hatch and `.sr-only`.

**Modify** `frontend/src/styles/reset.css` — add `font-feature-settings: 'cv11', 'ss01';` to `html` so Roboto Flex picks better defaults.

**New** `frontend/src/components/common/Icon.tsx` (+ `.css`):
- Renders `<span class="material-symbols-outlined">{name}</span>`
- Props: `name: string`, `size?: 16|18|20|24` (default 20), `filled?: boolean`, `title?: string`, `className?: string`
- CSS sets `font-variation-settings: 'FILL' var(--fill,0), 'wght' 400, 'GRAD' 0, 'opsz' var(--size,20)`

**New** `frontend/src/components/common/Select.tsx` (+ `.css`):
- Custom listbox replacing every native `<select>`. Uses ARIA combobox/listbox pattern (not menu).
- Props: `value: string`, `onChange: (v: string) => void`, `options: { value: string; label: ReactNode; meta?: string }[]`, `placeholder?: string`, `disabled?: boolean`, `id?: string`, `aria-label?: string`
- Keyboard: Space/Enter to open, Esc to close, Up/Down navigate, Home/End, type-ahead within 700 ms idle, Tab commits and leaves. Click-outside via document mousedown listener.
- Trigger: 32 px surf-2 pill with caret. Popup: `position: fixed`, JS-positioned anchor (to escape any parent `overflow: hidden`), max-height 320 px, scrollable, surf-2 menu items.
- Add `Select.test.tsx` exercising keyboard nav + type-ahead.

**Modify** `frontend/src/components/common/Button.tsx` + `Button.css`:
- Keep public API; add `iconOnly?: boolean`, `leadingIcon?: string`, `trailingIcon?: string` (Material Symbols names).
- Pill geometry: `border-radius: 999px` for primary/secondary, `8px` for ghost. Heights `28 / 36 / 44`.
- Primary: `--brand` bg + `--on-brand` text. Secondary: `--surf-2` bg + `--on-surf-1` text + 1 px `--border-subtle`. Danger variant uses `--danger`.
- `:focus-visible` ring `0 0 0 2px var(--brand-tint)`. Explicit transitions only (`background-color`, `color`, `box-shadow`) at `--dur-fast`.

**Verify**: `make dev`. App looks visibly modernized (fonts, colors) but layout unchanged. DevTools Network: Roboto fonts + Material Symbols load. No console errors. Run `docker exec ollama_frontend npm test` — Button + Select tests pass.

---

## Phase 2 — App shell, sidebar, ViewHeader

Goal: 260 px sectioned sidebar + reusable contextual header. Old chat view continues to function with its old header until Phase 3.

**Modify** `frontend/src/App.css` — drop `2.5rem` padding from `.app__main` (each view owns padding); set background to `--surf-0`. Confirm `.app` flex container stays.

**Modify** `frontend/src/router.tsx` — no structural changes. RootLayout, ToastContainer, ConfirmDialog mounts stay.

**Restructure JSX (preserve all hooks/handlers)** `frontend/src/components/sidebar/Sidebar.tsx` + `Sidebar.css`:
- **Untouched**: every hook call, `handleNewChat`, `handleCreateProject`, `handleDeleteProject`, `handleRename`, `handleChangeModel`, `handleDelete`, `handleSelectChat`, `projectsExpanded`/`chatsExpanded` state, the `useEffect`s on `loadChats` (40-42) and `settings.default_model` (44-46), `standaloneChats` filter (133), `currentProjectId` derivation (33-34).
- **New layout (top→bottom)**: `.sidebar__brand` row (28 px `<img>` logo + "Ollama::cito" wordmark in Roboto Flex 18 px wght 500) → `.sidebar__actions` (two pill buttons: `Icon edit_square` "New chat", `Icon create_new_folder` "New project") → `.sidebar__group` "Projects" (caption-size header, `Icon expand_more` chevron rotated by `aria-expanded`) → `.sidebar__group` "Chats" → `flex:1` spacer → `.sidebar__footer` containing `<Select>` model picker (replaces native at 162-174) + ghost `Icon settings` button linking to `/settings`.
- **CSS**: width 300→260, bg `--surf-1`, border-right 1 px `--border-subtle`. Group headers 11 px uppercase letter-spacing 0.06em color `--on-surf-2`.

**Modify** `frontend/src/components/sidebar/ChatItem.tsx` + `.css`:
- Replace `✎`/`×` text glyphs with `<Icon name="edit"/>` and `<Icon name="delete"/>` inside `.icon-btn` (visible on hover/focus only).
- Replace inline `<select>` for model with `<Select>`.
- Row geometry: 32 px tall, padding `4px 8px`, radius 8 px, no per-row border. Active state = `--brand-tint` bg + 3 px inset box-shadow accent on left.
- **Preserve**: double-click-to-rename, `isEditing`/`isSelectingModel` state, all props.

**Modify** `frontend/src/components/sidebar/ProjectItem.tsx` + `.css`:
- `📁` → `<Icon name="folder"/>`. `×` → `<Icon name="close"/>`. Chat-count becomes a pill chip (18 px, `--surf-3` bg).
- Same dense row geometry as ChatItem.

**New** `frontend/src/components/common/ViewHeader.tsx` + `.css`:
- Props: `breadcrumb?: ReactNode`, `title: ReactNode`, `actions?: ReactNode`
- 56 px tall, sticky top, `--surf-0` bg with 1 px bottom `--border-subtle`, padding `0 24px`. Title in 22 px wght 500. Breadcrumb segments separated by `Icon chevron_right`, color `--on-surf-2`, caption size.
- Used by ChatContainer (P3), ProjectDetail + AppSettings (P4).

**Verify**: Sidebar measures 260 px, brand row + logo render, sections collapse, model `<Select>` opens with arrow keys, Settings sits at bottom. Routes still navigate. Visual sweep: no leftover native `<select>` in sidebar.

---

## Phase 3 — Chat view

Goal: rewire ChatContainer header through `ViewHeader`, soften message bubbles, build the pill composer. This is the highest-risk phase because of streaming + file-attach logic — restrict changes to JSX wrappers + CSS.

**Modify** `frontend/src/components/chat/ChatContainer.tsx` + `ChatContainer.css`:
- Replace the `<header className="chat-container__header">` block (lines 158-199) with `<ViewHeader>`:
  - `breadcrumb`: when `currentChat.project_id`, render a button (`Icon arrow_back` + `chatProject?.name`) wired to the existing `navigate('/projects/' + currentChat.project_id)` call.
  - `title`: `currentChat.title` (single line, ellipsis).
  - `actions`: agent toggle (28 px pill with `Icon auto_awesome`, `aria-pressed` from `currentChat.agent_mode_enabled`, `disabled={!agentToggleAvailable || togglingAgent}`, `title={agentToggleTooltip}`) + `<Select>` for model (lets user change model from header instead of just reading it).
- **Untouched**: `useStreaming` wiring (42-44), `isStreamingThisChat` derivation, `projectHasFullRagConfig`, `togglingAgent` state, `agentToggleAvailable`, both `useEffect`s (63-71 chat reset, 81-92 file selection), `handleSend` (94-114) including agent routing, `handleToggleAgent` (116-137) including optimistic flip + rollback.
- Container CSS: full-height column, no border, bg `--surf-0`. MessageList scrolls; composer floats.

**Modify** `frontend/src/components/chat/Message.tsx` + `Message.css`:
- User bubble: pill on right, `max-width: 70%`, padding `10px 16px`, `border-radius: 20px 20px 4px 20px`, bg `--brand`, color `--on-brand`. No border. File chips inside use darker `--brand-press` tint.
- Assistant bubble: bg `--surf-1`, `border-radius: 20px 20px 20px 4px`, padding `12px 16px`, `box-shadow: var(--elev-1)`. **No border**.
- File-attachment icon mapping: `📄→description`, `📋→data_object`, `📊→table_chart`, `📎→attach_file` via `<Icon/>`.
- Sources block stays — restyled as surf-2 chip with `Icon link`.
- **Untouched**: `formatDate`, `tokens_used`, `tool_calls`, `rag_citations` rendering, all message-rewrite/copy logic.

**Modify** `frontend/src/components/chat/MessageInput.tsx` + `MessageInput.css` (CSS-heavy, careful TSX):
- **Preserve verbatim**: `handleSend` (27-32), `handleKeyDown` (34-39), `hasFiles` (41), the file-chip toggle button (59-77), the `isStreaming ? Stop : Send` branch (96-114), `aria-describedby` hint span (117-119).
- Visual: composer is a floating pill — `position: sticky; bottom: 16px; max-width: 760px; margin: 0 auto;`. Single rounded surface `border-radius: 28px`, padding `8px 8px 8px 20px`, bg `--surf-2`, `box-shadow: var(--elev-2)`. Textarea is borderless, transparent; keep `rows={3}`. Send button becomes a 40 px circular primary with `Icon arrow_upward`. Stop button: same 40 px circle, danger variant, `Icon stop`.
- File picker: render above the pill in a small row when `hasFiles`. Replace `✓`/`+` text with `Icon check`/`Icon add`. Caption label at 11 px.

**Modify** `frontend/src/components/chat/ToolCalls.tsx` + `ToolCalls.css`:
- Replace `▾`/`▸` with `<Icon expand_more/>` rotated by `aria-expanded`.
- Each item: 28 px row, status chip on right (`Icon check_circle` green / `Icon error` red / spinning `Icon hourglass_empty` pending).
- **Untouched**: `pending`/`ok`/`err` status derivation, `friendlyToolName`, `summarizeInput`.

**Modify** `frontend/src/components/chat/MessageList.css` only — padding `24px 24px 96px` (bottom inset clears the floating composer).

**Verify**: open an existing chat. Header shows breadcrumb → title, agent toggle + model `<Select>` on right. User messages right-pilled; assistant flat soft cards. Composer floats at bottom; Enter sends, Shift+Enter newlines; Stop appears mid-stream and aborts via existing `streaming.cancelStream`. File-chip toggle still flips `selectedFileIds`. Agent toggle still does optimistic flip + rollback.

---

## Phase 4 — Project, Settings, Files views

Goal: card-based layouts for the two form-heavy views and the file lists. Less trafficked, so we can take more liberty after primitives are validated.

**Modify** `frontend/src/components/projects/ProjectDetail.tsx` + `.css`:
- Replace `project-detail__header` with `<ViewHeader>`:
  - breadcrumb: `Icon home` → "Projects"
  - title: project name (22 px) + chat-count chip beside it
  - actions: `<Button variant="primary" leadingIcon="add">New chat</Button>` + `<Select>` for new-chat model + ghost `Icon settings` toggling `settingsExpanded`
- Wrap "Project Settings", "Chats", "Files", "Memory" in `.card` blocks (utility class: bg `--surf-1`, padding 16, radius 12, 1 px `--border-subtle`).
- Replace `<select>` for `default-model-edit` and `rag-corpus` with `<Select>`.
- Replace `▼ Project Settings` collapse with `<button>` containing `Icon tune` + label + `Icon expand_more`.
- Custom `.switch` (36×20 px pill toggle) for `auto_attach_all_files` and `rag_enabled` — keep all controlled-state logic.
- Form inputs: 36 px height, 8 px radius, bg `--surf-0`, focus border `--brand`. Hints in caption size, `--on-surf-2`.
- **Untouched**: `useEffect` initializing `selectedModel` from `currentProject?.default_model || settings.default_model`, `hasSettingsChanges` derivation, `handleTestRagConnection`, `handleSaveSettings`/`handleCancelSettings`.

**Modify** `frontend/src/components/settings/AppSettings.tsx` + `.css`:
- Replace `app-settings__header` with `<ViewHeader>` (breadcrumb home → "Settings"; title "Application Settings"; actions: sticky Save/Cancel).
- Wrap Model Configuration / Generation Parameters / About in `.card` blocks.
- Both `<select>` (`default-model`, `summarization-model`) → `<Select>`.
- **Untouched**: `handleSave`, `handleCancel`, `handleBack` including the discard-changes confirm prompt.

**Modify** `frontend/src/components/files/FileList.tsx` + `FileUpload.tsx` + their `.css`:
- Emoji icons in `getFileIcon` → `Icon` mapping (`description`/`data_object`/`table_chart`/`attach_file`).
- File rows: 48 px tall, dense, no per-row border; 1 px `--border-subtle` divider between siblings inside the parent card. Preview pre uses `--surf-0` bg.
- FileUpload trigger: secondary button with `leadingIcon="upload"`. Drag-over state uses `--brand-tint` bg.

**Verify**: walk `/projects/:id` and `/settings`. Save/Cancel enable only when changes exist. RAG "Test connection" still toasts. File upload accepts `.txt/.json/.csv/.md`, rejects 5 MB+, shows preview.

---

## Phase 5 — Modal + toast polish

Goal: M3-flavored modal + Gmail-style snackbar.

**Modify** `frontend/src/components/common/ConfirmDialog.tsx` + `.css`:
- **Untouched**: focus-on-confirm-button, Escape/Enter handlers, `resolveWith`, backdrop click closes.
- Backdrop: `rgba(0,0,0,0.5)` with `backdrop-filter: blur(2px)`. Surface: `--surf-2` card, 24 px padding, 28 px radius, max-width 360 px, `box-shadow: var(--elev-3)`. Title 18 px wght 500.
- Actions row right-aligned, gap 8, ghost Cancel + primary Confirm (danger variant when `variant === 'danger'`).
- Enter/exit `opacity` + `scale(0.96 → 1)` 150 ms.

**Modify** `frontend/src/components/common/ToastContainer.tsx` + `.css`:
- **Untouched**: store wiring, autoclose, role/aria-live.
- Position bottom-left at 24 px, 8 px stack gap. Each toast: 40 px pill, `--surf-3` bg, 24 px radius, `--elev-2` shadow, padding `0 16px`. Icons via `Icon` (`check_circle`/`error`/`warning`/`info`). Close `×` → `Icon close`.
- Slide-in `translateY(8px) → 0` + fade 200 ms.

**Verify**: trigger delete-chat (modal), create chat (success toast), upload too-large file (error toast). Modal Esc cancels, Enter confirms, focus correct.

---

## Design tokens (added in P1)

In `:root`:

```
/* Surfaces */
--surf-0: #15171C;  /* app canvas */
--surf-1: #1B1E25;  /* sidebar, cards, assistant bubble */
--surf-2: #232732;  /* composer, modal, popovers, select */
--surf-3: #2C313D;  /* hover/elevated chip */

/* Brand */
--brand:        #6FD18A;
--brand-hover:  #5BB874;
--brand-press:  #4FA365;
--brand-tint:   #1F2A22;  /* tinted container, active row */
--on-brand:     #0E1A0F;

/* Text on surfaces */
--on-surf-0:   #E6EAF2;  /* primary */
--on-surf-1:   #C2C7D2;  /* secondary */
--on-surf-2:   #8B92A0;  /* tertiary, captions */
--on-surf-dim: #6B7180;  /* disabled */

/* Status */
--success: #6FD18A;  /* same as brand */
--warning: #E6B566;
--danger:  #F2786F;
--danger-tint: #2A1B1A;

/* Borders */
--border-subtle: rgba(255,255,255,0.08);
--border-strong: rgba(255,255,255,0.14);

/* Elevation */
--elev-1: 0 1px 2px rgba(0,0,0,0.35);
--elev-2: 0 4px 12px rgba(0,0,0,0.40);
--elev-3: 0 16px 32px rgba(0,0,0,0.50);

/* Radii */
--r-xs: 4px;  --r-sm: 8px;  --r-md: 12px;
--r-lg: 20px;  --r-xl: 28px;  --r-pill: 999px;

/* Spacing (4px grid) */
--s-1: 4px; --s-2: 8px; --s-3: 12px; --s-4: 16px;
--s-5: 20px; --s-6: 24px; --s-8: 32px; --s-10: 40px;

/* Font sizes */
--fs-caption: 11px;  --fs-body-sm: 13px;  --fs-body: 14px;
--fs-title: 18px;  --fs-headline: 22px;

/* Font weights */
--fw-regular: 400;  --fw-medium: 500;  --fw-semibold: 600;

/* Durations */
--dur-fast: 120ms;  --dur-base: 180ms;  --dur-slow: 240ms;
--ease-std: cubic-bezier(0.2, 0, 0, 1);

/* Component heights */
--h-control-sm: 28px;  --h-control: 36px;  --h-control-lg: 44px;
```

---

## Critical files

**New**
- `frontend/src/components/common/Icon.tsx` + `Icon.css`
- `frontend/src/components/common/Select.tsx` + `Select.css` + `Select.test.tsx`
- `frontend/src/components/common/ViewHeader.tsx` + `ViewHeader.css`

**Modified**
- `frontend/index.html` (font + icon links)
- `frontend/src/styles/theme.css` (rewrite tokens)
- `frontend/src/styles/globals.css` (fonts, remove global transition)
- `frontend/src/styles/reset.css` (font-feature-settings)
- `frontend/src/App.css`
- `frontend/src/components/common/Button.tsx` + `Button.css`
- `frontend/src/components/sidebar/Sidebar.tsx` + `Sidebar.css`
- `frontend/src/components/sidebar/ChatItem.tsx` + `ChatItem.css`
- `frontend/src/components/sidebar/ProjectItem.tsx` + `ProjectItem.css`
- `frontend/src/components/chat/ChatContainer.tsx` + `ChatContainer.css`
- `frontend/src/components/chat/Message.tsx` + `Message.css`
- `frontend/src/components/chat/MessageInput.tsx` + `MessageInput.css`
- `frontend/src/components/chat/MessageList.css`
- `frontend/src/components/chat/ToolCalls.tsx` + `ToolCalls.css`
- `frontend/src/components/projects/ProjectDetail.tsx` + `ProjectDetail.css`
- `frontend/src/components/settings/AppSettings.tsx` + `AppSettings.css`
- `frontend/src/components/files/FileList.tsx` + `FileList.css`
- `frontend/src/components/files/FileUpload.tsx` + `FileUpload.css`
- `frontend/src/components/common/ConfirmDialog.tsx` + `ConfirmDialog.css`
- `frontend/src/components/common/ToastContainer.tsx` + `ToastContainer.css`

**Reuse (do not touch)**
- `frontend/src/hooks/useStreaming.ts`, `useChats.ts`, `useModels.ts`
- `frontend/src/stores/*` (chatStore, projectsStore, settingsStore, toastStore, confirmStore, streamingStore)
- `frontend/src/services/*`
- All backend code

---

## Risks and tradeoffs

- **Font latency / FOUT**: First paint may flash system fallback before Roboto Flex loads. `preconnect` + `font-display: swap` (default) keeps text legible. If FOUC becomes noticeable, follow-up by self-hosting Roboto Flex VF (one ~250 KB file) — not blocking.
- **Honest font fallback**: Google Sans isn't licensed for public web use. We use Roboto Flex (variable, same designer family) and match `opsz`/`wght` axes. Note this in the commit message and update CLAUDE.md's `Layout` section.
- **Custom `Select` a11y**: Combobox/listbox ARIA, not menu. Test Tab/Esc/Arrows/Home/End/type-ahead in `Select.test.tsx`. Avoid clipping inside `overflow: hidden` parents by using `position: fixed` placement.
- **MessageInput regression risk**: send/keypress/file-chip/stop logic is sensitive. Preserve lines 27-32 (`handleSend`), 34-39 (`handleKeyDown`), 41 (`hasFiles`), 59-77 (chip button), 96-114 (Send/Stop branch) verbatim. Only JSX wrappers + classes change.
- **ChatContainer header rework**: must preserve all three behaviors — back-to-project nav (161-168), `chatProject?.name` rendering (170-172), agent toggle with `aria-pressed`/tooltip/disabled state (176-189). All three move into `<ViewHeader>` slots without behavior change.
- **Stripped global transition**: removing `* { transition: ... }` makes some hover states feel snappier but exposes any state that relied on implicit border-color animation. Add explicit `transition: border-color var(--dur-fast)` to inputs and buttons in their own CSS files.
- **Sidebar overflow**: `<Select>` popup must not be clipped by `nav.sidebar { overflow: hidden }`. Use fixed-position popover.

---

## Verification (end-to-end after all phases)

1. `make dev` — both containers up; browser to `http://localhost:5173`.
2. **Sidebar**: 260 px wide, brand row + logo, sections collapse with chevron rotation, model `<Select>` keyboard-navigable, Settings at bottom.
3. **Routing**: `/`, `/chats/:id`, `/projects/:id`, `/settings` render with `<ViewHeader>` and correct breadcrumbs. Browser back/forward works.
4. **Dark only**: `<html data-theme="dark">`. `grep -r "prefers-color-scheme" frontend/src` returns nothing.
5. **Fonts/icons**: DevTools Network filter `fonts.gstatic` → Roboto Flex + Roboto Mono + Material Symbols load (< 350 KB total). No `?` glyphs anywhere (Material Symbols renders `?` for misspelled icon names — sweep visually).
6. **Chat flow**: create chat → type → Enter sends → response streams → Stop aborts → toggle agent (when RAG configured) → attach project file → tool-calls section expands.
7. **Project flow**: create project → expand settings → toggle RAG + Test connection → save → upload file → preview → delete via modal.
8. **Settings flow**: change default model → Save → toast → reload → setting persisted.
9. **Modal/toast**: ConfirmDialog Esc cancels, Enter confirms, focus on confirm button; toasts in bottom-left with correct icons.
10. **Tests**: `make test` (backend) + `docker exec ollama_frontend npm test` (frontend) pass. `make lint` clean.
11. **Smoke**: open with existing data — no 404s, no console errors, no missing icons.

---

## Optional follow-ups (out of scope but worth noting)

- Self-host Roboto Flex VF if FOUT is objectionable
- Code-block syntax highlighting (already listed as out-of-scope in CLAUDE.md — keep deferred)
- Density toggle (Gmail-style "comfortable / cozy / compact") — not requested
- Light theme — explicitly out of scope per CLAUDE.md
