# AI Cloud Drive 

A self-hosted file storage system with **RAG powered semantic search** (Retrieval Augmented Generation). Upload documents, ask questions in natural language, and get intelligent answers from your files.

## Project Scope and Intent

This project is designed as a **learning focused, production inspired system** to demonstrate end to end architecture, AI/ML integration, and backend engineering patterns.

It is not intended to replace mature platforms like Google Drive or Dropbox, but to showcase system design decisions, trade-offs, and scalability considerations in a controlled environment.

**Scale Assumptions**: Designed for 10-100 users with moderate document volumes; horizontal scaling patterns are demonstrated architecturally but not load tested.

## Design Trade-offs and Assumptions

| Decision | Trade-off | Rationale |
|----------|-----------|-----------|
| ChromaDB for vectors | Simplicity over scale | Local first, no external dependencies; would need managed vector DB at scale |
| Async embedding generation | Latency vs UX | Avoids blocking uploads; users see "processing" status |
| JWT stateless auth | Simplicity vs session control | No server side session state; token revocation requires expiry |
| Groq cloud LLM | Speed vs privacy | Fast inference; self-hosted LLM would add latency and infrastructure |
| MinIO for storage | S3 compatibility vs managed service | Easy local dev; production could use AWS S3 directly |

## RAG Quality and Limitations

- Responses are generated **only from retrieved document chunks**
- If semantic similarity scores fall below threshold, system returns "insufficient context" instead of hallucinating
- Chunk size (500 tokens) and overlap (50 tokens) tuned for general documents; may need adjustment for specialized content
- System does not guarantee factual correctness beyond provided document context
- No explicit cross document reasoning; retrieval focuses on high relevance chunks to reduce context dilution

**Retrieval Strategy**: Top-k semantic similarity search (k=5) with cosine similarity scores; retrieved chunks are concatenated as context for LLM generation.

## Security Considerations

| Aspect | Implementation | Out of Scope |
|--------|----------------|--------------|
| Authentication | JWT tokens validated per request | OAuth/SSO integration |
| Authorization | Per user file isolation | Fine-grained permissions |
| Admin Actions | Audit logged with timestamps | Intrusion detection |
| Data Storage | Server side encryption supported (MinIO) | End to end encryption |
| Network | Nginx reverse proxy | Zero-trust networking |

**Threat Model**: This system assumes trusted internal network. External deployment requires additional hardening (rate limiting, WAF, etc.)

## Observability and Monitoring (Planned)

- Structured logging across API, worker, and RAG pipeline
- Latency tracking for ingestion, retrieval, and generation stages
- Error rate monitoring for background tasks
- Metrics intended for future Prometheus/Grafana integration

##  Key Features

###  RAG Engineered Document Search (RAG)
- **Semantic Understanding**: Uses vector embeddings to understand document meaning, not just keywords
- **Natural Language Queries**: Ask questions like "What are the key findings in my research papers?"
- **Context Aware Responses**: LLM generates answers using relevant document chunks as context
- **Multi Document Support**: Search across PDF, TXT, and Markdown files simultaneously

### Secure Authentication System
- **JWT Based Auth**: Stateless authentication with secure token management
- **Email Verification**: SMTP based email confirmation for new accounts
- **Role Based Access**: Admin and regular user roles with different permissions
- **Account Security**: Failed login tracking and account suspension capabilities
- **Token Storage**: Client side storage for simplicity; production deployments may prefer httpOnly cookies

###  Enterprise File Management
- **S3 Compatible Storage**: MinIO provides reliable, scalable object storage
- **Background Indexing**: Celery workers process documents asynchronously
- **File Isolation**: Each user's files are completely isolated from others
- **Download & Share**: Secure file download with proper access control

###  Admin Dashboard
- **User Analytics**: Monitor user activity, storage usage, and query statistics
- **User Management**: Verify, suspend, or delete users with cascading file cleanup
- **Audit Logging**: Track all administrative actions for security compliance
- **System Overview**: Real-time KPIs for users, files, and queries


