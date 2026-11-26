# System Architecture - SaaS RAG Chatbot Backend

---

## 🏗️ HIGH-LEVEL ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │   React      │  │   External   │  │   Mobile Apps            │  │
│  │   Frontend   │  │   Websites   │  │   (Future)               │  │
│  │   (Admin)    │  │   (Widget)   │  │                          │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘  │
└─────────┼──────────────────┼──────────────────────┼──────────────────┘
          │                  │                      │
          │ HTTPS            │ HTTPS (CORS)         │ HTTPS
          ▼                  ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      API GATEWAY / LOAD BALANCER                    │
│                    (Rate Limiting, SSL Termination)                 │
└─────────────────────────────────────────────────────────────────────┘
          │                  │                      │
          ▼                  ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FASTAPI APPLICATION                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                     MIDDLEWARE LAYER                         │  │
│  │  • CORS Middleware                                           │  │
│  │  • Tenant Isolation Middleware                               │  │
│  │  • Rate Limiting Middleware                                  │  │
│  │  • Authentication Middleware (JWT)                           │  │
│  │  • Logging Middleware                                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│  ┌───────────────────────────▼──────────────────────────────────┐  │
│  │                      API ROUTES (v1)                         │  │
│  │  /auth  /bots  /knowledge  /chat  /analytics  /admin        │  │
│  └───────────────────────────┬──────────────────────────────────┘  │
│                              │                                      │
│  ┌───────────────────────────▼──────────────────────────────────┐  │
│  │                     SERVICE LAYER                            │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐    │  │
│  │  │  Auth  │ │  Bot   │ │   KB   │ │  Chat  │ │Analytics│    │  │
│  │  │Service │ │Service │ │Service │ │Service │ │ Service │    │  │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘    │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐               │  │
│  │  │Embedding│ │Qdrant │ │Scraper │ │Document│               │  │
│  │  │Service │ │Service │ │Service │ │Processor│              │  │
│  │  └────────┘ └────────┘ └────────┘ └────────┘               │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
          │                  │                      │
          ▼                  ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  PostgreSQL  │  │    Qdrant    │  │   File Storage (S3)      │  │
│  │  (Relational)│  │   (Vector)   │  │   (Documents)            │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐                                │
│  │    Redis     │  │   Embedding  │                                │
│  │   (Cache)    │  │    Models    │                                │
│  └──────────────┘  └──────────────┘                                │
└─────────────────────────────────────────────────────────────────────┘
          │                  │                      │
          ▼                  ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     EXTERNAL SERVICES                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  OpenAI API  │  │  SMTP Server │  │   Stripe API             │  │
│  │    (LLM)     │  │   (Email)    │  │   (Billing)              │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
          │                  │                      │
          ▼                  ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     MONITORING & OBSERVABILITY                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │    Sentry    │  │  Prometheus  │  │   CloudWatch/Logs        │  │
│  │    (Errors)  │  │  + Grafana   │  │                          │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 REQUEST FLOW DIAGRAMS

### 1. User Registration Flow
```
┌─────────┐
│  User   │
└────┬────┘
     │
     │ POST /api/v1/auth/register
     │ { email, password, name }
     ▼
┌──────────────────┐
│  Auth Router     │
└────┬─────────────┘
     │
     │ validate_input(data)
     ▼
┌──────────────────┐
│  Auth Service    │
├──────────────────┤
│ • Check if user  │
│   already exists │
│ • Hash password  │
│ • Create user    │
│ • Generate token │
└────┬─────────────┘
     │
     │ save_to_db(user)
     ▼
┌──────────────────┐
│  PostgreSQL      │
│  users table     │
└────┬─────────────┘
     │
     │ user_created
     ▼
┌──────────────────┐
│  Email Service   │
├──────────────────┤
│ Send verification│
│ email with token │
└────┬─────────────┘
     │
     │ email_sent
     ▼
┌──────────────────┐
│  Response:       │
│  { user, token } │
└──────────────────┘
```

