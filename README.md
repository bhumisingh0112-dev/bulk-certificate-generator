# Bulk Certificate Generator API

A backend API for submitting one bulk certificate-generation request, validating recipients, generating PDF certificates from a single predefined template, tracking job progress, isolating individual generation failures, and retrieving the generated files.

## Why this design

The assignment is centered on bulk processing, reliable failure handling, status tracking, certificate retrieval, and clean Python backend code. This implementation uses:

- **FastAPI** for the HTTP API and automatic OpenAPI/Swagger documentation.
- **SQLAlchemy + SQLite** as the default relational persistence layer. The database URL is configurable; SQLAlchemy also makes a later PostgreSQL migration straightforward after adding the appropriate database driver.
- **ReportLab** for deterministic PDF certificate generation using one predefined template.
- **FastAPI BackgroundTasks** for simple asynchronous-after-response generation without introducing queue infrastructure that is unnecessary for an assignment-sized deployment.
- **Per-recipient status records** so one failed certificate does not stop valid certificates in the same bulk request.

For a high-volume production system, the main upgrade would be moving background generation to a durable queue such as Celery/RQ with Redis or RabbitMQ and storing generated files in object storage such as S3.

## Features

- Submit many recipients in one bulk API request.
- Validate request shape and recipient email addresses.
- Detect duplicate emails and duplicate certificate IDs within a job.
- Automatically create a certificate ID when one is not supplied.
- Generate one PDF per valid recipient.
- Track `PENDING`, `PROCESSING`, `COMPLETED`, `COMPLETED_WITH_ERRORS`, and `FAILED` job states.
- Track per-recipient `PENDING`, `PROCESSING`, `SUCCESS`, and `FAILED` states.
- Continue processing after an individual generation failure.
- List successful certificates for a job.
- Download an individual certificate PDF.
- Download all successful certificates for a job as a ZIP file.
- Interactive Swagger documentation at `/docs`.
- Automated tests for all assignment-critical behavior.
- Docker support.

## Project structure

```text
.
├── app/
│   ├── api/routes.py
│   ├── core/config.py
│   ├── db/
│   │   ├── base.py
│   │   └── session.py
│   ├── models/job.py
│   ├── schemas/job.py
│   ├── services/
│   │   ├── certificate_service.py
│   │   └── job_service.py
│   └── main.py
├── examples/request.json
├── generated/.gitkeep
├── tests/
│   ├── conftest.py
│   └── test_jobs.py
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── pytest.ini
├── requirements.txt
└── README.md
```

## Local setup

### 1. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the API

```bash
uvicorn app.main:app --reload
```

The API will be available at:

- API: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

No manual database setup is required for the default SQLite configuration. Tables are created when the application starts.

## Docker

Build and run with Docker Compose:

```bash
docker compose up --build
```

Open `http://127.0.0.1:8000/docs`.

The Docker Compose configuration stores the SQLite database and generated PDFs in a named volume so data survives container recreation.

## API

### 1. Create a bulk generation job

`POST /api/jobs`

Example body:

```json
{
  "certificate_title": "Certificate of Completion",
  "course_name": "Backend Engineering Workshop",
  "issuer_name": "Example Learning Academy",
  "issue_date": "2026-10-07",
  "recipients": [
    {
      "name": "Aarav Sharma",
      "email": "aarav@example.com",
      "certificate_id": "BE-001"
    },
    {
      "name": "Diya Verma",
      "email": "diya@example.com",
      "certificate_id": "BE-002"
    }
  ]
}
```

Example response (`202 Accepted`):

```json
{
  "id": "7ca3bce3-618e-4aa0-9702-585dfc8ca0fd",
  "status": "PENDING",
  "total_count": 2,
  "success_count": 0,
  "failed_count": 0,
  "processed_count": 0,
  "progress_percent": 0.0,
  "created_at": "2026-10-07T06:00:00",
  "updated_at": "2026-10-07T06:00:00"
}
```

Generation runs as a background task after the request is accepted.

### 2. Check job status and progress

`GET /api/jobs/{job_id}`

Example completed response:

```json
{
  "id": "7ca3bce3-618e-4aa0-9702-585dfc8ca0fd",
  "status": "COMPLETED",
  "total_count": 2,
  "success_count": 2,
  "failed_count": 0,
  "processed_count": 2,
  "progress_percent": 100.0,
  "created_at": "2026-10-07T06:00:00",
  "updated_at": "2026-10-07T06:00:02",
  "certificate_title": "Certificate of Completion",
  "course_name": "Backend Engineering Workshop",
  "issuer_name": "Example Learning Academy",
  "issue_date": "2026-10-07",
  "recipients": [
    {
      "id": "recipient-uuid",
      "name": "Aarav Sharma",
      "email": "aarav@example.com",
      "certificate_id": "BE-001",
      "status": "SUCCESS",
      "error_message": null
    }
  ]
}
```

