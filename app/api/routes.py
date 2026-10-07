from io import BytesIO
from pathlib import Path
import zipfile

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.job import CertificateJob, Recipient
from app.schemas.job import CertificateItem, CertificateList, JobCreate, JobDetail, JobSummary
from app.services.job_service import create_job, process_job


router = APIRouter(prefix="/api", tags=["certificate-jobs"])


def _get_job_with_recipients(db: Session, job_id: str) -> CertificateJob:
    job = db.scalar(
        select(CertificateJob)
        .options(selectinload(CertificateJob.recipients))
        .where(CertificateJob.id == job_id)
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.post("/jobs", response_model=JobSummary, status_code=status.HTTP_202_ACCEPTED)
def submit_job(payload: JobCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    job = create_job(db, payload)
    if job.status == "PENDING":
        background_tasks.add_task(process_job, job.id)
    return job


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: str, db: Session = Depends(get_db)):
    return _get_job_with_recipients(db, job_id)


@router.get("/jobs/{job_id}/certificates", response_model=CertificateList)
def list_certificates(job_id: str, db: Session = Depends(get_db)):
    _get_job_with_recipients(db, job_id)
    recipients = db.scalars(
        select(Recipient).where(Recipient.job_id == job_id, Recipient.status == "SUCCESS")
    ).all()
    items = [
        CertificateItem(
            id=item.id,
            name=item.name,
            email=item.email,
            certificate_id=item.certificate_id,
            download_url=f"/api/certificates/{item.id}/download",
        )
        for item in recipients
    ]
    return CertificateList(job_id=job_id, count=len(items), certificates=items)


@router.get("/certificates/{recipient_id}/download")
def download_certificate(recipient_id: str, db: Session = Depends(get_db)):
    recipient = db.get(Recipient, recipient_id)
    if recipient is None:
        raise HTTPException(status_code=404, detail="Certificate record not found.")
    if recipient.status != "SUCCESS" or not recipient.file_path:
        raise HTTPException(status_code=409, detail="Certificate is not available for download.")

    path = Path(recipient.file_path)
    if not path.is_file():
        raise HTTPException(status_code=410, detail="Generated certificate file is no longer available.")

    return FileResponse(path, media_type="application/pdf", filename=path.name)


@router.get("/jobs/{job_id}/download")
def download_job_zip(job_id: str, db: Session = Depends(get_db)):
    _get_job_with_recipients(db, job_id)
    recipients = db.scalars(
        select(Recipient).where(Recipient.job_id == job_id, Recipient.status == "SUCCESS")
    ).all()

    existing_paths = [Path(r.file_path) for r in recipients if r.file_path and Path(r.file_path).is_file()]
    if not existing_paths:
        raise HTTPException(status_code=409, detail="No generated certificates are available for this job.")

    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in existing_paths:
            archive.write(path, arcname=path.name)
    memory_file.seek(0)

    return StreamingResponse(
        memory_file,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="certificates-{job_id}.zip"'},
    )
