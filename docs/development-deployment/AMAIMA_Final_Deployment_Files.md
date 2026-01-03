# AMAIMA Final Deployment Files

This document contains all deployment configuration files for the AMAIMA platform. The deployment infrastructure implements Docker Compose v5.x with modern syntax, Kubernetes manifests for orchestration, and GitHub Actions workflows for automated CI/CD.

## Directory Structure

```
amaima-deployment/
├── docker/
│   ├── compose.yaml
│   ├── backend/
│   │   └── Dockerfile
│   ├── frontend/
│   │   ├── Dockerfile
│   │   └── nginx.conf
│   └── nginx/
│       └── default.conf
├── kubernetes/
│   ├── namespace.yaml
│   ├── postgres-secret.yaml
│   ├── redis-deployment.yaml
│   ├── postgres-deployment.yaml
│   ├── backend-deployment.yaml
│   ├── frontend-deployment.yaml
│   ├── backend-service.yaml
│   ├── frontend-service.yaml
│   └── ingress.yaml
├── github/
│   ├── backend-ci.yml
│   ├── frontend-ci.yml
│   └── android-ci.yml
├── config/
│   ├── backend/
│   │   ├── amaima_config.yaml
│   │   └── uvicorn.py
│   └── frontend/
│       └── next.config.js
└── scripts/
    ├── deploy.sh
    ├── healthcheck.sh
    └── migrate.sh
```

---

## 1. Docker Compose Configuration

### Root Compose File

```yaml
version: "3.8"

services:
  postgres:
    image: postgres:16-alpine
    container_name: amaima-postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-amaima}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-amaima_secret}
      POSTGRES_DB: ${POSTGRES_DB:-amaima}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-db.sh:/docker-entrypoint-initdb.d/init-db.sh
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-amaima} -d ${POSTGRES_DB:-amaima}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    restart: unless-stopped
    networks:
      - amaima-network

  redis:
    image: redis:7-alpine
    container_name: amaima-redis
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 5s
    restart: unless-stopped
    networks:
      - amaima-network

  backend:
    build:
      context: ./docker/backend
      dockerfile: Dockerfile
    container_name: amaima-backend
    environment:
      - AMAIMA_ENV=${AMAIMA_ENV:-production}
      - DATABASE_URL=postgresql://${POSTGRES_USER:-amaima}:${POSTGRES_PASSWORD:-amaima}@postgres:5432/${POSTGRES_DB:-amaima}
      - REDIS_URL=redis://redis:6379/0
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - JWT_SECRET_KEY=${JWT_SECRET_KEY:-change_this_in_production}
      - JWT_ALGORITHM=RS256
      - JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
      - JWT_REFRESH_TOKEN_EXPIRE_DAYS=30
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - MODEL_CACHE_DIR=/app/models
      - OBSERVABILITY_ENABLED=true
    volumes:
      - model_cache:/app/models
      - ./config/backend/amaima_config.yaml:/app/config.yaml:ro
      - ./config/backend/uvicorn.py:/app/uvicorn.py:ro
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
    restart: unless-stopped
    networks:
      - amaima-network
    deploy:
      resources:
        limits:
          cpus: "4"
          memory: 16G
        reservations:
          cpus: "2"
          memory: 8G
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  frontend:
    build:
      context: ./docker/frontend
      dockerfile: Dockerfile
    container_name: amaima-frontend
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
      - NODE_ENV=production
    volumes:
      - ./config/frontend/next.config.js:/app/next.config.js:ro
    ports:
      - "3000:80"
    depends_on:
      backend:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
    networks:
      - amaima-network
    deploy:
      resources:
        limits:
          cpus: "1"
          memory: 1G
        reservations:
          cpus: "0.5"
          memory: 512M

volumes:
  postgres_data:
    name: amaima-postgres-data
  redis_data:
    name: amaima-redis-data
  model_cache:
    name: amaima-model-cache

networks:
  amaima-network:
    name: amaima-network
    driver: bridge
```

---

## 2. Backend Docker Configuration

### Backend Dockerfile

```dockerfile
# ============================================
# AMAIMA Backend Production Dockerfile
# ============================================

# Build stage
FROM python:3.10-slim-bookworm AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
WORKDIR /app
COPY . .

# Download NLTK data for verification engine
RUN python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('stopwords', quiet=True); nltk.download('wordnet', quiet=True)"

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Final stage
FROM python:3.10-slim-bookworm AS runner

# Create non-root user
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy from builder
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app

# Create directories
RUN mkdir -p /app/models /app/logs && chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entrypoint
WORKDIR /app
ENTRYPOINT ["python", "uvicorn.py"]
```

### Backend Requirements.txt

