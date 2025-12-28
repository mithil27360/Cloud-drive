# AI Cloud Drive

Self hosted file storage with RAG search. Upload docs, ask questions, get answers from your files.

## What it does

- Upload PDFs, TXT, Markdown
- Ask questions in plain English
- Get answers with sources from your documents
- Admin dashboard for user management

## Architecture

```
Frontend (HTML/JS) → Nginx → FastAPI
                              ↓
                    ┌─────────┼─────────┐
                    ↓         ↓         ↓
               PostgreSQL   MinIO    Redis
                              ↓
                         Celery Worker
                              ↓
                    ┌─────────┼─────────┐
                    ↓         ↓         ↓
               ChromaDB    Groq API   Embeddings
```

## Tech Stack

- **Backend**: FastAPI, Celery, PostgreSQL
- **Storage**: MinIO (S3-compatible)
- **RAG**: ChromaDB + Sentence Transformers + Groq (Llama 3.3 70B)
- **Auth**: JWT with email verification
- **Deploy**: Docker Compose

## Quick Start

```bash
git clone https://github.com/mithil27360/Cloud-drive.git
cd Cloud-drive
cp .env.example .env
# add your Groq API key and SMTP settings

docker-compose up --build -d
```

- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs
- Admin: http://localhost:3000/admin.html

## Project Structure

```
backend/
  app/
    routes/     # API endpoints
    rag/        # RAG engine
    storage/    # MinIO client
    tasks/      # Celery workers
  tests/        # pytest
frontend/
  index.html    # Main UI
  admin.html    # Admin panel
```

## How RAG works

1. Upload → file goes to MinIO, metadata to Postgres
2. Celery extracts text, chunks it
3. Chunks embedded → stored in ChromaDB
4. Query → find similar chunks → Groq generates answer

## Trade-offs

| Choice | Why |
|--------|-----|
| ChromaDB | Simple, local, no infra |
| Groq | Fast inference, free tier |
| MinIO | S3-compatible, runs locally |
| JWT | Stateless, simple |

## License

MIT
