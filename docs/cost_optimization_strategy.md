# OsuRender API - Cost Optimization & Infrastructure Strategy

## 1. Overview
The primary financial directive for the OsuRender API is to operate **strictly within the $30/month free compute credits** provided by the Modal platform. To achieve this, the architecture, codebase, and infrastructure choices must be ruthlessly optimized for efficiency.

Furthermore, **this project will NOT rely on any Amazon Web Services (AWS) products under any circumstances.** No AWS S3, no AWS RDS, no EC2, and no ElastiCache. All dependencies must be strictly limited to free-tier SaaS alternatives or native Modal capabilities.

## 2. Infrastructure Constraints & AWS Alternatives

### 2.1 Object & Asset Storage
- **Prohibited**: AWS S3.
- **Solution**: 
  - **Modal Volumes**: All short-term generated `.mp4` files, cached `.osz` beatmaps, and `.osk` skins must be saved in Modal Network Volumes. Modal Volumes are extremely cheap (pennies per GB) and immediately accessible across all serverless functions.
  - **Cloudflare R2**: If long-term external storage is absolutely required for public URL hosting, Cloudflare R2 will be used (which offers 10 GB of free storage and zero egress fees).

### 2.2 Relational Database
- **Prohibited**: AWS RDS / Aurora.
- **Solution**: 
  - **Supabase (Free Tier)** or **Neon Serverless Postgres**: Both provide robust, scalable PostgreSQL databases with generous free tiers that will easily accommodate the metadata requirements for millions of render jobs.

### 2.3 Message Broker / Redis
- **Prohibited**: AWS ElastiCache / SQS.
- **Solution**: 
  - **Upstash (Serverless Redis)** or **Redis Labs Cloud (Free Tier)**: Both provide free-tier Redis clusters suitable for managing task queues asynchronously without incurring monthly baseline costs.

## 3. Maximizing Output on the $30 Free Credit

To ensure the API can output the maximum number of renders per month (target: 150-250 at 4K, or 800-1000+ at 1080p) without hitting the paywall, the following optimizations must be implemented in the code:

### 3.1 Strict Compute Isolation & Fast Spin-down
- **Ephemeral Workers**: GPU instances (`gpu="T4"`) must ONLY be active during the exact duration of the `danser-go` process. The worker must accept the job, download assets quickly, render, upload, and terminate immediately.
- **Pre-Flight Checks on CPU**: Any validation, beatmap API fetching, or metadata resolution should happen on cheap CPU instances (or within the API Gateway) *before* spinning up the expensive T4 GPU container.

### 3.2 Aggressive Asset Caching (Modal Volumes)
- **Beatmap Caching**: Beatmaps (`.osz` files) can be 20MB to 100MB+. Downloading them on a GPU instance wastes expensive compute seconds. All downloaded beatmaps must be saved to a persistent `modal.Volume` so future renders of the same map can access them instantly.
- **Skin Caching**: Similarly, user skins must be extracted once and mounted persistently across all GPU workers.

### 3.3 Quality & Duration Throttling
- **1080p Default**: To stretch the compute credits, 1080p should be the default resolution. 4K renders take ~2-3x longer to process. 
- **Map Length Limits**: Implement strict limits on the length of `.osr` replays (e.g., maximum map duration of 5 or 6 minutes) to prevent users from submitting 30-minute marathon maps that burn through the daily compute budget.

### 3.4 Lean API Gateway
- The FastAPI frontend gateway must be configured with minimal CPU and RAM (e.g., 0.1 CPU, 128MB RAM). Since it is entirely stateless and only proxies requests to the database and queue, it does not need heavy resources.

### 3.5 Fallback & Cost Circuit Breakers
- Implement a script or API route to check the Modal billing status via their APIs (if available) or enforce an internal quota system in the PostgreSQL database. If the API approaches the $28 mark for the month, gracefully reject new rendering requests to ensure the account is not unexpectedly billed.
