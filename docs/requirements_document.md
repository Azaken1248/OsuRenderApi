# OsuRender API - Requirement Document

## 1. Introduction
The OsuRender API is a service that allows users to submit osu! replays (`.osr` files) and receive high-quality rendered videos using the `danser-go` engine. The current implementation relies on a basic monolithic architecture. The goal of this project is to refactor the codebase to meet industry-standard design patterns, ensuring security, reliability, scalability, and robust concurrent request handling.

## 2. Business Requirements
- **BR-1**: Provide a reliable platform for rendering `osu!` replays without manual intervention.
- **BR-2**: Scale seamlessly to accommodate variable loads, specially during peak hours (e.g., after large osu! tournaments).
- **BR-3**: Provide a clean, consistent RESTful API that third-party applications or frontend clients can easily consume.
- **BR-4**: Protect user data and the underlying infrastructure from malicious input.

## 3. Functional Requirements
- **FR-1**: **Job Submission**: Users must be able to upload a `.osr` file with rendering configuration (resolution, skin, background dim, motion blur, etc.) to queue a render job.
- **FR-2**: **Job Management**: Users must be able to query the status of a specific job (queued, downloading, rendering, completed, failed) and view rendering progress percentage.
- **FR-3**: **Media Delivery**: The system must provide a way to download or stream the rendered `.mp4` output and fetch generated video thumbnails.
- **FR-4**: **Asset Management**: The system must support uploading custom `.osk` skin files and caching downloaded `.osz` beatmap files securely.
- **FR-5**: **Log Management**: Job execution logs must be accessible for debugging failed renders.

## 4. Non-Functional Requirements (NFRs)

### 4.1 Scalability
- **NFR-1**: **Horizontal Scaling**: The API backend and render workers must be decoupled to allow horizontal scaling of workers based on the job queue length.
- **NFR-2**: **Stateless APIs**: The API tier must be fully stateless. State must be preserved in a robust data store (e.g., PostgreSQL/Redis), not in-memory dictionaries.
- **NFR-3**: **Concurrent Job Processing**: The system must be capable of processing multiple render jobs simultaneously across multiple distributed GPU workers.

### 4.2 Reliability
- **NFR-4**: **Fault Tolerance**: Worker crashes must not cause data loss or silent failures. Jobs must be requeued or appropriately marked as failed with detailed logs.
- **NFR-5**: **Rate Limiting & Throttling**: The system must enforce API rate limits per user/IP to prevent abuse and starvation of system resources.
- **NFR-6**: **Timeout Handling**: Long-running renders must have configurable hard timeouts to free up frozen GPU instances.

### 4.3 Security
- **NFR-7**: **Input Validation**: All uploaded files (`.osr`, `.osk`) must be aggressively validated to prevent directory traversal, execution of malicious payloads, and excessive file sizes.
- **NFR-8**: **Isolated Execution**: Render workers should operate in isolated containerized environments (e.g., Docker) with dropped privileges to mitigate the impact of a compromised rendering engine.
- **NFR-9**: **Data Protection**: API keys and secrets must be injected securely via secret managers (like Modal Secrets, AWS Secrets Manager, or HashiCorp Vault), never hardcoded.

## 5. Data Requirements
- **Persistent Metadata**: Job details (status, created_at, configurations, user ID) must be stored in a relational database.
- **Asset Storage**: Heavy binary files (Beatmaps, Skins, rendered videos) should be stored in an Object Storage service (e.g., AWS S3, Cloudflare R2, or a distributed volume system) rather than local file systems to allow stateless API access.

## 6. Constraints
- Must integrate with `danser-go` via CLI.
- Must execute efficiently on GPU-backed cloud hardware (e.g., Modal with NVIDIA T4 GPUs).
