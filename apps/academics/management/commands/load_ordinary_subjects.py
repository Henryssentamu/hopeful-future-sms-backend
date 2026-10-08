from django.core.management.base import BaseCommand, CommandError
from apps.academics.catalogue import load_ordinary_subjects


class Command(BaseCommand):
    help = "Add the NCDC lower-secondary subject menu without removing existing subjects or papers."

    def handle(self, *args, **options):
        try:
            load_ordinary_subjects()
        except ValueError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS("NCDC O-Level subject menu loaded."))
