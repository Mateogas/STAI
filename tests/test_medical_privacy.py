from datetime import date

from stai.medical import CertificateFields, MedicalCheckService
from stai.models import ApplicabilityStatus
from stai.state import Repo


class SpyExtractor:
    def __init__(self):
        self.called = False

    def __call__(self, _data, _kind):
        self.called = True
        return CertificateFields()


def test_policy_gate_happens_before_file_processing(tmp_path) -> None:
    repo = Repo(tmp_path / "db.sqlite", secret_path=tmp_path / "key")
    extractor = SpyExtractor()
    outcome = MedicalCheckService(repo, extractor=extractor).check(
        b"not-even-opened",
        filename="certificate.pdf",
        evaluation_date=date(2026, 8, 10),
        applicability=ApplicabilityStatus.DOES_NOT_APPLY,
        acknowledged=True,
    )
    assert outcome.kind == "does_not_apply"
    assert extractor.called is False
    assert repo.count_validation_results() == 0


def test_declined_privacy_notice_performs_no_processing(tmp_path) -> None:
    repo = Repo(tmp_path / "db.sqlite", secret_path=tmp_path / "key")
    extractor = SpyExtractor()
    outcome = MedicalCheckService(repo, extractor=extractor).check(
        b"%PDF-fake",
        filename="certificate.pdf",
        evaluation_date=date(2026, 8, 10),
        applicability=ApplicabilityStatus.APPLIES,
        acknowledged=False,
    )
    assert outcome.kind == "privacy_acknowledgement_required"
    assert extractor.called is False


def test_upload_rejection_creates_no_result_or_fingerprint(tmp_path) -> None:
    repo = Repo(tmp_path / "db.sqlite", secret_path=tmp_path / "key")
    outcome = MedicalCheckService(repo, extractor=SpyExtractor()).check(
        b"PK\x03\x04archive",
        filename="certificate.zip",
        evaluation_date=date(2026, 8, 10),
        applicability=ApplicabilityStatus.APPLIES,
        acknowledged=True,
    )
    assert outcome.kind == "upload_rejection"
    assert outcome.code == "unsupported_media_type"
    assert outcome.fingerprint is None
    assert repo.count_validation_results() == 0


def test_outcome_dump_never_contains_medical_input_fields(tmp_path) -> None:
    repo = Repo(tmp_path / "db.sqlite", secret_path=tmp_path / "key")
    outcome = MedicalCheckService(repo, extractor=SpyExtractor()).check(
        b"not-supported",
        filename="x.pdf",
        evaluation_date=date(2026, 8, 10),
        applicability=ApplicabilityStatus.APPLIES,
        acknowledged=True,
    )
    dumped = outcome.model_dump_json().lower()
    for forbidden in ("filename", "ocr", "diagnosis", "patient_name", "confidence"):
        assert forbidden not in dumped

