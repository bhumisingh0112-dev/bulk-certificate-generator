from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field


class RecipientInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    certificate_id: str | None = Field(default=None, max_length=100)


class JobCreate(BaseModel):
    certificate_title: str = Field(min_length=3, max_length=160)
    course_name: str = Field(min_length=2, max_length=200)
    issuer_name: str = Field(min_length=2, max_length=160)
    issue_date: date
    recipients: list[RecipientInput] = Field(min_length=1, max_length=1000)


class RecipientStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    certificate_id: str
    status: Literal["PENDING", "PROCESSING", "SUCCESS", "FAILED"]
    error_message: str | None = None


class JobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: Literal["PENDING", "PROCESSING", "COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"]
    total_count: int
    success_count: int
    failed_count: int
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def processed_count(self) -> int:
        return self.success_count + self.failed_count

    @computed_field
    @property
    def progress_percent(self) -> float:
        if self.total_count == 0:
            return 0.0
        return round((self.processed_count / self.total_count) * 100, 2)


class JobDetail(JobSummary):
    certificate_title: str
    course_name: str
    issuer_name: str
    issue_date: date
    recipients: list[RecipientStatus]


class CertificateItem(BaseModel):
    id: str
    name: str
    email: str
    certificate_id: str
    download_url: str


class CertificateList(BaseModel):
    job_id: str
    count: int
    certificates: list[CertificateItem]
