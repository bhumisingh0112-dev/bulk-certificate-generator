from pathlib import Path
import uuid

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.job import CertificateJob, Recipient
from app.schemas.job import JobCreate
from app.services.certificate_service import generate_certificate


_email_adapter = TypeAdapter(EmailStr)


def _new_certificate_id() -> str:
    return f"CERT-{uuid.uuid4().hex[:10].upper()}"


def create_job(db: Session, payload: JobCreate) -> CertificateJob:
    job = CertificateJob(
        certificate_title=payload.certificate_title.strip(),
        course_name=payload.course_name.strip(),
        issuer_name=payload.issuer_name.strip(),
        issue_date=payload.issue_date,
        total_count=len(payload.recipients),
    )
    db.add(job)
    db.flush()

    seen_emails: set[str] = set()
    seen_certificate_ids: set[str] = set()

    for item in payload.recipients:
        certificate_id = (item.certificate_id or _new_certificate_id()).strip()
        email = item.email.strip().lower()
        status = "PENDING"
        error_message = None

        try:
            _email_adapter.validate_python(email)
        except ValidationError:
            status = "FAILED"
            error_message = "Invalid email address."

        if email in seen_emails and status == "PENDING":
            status = "FAILED"
            error_message = "Duplicate email address in this job."

        if certificate_id in seen_certificate_ids and status == "PENDING":
            status = "FAILED"
            error_message = "Duplicate certificate_id in this job."

        seen_emails.add(email)
        seen_certificate_ids.add(certificate_id)

        recipient = Recipient(
            job_id=job.id,
            name=item.name.strip(),
            email=email,
            certificate_id=certificate_id,
            status=status,
            error_message=error_message,
        )
        db.add(recipient)
        if status == "FAILED":
            job.failed_count += 1

    if job.failed_count == job.total_count:
        job.status = "COMPLETED_WITH_ERRORS"

    db.commit()
    db.refresh(job)
    return job


def process_job(job_id: str) -> None:
    """Process a bulk job in a FastAPI background task.

    Each recipient is isolated: one generation failure is recorded and processing
    continues for the remaining recipients.
    """
    db = SessionLocal()
    try:
        job = db.get(CertificateJob, job_id)
        if job is None:
            return

        if job.status == "COMPLETED_WITH_ERRORS" and job.failed_count == job.total_count:
            return

        job.status = "PROCESSING"
        db.commit()

        recipients = db.scalars(
            select(Recipient).where(Recipient.job_id == job_id).order_by(Recipient.created_at)
        ).all()

        job_output_dir = Path(settings.storage_dir) / job.id

        for recipient in recipients:
            if recipient.status != "PENDING":
                continue

            recipient.status = "PROCESSING"
            db.commit()

            try:
                output_path = generate_certificate(
                    output_dir=job_output_dir,
                    recipient_id=recipient.id,
                    recipient_name=recipient.name,
                    certificate_id=recipient.certificate_id,
                    certificate_title=job.certificate_title,
                    course_name=job.course_name,
                    issuer_name=job.issuer_name,
                    issue_date=job.issue_date.isoformat(),
                )
                recipient.file_path = str(output_path)
                recipient.status = "SUCCESS"
                recipient.error_message = None
                job.success_count += 1
            except Exception as exc:  # per-recipient isolation is intentional
                recipient.status = "FAILED"
                recipient.error_message = f"Certificate generation failed: {exc}"
                job.failed_count += 1

            db.commit()

        if job.failed_count == 0:
            job.status = "COMPLETED"
        elif job.success_count > 0:
            job.status = "COMPLETED_WITH_ERRORS"
        else:
            job.status = "FAILED"
        db.commit()
    except Exception:
        db.rollback()
        job = db.get(CertificateJob, job_id)
        if job is not None:
            job.status = "FAILED"
            db.commit()
    finally:
        db.close()