```
# ============================================
# AMAIMA Backend Production Dependencies
# ============================================

# Core Framework
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.5.0
pydantic-settings>=2.1.0

# API Documentation
fastapi-docs>=0.1.0
fastapi-openapi>=1.0.0

# Database
asyncpg>=0.29.0
sqlalchemy[asyncio]>=2.0.25
alembic>=1.13.0

# Redis
redis>=5.0.0
aioredis>=2.0.0

# Authentication
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.6

# ML & Inference
torch>=2.1.0
torchvision>=0.16.0
tensorflow>=2.15.0
tensorrt>=8.6.0
onnx>=1.15.0
onnxruntime>=1.16.0
transformers>=4.36.0
tokenizers>=0.15.0

# NLP & Processing
spacy>=3.7.0
nltk>=3.8.0
sentence-transformers>=0.3.0

# Verification & Security
numpy>=1.26.0
scipy>=1.11.0
Pillow>=10.0.0
python-levenshtein>=0.23.0

# Observability
prometheus-client>=0.19.0
opentelemetry-api>=1.21.0
opentelemetry-sdk>=1.21.0
opentelemetry-instrumentation-fastapi>=0.42b0
opentelemetry-exporter-otlp>=1.21.0

# Configuration & Logging
pyyaml>=6.0.1
python-dotenv>=1.0.0
loguru>=0.7.2

# HTTP Client
httpx>=0.26.0
aiofiles>=23.2.1

# Utilities
python-dateutil>=2.8.2
humanize>=4.9.0
orjson>=3.9.0
```

### Backend Configuration File

```yaml
# ============================================
# AMAIMA Backend Configuration (Production)
# ============================================

# Application Settings
app:
  name: "AMAIMA"
  version: "5.0.0"
  environment: "${AMAIMA_ENV}"
  debug: false
  host: "0.0.0.0"
  port: 8000

# Database Configuration
database:
  url: "${DATABASE_URL}"
  pool_size: 20
  max_overflow: 10
  pool_timeout: 30
  pool_recycle: 1800
  echo: false

# Redis Configuration
redis:
  url: "${REDIS_URL}"
  db: 0
  max_connections: 50
  socket_timeout: 5.0
  socket_connect_timeout: 5.0

# JWT Authentication
jwt:
  secret_key: "${JWT_SECRET_KEY}"
  algorithm: "RS256"
  access_token_expire_minutes: 15
  refresh_token_expire_days: 30
  public_key_path: "/app/keys/public.pem"
  private_key_path: "/app/keys/private.pem"

# Smart Router Engine Configuration
router:
  complexity_levels:
    - TRIVIAL
    - SIMPLE
    - MODERATE
    - COMPLEX
    - EXPERT
  default_model: "llama2-7b"
  model_mapping:
    TRIVIAL: "llama2-7b"
    SIMPLE: "llama2-13b"
    MODERATE: "llama2-70b"
    COMPLEX: "mixtral-8x7b"
    EXPERT: "gpt4-turbo"
  cache_ttl: 3600
  enable_predictive_preloading: true

# Progressive Model Loader Configuration
model_loader:
  cache_dir: "${MODEL_CACHE_DIR:-/app/models}"
  tensorrt_enabled: true
  quantization:
    default: "FP16"
    available: ["FP32", "FP16", "INT8", "INT4"]
  memory:
    max_usage_percent: 80
    eviction_policy: "lru"
    monitor_interval: 5.0
  preload:
    enabled: true
    prediction_window: 100
    max_preloaded_models: 3

# Multi-Layer Verification Engine Configuration
verification:
  enabled: true
  levels:
    - syntax
    - semantic
    - safety
    - consistency
  syntax:
    enabled: true
    strict_mode: false
  semantic:
    enabled: true
    confidence_threshold: 0.7
    cross_reference_enabled: true
  safety:
    enabled: true
    content_policy: "standard"
    scan_code: true
    scan_files: true
  consistency:
    enabled: true
    historical_check: true
    anomaly_detection: true

# Production API Server Configuration
api:
  cors:
    enabled: true
    origins:
      - "http://localhost:3000"
      - "https://*.amaima.ai"
    methods:
      - "*"
    headers:
      - "*"
  rate_limiting:
    enabled: true
    default_requests_per_minute: 60
    default_requests_per_hour: 1000
    burst_multiplier: 2.0
  request_size_limit: "50mb"
  response_compression: true

# Observability Configuration
observability:
  enabled: "${OBSERVABILITY_ENABLED:-true}"
  log_level: "${LOG_LEVEL:-INFO}"
  log_format: "json"
  metrics:
    enabled: true
    path: "/metrics"
    include:
      - request_count
      - request_duration
      - model_inference_time
      - verification_time
      - cache_hit_rate
  tracing:
    enabled: true
    sample_rate: 1.0
    exporter: "otlp"
  logging:
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file:
      enabled: true
      path: "/app/logs/amaima.log"
      max_size: "100mb"
      backup_count: 5

# Continuous Learning Engine Configuration
learning:
  enabled: true
  nemotoolkit_path: "/app/nemo"
  feedback_collection:
    enabled: true
    storage: "database"
  reinforcement_learning:
    enabled: true
    update_interval: 3600
    model_checkpoint_interval: 86400

# Benchmark Suite Configuration
benchmark:
  enabled: true
  domains:
    - mathematics
    - reasoning
    - coding
    - science
    - language
  schedule: "0 0 * * 0"
  retention_days: 90

# Cost Analysis Configuration
cost:
  enabled: true
  tracking:
    enabled: true
    granularity: "per_query"
  budgets:
    enabled: true
    default_monthly_limit: 10000.0
    alerts:
      - threshold: 0.5
        action: "warning"
      - threshold: 0.8
        action: "alert"
      - threshold: 0.95
        action: "critical"

# DARPA Readiness Framework Configuration
compliance:
  enabled: true
  standards:
    - "NIST 800-53"
    - "FEDRAMP"
  audit:
    enabled: true
    interval_days: 30
    automated_collection: true
  reporting:
    enabled: true
    formats:
      - "pdf"
      - "html"
      - "json"
```