The response exposes `processed_count` and `progress_percent`, derived from successful and failed recipient counts.

### 3. List generated certificates

`GET /api/jobs/{job_id}/certificates`

Returns only successfully generated certificates and a download URL for each one.

### 4. Download one certificate

`GET /api/certificates/{recipient_id}/download`

Returns the generated PDF.

### 5. Download all successful certificates

`GET /api/jobs/{job_id}/download`

Returns a ZIP containing all successful certificate PDFs for the job. This is a small convenience feature beyond the minimum requirement.

### 6. Health check

`GET /health`

```json
{"status":"ok"}
```

## Validation and failure handling

There are two validation levels:

1. **Request-level validation** — malformed job data such as an empty recipient list is rejected with HTTP `422`.
2. **Recipient-level validation** — an invalid email, duplicate email, or duplicate certificate ID is recorded as `FAILED` for that recipient while other valid recipients continue processing.

PDF rendering errors are also isolated to the affected recipient. The job becomes `COMPLETED_WITH_ERRORS` when at least one certificate succeeds and at least one fails.

## Running tests

```bash
pytest
```

The test suite covers:

- Creating a generation job.
- Request-level input validation.
- Invalid recipient isolation.
- PDF certificate generation.
- Job status/progress.
- Individual certificate generation failure isolation.
- Retrieving generated certificate PDFs.
- Bulk ZIP retrieval.

## Example cURL

Create a job:

```bash
curl -X POST "http://127.0.0.1:8000/api/jobs" \
  -H "Content-Type: application/json" \
  --data @examples/request.json
```

Then use the returned job ID:

```bash
curl "http://127.0.0.1:8000/api/jobs/<JOB_ID>"
```

List generated certificates:

```bash
curl "http://127.0.0.1:8000/api/jobs/<JOB_ID>/certificates"
```

Download all successful certificates:

```bash
curl -L "http://127.0.0.1:8000/api/jobs/<JOB_ID>/download" -o certificates.zip
```

## Processing flow

1. The client submits one request containing certificate metadata and many recipients.
2. A database job and recipient records are created.
3. Recipient validation failures are recorded without rejecting valid recipients.
4. The HTTP request returns `202 Accepted`.
5. A background task processes pending recipients one at a time.
6. Each generated PDF is saved under the job's storage directory.
7. Each recipient is marked `SUCCESS` or `FAILED` independently.
8. Job counters and final state are persisted.
9. The client polls the job endpoint and retrieves successful certificates when ready.

## Important design decisions and alternatives

### BackgroundTasks instead of Celery

FastAPI `BackgroundTasks` keeps the solution easy to run and review while still avoiding certificate generation inside the response path. It is appropriate for this assignment. It is not a durable queue: a process crash can interrupt work. For a production system with large workloads, Celery/RQ plus Redis/RabbitMQ would be preferable.

### SQLite by default

SQLite satisfies the relational-database requirement and makes reviewer setup almost zero-configuration. SQLAlchemy keeps persistence code database-agnostic enough to move to PostgreSQL using `DATABASE_URL`.

### Local filesystem for generated PDFs

Local files keep the assignment runnable without cloud credentials. In production, object storage such as S3 would provide better durability, scaling, lifecycle management, and multi-instance access.

### One fixed certificate template

The renderer intentionally contains one predefined design because the assignment does not require a template editor or multiple designs. Recipient-specific values are injected into that fixed layout.

### Per-recipient persistence

Recipient state is stored separately rather than only keeping aggregate counters. This makes failures explainable and lets the API return exactly which recipients succeeded or failed.

## Learning

This project demonstrates practical bulk API design, stateful background processing, relational persistence, PDF generation, partial-failure handling, file delivery, test isolation, and documenting engineering trade-offs.

## Future scope

- Durable distributed queue with retries and idempotency keys.
- PostgreSQL in production.
- S3-compatible object storage with signed download URLs.
- Authentication and authorization.
- Webhook callback when a job finishes.
- Configurable concurrency and rate limiting.
- Observability with structured logs, metrics, and tracing.
- Expiration/cleanup policy for generated files.
- CSV upload as an additional bulk-recipient input format.

## Submission checklist

- [x] Python backend.
- [x] FastAPI.
- [x] Relational database.
- [x] Bulk request accepting many recipients.
- [x] Recipient validation.
- [x] Single predefined certificate template.
- [x] PDF generation.
- [x] Job status/progress tracking.
- [x] Individual failure isolation.
- [x] Generated-certificate retrieval.
- [x] Tests for important functionality.
- [x] Setup, run, test, request, retrieval, and design-decision documentation.
