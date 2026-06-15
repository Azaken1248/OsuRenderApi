# Error Codes

All API errors return a JSON response with a `detail` field:

```json
{
  "detail": "Human-readable error message"
}
```

::: info Production Mode
When `DEBUG=false`, internal error messages are masked with: `"An internal rendering error occurred."` to prevent information leakage.
:::

## HTTP Status Codes

### Client Errors (4xx)

| Status | Code | When |
|--------|------|------|
| **400** | Bad Request | Invalid file extension, empty file, malformed request |
| **401** | Unauthorized | Missing or invalid webhook `X-Signature` header |
| **403** | Forbidden | Invalid artifact prefix (path traversal attempt) |
| **404** | Not Found | Job or artifact doesn't exist |
| **413** | Payload Too Large | Replay > 50 MB or skin > 200 MB |
| **415** | Unsupported Media Type | Invalid replay structure (osrparse failure) or non-ZIP skin |
| **422** | Unprocessable Entity | Pydantic validation failure, invalid skin archive structure |
| **429** | Too Many Requests | Rate limit exceeded or per-IP job limit reached |

### Server Errors (5xx)

| Status | Code | When |
|--------|------|------|
| **500** | Internal Server Error | Unhandled exception, storage upload failure, or webhook misconfiguration |
| **503** | Service Unavailable | Render queue at capacity or infrastructure overloaded |

## Error Categories

### Validation Errors

```json
// File extension
{ "detail": "File must be an osu! replay (.osr) file." }

// Empty file
{ "detail": "Uploaded replay file is empty." }

// File too large
{ "detail": "Replay file exceeds maximum size of 50MB." }

// Invalid replay
{ "detail": "Invalid replay file. The structure is corrupted or unsupported." }

// Invalid skin name
{ "detail": "Invalid skin name. Only alphanumeric characters, underscores, hyphens, and spaces are allowed." }

// Invalid resolution
{ "detail": "Resolution must be one of: {'1080p', '4k'}" }
```

### Rate Limiting Errors

```json
// SlowApi rate limit
{ "detail": "Rate limit exceeded: 5 per 1 minute" }

// Per-IP concurrency
{ "detail": "You already have 2 active render jobs. Please wait for them to finish before queueing more." }
```

### Capacity Errors

```json
// Queue full
{ "detail": "The render queue is currently full. Please try again later." }

// Rendering at capacity
{ "detail": "The render infrastructure is at maximum capacity. Please try again later." }
```