---

## 3. Frontend Docker Configuration

### Frontend Dockerfile

```dockerfile
# ============================================
# AMAIMA Frontend Production Dockerfile
# ============================================

# Build stage
FROM node:20-alpine AS builder

# Set environment variables
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

# Install dependencies
WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build application
RUN npm run build

# Production stage
FROM node:20-alpine AS runner

# Set environment variables
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Create directories
WORKDIR /app
RUN mkdir -p /app/public && chown -R nextjs:nodejs /app

# Copy built assets
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# Copy nginx configuration
COPY --from=builder /app/docker/nginx/default.conf /etc/nginx/http.d/default.conf

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# Entrypoint
ENV PORT=3000
EXPOSE 3000

CMD ["node", "server.js"]
```

### Frontend Nginx Configuration

```nginx
# ============================================
# AMAIMA Frontend Nginx Configuration
# ============================================

server {
    listen 3000;
    server_name _;
    root /app;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' http://localhost:8000 wss://localhost:8000 https://api.amaima.ai wss://api.amaima.ai; frame-ancestors 'self';" always;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/json application/xml+rss;
    gzip_disable "MSIE [1-6]\.";

    # Static asset caching
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # API proxy
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # WebSocket proxy
    location /ws/ {
        proxy_pass http://backend:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }

    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }

    # Next.js static files
    location /_next/static/ {
        alias /app/.next/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Next.js public files
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Error pages
    error_page 500 502 503 504 /50x.html;
    location = /50x.html {
        root /usr/share/nginx/html;
    }
}
```

### Frontend next.config.js

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
    output: 'standalone',
    reactStrictMode: true,
    poweredByHeader: false,
    
    // Environment variables exposed to client
    env: {
        NEXT_PUBLIC_APP_NAME: 'AMAIMA',
        NEXT_PUBLIC_APP_VERSION: '5.0.0',
    },
    
    // Image optimization
    images: {
        formats: ['image/avif', 'image/webp'],
        deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048, 3840],
    },
    
    // Headers for security
    async headers() {
        return [
            {
                source: '/:path*',
                headers: [
                    {
                        key: 'X-Frame-Options',
                        value: 'SAMEORIGIN',
                    },
                    {
                        key: 'X-Content-Type-Options',
                        value: 'nosniff',
                    },
                    {
                        key: 'X-XSS-Protection',
                        value: '1; mode=block',
                    },
                    {
                        key: 'Referrer-Policy',
                        value: 'strict-origin-when-cross-origin',
                    },
                    {
                        key: 'Permissions-Policy',
                        value: 'camera=(), microphone=(), geolocation=()',
                    },
                ],
            },
        ];
    },
    
    // Redirects
    async redirects() {
        return [
            {
                source: '/login',
                destination: '/auth/login',
                permanent: true,
            },
            {
                source: '/register',
                destination: '/auth/register',
                permanent: true,
            },
        ];
    },
    
    // Webpack configuration
    webpack: (config, { isServer }) => {
        // TensorFlow.js configuration
        if (!isServer) {
            config.resolve.fallback = {
                ...config.resolve.fallback,
                fs: false,
                path: false,
            };
        }
        
        return config;
    },
    
    // Experimental features
    experimental: {
        optimizePackageImports: ['@/components/ui', 'lucide-react', 'framer-motion'],
    },
};

module.exports = nextConfig;
```

---

## 4. Kubernetes Manifests

### Namespace Configuration

```yaml
# ============================================
# AMAIMA Kubernetes Namespace Configuration
# ============================================

apiVersion: v1
kind: Namespace
metadata:
  name: amaima
  labels:
    app.kubernetes.io/name: amaima
    app.kubernetes.io/version: 5.0.0
    app.kubernetes.io/managed-by: kubectl
---

apiVersion: v1
kind: Namespace
metadata:
  name: amaima-monitoring
  labels:
    app.kubernetes.io/name: amaima-monitoring
```

### PostgreSQL Secret

```yaml
# ============================================
# AMAIMA PostgreSQL Secret Configuration
# ============================================

apiVersion: v1
kind: Secret
metadata:
  name: amaima-postgres-secret
  namespace: amaima
type: Opaque
stringData:
  POSTGRES_USER: amaima
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  POSTGRES_DB: amaima
---

apiVersion: v1
kind: Secret
metadata:
  name: amaima-jwt-secret
  namespace: amaima
type: Opaque
stringData:
  JWT_SECRET_KEY: ${JWT_PRIVATE_KEY_BASE64}
  JWT_PUBLIC_KEY: ${JWT_PUBLIC_KEY_BASE64}
