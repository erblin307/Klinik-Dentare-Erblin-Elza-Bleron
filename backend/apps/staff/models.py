from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.constraints import SameClinicConstraint
from apps.core.models import ClinicScopedModel


# A photo is a file of the website (frontend/public/photos/…), referenced by
# its path. Only plain paths below /photos/ are accepted: no external URLs
# (no third-party requests from patients' browsers) and no "..".
WEBSITE_PHOTO_PATTERN = r"^/photos/(?!.*\.\.)[A-Za-z0-9][A-Za-z0-9/_.-]*\.(jpe?g|png|webp|avif)$"
validate_website_photo = RegexValidator(
    regex=WEBSITE_PHOTO_PATTERN,
    message=_("Enter a path of an image on the website, e.g. /photos/dentists/arta.jpg."),
)


class StaffRole(models.TextChoices):
    DENTIST = "dentist", _("Dentist")
    HYGIENIST = "hygienist", _("Hygienist")
    ASSISTANT = "assistant", _("Dental assistant")
    RECEPTIONIST = "receptionist", _("Receptionist")
    MANAGER = "manager", _("Practice manager")


class StaffMember(ClinicScopedModel):
    """A person working at a clinic."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_memberships",
        help_text="Login account, if this person signs in to the system.",
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    role = models.CharField(max_length=20, choices=StaffRole.choices)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "staff member"
        constraints = [
            # Target key for SameClinicConstraint foreign keys.
            models.UniqueConstraint(
                fields=["clinic", "id"], name="staff_staffmember_clinic_key"
            ),
            models.UniqueConstraint(
                fields=["clinic", "user"], name="staff_staffmember_unique_user"
            ),
            models.CheckConstraint(
                condition=Q(role__in=StaffRole.values),
                name="staff_staffmember_role_valid",
            ),
        ]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Dentist(ClinicScopedModel):
    """Clinical profile of a staff member who treats patients and can be booked."""

    staff_member = models.OneToOneField(
        StaffMember, on_delete=models.CASCADE, related_name="dentist_profile"
    )
    license_number = models.CharField(max_length=64, blank=True)
    specialty = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True, help_text="Public profile text.")
    photo = models.CharField(
        max_length=200,
        blank=True,
        validators=[validate_website_photo],
        help_text="Path of the portrait on the website, e.g. /photos/dentists/arta.jpg "
        "(portrait 4:5, about 1000×1250 px). Leave empty to show initials. "
        "Images in /photos/demo/ are labelled as demo photos.",
    )
    is_bookable = models.BooleanField(
        default=True, help_text="Whether new appointments can be booked."
    )
    services = models.ManyToManyField(
        "catalog.Service", through="DentistService", related_name="dentists", blank=True
    )

    class Meta:
        constraints = [
            # Target key for SameClinicConstraint foreign keys.
            models.UniqueConstraint(
                fields=["clinic", "id"], name="staff_dentist_clinic_key"
            ),
            SameClinicConstraint(
                field="staff_member", name="staff_dentist_staff_member_same_clinic"
            ),
            models.CheckConstraint(
                condition=Q(photo="") | Q(photo__regex=WEBSITE_PHOTO_PATTERN),
                name="staff_dentist_photo_path_valid",
            ),
        ]

    def __str__(self):
        return f"Dr. {self.staff_member.full_name}"

    def clean(self):
        if self.staff_member_id and self.staff_member.role != StaffRole.DENTIST:
            raise ValidationError(
                {"staff_member": _("The staff member's role must be “Dentist”.")}
            )


class DentistService(ClinicScopedModel):
    """A service a dentist performs."""

    dentist = models.ForeignKey(
        Dentist, on_delete=models.CASCADE, related_name="service_links"
    )
    service = models.ForeignKey(
        "catalog.Service", on_delete=models.CASCADE, related_name="dentist_links"
    )

    class Meta:
        verbose_name = "dentist service"
        constraints = [
            models.UniqueConstraint(
                fields=["dentist", "service"], name="staff_dentistservice_unique_pair"
            ),
            SameClinicConstraint(
                field="dentist", name="staff_dentistservice_dentist_same_clinic"
            ),
            SameClinicConstraint(
                field="service", name="staff_dentistservice_service_same_clinic"
            ),
        ]

    def __str__(self):
        return f"{self.dentist} – {self.service}"
