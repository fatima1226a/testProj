"""Generate demo data in a temporary directory and import it into the database."""
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from pipeline.lastlight.demo import generate
from pipeline.lastlight.validate import read_json
from server.datasets.models import DatasetRelease
from server.datasets.services import load_release


class Command(BaseCommand):
    help = "Generate and load the synthetic demo; preserve an existing identical release"

    def handle(self, *args, **options):
        try:
            with TemporaryDirectory(prefix="lastlight-demo-") as temporary:
                directory = generate(temporary)
                dataset_id = read_json(directory / "sites.json")["datasetId"]
                release = DatasetRelease.objects.filter(pk=dataset_id).first()
                if release is not None:
                    # Audit reports contain execution timestamps. Keep the original
                    # immutable release rather than replacing its reports on restart.
                    for name in ("sites", "provenance"):
                        if bytes(getattr(release, f"{name}_body")) != (directory / f"{name}.json").read_bytes():
                            raise ValueError("Demo content changed; use a new datasetId")
                    created = False
                else:
                    release, created = load_release(directory)
        except (ValueError, OSError, ValidationError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f"{release.pk}: {'created' if created else 'already loaded'}"))