```

### Redis Deployment

```yaml
# ============================================
# AMAIMA Redis Deployment Configuration
# ============================================

apiVersion: apps/v1
kind: Deployment
metadata:
  name: amaima-redis
  namespace: amaima
  labels:
    app.kubernetes.io/name: amaima-redis
    app.kubernetes.io/component: cache
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: amaima-redis
  template:
    metadata:
      labels:
        app.kubernetes.io/name: amaima-redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          command:
            - redis-server
            - --appendonly
            - "yes"
            - --maxmemory
            - "512mb"
            - --maxmemory-policy
            - allkeys-lru
          ports:
            - containerPort: 6379
              name: redis
          resources:
            requests:
              memory: "256Mi"
              cpu: "100m"
            limits:
              memory: "1Gi"
              cpu: "500m"
          livenessProbe:
            exec:
              command:
                - redis-cli
                - ping
            initialDelaySeconds: 10
            periodSeconds: 10
          readinessProbe:
            exec:
              command:
                - redis-cli
                - ping
            initialDelaySeconds: 5
            periodSeconds: 5
      volumes:
        - name: redis-data
          persistentVolumeClaim:
            claimName: amaima-redis-pvc

---

apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: amaima-redis-pvc
  namespace: amaima
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
  storageClassName: gp3

---

apiVersion: v1
kind: Service
metadata:
  name: amaima-redis
  namespace: amaima
spec:
  selector:
    app.kubernetes.io/name: amaima-redis
  ports:
    - port: 6379
      targetPort: 6379
      name: redis
  clusterIP: None
```

### PostgreSQL Deployment

```yaml
# ============================================
# AMAIMA PostgreSQL Deployment Configuration
# ============================================

apiVersion: apps/v1
kind: Deployment
metadata:
  name: amaima-postgres
  namespace: amaima
  labels:
    app.kubernetes.io/name: amaima-postgres
    app.kubernetes.io/component: database
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: amaima-postgres
  template:
    metadata:
      labels:
        app.kubernetes.io/name: amaima-postgres
    spec:
      containers:
        - name: postgres
          image: postgres:16-alpine
          envFrom:
            - secretRef:
                name: amaima-postgres-secret
          ports:
            - containerPort: 5432
              name: postgres
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "4Gi"
              cpu: "2"
          volumeMounts:
            - name: postgres-data
              mountPath: /var/lib/postgresql/data
          livenessProbe:
            exec:
              command:
                - pg_isready
                - -U
                - amaima
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            exec:
              command:
                - pg_isready
                - -U
                - amaima
            initialDelaySeconds: 5
            periodSeconds: 5
      volumes:
        - name: postgres-data
          persistentVolumeClaim:
            claimName: amaima-postgres-pvc

---

apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: amaima-postgres-pvc
  namespace: amaima
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
  storageClassName: gp3

---

apiVersion: v1
kind: Service
metadata:
  name: amaima-postgres
  namespace: amaima
spec:
  selector:
    app.kubernetes.io/name: amaima-postgres
  ports:
    - port: 5432
      targetPort: 5432
      name: postgres
  clusterIP: None
```

### Backend Deployment

```yaml
# ============================================
# AMAIMA Backend Deployment Configuration
# ============================================

apiVersion: apps/v1
kind: Deployment
metadata:
  name: amaima-backend
  namespace: amaima
  labels:
    app.kubernetes.io/name: amaima-backend
    app.kubernetes.io/component: api
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app.kubernetes.io/name: amaima-backend
  template:
    metadata:
      labels:
        app.kubernetes.io/name: amaima-backend
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      serviceAccountName: amaima-backend
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
      containers:
        - name: backend
          image: amaima/backend:5.0.0
          imagePullPolicy: Always
          env:
            - name: AMAIMA_ENV
              value: "production"
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: amaima-postgres-secret
                  key: DATABASE_URL
            - name: REDIS_URL
              value: "redis://amaima-redis:6379/0"
            - name: JWT_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: amaima-jwt-secret
                  key: JWT_SECRET_KEY
          ports:
            - containerPort: 8000
              name: http
          resources:
            requests:
              memory: "8Gi"
              cpu: "2000m"
              nvidia.com/gpu: 1
            limits:
              memory: "16Gi"
              cpu: "4000m"
              nvidia.com/gpu: 1
          volumeMounts:
            - name: model-cache
              mountPath: /app/models
            - name: config
              mountPath: /app/config.yaml
              subPath: config.yaml
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 15
            timeoutSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
      volumes:
        - name: model-cache
          persistentVolumeClaim:
            claimName: amaima-model-pvc
        - name: config
          configMap:
            name: amaima-backend-config

---

apiVersion: v1
kind: ConfigMap
metadata:
  name: amaima-backend-config
  namespace: amaima
data:
  config.yaml: |
    # AMAIMA Backend Configuration
    app:
      name: AMAIMA
      version: 5.0.0
      environment: production
    database:
      pool_size: 20
      max_overflow: 10
    redis:
      max_connections: 50
    observability:
      enabled: true
      log_level: INFO

---

apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: amaima-model-pvc
  namespace: amaima
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Gi
  storageClassName: gp3

---

apiVersion: v1
kind: ServiceAccount
metadata:
  name: amaima-backend
  namespace: amaima

---

apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: amaima-backend-role
  namespace: amaima
rules:
  - apiGroups: [""]
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list", "watch"]

---

apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: amaima-backend-rolebinding
  namespace: amaima
subjects:
  - kind: ServiceAccount
    name: amaima-backend
    namespace: amaima
roleRef:
  kind: Role
  name: amaima-backend-role
  apiGroup: rbac.authorization.k8s.io

---

apiVersion: v1
kind: Service
metadata:
  name: amaima-backend
  namespace: amaima
  labels:
    app.kubernetes.io/name: amaima-backend
spec:
  type: ClusterIP
  ports:
    - port: 8000
      targetPort: 8000
      name: http
  selector:
    app.kubernetes.io/name: amaima-backend
```

### Frontend Deployment

```yaml
# ============================================
# AMAIMA Frontend Deployment Configuration
# ============================================

apiVersion: apps/v1
kind: Deployment
metadata:
  name: amaima-frontend
  namespace: amaima
  labels:
    app.kubernetes.io/name: amaima-frontend
    app.kubernetes.io/component: frontend
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: amaima-frontend
  template:
    metadata:
      labels:
        app.kubernetes.io/name: amaima-frontend
    spec:
      containers:
        - name: frontend
          image: amaima/frontend:5.0.0
          imagePullPolicy: Always
          env:
            - name: NEXT_PUBLIC_API_URL
              value: "https://api.amaima.ai"
          ports:
            - containerPort: 3000
              name: http
          resources:
            requests:
              memory: "256Mi"
              cpu: "100m"
            limits:
              memory: "1Gi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /health
              port: 3000
            initialDelaySeconds: 10
            periodSeconds: 15
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health
              port: 3000
            initialDelaySeconds: 5
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3

---

apiVersion: v1
kind: Service
metadata:
  name: amaima-frontend
  namespace: amaima
  labels:
    app.kubernetes.io/name: amaima-frontend
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: 3000
      name: http
  selector:
    app.kubernetes.io/name: amaima-frontend
```

### Horizontal Pod Autoscaler

```yaml
# ============================================
# AMAIMA Horizontal Pod Autoscaler Configuration
# ============================================

apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: amaima-backend-hpa
  namespace: amaima
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: amaima-backend
  minReplicas: 3
  maxReplicas: 15
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Percent
          value: 100
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60

---

apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: amaima-frontend-hpa
  namespace: amaima
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: amaima-frontend
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### Ingress Configuration

```yaml
# ============================================
# AMAIMA Ingress Configuration
# ============================================

apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: amaima-ingress
  namespace: amaima
  annotations:
    kubernetes.io/ingress.class: nginx
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "30"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "300"
    nginx.ingress.kubernetes.io/websocket-services: "amaima-backend"
    nginx.ingress.kubernetes.io/configuration-snippet: |
      more_set_headers "Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' https://api.amaima.ai wss://api.amaima.ai; frame-ancestors 'self';";
      more_set_headers "X-Frame-Options: SAMEORIGIN";
      more_set_headers "X-Content-Type-Options: nosniff";
      more_set_headers "X-XSS-Protection: 1; mode=block";
spec:
  tls:
    - hosts:
        - amaima.ai
        - www.amaima.ai
        - api.amaima.ai
      secretName: amaima-tls-secret
  rules:
    - host: amaima.ai
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: amaima-frontend
                port:
                  number: 80
    - host: www.amaima.ai
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: amaima-frontend
                port:
                  number: 80
    - host: api.amaima.ai
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: amaima-backend
                port:
                  number: 8000
          - path: /ws
            pathType: Prefix
            backend:
              service:
                name: amaima-backend
                port:
                  number: 8000
          - path: /metrics
            pathType: Exact
            backend:
              service:
                name: amaima-backend
                port:
                  number: 8000

---

apiVersion: v1
kind: Secret
metadata:
  name: amaima-tls-secret
  namespace: amaima
type: kubernetes.io/tls
data:
  tls.crt: ${TLS_CERT_BASE64}
  tls.key: ${TLS_KEY_BASE64}
```

---

## 5. GitHub Actions Workflows

### Backend CI/CD Workflow

