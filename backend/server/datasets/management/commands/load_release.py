from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from server.datasets.services import load_release

class Command(BaseCommand):
    help = "Run backend release-guard and atomically import an immutable release"

    def add_arguments(self, parser):
        parser.add_argument("directory")
        parser.add_argument("--commit", help="Expected CI commit (required for passed level-1/parity)")
        parser.add_argument("--manifest", help="Fixture manifest for CI evidence")

    def handle(self, *args, **options):
        try:
            release, created = load_release(options["directory"], current_commit=options["commit"],
                                           manifest_path=options["manifest"])
        except (ValueError, OSError, ValidationError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f"{release.pk}: {'created' if created else 'already loaded'}"))
