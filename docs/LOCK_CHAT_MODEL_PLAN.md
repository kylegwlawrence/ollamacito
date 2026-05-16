# Plan: Lock chat model after creation

## Context

Today a chat's model can be changed at any time:
- **Chat card** (`ChatItem`): the model name is a button; clicking replaces the card content with a `<Select>`. This is the wide-click-target bug that prompted the user's original report.
- **Chat view header** (`ChatContainer`): a `<Select>` in the header lets you switch the chat's model mid-conversation.

The user wants this capability removed entirely — once a chat is created, its model is fixed. The model is still shown (read-only) in both places so users know which model the chat is running. Removal is enforced in the backend as well: `PATCH /chats/:id` with `model` returns 422 instead of silently dropping the field.

Out of scope: the **"Select model for new chats"** Select at the top of the project's Chats section, and the user's default model in Settings — both choose the model *at chat creation time*, so they remain.

## Critical files

**Frontend**
- `frontend/src/components/sidebar/ChatItem.tsx` + `ChatItem.css`
- `frontend/src/components/sidebar/Sidebar.tsx`
- `frontend/src/components/projects/ProjectDetail.tsx`
- `frontend/src/components/chat/ChatContainer.tsx` + `ChatContainer.css`
- `frontend/src/hooks/useChats.ts`
- `frontend/src/types/chat.ts`

**Backend**
- `backend/app/schemas/chat.py`
- `backend/app/api/v1/endpoints/chats.py`
- `backend/tests/test_api/test_chats.py`

## Implementation

### Phase 1 — Frontend: remove model-change UI, show read-only label

Done first so no UI is left calling an API the backend has just rejected.

**`frontend/src/types/chat.ts`** — remove `model?: string` from `ChatUpdate`.

**`frontend/src/hooks/useChats.ts`** — change `updateChat(chatId, updates: { title?: string; model?: string })` to `updates: { title?: string }`.

**`frontend/src/components/sidebar/ChatItem.tsx`** — substantial trim:
- Remove `onChangeModel` from props and call sites.
- Remove `isSelectingModel` state and `handleModelChange`.
- Remove `useModels`, `modelOptions`, `Select` imports.
- Drop the `isSelectingModel ? <Select…/> : …` branch — leaves just the title + footer branch (and the existing `isEditing` branch for renaming).
- Replace the model `<button className="chat-item__model-btn">` with `<span className="chat-item__model" title={chat.model}>{chat.model}</span>` (read-only label).
- Simplify the card's `onClick` and `onKeyDown` — drop the `!isSelectingModel` guards.
- Update `aria-label` (drop the "Change model" affordance hint).

**`frontend/src/components/sidebar/ChatItem.css`**:
- Replace `.chat-item__model-btn` with `.chat-item__model`: keep the typography (`--fs-caption`, `Roboto Mono`, `--on-surf-dim`, ellipsis), drop `flex: 1`, `text-align: left`, `cursor: pointer`, the `:hover` color transition, and `background: none; border: none`.
- Delete `.chat-item__model-select` — no longer rendered.

**`frontend/src/components/sidebar/Sidebar.tsx`**:
- Remove the `handleChangeModel` definition.
- Remove the `onChangeModel={handleChangeModel}` prop from the `<ChatItem>` JSX.

**`frontend/src/components/projects/ProjectDetail.tsx`**:
- Remove the `handleChangeModel` definition.
- Remove the `onChangeModel={handleChangeModel}` prop from the `<ChatItem>` JSX.

**`frontend/src/components/chat/ChatContainer.tsx`**:
- Remove the `Select` import and the `useModels` import — they're only used for the model picker.
- Remove the `const { models } = useModels()` call and the `modelOptions` line.
- Remove `handleChangeModel`.
- Replace the `<Select … />` with `<span className="chat-container__model-label" title={currentChat.model}>{currentChat.model}</span>`.

**`frontend/src/components/chat/ChatContainer.css`** — append a new rule:
```css
.chat-container__model-label {
  font-size: var(--fs-body-sm);
  color: var(--on-surf-2);
  font-family: 'Roboto Mono', monospace;
  white-space: nowrap;
  padding: 0 var(--s-2);
}
```

**Commit**:
```
refactor(chat): lock chat model after creation; show as read-only label
```

### Phase 2 — Backend: reject `model` in chat update

**`backend/app/schemas/chat.py`** — in `ChatUpdate`:
- Remove the `model: Optional[str] = Field(...)` line.
- Add `model_config = {"extra": "forbid"}` so any PATCH still supplying `model` (or any unknown key) returns 422.

**`backend/app/api/v1/endpoints/chats.py`** — in `update_chat()`, remove the two-line `model` branch:
```python
if chat_data.model is not None:
    chat.model = chat_data.model
```

**`backend/tests/test_api/test_chats.py`** — rewrite the existing test:
- Rename `test_update_chat_changes_title_and_model` → `test_update_chat_changes_title`.
- PATCH only `{"title": "new"}`; assert `patched["title"] == "new"` and `patched["model"] == "old:1b"`.
- Add a sibling test `test_update_chat_rejects_model_change`: create with `model: "old:1b"`, PATCH `{"model": "new:7b"}`, assert 422 and a follow-up GET still shows `"old:1b"`.

**Commit**:
```
refactor(api): forbid model changes on PATCH /chats/:id
```

## Verification

**Phase 1 (frontend):**
- `make dev` — Vite hot-reloads. Open a project with multiple chats.
- Chat card: model name visible in footer as plain text. Clicking it does nothing — only the title row, empty footer space, and edit/delete icons are interactive. Click anywhere in the card → opens the chat.
- Chat view header: model name visible as a small Roboto-Mono label next to the agent toggle. Not clickable.
- Edit (rename) and delete flows on chat cards still work.
- Agent toggle in the chat header still works.
- Creating a new chat from the project's "New chat" button still uses the project-level model selector.
- `docker exec ollama_frontend npm test` — passes.
- `make lint` (frontend leg) — passes.

**Phase 2 (backend):**
- `make test` — `test_update_chat_changes_title` passes; new `test_update_chat_rejects_model_change` passes (422).
- Manual: `curl -X PATCH http://localhost:8000/api/v1/chats/<id> -H 'Content-Type: application/json' -d '{"model": "x"}'` → 422.
- Manual: same `curl` with `{"title": "x"}` → 200.
- `make lint` (backend leg, ruff) — passes.

## Notes on safety

- The `chats.model` column is **not** touched — it's still required at create-time via `ChatBase.model`, and existing chats keep their model.
- `useModels` still loads the model list for the new-chat selectors — only the call sites inside `ChatContainer`/`ChatItem` go away.
- `extra="forbid"` on `ChatUpdate` will also reject any other unknown keys the frontend might send. The frontend currently only sends `title`, `is_archived`, `agent_mode_enabled` — all explicit fields — so this is safe.
