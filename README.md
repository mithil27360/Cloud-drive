# AI Cloud Drive 

A self-hosted file storage system with **RAG-powered semantic search**. Upload documents, ask questions in natural language, and get intelligent answers from your files.

## Project Scope

A **learning-focused, production-inspired system** demonstrating end-to-end architecture, AI/ML integration, and backend engineering patterns. Designed for 10-100 users; horizontal scaling patterns are demonstrated architecturally.

## Design Trade-offs

| Decision | Trade-off | Rationale |
|----------|-----------|-----------|
| ChromaDB for vectors | Simplicity over scale | Local-first, no external dependencies |
| Async embedding generation | Latency vs UX | Avoids blocking uploads |
| JWT stateless auth | Simplicity vs session control | No server-side session state |
| Groq cloud LLM | Speed vs privacy | Fast inference; self-hosted adds latency |
| MinIO for storage | S3 compatibility vs managed service | Easy local dev; prod uses AWS S3 |

## RAG Quality & Limitations

- Responses generated **only from retrieved document chunks**
- Returns "insufficient context" instead of hallucinating when similarity scores are low
- Chunk size (500 tokens) tuned for general documents
- No cross-document reasoning; focuses on high-relevance chunks

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  Dashboard  │    │  Admin UI   │    │  API Docs   │         │
│  │  (HTML/JS)  │    │  (HTML/JS)  │    │  (Swagger)  │         │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘         │
└─────────┼──────────────────┼──────────────────┼─────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                       NGINX REVERSE PROXY                        │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       FastAPI Backend                            │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │  Auth   │  │  Files  │  │   RAG   │  │  Admin  │            │
│  │ Routes  │  │ Routes  │  │ Engine  │  │ Routes  │            │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘            │
└─────────────────────────────┬───────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   PostgreSQL    │ │     MinIO       │ │     Redis       │
│   (Metadata)    │ │  (File Storage) │ │  (Task Queue)   │
└─────────────────┘ └─────────────────┘ └────────┬────────┘
                                                  │
                                                  ▼
                              ┌─────────────────────────────────┐
                              │         CELERY WORKER           │
                              │  • Text extraction              │
                              │  • Chunk splitting              │
                              │  • Vector embedding             │
                              │  • ChromaDB indexing            │
                              └────────────────┬────────────────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    ▼                          ▼                          ▼
          ┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
          │    ChromaDB     │        │    Groq API     │        │   Sentence      │
          │  (Vector Store) │        │  (LLM - Llama)  │        │  Transformers   │
          └─────────────────┘        └─────────────────┘        └─────────────────┘
```

## Key Features

### RAG-Powered Search
- Semantic understanding with vector embeddings
- Natural language queries across PDF, TXT, and Markdown files
- Context-aware responses with source citations

### Authentication & Security
- JWT-based auth with email verification
- Role-based access (admin/user)
- Rate limiting and security middleware

### File Management
- S3-compatible storage (MinIO)
- Background indexing with Celery
- Per-user file isolation

### Admin Dashboard
- User management & analytics
- Audit logging
- System KPIs

## Security

| Aspect | Implementation |
|--------|----------------|
| Authentication | JWT tokens per request |
| Authorization | Per-user file isolation |
| Admin Actions | Audit logged |
| Network | Nginx reverse proxy |

> ⚠️ **Production**: Change all default credentials in `.env`. Do not expose MinIO ports publicly.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI (Python) |
| Frontend | Vanilla JS, HTML5, CSS3 |
| Database | PostgreSQL |
| Storage | MinIO (S3-compatible) |
| Vector DB | ChromaDB |
| LLM | Groq API (Llama 3.3 70B) |
| Embeddings | Sentence Transformers |
| Task Queue | Celery + Redis |
| Proxy | Nginx |
| Deploy | Docker Compose |

## Quick Start

### Prerequisites
- Docker & Docker Compose
- [Groq API Key](https://console.groq.com)
- SMTP credentials (for email verification)

### Setup
```bash
git clone https://github.com/mithil27360/Cloud-drive.git
cd Cloud-drive
cp .env.example .env
# Edit .env with your API keys and SMTP settings

docker-compose up --build -d

# Access:
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
# Admin: http://localhost:3000/admin.html
```

## Project Structure

```
Cloud-drive/
├── backend/
│   ├── app/
│   │   ├── routes/          # API endpoints
│   │   ├── rag/             # RAG engine
│   │   ├── storage/         # MinIO client
│   │   ├── tasks/           # Celery tasks
│   │   ├── models.py        # SQLAlchemy models
│   │   └── auth.py          # JWT auth
│   └── tests/               # pytest suite
├── frontend/
│   ├── index.html           # Dashboard
│   ├── admin.html           # Admin panel
│   └── app.js               # App logic
├── docker-compose.yml
└── .env.example
```

## RAG Pipeline

1. **Upload** → File stored in MinIO, metadata in PostgreSQL
2. **Index** → Celery extracts text, splits into chunks
3. **Embed** → Sentence Transformers → 384-dim vectors
4. **Store** → Vectors indexed in ChromaDB
5. **Query** → User query embedded, similar chunks retrieved
6. **Generate** → Groq LLM synthesizes answer from context

## Observability (Planned)

- Structured logging across API and workers
- Latency tracking for RAG stages
- Prometheus/Grafana integration ready

## License

MIT License
