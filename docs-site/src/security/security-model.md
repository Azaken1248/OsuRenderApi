---
title: "Security Model"
description: "Defense-in-depth security architecture — HMAC verification, Cloudflare ingress, advisory locks, and input sanitization."
---

# Security Model

OsuRender API employs a defense-in-depth security model to protect the infrastructure from abuse and malicious payloads.

## Admission Control Hierarchy

Every render request passes through a strict sequence of checks before it is accepted into the system:

```mermaid
graph TD
    Request[Incoming Request] --> Ext{1. File Extension / Size}
    Ext -->|Invalid| R400[400/413 Error]
    Ext -->|Valid| OSR{2. osrparse Validation}
    
    OSR -->|Invalid| R415[415 Error]
    OSR -->|Valid| Rate{3. IP Rate Limit<br/>5 per min}
    
    Rate -->|Exceeded| R429[429 Error]
    Rate -->|Valid| Queue{4. Global Queue<br/>Limit Check}
    
    Queue -->|Full| R503[503 Error]
    Queue -->|OK| Lock[5. Acquire pg_advisory_xact_lock]
    
    Lock --> Active{6. Active Jobs for IP < 2?}
    
    Active -->|No| R429_2[429 Error]
    Active -->|Yes| Insert[7. DB Insert + Outbox Event]
    
    Insert --> S3[8. Upload to S3]
    
    S3 -->|Fails| R500[500 Error + Job FAILED]
    S3 -->|Succeeds| Accept[202 Accepted]
    
    style Accept fill:#22c55e20,stroke:#22c55e
    style R400 fill:#ef444420,stroke:#ef4444
    style R415 fill:#ef444420,stroke:#ef4444
    style R429 fill:#f59e0b20,stroke:#f59e0b
    style R429_2 fill:#f59e0b20,stroke:#f59e0b
    style R503 fill:#ef444420,stroke:#ef4444
    style R500 fill:#ef444420,stroke:#ef4444
```

## Layers of Defense

### 1. Perimeter (Cloudflare)
- The API should only accept traffic from Cloudflare IP ranges
- Cloudflare provides DDoS protection and Web Application Firewall (WAF) capabilities
- `CF-Connecting-IP` header is used for rate limiting

### 2. Rate Limiting (SlowApi)
- Prevents API abuse and brute-force attacks
- Backed by Redis for high performance across multiple API instances

### 3. Concurrency Limits (PostgreSQL)
- Prevents a single user from hogging the render queue
- Uses `pg_advisory_xact_lock` to prevent race conditions where a user submits multiple jobs simultaneously

### 4. Input Validation (FastAPI/Pydantic)
- Strict validation of all input parameters
- Ensures filenames and skin names don't contain path traversal characters

### 5. File Validation
- Replay files are parsed with `osrparse` to ensure they are valid osu!standard replays
- Skin archives are subjected to rigorous structural checks (see [Input Validation](/src/security/input-validation))

### 6. Subprocess Sandboxing
- `danser-go` is executed in a controlled environment
- Only a strict whitelist of environment variables is passed to the subprocess, preventing secret leakage

### 7. Error Masking
- When `DEBUG=false`, internal error messages (e.g., database connection errors, stack traces) are replaced with a generic message to prevent information disclosure.
