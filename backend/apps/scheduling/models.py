from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _

from apps.core.constraints import SameClinicConstraint
from apps.core.models import ClinicScopedModel


class Weekday(models.IntegerChoices):
    # Same numbering as datetime.date.weekday().
    MONDAY = 0, _("Monday")
    TUESDAY = 1, _("Tuesday")
    WEDNESDAY = 2, _("Wednesday")
    THURSDAY = 3, _("Thursday")
    FRIDAY = 4, _("Friday")
    SATURDAY = 5, _("Saturday")
    SUNDAY = 6, _("Sunday")


class WorkingHours(ClinicScopedModel):
    """
    A recurring weekly block in which a dentist is available, e.g.
    Monday 09:00–13:00. Times are local to the clinic's time zone. A dentist
    may have several non-overlapping blocks per weekday (e.g. a lunch break).
    """

    dentist = models.ForeignKey(
        "staff.Dentist", on_delete=models.CASCADE, related_name="working_hours"
    )
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        verbose_name = verbose_name_plural = "working hours"
        constraints = [
            models.CheckConstraint(
                condition=Q(weekday__gte=0, weekday__lte=6),
                name="scheduling_workinghours_weekday_valid",
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")),
                name="scheduling_workinghours_end_after_start",
            ),
            models.UniqueConstraint(
                fields=["dentist", "weekday", "start_time"],
                name="scheduling_workinghours_unique_start",
            ),
            SameClinicConstraint(
                field="dentist", name="scheduling_workinghours_dentist_same_clinic"
            ),
        ]

    def __str__(self):
        return (
            f"{self.dentist} – {self.get_weekday_display()} "
            f"{self.start_time:%H:%M}–{self.end_time:%H:%M}"
        )

    def clean(self):
        # Overlapping blocks are harmless for availability but indicate a data
        # entry mistake, so they are rejected on validation (not in the DB).
        if None in (self.dentist_id, self.weekday, self.start_time, self.end_time):
            return
        overlapping = WorkingHours.objects.filter(
            dentist_id=self.dentist_id,
            weekday=self.weekday,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time,
        ).exclude(pk=self.pk)
        if overlapping.exists():
            raise ValidationError(
                _("These hours overlap another block of this dentist on the same day.")
            )


class TimeOff(ClinicScopedModel):
    """
    A period in which a dentist (or, without a dentist, the whole clinic) is
    unavailable: vacation, training, public holiday, ...
    """

    dentist = models.ForeignKey(
        "staff.Dentist",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="time_off",
        help_text="Leave empty for a clinic-wide closure.",
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    reason = models.CharField(
        max_length=200, blank=True, help_text="Internal note. Avoid medical details."
    )

    class Meta:
        verbose_name = verbose_name_plural = "time off"
        constraints = [
            models.CheckConstraint(
                condition=Q(end_at__gt=F("start_at")),
                name="scheduling_timeoff_end_after_start",
            ),
            SameClinicConstraint(
                field="dentist", name="scheduling_timeoff_dentist_same_clinic"
            ),
        ]
        indexes = [
            models.Index(fields=["clinic", "start_at"], name="scheduling_timeoff_start_idx"),
        ]

    def __str__(self):
        who = self.dentist if self.dentist_id else _("Whole clinic")
        return f"{who}: {self.start_at:%Y-%m-%d %H:%M} – {self.end_at:%Y-%m-%d %H:%M}"