### 2. Document Upload & Indexing Flow
```
┌─────────┐
│  User   │
└────┬────┘
     │
     │ POST /api/v1/knowledge/documents/upload
     │ (multipart/form-data: file)
     ▼
┌──────────────────────────────────────────────────┐
│  Knowledge Base Router                           │
├──────────────────────────────────────────────────┤
│ • Validate file type (PDF, DOCX, TXT)           │
│ • Check file size (< 50MB)                      │
│ • Check user permissions                         │
│ • Check org quota                                │
└────┬─────────────────────────────────────────────┘
     │
     │ save_file(file)
     ▼
┌──────────────────────────────────────────────────┐
│  File Storage (uploaded_documents/)              │
│  Path: /{org_id}/{bot_id}/{filename}            │
└────┬─────────────────────────────────────────────┘
     │
     │ file_saved
     ▼
┌──────────────────────────────────────────────────┐
│  Document Processor Service                      │
├──────────────────────────────────────────────────┤
│ 1. Extract text (PyPDF2/python-docx)            │
│ 2. Extract metadata (pages, title, author)      │
│ 3. Chunk text (512 tokens, 50 overlap)          │
└────┬─────────────────────────────────────────────┘
     │
     │ chunks_created
     ▼
┌──────────────────────────────────────────────────┐
│  Embedding Service                               │
├──────────────────────────────────────────────────┤
│ 1. Load model (all-MiniLM-L6-v2)                │
│ 2. Batch process (32 chunks at a time)          │
│ 3. Generate 384-dim vectors                     │
└────┬─────────────────────────────────────────────┘
     │
     │ embeddings_generated
     ▼
┌──────────────────────────────────────────────────┐
│  Qdrant Service                                  │
├──────────────────────────────────────────────────┤
│ 1. Create/get collection: bot_embeddings_{id}   │
│ 2. Prepare payloads with metadata               │
│ 3. Batch insert vectors                         │
└────┬─────────────────────────────────────────────┘
     │
     │ vectors_indexed
     ▼
┌──────────────────────────────────────────────────┐
│  PostgreSQL                                      │
├──────────────────────────────────────────────────┤
│ • Update document status: 'indexed'             │
│ • Save chunk references                         │
│ • Update source metadata                        │
└────┬─────────────────────────────────────────────┘
     │
     │ indexing_complete
     ▼
┌──────────────────────────────────────────────────┐
│  Response:                                       │
│  {                                               │
│    "status": "indexed",                         │
│    "chunks_count": 47,                          │
│    "pages": 10                                  │
│  }                                               │
└──────────────────────────────────────────────────┘
```

