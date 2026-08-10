# Frontend Skill

Load this file when working on: the React app, chat UI, document management UI,
citation viewer, streaming, or the Vite build.

## React architecture (feature-based)

```
apps/web/src/
├── components/          # shared, reusable UI primitives
├── features/
│   ├── chat/            # conversation, message list, input, streaming
│   ├── documents/       # upload, list, status, metadata, reindex, delete
│   ├── citations/       # citation viewer, source passage display
│   └── auth/            # login, session management
├── hooks/               # shared custom hooks (useHealth, useAuth, ...)
├── services/            # API call functions (no business logic in components)
├── stores/              # Zustand stores — only for genuine UI-only state
└── types/               # TypeScript type definitions
```

Keep business logic out of presentation components.
Use **TanStack Query** for all server state.
Use **Zustand** only for UI state that genuinely can't live in server state.

## Chat UI requirements

- Conversation history (scrollable)
- **Streaming** responses (SSE)
- Markdown rendering
- Interactive citations — clicking `[1]` opens the citation viewer
- Source preview panel
- **Loading state** — spinner while waiting
- **Error state** — structured error message, not a blank screen
- **Abstention state** — "I don't have enough evidence" must look intentional,
  not like a bug; design it as a first-class state

Example rendered response:
```
The policy specifies a 30-day settlement period.[1]

Sources:
[1] Policy-2026.pdf §8.2 p.12
```

## Document management UI requirements

Users should be able to:
- Upload documents (PDF, DOCX, HTML, TXT)
- See processing status: `uploading → processing → ready | failed`
- Inspect metadata: jurisdiction, allowed roles, version, filename
- Reindex a document
- Delete a document

Don't show a document as `ready` until indexing has actually succeeded —
a premature "ready" state undermines the evidence guarantees the system is built on.

## Citation viewer

Shows: document name, page, section, source passage (highlighted), jurisdiction,
document version. Never shows content the requesting user isn't authorized to see —
re-check authorization server-side at render time.

## Streaming (SSE)

Use Server-Sent Events (or equivalent) for chat streaming.
Stream only safe response content — never system prompts, hidden chain-of-thought,
secrets, or unauthorized retrieved content, even partially.

## Error handling

All API errors return structured codes:
```json
{
  "error": {
    "code": "RETRIEVAL_FAILED",
    "message": "Unable to retrieve supporting evidence."
  }
}
```

The UI must handle these codes explicitly, not display raw HTTP error text.
Internal technical detail stays in server logs only.

## API service layer

All network calls go through `src/services/`. Components never call `fetch` directly.

```typescript
// src/services/api.ts
export async function healthCheck(): Promise<HealthResponse> { ... }
export async function sendMessage(payload: ChatPayload): Promise<void> { ... }
export async function uploadDocument(file: File, meta: DocMeta): Promise<DocResponse> { ... }
```

## Environment configuration

```
VITE_API_BASE_URL=http://localhost:8000
```

Never hard-code API URLs in component code.
