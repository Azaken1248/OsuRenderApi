# Reporting Vulnerabilities

Security is a top priority for OsuRender API. We appreciate the efforts of the security community in helping us keep the project safe.

## Responsible Disclosure

If you believe you have found a security vulnerability in OsuRender API, please report it to us **privately** before opening a public GitHub issue.

Please send an email to the project maintainers (or use GitHub Security Advisories if enabled on the repository) with the following details:

- A description of the vulnerability
- Steps to reproduce the issue
- Potential impact (e.g., data exfiltration, RCE, DoS)
- Any suggested mitigations

## Scope

The following components are in scope for security reports:
- The FastAPI application and endpoints
- The transactional outbox dispatcher
- The Celery worker orchestration logic
- The deployment configurations (`docker-compose.yml`, Dockerfile)

**Out of scope:**
- Vulnerabilities in `danser-go` itself (please report these to the [danser-go repository](https://github.com/Wieku/danser-go))
- Vulnerabilities in underlying infrastructure (e.g., PostgreSQL, Redis, Cloudflare, Modal) unless the vulnerability is caused by a misconfiguration in our code.

## Response Timeline

We will make our best effort to:
1. Acknowledge receipt of your report within 48 hours.
2. Verify the vulnerability and provide a timeline for a fix within 1 week.
3. Keep you informed of progress as we develop and deploy the fix.
4. Publicly acknowledge your contribution (if desired) once the fix is released.
