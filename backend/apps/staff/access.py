"""
Clinic-level access control for staff users.

A login account gets access to a clinic through an active ``StaffMember``
record of an active clinic. What it may do there follows from the staff
member's role (``ROLE_PERMISSIONS``). Superusers have access to everything.

* ``accessible_clinic_ids(user)`` — which clinics' data the user may see.
* ``ClinicRoleBackend`` — Django authentication backend that answers
  ``user.has_perm(perm)`` (any of the user's clinics) and
  ``user.has_perm(perm, obj)`` (only the role in ``obj``'s clinic).
"""

from django.contrib.auth.backends import BaseBackend

from apps.clinics.models import Clinic

from .models import StaffMember, StaffRole

VIEW = ("view",)
EDIT = ("view", "add", "change")
MANAGE = ("view", "add", "change", "delete")


def _grant(**models):
    """_grant(catalog__service=MANAGE) -> {"catalog.view_service", ...}"""
    perms = set()
    for key, actions in models.items():
        app_label, model_name = key.split("__")
        perms.update(f"{app_label}.{action}_{model_name}" for action in actions)
    return frozenset(perms)


_CLINICAL_STAFF = _grant(
    clinics__clinic=VIEW,
    catalog__service=VIEW,
    staff__staffmember=VIEW,
    staff__dentist=VIEW,
    staff__dentistservice=VIEW,
    scheduling__workinghours=VIEW,
    scheduling__timeoff=VIEW,
    patients__patient=VIEW,
    appointments__appointment=("view", "change"),
)

# Appointments and patients are never deleted through the admin: appointments
# are cancelled, patients deactivated (the database protects them anyway).
ROLE_PERMISSIONS = {
    StaffRole.MANAGER: _grant(
        clinics__clinic=("view", "change"),
        catalog__service=MANAGE,
        staff__staffmember=MANAGE,
        staff__dentist=MANAGE,
        staff__dentistservice=MANAGE,
        scheduling__workinghours=MANAGE,
        scheduling__timeoff=MANAGE,
        patients__patient=EDIT,
        appointments__appointment=EDIT,
        knowledge__knowledgeentry=MANAGE,
        # Transcripts may be read and erased (privacy requests), never edited.
        chatbot__chatconversation=("view", "delete"),
        chatbot__chatmessage=VIEW,
    ),
    StaffRole.RECEPTIONIST: _grant(
        clinics__clinic=VIEW,
        catalog__service=VIEW,
        staff__staffmember=VIEW,
        staff__dentist=VIEW,
        staff__dentistservice=VIEW,
        scheduling__workinghours=VIEW,
        scheduling__timeoff=MANAGE,
        patients__patient=EDIT,
        appointments__appointment=EDIT,
    ),
    StaffRole.DENTIST: _CLINICAL_STAFF,
    StaffRole.HYGIENIST: _CLINICAL_STAFF,
    StaffRole.ASSISTANT: _CLINICAL_STAFF,
}


def clinic_permissions(user):
    """{clinic_id: permissions} from the user's active memberships, cached on the user."""
    if not (user.is_authenticated and user.is_active):
        return {}
    cache = getattr(user, "_clinic_permissions_cache", None)
    if cache is None:
        cache = {}
        memberships = StaffMember.objects.filter(
            user=user, is_active=True, clinic__is_active=True
        ).values_list("clinic_id", "role")
        for clinic_id, role in memberships:
            cache.setdefault(clinic_id, set()).update(ROLE_PERMISSIONS.get(role, ()))
        user._clinic_permissions_cache = cache
    return cache


def accessible_clinic_ids(user):
    """Ids of the clinics whose data ``user`` may see; ``None`` means all (superuser)."""
    if user.is_active and user.is_superuser:
        return None
    return set(clinic_permissions(user))


def clinic_ids_with_perm(user, perm):
    """Ids of the clinics in which ``user`` has ``perm``; ``None`` means all (superuser)."""
    if user.is_active and user.is_superuser:
        return None
    return {clinic_id for clinic_id, perms in clinic_permissions(user).items() if perm in perms}


def _clinic_id_of(obj):
    return obj.pk if isinstance(obj, Clinic) else getattr(obj, "clinic_id", None)


class ClinicRoleBackend(BaseBackend):
    """Model permissions from clinic staff roles (authorization only, no login)."""

    def get_all_permissions(self, user_obj, obj=None):
        memberships = clinic_permissions(user_obj)
        if obj is None:
            return set().union(*memberships.values())
        return set(memberships.get(_clinic_id_of(obj), ()))

    def has_module_perms(self, user_obj, app_label):
        return any(perm.startswith(f"{app_label}.") for perm in self.get_all_permissions(user_obj))
