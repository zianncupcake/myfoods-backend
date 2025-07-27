# MyFoods Backend

A FastAPI-based microservice for asynchronously scraping and processing social media content (TikTok/Instagram) with Celery task queue, PostgreSQL database, and Cloudflare R2 storage.

## Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   FastAPI   │────▶│    Celery    │────▶│ PostgreSQL  │
│   (API)     │     │   (Worker)   │     │    (DB)     │
└─────────────┘     └──────────────┘     └─────────────┘
       │                    │                     
       │                    ▼                     
       │            ┌──────────────┐              
       │            │    Redis     │              
       │            │   (Queue)    │              
       │            └──────────────┘              
       │                    │                     
       ▼                    ▼                     
┌─────────────┐     ┌──────────────┐              
│ Cloudflare  │     │  Playwright  │              
│     R2      │     │  (Scraper)   │              
└─────────────┘     └──────────────┘              
```

## Tech Stack

- **Framework**: FastAPI (async Python web framework)
- **Database**: PostgreSQL with Tortoise ORM
- **Task Queue**: Celery with Redis backend
- **Storage**: Cloudflare R2 (S3-compatible object storage)
- **Web Scraping**: Playwright (headless browser) + httpx
- **Authentication**: JWT with OAuth2
- **Database Migrations**: Aerich

## Key Components

### 1. API Layer (app/main.py)
- RESTful endpoints for user management, items CRUD, and URL submission
- WebSocket support for real-time task status updates
- JWT-based authentication with OAuth2 flow

### 2. Background Tasks (app/worker/)
- Celery worker for async URL processing
- Scrapes TikTok/Instagram content using Playwright
- Uploads images to Cloudflare R2
- Handles retries and error recovery

### 3. Data Models (app/models.py)
- **User**: Authentication and ownership
- **Item**: Scraped content with metadata (URL, image, tags, categories)

## CI/CD Requirements

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Redis (Celery broker)
REDISCLOUD_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=1000

# Cloudflare R2
R2_ACCOUNT_ID=xxx
R2_ACCESS_KEY_ID=xxx
R2_SECRET_ACCESS_KEY=xxx
R2_BUCKET_NAME=xxx
R2_PUBLIC_URL_BASE=https://xxx
```

### Dependencies
- Python 3.9+ (see runtime.txt)
- PostgreSQL 13+
- Redis 4.0+
- System packages for Playwright (chromium dependencies)

### Build & Deployment Steps

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Database Migrations**
   ```bash
   aerich init -t app.config.TORTOISE_ORM_CONFIG
   aerich init-db  # First time only
   aerich migrate  # Generate migrations
   aerich upgrade  # Apply migrations
   ```

3. **Run Services**
   ```bash
   # API Server
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   
   # Celery Worker
   celery -A app.worker.celery_app worker --loglevel=info
   ```

### Container Considerations

**Multi-stage Dockerfile recommended:**
```dockerfile
# Stage 1: Builder
FROM python:3.9-slim as builder
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels -r requirements.txt

# Stage 2: Runtime
FROM python:3.9-slim
# Install Playwright dependencies
RUN apt-get update && apt-get install -y \
    wget \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
RUN pip install --no-cache /wheels/*
RUN playwright install chromium
```

### Health Checks & Monitoring

**API Health Check Endpoint:**
```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": await check_db_connection(),
        "redis": await check_redis_connection(),
        "timestamp": datetime.utcnow()
    }
```

**Celery Health Check:**
```bash
celery -A app.worker.celery_app inspect ping
```

### Deployment Platforms

**Heroku** (Procfile included):
```
web: gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
worker: celery -A app.worker.celery_app worker --loglevel=info
```

**Kubernetes Manifest Structure:**
```yaml
# API Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myfoods-api
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: api
        image: myfoods-backend:latest
        command: ["uvicorn", "app.main:app", "--host", "0.0.0.0"]
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: myfoods-secrets
              key: database-url

# Celery Worker Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myfoods-worker
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: worker
        image: myfoods-backend:latest
        command: ["celery", "-A", "app.worker.celery_app", "worker"]
```

### CI Pipeline Recommendations

1. **Build Stage**
   - Run `pip install` with cache
   - Install Playwright browsers
   - Build Docker image

2. **Test Stage**
   - Unit tests for CRUD operations
   - Integration tests for API endpoints
   - Mock external services (R2, social media sites)

3. **Security Scan**
   - Dependency vulnerability scan (`safety check`)
   - Container image scan
   - Secret detection

4. **Database Migration**
   - Run aerich migrations in staging first
   - Backup production DB before migration

5. **Deployment**
   - Blue-green deployment for zero downtime
   - Health check validation
   - Rollback strategy

### Monitoring & Logging

- **Application Logs**: Structured JSON logging to stdout
- **Metrics**: Export Celery task metrics, API response times
- **Alerts**: Failed scraping tasks, high error rates, storage failures

### Scaling Considerations

1. **Horizontal Scaling**
   - API: Stateless, scale based on CPU/memory
   - Workers: Scale based on queue depth
   - Use Redis Sentinel/Cluster for HA

2. **Performance Optimization**
   - Enable connection pooling for PostgreSQL
   - Implement caching layer for frequently accessed data
   - Use CDN for R2 public URLs

3. **Rate Limiting**
   - Implement API rate limiting
   - Respect social media platform limits
   - Use exponential backoff for retries

### Security Best Practices

1. **Secrets Management**
   - Use environment variables or secret management service
   - Rotate credentials regularly
   - Never commit secrets to version control

2. **Network Security**
   - Use HTTPS for all endpoints
   - Implement CORS properly
   - Firewall rules for Redis/PostgreSQL

3. **Input Validation**
   - Validate all user inputs
   - Sanitize URLs before processing
   - Implement request size limits

## API Documentation

FastAPI automatically generates OpenAPI documentation available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Development Setup

```bash
# Clone repository
git clone <repo-url>
cd myfoods-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Set up environment variables
cp .env.example .env
# Edit .env with your values

# Initialize database
aerich init-db
aerich upgrade

# Run development servers
uvicorn app.main:app --reload  # API
celery -A app.worker.celery_app worker --loglevel=info  # Worker
```

## Troubleshooting

1. **Playwright Issues**: Ensure all system dependencies are installed
2. **Database Connection**: Check DATABASE_URL format and network access
3. **Celery Tasks Not Processing**: Verify Redis connection and worker logs
4. **R2 Upload Failures**: Check credentials and bucket permissions