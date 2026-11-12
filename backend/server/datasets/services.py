from pathlib import Path
from django.core.exceptions import ValidationError
from django.db import transaction
from pipeline.lastlight.guard import GuardError, inspect_release
from pipeline.lastlight.guard.rules import check_existing_release
from pipeline.lastlight.validate import DOCUMENTS, parse_json
from .models import DatasetRelease

def release_snapshot(release):
    return {"datasetId": release.pk, "sitesSha256": release.sites_sha256, "mode": release.mode,
            "documents": {name: bytes(getattr(release, f"{name}_body")) for name in DOCUMENTS}}


@transaction.atomic
def load_release(directory, *, current_commit=None, manifest_path=None):
    directory = Path(directory)
    # Capture the exact bytes once; changes to files after validation cannot
    # silently change what gets persisted.
    try:
        raw = {name: (directory / f"{name}.json").read_bytes() for name in DOCUMENTS}
    except OSError as error:
        raise ValidationError(f"D3: cannot read release: {error}") from error
    try:
        provenance = parse_json(raw["provenance"], "provenance.json")
    except ValueError as error:
        raise ValidationError(f"D3: {error}") from error
    dataset_id = provenance.get("datasetId") if isinstance(provenance, dict) else None
    previous = DatasetRelease.objects.select_for_update().filter(pk=dataset_id).first() if isinstance(dataset_id, str) else None
    report = inspect_release(directory, document_bytes=raw, current_commit=current_commit,
                             manifest_path=manifest_path,
                             existing_release=release_snapshot(previous) if previous else None)
    try:
        report.require_ok()
    except GuardError as error:
        raise ValidationError(str(error)) from error
    provenance = report.documents["provenance"]
    values = {"mode": provenance["mode"], "sites_sha256": provenance["sitesSha256"],
              **{f"{name}_body": body for name, body in report.document_bytes.items()}}
    release, created = DatasetRelease.objects.get_or_create(dataset_id=provenance["datasetId"], defaults=values)
    try:
        check_existing_release(report, release_snapshot(release))
    except ValueError as error:
        raise ValidationError(f"D2: {error}") from error
    return release, created