### 3. Chat Message Flow (Hybrid Search + LLM)
```
┌─────────────┐
│Widget/Client│
└──────┬──────┘
       │
       │ POST /api/v1/chat/{bot_id}/message
       │ { message: "What is your pricing?" }
       ▼
┌──────────────────────────────────────────────────┐
│  Chat Router                                     │
├──────────────────────────────────────────────────┤
│ • Validate API key / JWT token                  │
│ • Check domain allowlist (for widget)           │
│ • Rate limit check                              │
│ • Get/create conversation                       │
└────┬─────────────────────────────────────────────┘
     │
     │ retrieve_context(message)
     ▼
┌──────────────────────────────────────────────────┐
│  Retrieval Service (Hybrid Search)               │
└────┬─────────────────────────────────────────────┘
     │
     ├─────────────────────┬────────────────────────┐
     │                     │                        │
     ▼                     ▼                        ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
│ Embedding    │  │   Qdrant     │  │   BM25           │
│ Service      │  │   Service    │  │   (PostgreSQL)   │
├──────────────┤  ├──────────────┤  ├──────────────────┤
│ Generate     │  │ Vector       │  │ Keyword          │
│ query        │→ │ similarity   │  │ search on        │
│ embedding    │  │ search       │  │ chunks           │
└──────────────┘  └──────┬───────┘  └────┬─────────────┘
                         │               │
                         ├───────────────┘
                         │
                         ▼
                  ┌──────────────────┐
                  │ RRF Fusion       │
                  │ (Reciprocal Rank)│
                  └────┬─────────────┘
                       │
                       ▼
                  ┌──────────────────┐
                  │ Metadata Filter  │
                  │ • org_id match   │
                  │ • is_active=true │
                  │ • bot_id match   │
                  └────┬─────────────┘
                       │
                       ▼
                  ┌──────────────────┐
                  │ Deduplication    │
                  │ Top 5 chunks     │
                  └────┬─────────────┘
                       │
                       │ context_chunks
                       ▼
┌──────────────────────────────────────────────────┐
│  Chat Service                                    │
├──────────────────────────────────────────────────┤
│ 1. Build prompt with context                    │
│ 2. Add conversation history (last 5 messages)   │
│ 3. Add bot settings (tone, temperature)         │
└────┬─────────────────────────────────────────────┘
     │
     │ generate_response(prompt)
     ▼
┌──────────────────────────────────────────────────┐
│  OpenAI API                                      │
├──────────────────────────────────────────────────┤
│ • Model: gpt-3.5-turbo or gpt-4                 │
│ • Stream response (SSE)                         │
│ • Track tokens used                             │
└────┬─────────────────────────────────────────────┘
     │
     │ response_generated
     ▼
┌──────────────────────────────────────────────────┐
│  PostgreSQL                                      │
├──────────────────────────────────────────────────┤
│ • Save user message                             │
│ • Save assistant response                       │
│ • Link to sources used                          │
│ • Track latency                                 │
└────┬─────────────────────────────────────────────┘
     │
     │ message_saved
     ▼
┌──────────────────────────────────────────────────┐
│  Analytics Service                               │
├──────────────────────────────────────────────────┤
│ • Track event: message_sent                     │
│ • Update conversation metrics                   │
│ • Update usage counter                          │
└────┬─────────────────────────────────────────────┘
     │
     │ response_ready
     ▼
┌──────────────────────────────────────────────────┐
│  Response (Streamed):                           │
│  {                                               │
│    "response": "Our pricing starts at...",      │
│    "sources": [                                 │
│      {                                           │
│        "content": "...",                        │
│        "source_name": "pricing.pdf",            │
│        "page": 2                                │
│      }                                           │
│    ],                                            │
│    "conversation_id": "uuid-123",               │
│    "latency_ms": 234                            │
│  }                                               │
└──────────────────────────────────────────────────┘
```

---

## 🔐 AUTHENTICATION & AUTHORIZATION FLOW

```
┌─────────────────────────────────────────────────────────────┐
│                    LOGIN REQUEST                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  POST /api/v1/auth/login                                    │
│  { email: "user@example.com", password: "pass123" }         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Auth Service                                               │
├─────────────────────────────────────────────────────────────┤
│  1. Find user by email                                      │
│  2. Verify password (bcrypt.verify)                         │
│  3. Check is_active, is_verified                           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Security Service                                           │
├─────────────────────────────────────────────────────────────┤
│  1. Generate access_token (JWT)                            │
│     • payload: { user_id, email, org_ids[] }              │
│     • expiry: 30 minutes                                   │
│  2. Generate refresh_token (JWT)                           │
│     • payload: { user_id, token_id }                      │
│     • expiry: 7 days                                       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Response:                                                  │
│  {                                                          │
│    "access_token": "eyJ0eXAi...",                          │
│    "refresh_token": "eyJ0eXAi...",                         │
│    "token_type": "bearer",                                 │
│    "user": { id, email, name, organizations[] }            │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              SUBSEQUENT AUTHENTICATED REQUEST               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  GET /api/v1/bots                                           │
│  Headers: { Authorization: "Bearer eyJ0eXAi..." }           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Authentication Middleware                                  │
├─────────────────────────────────────────────────────────────┤
│  1. Extract token from header                              │
│  2. Verify token signature                                 │
│  3. Check token expiration                                 │
│  4. Decode payload                                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Tenant Isolation Middleware                                │
├─────────────────────────────────────────────────────────────┤
│  1. Extract organization_id from context                   │
│  2. Inject into request.state.org_id                       │
│  3. Verify user membership in org                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  RBAC Permission Check                                      │
├─────────────────────────────────────────────────────────────┤
│  1. Get user role in org (owner, admin, member, viewer)    │
│  2. Check required permission (e.g., "bot:create")         │
│  3. Allow/Deny based on role permissions                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Route Handler                                              │
├─────────────────────────────────────────────────────────────┤
│  • Access request.state.current_user                       │
│  • Access request.state.org_id                             │
│  • Execute business logic                                  │
│  • All DB queries auto-scoped by org_id                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🗄️ DATABASE SCHEMA DIAGRAM

```
┌─────────────────────┐
│   Organization      │
├─────────────────────┤
│ • id (PK)          │
│ • name             │
│ • slug             │
│ • subscription_plan│
│ • is_active        │
│ • created_at       │
└──────────┬──────────┘
           │
           │ 1:N
           ▼
