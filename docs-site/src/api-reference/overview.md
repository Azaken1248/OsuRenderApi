---
title: "API Overview"
description: "RESTful API reference for OsuRender — versioned endpoints, authentication, request/response formats, and interactive Swagger documentation."
---

# API Overview

The OsuRender API follows RESTful conventions with a versioned endpoint structure. All modern endpoints are prefixed with `/v1/`.

## Base URL

```
http://localhost:8727
```

In production, the API is served behind Cloudflare at your configured `API_BASE_URL`.

## Versioning

| Prefix | Status | Description |
|--------|--------|-------------|
| `/v1/` | **Active** | Current stable API |
| `/` (root) | **Legacy** | Backward-compatible endpoints for the monolithic application |

## Content Types

| Endpoint | Request Type | Response Type |
|----------|-------------|---------------|
| `POST /v1/render` | `multipart/form-data` | `application/json` |
| `POST /v1/skins/upload` | `multipart/form-data` | `application/json` |
| All other endpoints | — | `application/json` |

## Request IDs

Every request is assigned a correlation ID for tracing. You can provide your own:

```
X-Request-ID: my-custom-id
```

If omitted, the API generates an 8-character UUID. The ID is returned in the response header:

```
X-Request-ID: a1b2c3d4
```

## HATEOAS Links

Job creation responses include navigable links:

```json
{
  "job_id": "550e8400-...",
  "status": "queued",
  "links": {
    "status": "/v1/jobs/550e8400-..."
  }
}
```

## Interactive Documentation

Below is the live Swagger UI playground. You can use it to test endpoints directly from your browser.

<div class="swagger-container">
  <iframe src="https://render.azaken.com/api/docs" title="OsuRender API Swagger UI"></iframe>
</div>

You can also view the [ReDoc format](https://render.azaken.com/api/redoc) or download the [OpenAPI Spec](https://render.azaken.com/api/openapi.json).

## Authentication

Currently, the API does not require authentication tokens. Access control is managed through:

- **Rate limiting** per IP (via `CF-Connecting-IP` or remote address)
- **Per-IP concurrency limits** (max 2 active jobs)
- **Global queue circuit breakers** (max 100 queued, max 20 rendering)

See [Rate Limiting](/src/api-reference/rate-limiting) for details.

## Endpoint Summary

| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| `GET` | `/health` | Health check | — |
| `POST` | `/v1/render` | Submit replay for rendering | 5/min |
| `GET` | `/v1/jobs/{job_id}` | Get job status | — |
| `GET` | `/v1/jobs` | List all jobs (paginated) | — |
| `POST` | `/v1/jobs/{job_id}/webhook` | Modal completion callback | — |
| `GET` | `/v1/skins` | List available skins | — |
| `POST` | `/v1/skins/upload` | Upload a custom skin | 2/min |
| `GET` | `/v1/artifacts/{key}` | Download/stream artifacts | — |