```yaml
# ============================================
# AMAIMA Backend CI/CD Workflow
# ============================================

name: AMAIMA Backend CI/CD

on:
  push:
    branches: [main, develop]
    paths:
      - 'backend/**'
      - '.github/workflows/backend-ci.yml'
  pull_request:
    branches: [main, develop]
    paths:
      - 'backend/**'
      - '.github/workflows/backend-ci.yml'

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}/amaima-backend

jobs:
  test:
    runs-on: ubuntu-latest
    container: python:3.10-slim

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r backend/requirements.txt
          pip install pytest pytest-asyncio pytest-cov httpx

      - name: Run linter
        run: |
          pip install ruff black
          ruff check backend/
          black --check backend/

      - name: Run type checker
        run: |
          pip install mypy
          mypy backend/

      - name: Run unit tests
        run: |
          pytest backend/tests/unit -v --cov=backend --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./coverage.xml
          fail_ci_if_error: false

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata for Docker
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha
            type=ref,event=branch
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    environment:
      name: staging
      url: https://staging.api.amaima.ai

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Update Kubernetes manifests
        run: |
          sed -i 's|amaima/backend:.*|amaima/backend:${{ github.sha }}|g' kubernetes/backend-deployment.yaml

      - name: Deploy to Kubernetes
        uses: azure/k8s-deploy@v4
        with:
          manifests: |
            kubernetes/backend-deployment.yaml
            kubernetes/backend-service.yaml
          images: |
            ghcr.io/${{ github.repository }}/amaima-backend:${{ github.sha }}
          namespace: amaima
          kubectl: kubectl

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    environment:
      name: production
      url: https://api.amaima.ai
    permissions:
      contents: read
      packages: read

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Configure kubectl for production
        uses: azure/k8s-set-context@v4
        with:
          kubeconfig: ${{ secrets.KUBECONFIG_PRODUCTION }}

      - name: Deploy to production
        run: |
          kubectl set image deployment/amaima-backend backend=ghcr.io/${{ github.repository }}/amaima-backend:${{ github.sha }} -n amaima
          kubectl rollout status deployment/amaima-backend -n amaima --timeout=10m
```

### Frontend CI/CD Workflow

```yaml
# ============================================
# AMAIMA Frontend CI/CD Workflow
# ============================================

name: AMAIMA Frontend CI/CD

on:
  push:
    branches: [main, develop]
    paths:
      - 'frontend/**'
      - '.github/workflows/frontend-ci.yml'
  pull_request:
    branches: [main, develop]
    paths:
      - 'frontend/**'
      - '.github/workflows/frontend-ci.yml'

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}/amaima-frontend

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        working-directory: ./frontend
        run: npm ci

      - name: Run linter
        working-directory: ./frontend
        run: npm run lint

      - name: Run type checker
        working-directory: ./frontend
        run: npm run type-check

      - name: Run unit tests
        working-directory: ./frontend
        run: npm run test -- --coverage

      - name: Run e2e tests
        working-directory: ./frontend
        run: npm run test:e2e
        env:
          NEXT_PUBLIC_API_URL: http://localhost:8000

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata for Docker
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha
            type=ref,event=branch
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    environment:
      name: staging
      url: https://staging.amaima.ai

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Update Kubernetes manifests
        run: |
          sed -i 's|amaima/frontend:.*|amaima/frontend:${{ github.sha }}|g' kubernetes/frontend-deployment.yaml

      - name: Deploy to Kubernetes
        uses: azure/k8s-deploy@v4
        with:
          manifests: |
            kubernetes/frontend-deployment.yaml
            kubernetes/frontend-service.yaml
          images: |
            ghcr.io/${{ github.repository }}/amaima-frontend:${{ github.sha }}
          namespace: amaima
          kubectl: kubectl

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    environment:
      name: production
      url: https://amaima.ai

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Configure kubectl for production
        uses: azure/k8s-set-context@v4
        with:
          kubeconfig: ${{ secrets.KUBECONFIG_PRODUCTION }}

      - name: Deploy to production
        run: |
          kubectl set image deployment/amaima-frontend frontend=ghcr.io/${{ github.repository }}/amaima-frontend:${{ github.sha }} -n amaima
          kubectl rollout status deployment/amaima-frontend -n amaima --timeout=5m
```

### Android CI/CD Workflow