┌─────────────────────┐
│   Membership        │
├─────────────────────┤
│ • id (PK)          │
│ • user_id (FK)     │──┐
│ • org_id (FK)      │  │
│ • role             │  │
│ • created_at       │  │
└─────────────────────┘  │
                         │
           ┌─────────────┘
           │ N:1
           ▼
┌─────────────────────┐
│   User              │
├─────────────────────┤
│ • id (PK)          │
│ • email (unique)   │
│ • hashed_password  │
│ • full_name        │
│ • is_active        │
│ • is_verified      │
│ • is_superadmin    │
│ • created_at       │
└─────────────────────┘

┌─────────────────────┐
│   Bot               │
├─────────────────────┤
│ • id (PK)          │
│ • org_id (FK)      │───────────┐
│ • name             │           │
│ • description      │           │
│ • status           │           │
│ • settings (JSON)  │           │
│ • widget_settings  │           │
│ • api_key (unique) │           │
│ • allowed_domains[]│           │
│ • created_by (FK)  │           │
│ • created_at       │           │
└──────────┬──────────┘           │
           │                      │
           │ 1:N                  │ N:1
           ▼                      │
┌─────────────────────┐           │
│ KnowledgeSource     │           │
├─────────────────────┤           │
│ • id (PK)          │           │
│ • bot_id (FK)      │           │
│ • source_type      │           │
│ • name             │           │
│ • status           │           │
│ • metadata (JSON)  │           │
│ • created_at       │           │
└──────────┬──────────┘           │
           │                      │
           │ 1:N                  │
           ├──────────────────────┘
           │
           ├─────────┬─────────┬──────────┐
           ▼         ▼         ▼          ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ Document │ │ WebPage  │ │TextContent│
    ├──────────┤ ├──────────┤ ├──────────┤
    │ • id     │ │ • id     │ │ • id     │
    │ • source │ │ • source │ │ • source │
    │ • file   │ │ • url    │ │ • content│
    │ • path   │ │ • title  │ │ • title  │
    │ • size   │ │ • content│ │ • tags   │
    └──────────┘ └──────────┘ └──────────┘
           │         │         │
           └────┬────┴────┬────┘
                │         │
                ▼         ▼
           ┌─────────────────────┐
           │   Chunk             │
           ├─────────────────────┤
           │ • id (PK)          │
           │ • source_id (FK)   │
           │ • bot_id (FK)      │
           │ • org_id (FK)      │
           │ • content          │
           │ • embedding_id     │──→ Qdrant
           │ • metadata (JSON)  │
           │ • is_active        │
           └─────────────────────┘

┌─────────────────────┐
│   Conversation      │
├─────────────────────┤
│ • id (PK)          │
│ • bot_id (FK)      │──┐
│ • org_id (FK)      │  │
│ • session_id       │  │
│ • visitor_id       │  │
│ • started_at       │  │
│ • ended_at         │  │
│ • rating           │  │
│ • feedback         │  │
└──────────┬──────────┘  │
           │             │
           │ 1:N         │ N:1
           ▼             │
