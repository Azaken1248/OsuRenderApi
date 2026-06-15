---
title: "Production Deployment"
description: "Production deployment guide for OsuRender API — infrastructure requirements, scaling strategies, TLS, and health check configuration."
---

# Production Deployment

This guide covers deploying OsuRender API to a production environment.

## Infrastructure Requirements

| Component | Recommended Service | Free Tier? |
|-----------|-------------------|------------|
| **PostgreSQL** | Supabase / Neon Serverless | <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> |
| **Redis** | Upstash / Redis Labs | <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> |
| **Object Storage** | Cloudflare R2 | <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> (10 GB + zero egress) |
| **API Hosting** | VPS / Railway / Render | Varies |
| **GPU Compute** | Modal | <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> ($30/month credits) |
| **CDN/Proxy** | Cloudflare | <img src="/icons/check.svg" width="16" style="display: inline-block; vertical-align: middle; margin-bottom: 2px;" /> |

## Deployment Steps

### 1. Provision Infrastructure

Set up external services and collect credentials:

```env
DATABASE_URL=postgresql+asyncpg://user:pass@db.supabase.co:5432/osurender
DATABASE_URL_SYNC=postgresql+psycopg2://user:pass@db.supabase.co:5432/osurender
REDIS_URL=redis://default:pass@us1-abc.upstash.io:6379
STORAGE_ENDPOINT=your-account.r2.cloudflarestorage.com
STORAGE_ACCESS_KEY=your_r2_access_key
STORAGE_SECRET_KEY=your_r2_secret_key
STORAGE_USE_SSL=true
```

### 2. Deploy Application

```bash
# Build and push Docker image
docker build -t osurender-api:latest .
docker push your-registry/osurender-api:latest

# Or deploy directly with Docker Compose on a VPS
scp docker-compose.yml .env user@server:~/osurender/
ssh user@server "cd osurender && docker-compose up -d"
```

### 3. Deploy Modal GPU Workers

```bash
# Create Modal secrets
modal secret create osurender-secrets \
  S3_ENDPOINT="https://your-account.r2.cloudflarestorage.com" \
  S3_ACCESS_KEY="your_r2_key" \
  S3_SECRET_KEY="your_r2_secret" \
  WEBHOOK_SECRET="your_webhook_secret"

# Deploy the GPU worker
modal deploy src.modal_deploy
```

### 4. Configure Cloudflare

1. Set up DNS to point to your server
2. Enable **Cloudflare proxy** (orange cloud)
3. Set up **firewall rules** to only allow Cloudflare IPs to your origin
4. Enable **Authenticated Origin Pulls** for extra security

## Cost Optimization

The architecture is designed to run within Modal's **$30/month free compute credits**:

| Strategy | Impact |
|----------|--------|
| **1080p default** | ~2x faster renders than 4K |
| **Beatmap caching** (Modal Volumes) | Avoids re-downloading 20-100 MB beatmaps |
| **Skin caching** (Modal Volumes) | Extract once, reuse across renders |
| **Pre-flight on CPU** | Validation and API calls on cheap CPU instances |
| **Fast spin-down** | GPU active only during danser execution |

Expected capacity on free tier: **150-250 renders/month at 4K** or **800-1000+ at 1080p**.

## Security Checklist

- [ ] `DEBUG=false` in production
- [ ] `WEBHOOK_SECRET` is a strong random string
- [ ] `CORS_ORIGINS` restricted to your domains
- [ ] Cloudflare-only ingress (firewall non-CF IPs)
- [ ] PostgreSQL credentials are unique and strong
- [ ] R2 credentials have minimal permissions
- [ ] Modal secrets are configured securely