```yaml
# ============================================
# AMAIMA Android CI/CD Workflow
# ============================================

name: AMAIMA Android CI/CD

on:
  push:
    branches: [main, develop]
    paths:
      - 'android/**'
      - '.github/workflows/android-ci.yml'
  pull_request:
    branches: [main, develop]
    paths:
      - 'android/**'
      - '.github/workflows/android-ci.yml'
  workflow_dispatch:
    inputs:
      variant:
        description: 'Build variant (debug/release)'
        required: false
        default: 'debug'

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up JDK
        uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '17'

      - name: Set up Android SDK
        uses: android-actions/setup-android@v3

      - name: Cache Gradle packages
        uses: actions/cache@v4
        with:
          path: |
            ~/.gradle/caches
            ~/.gradle/wrapper
            ~/.android/build-cache
          key: ${{ runner.os }}-gradle-${{ hashFiles('android/**/build.gradle.kts') }}
          restore-keys: |
            ${{ runner.os }}-gradle-

      - name: Run lint
        working-directory: ./android
        run: ./gradlew lint

      - name: Run unit tests
        working-directory: ./android
        run: ./gradlew testDebugUnitTest

      - name: Upload test results
        uses: actions/upload-artifact@v4
        with:
          name: android-test-results
          path: android/app/build/test-results/

  build-debug:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up JDK
        uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '17'

      - name: Set up Android SDK
        uses: android-actions/setup-android@v3

      - name: Build debug APK
        working-directory: ./android
        run: ./gradlew assembleDebug

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: amaima-debug.apk
          path: android/app/build/outputs/apk/debug/

  build-release:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'workflow_dispatch' || github.ref == 'refs/heads/release'
    permissions:
      contents: read
      packages: read

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up JDK
        uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '17'

      - name: Set up Android SDK
        uses: android-actions/setup-android@v3

      - name: Decode keystore
        run: |
          echo "${{ secrets.RELEASE_KEYSTORE }}" | base64 -d > android/app/release.keystore
          echo "storePassword=${{ secrets.KEYSTORE_PASSWORD }}" > android/keystore.properties
          echo "keyPassword=${{ secrets.KEY_PASSWORD }}" >> android/keystore.properties
          echo "keyAlias=${{ secrets.KEY_ALIAS }}" >> android/keystore.properties

      - name: Build release APK
        working-directory: ./android
        run: ./gradlew assembleRelease

      - name: Upload release APK
        uses: actions/upload-artifact@v4
        with:
          name: amaima-release.apk
          path: android/app/build/outputs/apk/release/

      - name: Create GitHub release
        uses: softprops/action-gh-release@v2
        with:
          files: android/app/build/outputs/apk/release/amaima-release.apk
          tag_name: v${{ github.event.inputs.version }}
          generate_release_notes: true

  deploy-play-store:
    needs: build-release
    runs-on: ubuntu-latest
    if: github.event_name == 'workflow_dispatch'
    permissions:
      contents: read
      id-token: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Download release APK
        uses: actions/download-artifact@v4
        with:
          name: amaima-release.apk

      - name: Authenticate to Google Play
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GOOGLE_PLAY_SERVICE_ACCOUNT }}

      - name: Deploy to Google Play
        uses: r0adkll/upload-google-play@v1
        with:
          package-name: ai.amaima.app
          release-file: amaima-release.apk
          track: internal
          status: completed
```

---

## 6. Deployment Scripts

### Health Check Script

```bash
#!/bin/bash
# ============================================
# AMAIMA Health Check Script
# ============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

# Counters
PASSED=0
FAILED=0

# Function to print status
print_status() {
    local service=$1
    local status=$2
    local message=$3
    
    if [ "$status" = "OK" ]; then
        echo -e "${GREEN}✓${NC} $service: $message"
        ((PASSED++))
    else
        echo -e "${RED}✗${NC} $service: $message"
        ((FAILED++))
    fi
}

echo "========================================"
echo "AMAIMA Health Check"
echo "========================================"
echo ""

# Check PostgreSQL
echo "Checking PostgreSQL..."
if pg_isready -h $POSTGRES_HOST -p $POSTGRES_PORT -q 2>/dev/null; then
    print_status "PostgreSQL" "OK" "Database is responding"
else
    print_status "PostgreSQL" "FAIL" "Database is not responding"
fi

# Check Redis
echo "Checking Redis..."
if redis-cli -h $REDIS_HOST -p $REDIS_PORT ping 2>/dev/null | grep -q "PONG"; then
    print_status "Redis" "OK" "Cache server is responding"
else
    print_status "Redis" "FAIL" "Cache server is not responding"
fi

# Check Backend API
echo "Checking Backend API..."
if curl -sf "$BACKEND_URL/health" > /dev/null 2>&1; then
    RESPONSE=$(curl -sf "$BACKEND_URL/health" 2>/dev/null)
    if echo "$RESPONSE" | grep -q '"status":"healthy"'; then
        print_status "Backend API" "OK" "API is healthy"
    else
        print_status "Backend API" "WARN" "API responded but status is not healthy"
    fi
else
    print_status "Backend API" "FAIL" "API is not responding"
fi

# Check Frontend
echo "Checking Frontend..."
if curl -sf "$FRONTEND_URL/health" > /dev/null 2>&1; then
    print_status "Frontend" "OK" "Frontend is serving"
else
    print_status "Frontend" "FAIL" "Frontend is not serving"
fi

# Check WebSocket
echo "Checking WebSocket..."
WS_RESPONSE=$(curl -sf "$BACKEND_URL/ws/health" 2>/dev/null || echo "")
if [ -n "$WS_RESPONSE" ]; then
    print_status "WebSocket" "OK" "WebSocket endpoint is accessible"
else
    print_status "WebSocket" "WARN" "WebSocket health check not available"
fi

# Check Backend metrics endpoint
echo "Checking Prometheus metrics..."
if curl -sf "$BACKEND_URL/metrics" > /dev/null 2>&1; then
    METRICS_COUNT=$(curl -sf "$BACKEND_URL/metrics" 2>/dev/null | grep -c "^amaima_" || echo "0")
    print_status "Prometheus metrics" "OK" "Found $METRICS_COUNT AMAIMA metrics"
else
    print_status "Prometheus metrics" "FAIL" "Metrics endpoint not accessible"
fi

# Summary
echo ""
echo "========================================"
echo "Health Check Summary"
echo "========================================"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Health check failed!${NC}"
    exit 1
else
    echo -e "${GREEN}All checks passed!${NC}"
    exit 0
fi
```

### Database Migration Script

