from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import Run
from .payloads import validate_snapshots

@transaction.atomic
def create_run(*, user, dataset, site_id, plan, result, label=""):
    validate_snapshots(plan, result)
    # Serialize per-user writes on databases with row locking (PostgreSQL).
    get_user_model().objects.select_for_update().get(pk=user.pk)
    run = Run.objects.create(user=user, dataset=dataset, site_id=site_id,
                             plan=plan, result=result, label=label)
    keep = list(Run.objects.filter(user=user).values_list("pk", flat=True)[:settings.RUN_HISTORY_LIMIT])
    Run.objects.filter(user=user).exclude(pk__in=keep).delete()
    return run
