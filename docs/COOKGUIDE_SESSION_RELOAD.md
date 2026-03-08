# Cookbook: Install & Test Session Reload

## What This Feature Does

When a user refreshes the page or returns later, the chat widget automatically restores their last conversation. Messages are persisted to SQLite and conversation history is fed into the LangGraph multi-agent pipeline so the LLM has full multi-turn context.

---

## 1. Install

### Prerequisites
- Python 3.8+
- Node.js 16+
- OpenAI API key

### Quick Start

```bash
cd guard-demo-client

# Backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend
npm install

# Run everything
python start_all.py
```

Or run backend and frontend manually in two terminals:

```bash
# Terminal 1
source venv/bin/activate
python start_backend.py

# Terminal 2
npm run dev
```

### Database Migration

No manual migration is needed. SQLAlchemy's `create_all()` automatically creates the new `chat_sessions` and `chat_messages` tables on startup. Existing databases are unaffected — the new tables are simply added alongside existing ones.

---

## 2. Test

### Test A — Session Persistence (Basic)

1. Open http://localhost:3000
2. Click the chat bubble to expand the chat widget
3. Send a message (e.g., "Hello, what can you help me with?")
4. Wait for the assistant response
5. **Refresh the page** (F5 / Cmd+R)
6. Click the chat bubble again

**Expected**: Your previous messages (both user and assistant) are restored in the chat window.

### Test B — Multi-Turn Context via LangGraph

1. Open http://localhost:3000
2. Send: `"My name is Alice and I work at Acme Corp."`
3. Wait for the response
4. **Refresh the page**
5. After messages reload, send: `"What's my name and where do I work?"`

**Expected**: The assistant correctly recalls "Alice" and "Acme Corp" because conversation history is loaded from the DB and injected into the LangGraph agent pipeline.

### Test C — Session ID in localStorage

1. Open browser DevTools → Application → Local Storage → http://localhost:3000
2. Send a chat message
3. Check that `guard_demo_session_id` appears with a UUID value
4. Refresh the page — the key persists and the same session is reloaded

### Test D — New Session After Clearing Storage

1. In DevTools → Application → Local Storage, delete the `guard_demo_session_id` key
2. Refresh the page
3. The widget falls back to loading the most recent session from the server (`GET /api/sessions/last`)
4. Send a new message without any stored session — a brand-new session is created

### Test E — API Verification

You can verify the backend directly with curl:

```bash
# Send a message (creates a new session)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!"}'

# Response includes session_id:
# {"response": "...", "session_id": "abc-123-...", ...}

# Retrieve the last session
curl http://localhost:8000/api/sessions/last

# Retrieve a specific session by ID
curl http://localhost:8000/api/sessions/<session_id>
```

### Test F — Verify LangGraph Integration

1. Send a message that triggers the RAG agent (e.g., ask about uploaded documents)
2. Then send a follow-up referencing the previous answer
3. Confirm the agent uses context from the prior turn

Repeat for tool agent and general agent routes to verify all four agents receive conversation history.

---

## 3. Architecture Overview

```
Browser (ChatWidget)
  │
  │  On mount: GET /api/sessions/last (or /api/sessions/{id})
  │  ← restores messages to UI + stores session_id in localStorage
  │
  │  On send: POST /api/chat { message, session_id }
  │  ← receives response + session_id
  │
Backend (FastAPI)
  │
  ├─ /api/chat
  │    1. Resolve or create ChatSession
  │    2. Load ChatMessageRecord[] → conversation_history
  │    3. Invoke LangGraph agent_graph with conversation_history in state
  │    4. Save user + assistant messages to chat_messages table
  │
  ├─ /api/sessions/last   → most recent session + messages
  └─ /api/sessions/{id}   → specific session + messages

LangGraph Pipeline
  │
  input_guard → router → [rag|tool|pii|general] → output_guard
                              │
                    Each agent receives conversation_history
                    and injects it into OpenAI messages list
```

## 4. New Database Tables

| Table | Key Columns |
|-------|------------|
| `chat_sessions` | `id`, `session_id` (unique), `created_at`, `updated_at` |
| `chat_messages` | `id`, `session_id` (FK), `role`, `content`, `tool_traces`, `lakera`, `graph_trace`, `created_at` |

## 5. Files Changed

| File | What |
|------|------|
| `backend/models.py` | `ChatSession` + `ChatMessageRecord` models |
| `backend/schemas.py` | `SessionMessageResponse`, `SessionResponse` schemas |
| `backend/main.py` | Chat endpoint saves messages; new session endpoints |
| `backend/agent.py` | Loads conversation history from DB before graph invocation |
| `backend/graph.py` | `conversation_history` in `GraphState`; passed to all agent nodes |
| `backend/agents/general_agent.py` | Accepts + uses `conversation_history` |
| `backend/agents/rag_agent.py` | Accepts + uses `conversation_history` |
| `backend/agents/pii_agent.py` | Accepts + uses `conversation_history` |
| `backend/agents/tool_agent.py` | Accepts + uses `conversation_history` |
| `src/types/index.ts` | `SessionData`, `SessionMessage` types |
| `src/services/api.ts` | `getLastSession()`, `getSession()` methods |
| `src/components/ChatWidget.tsx` | Session reload on mount, session_id persistence |