```bash
#!/bin/bash
# ============================================
# AMAIMA Database Migration Script
# ============================================

set -e

# Configuration
DATABASE_URL="${DATABASE_URL:-postgresql://amaima:amaima@localhost:5432/amaima}"
MIGRATIONS_DIR="${MIGRATIONS_DIR:-./migrations}"

echo "========================================"
echo "AMAIMA Database Migration"
echo "========================================"

# Check for Alembic
if ! command -v alembic &> /dev/null; then
    echo "Installing Alembic..."
    pip install alembic
fi

# Run migrations
echo "Running database migrations..."
alembic upgrade head

echo "Migrations completed successfully!"
```

### Deployment Script

```bash
#!/bin/bash
# ============================================
# AMAIMA Deployment Script
# ============================================

set -e

# Configuration
ENVIRONMENT="${ENVIRONMENT:-development}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================"
echo "AMAIMA Deployment Script"
echo "Environment: $ENVIRONMENT"
echo "========================================"

# Pre-deployment checks
echo ""
echo "Running pre-deployment checks..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

# Check Docker Compose
if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    exit 1
fi

# Check for .env file
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found. Using default values.${NC}"
fi

# Pull latest images
echo ""
echo "Pulling latest images..."
docker compose -f $COMPOSE_FILE pull

# Build services
echo ""
echo "Building services..."
docker compose -f $COMPOSE_FILE build --no-cache

# Run database migrations
echo ""
echo "Running database migrations..."
docker compose -f $COMPOSE_FILE exec -T backend python /app/scripts/migrate.py || true

# Stop existing services
echo ""
echo "Stopping existing services..."
docker compose -f $COMPOSE_FILE down

# Start services
echo ""
echo "Starting services..."
docker compose -f $COMPOSE_FILE up -d

# Wait for services to be healthy
echo ""
echo "Waiting for services to be healthy..."
sleep 10

# Run health check
echo ""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$SCRIPT_DIR/healthcheck.sh"

# Deployment complete
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Frontend: http://localhost:3000"
echo "Backend API: http://localhost:8000"
echo "API Documentation: http://localhost:8000/docs"
echo ""
```

---

## 7. Environment Configuration

### Development Environment Template

```bash
# ============================================
# AMAIMA Development Environment Variables
# ============================================

# Application
AMAIMA_ENV=development
DEBUG=true
LOG_LEVEL=DEBUG

# Database
POSTGRES_USER=amaima
POSTGRES_PASSWORD=amaima_secret
POSTGRES_DB=amaima
DATABASE_URL=postgresql://amaima:amaima_secret@localhost:5432/amaima

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT Authentication
JWT_SECRET_KEY=your-development-secret-key-change-in-production
JWT_ALGORITHM=RS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000

# Model Configuration
MODEL_CACHE_DIR=./models
TENSORRT_ENABLED=false

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=AMAIMA
NEXT_PUBLIC_APP_VERSION=5.0.0

# Observability
OBSERVABILITY_ENABLED=false
```

### Production Environment Template

```bash
# ============================================
# AMAIMA Production Environment Variables
# ============================================

# Application
AMAIMA_ENV=production
DEBUG=false
LOG_LEVEL=INFO

# Database - Use secure credentials from secrets manager
POSTGRES_USER=amaima
POSTGRES_DB=amaima
DATABASE_URL=postgresql://amaima:${POSTGRES_PASSWORD}@postgres:5432/amaima

# Redis
REDIS_URL=redis://redis:6379/0

# JWT Authentication - Use RS256 key pairs in production
JWT_SECRET_KEY=${JWT_PRIVATE_KEY_BASE64_DECODED}
JWT_ALGORITHM=RS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=https://amaima.ai,https://www.amaima.ai,https://api.amaima.ai

# Model Configuration
MODEL_CACHE_DIR=/app/models
TENSORRT_ENABLED=true

# Frontend
NEXT_PUBLIC_API_URL=https://api.amaima.ai
NEXT_PUBLIC_APP_NAME=AMAIMA
NEXT_PUBLIC_APP_VERSION=5.0.0

# Observability
OBSERVABILITY_ENABLED=true
LOG_LEVEL=INFO
```

---

## 8. Deployment Verification Checklist

### Pre-Deployment Verification

- [ ] All environment variables configured
- [ ] Database credentials secured
- [ ] JWT keys generated and secured
- [ ] TLS certificates obtained
- [ ] DNS records configured
- [ ] Firewall rules updated
- [ ] Monitoring alerts configured
- [ ] Backup systems tested
- [ ] Security scan completed
- [ ] Performance baseline established

### Post-Deployment Verification

- [ ] All containers running
- [ ] Health checks passing
- [ ] Database migrations applied
- [ ] Redis connection verified
- [ ] API documentation accessible
- [ ] Frontend serving correctly
- [ ] WebSocket connections working
- [ ] Metrics endpoint responding
- [ ] Logging functional
- [ ] Performance metrics captured
- [ ] Alerting tested
- [ ] Backup scheduled confirmed
- [ ] Rollback plan verified

This complete deployment package provides all configuration files necessary to deploy the AMAIMA platform across development, staging, and production environments using Docker Compose and Kubernetes orchestration.