┌─────────────────────┐  │
│   Message           │  │
├─────────────────────┤  │
│ • id (PK)          │  │
│ • conversation_id  │  │
│ • role             │  │
│ • content          │  │
│ • sources_used[]   │  │
│ • latency_ms       │  │
│ • timestamp        │  │
└─────────────────────┘  │
                         │
                         │
┌─────────────────────┐  │
│   Event             │  │
│   (Analytics)       │  │
├─────────────────────┤  │
│ • id (PK)          │  │
│ • org_id (FK)      │──┘
│ • bot_id (FK)      │
│ • event_type       │
│ • event_data (JSON)│
│ • timestamp        │
└─────────────────────┘

┌─────────────────────┐
│   Plan              │
├─────────────────────┤
│ • id (PK)          │
│ • name             │
│ • slug             │
│ • price            │
│ • features (JSON)  │
│ • limits (JSON)    │
└──────────┬──────────┘
           │
           │ 1:N
           ▼
┌─────────────────────┐
│   Subscription      │
├─────────────────────┤
│ • id (PK)          │
│ • org_id (FK)      │──┐
│ • plan_id (FK)     │  │
│ • status           │  │
│ • current_period   │  │
│ • stripe_sub_id    │  │
└─────────────────────┘  │
                         │
                         │ N:1
┌─────────────────────┐  │
│   UsageCounter      │  │
├─────────────────────┤  │
│ • id (PK)          │  │
│ • org_id (FK)      │──┘
│ • metric_type      │
│ • count            │
│ • period_start     │
│ • period_end       │
│ • reset_at         │
└─────────────────────┘

┌─────────────────────┐
│   AuditLog          │
├─────────────────────┤
│ • id (PK)          │
│ • org_id (FK)      │
│ • user_id (FK)     │
│ • action           │
│ • resource_type    │
│ • resource_id      │
│ • changes (JSON)   │
│ • ip_address       │
│ • timestamp        │
└─────────────────────┘
```

---

## 🔍 QDRANT VECTOR STORE STRUCTURE

```
┌─────────────────────────────────────────────────────────────┐
│                    QDRANT INSTANCE                          │
└─────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴──────────────┬─────────────┐
                │                            │             │
                ▼                            ▼             ▼
    ┌───────────────────┐      ┌───────────────────┐   ┌─────...
    │ Collection:       │      │ Collection:       │   │
    │ bot_embeddings_1  │      │ bot_embeddings_2  │   │ ...
    └───────────────────┘      └───────────────────┘   └─────...
                │
                │
    ┌───────────▼───────────────────────────────────────────┐
    │  COLLECTION SCHEMA                                    │
    ├───────────────────────────────────────────────────────┤
    │  Vectors:                                             │
    │    • Dimension: 384 (all-MiniLM-L6-v2)               │
    │    • Distance: Cosine                                │
    │                                                       │
    │  Payload (Metadata):                                 │
    │    • chunk_id (string, keyword)                      │
    │    • organization_id (string, keyword) ← FILTER      │
    │    • bot_id (string, keyword)                        │
    │    • source_id (string, keyword)                     │
    │    • source_type (string, keyword)                   │
    │      - "document" | "webpage" | "text"               │
    │    • document_id (string, keyword, optional)         │
    │    • webpage_id (string, keyword, optional)          │
    │    • text_content_id (string, keyword, optional)     │
    │    • content (string, text)                          │
    │    • metadata (object, json)                         │
    │      - page_number                                   │
    │      - section_title                                 │
    │      - chunk_index                                   │
    │    • is_active (boolean) ← FILTER                    │
    │    • created_at (string, datetime)                   │
    └───────────────────────────────────────────────────────┘

    SEARCH QUERY EXAMPLE:
    ┌───────────────────────────────────────────────────────┐
    │  search(                                              │
    │    collection_name="bot_embeddings_123",             │
    │    query_vector=[0.123, 0.456, ...],  # 384-dim      │
    │    query_filter={                                    │
    │      "must": [                                       │
    │        {"key": "organization_id", "match": "org_1"}, │
    │        {"key": "bot_id", "match": "bot_123"},        │
    │        {"key": "is_active", "match": true}           │
    │      ]                                               │
    │    },                                                │
    │    limit=5,                                          │
    │    with_payload=true                                 │
    │  )                                                   │
    └───────────────────────────────────────────────────────┘
