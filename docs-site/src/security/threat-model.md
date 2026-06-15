# Threat Model

This document outlines the anticipated threats to the OsuRender API and the corresponding mitigations in place.

## Unauthenticated Abuse

**Threat:** An attacker floods the API with render requests to exhaust compute resources or inflate cloud billing.

**Mitigations:**
- Strict rate limiting (5 requests/minute per IP)
- Strict concurrency limiting (max 2 active jobs per IP)
- Global queue limits (circuit breakers)
- Cloudflare WAF capabilities

## Webhook Spoofing

**Threat:** An attacker discovers the Modal webhook endpoint and sends fake completion payloads to manipulate job states.

**Mitigations:**
- **HMAC-SHA256 Signature:** The payload must be signed using a shared secret (`WEBHOOK_SECRET`)
- **Replay Protection:** The payload includes a timestamp and nonce. The API rejects payloads older than 5 minutes or if the nonce was already used.

## IP Spoofing

**Threat:** An attacker spoofs the `X-Forwarded-For` or `CF-Connecting-IP` headers to bypass rate limits.

**Mitigations:**
- The API assumes the environment is protected by a perimeter firewall that only allows Cloudflare IP ranges.
- If the origin is properly protected, `CF-Connecting-IP` is guaranteed to be set by Cloudflare and cannot be spoofed by the client.

## Resource Exhaustion (Zip Bombs)

**Threat:** An attacker uploads a tiny, highly-compressed `.osk` file that expands to terabytes of data, exhausting disk space or memory during extraction.

**Mitigations:**
- ZIP ratio validation (rejects if compressed:uncompressed ratio > 100)
- Hard limit on total uncompressed size (e.g., 1 GB)
- Limits on archive nesting depth
- See [Input Validation](/src/security/input-validation) for details.

## Path Traversal

**Threat:** An attacker uses `../` in a skin name or filename to overwrite system files or access artifacts belonging to other jobs.

**Mitigations:**
- Skin names are validated against `^[a-zA-Z0-9_ -]+$`
- The artifacts endpoint validates the requested prefix and key format before querying S3
- Object storage keys are generated securely using UUIDs

## Secret Leakage

**Threat:** A vulnerability in `danser-go` allows an attacker to execute arbitrary code or read environment variables (like database credentials).

**Mitigations:**
- `danser-go` is executed in an isolated container
- Subprocess environment allowlisting: The Python wrapper explicitly constructs the environment variables passed to `danser-go`, omitting sensitive variables like `DATABASE_URL` or `WEBHOOK_SECRET`.
