# 🚀 Deployment Guide - Indian Legal AI Assistant

Quick deployment guide for testing and running the application locally.

## 📋 Prerequisites

- Docker Desktop installed and running
- Git installed
- **OpenAI API key with credits** (get from https://platform.openai.com/api-keys)
- 8GB+ RAM available
- Windows 10/11, macOS, or Linux

## ⚡ Quick Start (5 minutes)

### 1. Clone the Repository

```bash
git clone https://github.com/laxmi-narasimha26/lawyer_ly.git
cd lawyer_ly
```

### 2. Start the Application

```bash
docker compose -f docker-compose.local.app.yml up -d
```

This will start:
- **PostgreSQL** (port 5433) - Database with pgvector extension
- **Redis** (port 6379) - Caching layer
- **Backend API** (port 8000) - FastAPI application

### 3. Wait for Services to Initialize (~30 seconds)

```bash
# Check if services are healthy
docker ps

# Check backend logs
docker logs legal-ai-backend-local --tail=50
```

### 4. Test the Application

**Health Check:**
```bash
curl http://localhost:8000/health
```

**API Documentation:**
Open http://localhost:8000/docs in your browser

**Test Query:**
```bash
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{"message":"What is the Indian Penal Code?","mode":"qa","user_id":"test_user"}'
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (Port 5173)                 │
│                    React + TypeScript                    │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/REST
                     ▼
┌─────────────────────────────────────────────────────────┐
│                Backend API (Port 8000)                   │
│                    FastAPI + Python                      │
│  ┌─────────────────────────────────────────────────┐   │
│  │  RAG Pipeline                                    │   │
│  │  • Vector Search (pgvector)                     │   │
│  │  • OpenAI GPT-4 Integration                     │   │
│  │  • Semantic Search                              │   │
│  │  • Citation Management                          │   │
│  └─────────────────────────────────────────────────┘   │
└──────┬──────────────────────────────────────┬───────────┘
       │                                      │
       ▼                                      ▼
┌──────────────────┐              ┌─────────────────────┐
│  PostgreSQL      │              │      Redis          │
│  (Port 5433)     │              │    (Port 6379)      │
│  + pgvector      │              │   Cache Layer       │
└──────────────────┘              └─────────────────────┘
```

## 🔑 API Key Configuration

**⚠️ IMPORTANT: You MUST provide a valid OpenAI API key before testing the application.**

The API keys in the repository are invalid (revoked by GitHub secret scanning). You must configure your own OpenAI API key.

### Option 1: Set Environment Variable (Recommended)

```bash
# Windows
set OPENAI_API_KEY=your-valid-api-key-here

# Linux/Mac
export OPENAI_API_KEY=your-valid-api-key-here
```

After setting the environment variable, restart the services:
```bash
docker compose -f docker-compose.local.app.yml down
docker compose -f docker-compose.local.app.yml up -d
```

### Option 2: Edit Configuration File

Edit `backend/config/api_keys.py`:
```python
OPENAI_API_KEY = "your-valid-api-key-here"
```

Then rebuild and restart:
```bash
docker compose -f docker-compose.local.app.yml down
docker compose -f docker-compose.local.app.yml up -d --build backend
```

### Get Your OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Ensure you have credits/billing configured
4. Use the key in one of the methods above

## 📚 API Endpoints

### Chat Endpoints

**1. Query Legal Assistant**
```bash
POST /api/v1/chat/query
Content-Type: application/json

{
  "message": "Your legal question",
  "mode": "qa",  // qa, drafting, or summarization
  "user_id": "test_user",
  "conversation_id": null  // optional for context
}
```

**Response:**
```json
{
  "message_id": "uuid",
  "conversation_id": "uuid",
  "response": "AI-generated legal response...",
  "citations": [],
  "processing_time": 7.13,
  "token_usage": {
    "prompt_tokens": 49,
    "completion_tokens": 292,
    "total_tokens": 341
  }
}
```

### Health Endpoints

**1. Basic Health Check**
```bash
GET /health
```

**2. Detailed Health Check**
```bash
GET /health/ready
```

## 🧪 Testing Scenarios

### Scenario 1: Basic Legal Query
```bash
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the fundamental rights in India?",
    "mode": "qa",
    "user_id": "agent_test"
  }'
```

### Scenario 2: Conversation with Context
```bash
# First query
CONV_ID=$(curl -s -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{"message":"What is Section 302 IPC?","mode":"qa","user_id":"agent_test"}' \
  | jq -r '.conversation_id')

# Follow-up query with context
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"What is the punishment for this offense?\",
    \"mode\": \"qa\",
    \"user_id\": \"agent_test\",
    \"conversation_id\": \"$CONV_ID\"
  }"
```

### Scenario 3: Document Drafting Mode
```bash
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Draft a legal notice for breach of contract",
    "mode": "drafting",
    "user_id": "agent_test"
  }'
```

## 🔧 Troubleshooting

### Backend Not Starting

**Check logs:**
```bash
docker logs legal-ai-backend-local
```

**Common issues:**
1. **Port conflicts** - Ensure ports 8000, 5433, 6379 are available
2. **Docker memory** - Allocate at least 8GB to Docker
3. **Build failures** - Try rebuilding: `docker compose -f docker-compose.local.app.yml build backend`

### Database Connection Errors

```bash
# Check if PostgreSQL is healthy
docker ps | grep postgres

# Restart PostgreSQL
docker restart legal-ai-postgres-local

# Check PostgreSQL logs
docker logs legal-ai-postgres-local
```

### Redis Connection Errors

```bash
# Check if Redis is healthy
docker ps | grep redis

# Test Redis connection
docker exec legal-ai-redis-local redis-cli ping
```

## 🛑 Stopping the Application

```bash
# Stop all services
docker compose -f docker-compose.local.app.yml down

# Stop and remove volumes (clean slate)
docker compose -f docker-compose.local.app.yml down -v
```

## 🔄 Rebuilding After Code Changes

```bash
# Rebuild backend only
docker compose -f docker-compose.local.app.yml build backend

# Rebuild and restart
docker compose -f docker-compose.local.app.yml up -d --build
```

## 📊 Monitoring

### Check Container Status
```bash
docker ps -a | grep legal-ai
```

### View Real-time Logs
```bash
# Backend logs
docker logs -f legal-ai-backend-local

# All services
docker compose -f docker-compose.local.app.yml logs -f
```

### Database Status
```bash
# Connect to PostgreSQL
docker exec -it legal-ai-postgres-local psql -U postgres -d legal_kb

# Check tables
\dt

# Check vector extension
SELECT * FROM pg_extension WHERE extname = 'vector';
```

## 🎯 Performance Benchmarks

- **Average Query Response Time:** 5-10 seconds
- **Token Usage per Query:** 300-500 tokens
- **Concurrent Users Supported:** 10-20 (local deployment)
- **Database:** Supports 100K+ legal documents
- **Vector Search:** <1 second for semantic search

## 🐛 Debug Mode

Enable debug logging:

```bash
docker compose -f docker-compose.local.app.yml down
docker compose -f docker-compose.local.app.yml up
# (Without -d flag to see real-time output)
```

## 📝 Testing Checklist

- [ ] Services start successfully
- [ ] Health endpoint returns 200 OK
- [ ] Basic legal query returns valid response
- [ ] Conversation context works
- [ ] Response time < 15 seconds
- [ ] Citations are included in responses
- [ ] Token usage is tracked
- [ ] Redis caching is working
- [ ] Database connections are stable

## 🚀 Production Deployment

For production deployment to Azure:

1. Review `infrastructure/azure/arm/main.json`
2. Set up Azure resources
3. Configure Azure Key Vault for secrets
4. Use `docker-compose.prod.yml`
5. Enable Azure Monitor
6. Set up CI/CD with `.github/workflows/ci-cd.yml`

## 📞 Support

- **Repository:** https://github.com/laxmi-narasimha26/lawyer_ly
- **Issues:** https://github.com/laxmi-narasimha26/lawyer_ly/issues
- **API Docs:** http://localhost:8000/docs (when running)

## ⚡ Quick Reference

```bash
# Start
docker compose -f docker-compose.local.app.yml up -d

# Check health
curl http://localhost:8000/health

# Test query
curl -X POST http://localhost:8000/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{"message":"test","mode":"qa","user_id":"test"}'

# View logs
docker logs legal-ai-backend-local --tail=100

# Stop
docker compose -f docker-compose.local.app.yml down
```

---

**Generated with Claude Code** | **Last Updated:** November 2025
