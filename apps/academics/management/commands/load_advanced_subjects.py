from django.core.management.base import BaseCommand, CommandError
from apps.academics.catalogue import load_advanced_subjects


class Command(BaseCommand):
    help = "Add the NCDC higher-secondary subject menu without removing existing subjects or papers."

    def handle(self, *args, **options):
        try:
            load_advanced_subjects()
        except ValueError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS("NCDC A-Level subject menu loaded."))