```

---

## 🔄 MULTI-TENANCY ISOLATION

```
┌─────────────────────────────────────────────────────────────┐
│                   TENANT ISOLATION STRATEGY                 │
└─────────────────────────────────────────────────────────────┘

REQUEST FLOW WITH TENANT ISOLATION:
────────────────────────────────────

1. User makes request
   ↓
2. Authentication Middleware extracts JWT
   ↓
3. JWT payload contains: { user_id, email, org_ids: ["org_1", "org_2"] }
   ↓
4. Tenant Middleware:
   • Checks which org user is acting on behalf of (from header or context)
   • Validates user has membership in that org
   • Injects org_id into request.state
   ↓
5. Database Query:
   SELECT * FROM bots
   WHERE organization_id = :org_id  ← AUTO-INJECTED
   AND status = 'active'
   ↓
6. Qdrant Query:
   query_filter = {
     "must": [
       {"key": "organization_id", "match": request.state.org_id}
     ]
   }
   ↓
7. Response returned (only data for that org)


DATA ISOLATION LAYERS:
──────────────────────

Layer 1: DATABASE
┌─────────────────────────────────────┐
│  Every table has organization_id    │
│  Every query filtered by org_id     │
│  Enforced at ORM level (SQLAlchemy) │
└─────────────────────────────────────┘

Layer 2: VECTOR STORE
┌─────────────────────────────────────┐
│  organization_id in payload         │
│  Filtered on every search           │
│  No cross-tenant vector access      │
└─────────────────────────────────────┘

Layer 3: FILE STORAGE
┌─────────────────────────────────────┐
│  Path: /{org_id}/{bot_id}/{file}   │
│  Access checked before serving      │
│  S3 bucket policies (production)    │
└─────────────────────────────────────┘

Layer 4: API KEYS
┌─────────────────────────────────────┐
│  API key → bot_id → organization_id │
│  Domain allowlist per bot           │
│  Rate limiting per org              │
└─────────────────────────────────────┘


EXAMPLE: USER SWITCHING ORGANIZATIONS
──────────────────────────────────────

User belongs to Org A and Org B

Request 1:
  Headers: {
    Authorization: "Bearer token...",
    X-Organization-ID: "org_a"
  }
  → All queries scoped to org_a
  → Only sees org_a's bots, conversations, etc.

Request 2:
  Headers: {
    Authorization: "Bearer token...",
    X-Organization-ID: "org_b"
  }
  → All queries scoped to org_b
  → Only sees org_b's bots, conversations, etc.