##  System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  Dashboard  │    │  Admin UI   │    │  API Docs   │         │
│  │  (HTML/JS)  │    │  (HTML/JS)  │    │  (Swagger)  │         │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘         │
└─────────┼──────────────────┼──────────────────┼─────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                       NGINX REVERSE PROXY                        │
│              (SSL Termination, Load Balancing)                   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       APPLICATION LAYER                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    FastAPI Backend                       │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │    │
│  │  │  Auth   │  │  Files  │  │   RAG   │  │  Admin  │    │    │
│  │  │ Routes  │  │ Routes  │  │ Engine  │  │ Routes  │    │    │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘    │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────┬───────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   PostgreSQL    │ │     MinIO       │ │     Redis       │
│   (Metadata)    │ │  (File Storage) │ │  (Task Queue)   │
│                 │ │                 │ │                 │
│ • Users         │ │ • PDF files     │ │ • Celery broker │
│ • Files         │ │ • Documents     │ │ • Result store  │
│ • Chat History  │ │ • User folders  │ │                 │
│ • Audit Logs    │ │                 │ │                 │
└─────────────────┘ └─────────────────┘ └────────┬────────┘
                                                  │
                                                  ▼
                              ┌─────────────────────────────────┐
                              │         CELERY WORKER           │
                              │    (Background Processing)      │
                              │                                 │
                              │  • Document text extraction     │
                              │  • Chunk splitting              │
                              │  • Vector embedding generation  │
                              │  • ChromaDB indexing            │
                              └────────────────┬────────────────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    ▼                          ▼                          ▼
          ┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐
          │    ChromaDB     │        │    Groq API     │        │   Sentence Transformers   │
          │  (Vector Store) │        │  (LLM - Llama)  │        │  (Embeddings)   │
          │                 │        │                 │        │                 │
          │ Semantic search │        │ Answer generation│       │ Text → Vectors  │
          │ Similarity match│        │ Context synthesis│       │ 384 dim vectors │
          └─────────────────┘        └─────────────────┘        └─────────────────┘
```


##  Implementation Details

### RAG Pipeline
1. **Document Upload** → File stored in MinIO, metadata in PostgreSQL
2. **Background Indexing** → Celery worker extracts text, splits into chunks
3. **Vector Embedding** → Sentence Transformers model converts chunks to 384 dim vectors
4. **Storage** → Vectors stored in ChromaDB with document references
5. **Query Processing** → User query embedded, similar chunks retrieved
6. **Answer Generation** → Groq LLM synthesizes answer from relevant context

### Authentication Flow
1. **Registration** → User submits email/password
2. **Verification Email** → SMTP sends verification link
3. **Email Confirmation** → User clicks link, account activated
4. **Login** → JWT token issued, stored in localStorage
5. **Protected Routes** → Token validated on each API request

### Admin Cascading Delete
When an admin deletes a user:
1. All user files deleted from MinIO storage
2. File records removed from PostgreSQL
3. Chat history purged
4. User record deleted
5. Action logged in audit trail


## �️ Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Backend** | FastAPI (Python) | REST API, async support |
| **Frontend** | Vanilla JS, HTML5, CSS3 | Zero dependency UI |
| **Database** | PostgreSQL | Relational data storage |
| **Object Storage** | MinIO | S3 compatible file storage |
| **Vector DB** | ChromaDB | Semantic similarity search |
| **LLM** | Groq API (Llama 3.3 70B) | Fast inference, answer generation |
| **Embeddings** | Sentence Transformers (all MiniLM-L6-v2) | Text vectorization |
| **Task Queue** | Celery + Redis | Background job processing |
| **Reverse Proxy** | Nginx | Routing, static file serving |
| **Containerization** | Docker Compose | Multi-service orchestration |


##  Quick Start

### Prerequisites
- Docker & Docker Compose
- Groq API Key ([console.groq.com](https://console.groq.com))
- SMTP credentials (for email verification)

### Setup
```bash
# Clone and configure
git clone https://github.com/mithil27360/Cloud-drive.git
cd ai-cloud-drive
cp .env.example .env
# Edit .env with your API keys and SMTP settings

# Launch
docker-compose up --build -d

# Access
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
# Admin: http://localhost:3000/admin.html
```


##  Project Structure

```
ai-cloud-drive/
├── backend/
│   ├── app/
│   │   ├── routes/          # API endpoints (auth, files, admin)
│   │   ├── rag/             # RAG engine (indexer, llm, engine)
│   │   ├── storage/         # MinIO client
│   │   ├── tasks/           # Celery background tasks
│   │   ├── models.py        # SQLAlchemy models
│   │   └── auth.py          # JWT authentication
│   └── tests/               # pytest test suite
├── frontend/
│   ├── index.html           # Main dashboard
│   ├── admin.html           # Admin panel
│   ├── app.js               # Dashboard logic
│   └── admin.js             # Admin logic
├── docker-compose.yml       # Service orchestration
└── .env.example             # Environment template
```


##  License

MIT License - Use freely for learning or production.


*Built for learning cloud architecture, AI/ML integration, and full-stack development.*