```

---

## 🚀 DEPLOYMENT ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│                     PRODUCTION DEPLOYMENT                   │
│                         (AWS Example)                       │
└─────────────────────────────────────────────────────────────┘

                         ┌─────────────┐
                         │   Route 53  │
                         │    (DNS)    │
                         └──────┬──────┘
                                │
                         ┌──────▼──────┐
                         │ CloudFront  │
                         │    (CDN)    │
                         └──────┬──────┘
                                │
                         ┌──────▼──────────────────┐
                         │  Application Load       │
                         │  Balancer (ALB)         │
                         │  • SSL Termination      │
                         │  • Health Checks        │
                         └──────┬──────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
            ┌───────▼────────┐      ┌──────▼────────┐
            │   Target Group │      │ Target Group  │
            │   (Web Tier)   │      │ (Worker Tier) │
            └───────┬────────┘      └──────┬────────┘
                    │                       │
        ┌───────────┴────────┐          ┌──▼─────────┐
        │                    │          │  Background │
    ┌───▼───┐          ┌────▼────┐     │  Workers    │
    │  ECS  │          │   ECS   │     │  (Celery)   │
    │FastAPI│   ...    │ FastAPI │     └─────────────┘
    │Container│        │Container│
    └───┬───┘          └────┬────┘
        │                   │
        └────────┬──────────┘
                 │
     ┌───────────┴────────────────────┐
     │                                │
┌────▼─────┐                    ┌─────▼────┐
│   RDS    │                    │ ElastiCache│
│PostgreSQL│                    │   Redis   │
│Multi-AZ  │                    │  (Cache)  │
└────┬─────┘                    └──────────┘
     │
     │ (Backup to S3)
     ▼
┌──────────┐
│   S3     │
│ Backups  │
└──────────┘

┌─────────────────────────────────────┐
│   Qdrant (Vector Store)             │
│   • Dedicated EC2 instance          │
│   • EBS volumes for persistence     │
│   • Regular snapshots               │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│   S3 Bucket                         │
│   • User uploaded documents         │
│   • Versioning enabled              │
│   • Lifecycle policies              │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│   Monitoring & Logging              │
│   ┌──────────┐  ┌────────────────┐  │
│   │CloudWatch│  │  Sentry        │  │
│   │  Logs    │  │ (Errors)       │  │
│   └──────────┘  └────────────────┘  │
│   ┌──────────┐  ┌────────────────┐  │
│   │Prometheus│  │   Grafana      │  │
│   │  Metrics │  │  (Dashboards)  │  │
│   └──────────┘  └────────────────┘  │
└─────────────────────────────────────┘

SCALING CONFIGURATION:
─────────────────────
• Auto Scaling Group: 2-10 instances
• Scale up: CPU > 70% for 5 min
• Scale down: CPU < 30% for 10 min
• Health check: /health endpoint
• Rolling updates: max 25% unhealthy
```

---

## 🔄 CI/CD PIPELINE

```
┌─────────────────────────────────────────────────────────────┐
│                   GITHUB ACTIONS WORKFLOW                   │
└─────────────────────────────────────────────────────────────┘

TRIGGER: Push to main branch or Pull Request
───────────────────────────────────────────

   ┌──────────────┐
   │  Git Push    │
   │  to main     │
   └──────┬───────┘
          │
          ▼
   ┌──────────────────────────────────┐
   │  JOB 1: Linting & Formatting     │
   ├──────────────────────────────────┤
   │  • black --check app/            │
   │  • flake8 app/                   │
   │  • mypy app/                     │
   └──────┬───────────────────────────┘
          │ (parallel)
          ▼
   ┌──────────────────────────────────┐
   │  JOB 2: Unit Tests               │
   ├──────────────────────────────────┤
   │  • pytest tests/unit/            │
   │  • coverage report (min 80%)     │
   │  • upload coverage to Codecov    │
   └──────┬───────────────────────────┘
          │ (parallel)
          ▼
   ┌──────────────────────────────────┐
   │  JOB 3: Integration Tests        │
   ├──────────────────────────────────┤
   │  • Start test DB (PostgreSQL)    │
   │  • Start test Qdrant             │
   │  • pytest tests/integration/     │
   └──────┬───────────────────────────┘
          │
          ▼
   ┌──────────────────────────────────┐
   │  JOB 4: Build Docker Image       │
   ├──────────────────────────────────┤
   │  • docker build -t app:$SHA      │
   │  • docker push to ECR            │
   │  • tag: latest, $BRANCH, $SHA    │
   └──────┬───────────────────────────┘
          │
          ▼
   ┌──────────────────────────────────┐
   │  JOB 5: Deploy to Staging        │
   ├──────────────────────────────────┤
   │  • Update ECS task definition    │
   │  • Deploy to staging cluster     │
   │  • Wait for health check         │
   │  • Run smoke tests               │
   └──────┬───────────────────────────┘
          │
          │ (manual approval for prod)
          ▼
   ┌──────────────────────────────────┐
   │  JOB 6: Deploy to Production     │
   ├──────────────────────────────────┤
   │  • Blue-Green deployment         │
   │  • Update task definition        │
   │  • Deploy to prod cluster        │
   │  • Shift traffic gradually       │
   │  • Monitor error rates           │
   │  • Rollback if errors > 1%       │
   └──────┬───────────────────────────┘
          │
          ▼
   ┌──────────────────────────────────┐
   │  JOB 7: Post-Deployment          │
   ├──────────────────────────────────┤
   │  • Run production smoke tests    │
   │  • Update monitoring dashboards  │
   │  • Send Slack notification       │
   │  • Create deployment tag         │
   └──────────────────────────────────┘
```

---

## 📊 MONITORING & OBSERVABILITY

```
┌─────────────────────────────────────────────────────────────┐
│                  OBSERVABILITY STACK                        │
└─────────────────────────────────────────────────────────────┘

ERROR TRACKING (Sentry):
────────────────────────
  Application → Sentry SDK → Sentry.io
                             ↓
                    ┌────────────────┐
                    │ Error Dashboard│
                    │ • Stack traces │
                    │ • Breadcrumbs  │
                    │ • User context │
                    │ • Alerts       │
                    └────────────────┘

METRICS (Prometheus + Grafana):
────────────────────────────────
  Application → /metrics endpoint
                ↓
         ┌──────────────┐
         │  Prometheus  │
         │  (Scrape)    │
         └──────┬───────┘
                │
                ▼
         ┌──────────────┐
         │   Grafana    │
         │  Dashboards  │
         └──────────────┘

  KEY METRICS:
  • Request rate (req/s)
  • Response time (p50, p95, p99)
  • Error rate (%)
  • Database connection pool
  • Qdrant search latency
  • LLM API latency
  • Active conversations
  • Message throughput

LOGGING (Structured JSON):
──────────────────────────
  Application → JSON Logs → CloudWatch/ELK
                             ↓
                    ┌────────────────┐
                    │  Log Explorer  │
                    │  • Filter logs │
                    │  • Full-text   │
                    │  • Trace IDs   │
                    └────────────────┘

  LOG FORMAT:
  {
    "timestamp": "2025-10-13T10:30:45Z",
    "level": "INFO",
    "logger": "app.services.chat",
    "trace_id": "abc-123",
    "user_id": "user_456",
    "org_id": "org_789",
    "message": "Chat response generated",
    "latency_ms": 234,
    "sources_used": 3
  }

DISTRIBUTED TRACING (Optional - Jaeger):
────────────────────────────────────────
  Request → FastAPI → Service Layer → DB/Qdrant
    ↓         ↓           ↓              ↓
    └─────────┴───────────┴──────────────┘
                    ↓
                 Jaeger
                    ↓
         ┌──────────────────┐
         │  Trace Timeline  │
         │  • Request path  │
         │  • Span duration │
         │  • Dependencies  │
         └──────────────────┘

ALERTING:
─────────
  Prometheus Alerts → AlertManager → Slack/PagerDuty/Email

  ALERT RULES:
  • API error rate > 1% for 5 min → P1
  • Response time p95 > 5s for 5 min → P2
  • Database connections > 90% → P2
  • Disk usage > 80% → P3
  • Failed deployments → P1
```

---

**Architecture Documentation Complete**

This visual architecture guide complements the other documentation files and provides a clear understanding of how all components interact in the SaaS RAG Chatbot system.

**Key Takeaways:**
- Multi-layered security with tenant isolation at every level
- Scalable architecture with load balancing and auto-scaling
- Comprehensive monitoring and observability
- Hybrid search combining vector similarity and keyword matching
- Clean separation of concerns with service layer architecture

**Next Steps:**
- Review this architecture before starting implementation
- Refer back during development for architectural decisions
- Use as reference for team discussions and onboarding

---

*Created: October 13, 2025*  
*For: RAG_App_Complete Backend Development*

