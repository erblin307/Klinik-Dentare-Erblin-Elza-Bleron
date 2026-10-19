from datetime import time, timedelta

from django.core.exceptions import ValidationError

from apps.scheduling.models import TimeOff, Weekday, WorkingHours

from .factories import MONDAY_9AM, make_clinic, make_dentist
from .utils import IntegrityTestCase


class WorkingHoursTests(IntegrityTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinic = make_clinic()
        cls.dentist = make_dentist(cls.clinic)
        cls.morning = WorkingHours.objects.create(
            clinic=cls.clinic,
            dentist=cls.dentist,
            weekday=Weekday.MONDAY,
            start_time=time(9),
            end_time=time(13),
        )

    def hours(self, start, end, weekday=Weekday.MONDAY):
        return WorkingHours(
            clinic=self.clinic,
            dentist=self.dentist,
            weekday=weekday,
            start_time=start,
            end_time=end,
        )

    def test_end_must_be_after_start(self):
        for start, end in [(time(14), time(14)), (time(18), time(14))]:
            with self.subTest(start=start, end=end):
                with self.assertViolates("scheduling_workinghours_end_after_start"):
                    self.hours(start, end).save()

    def test_weekday_must_be_between_monday_and_sunday(self):
        with self.assertViolates("scheduling_workinghours_weekday_valid"):
            self.hours(time(9), time(13), weekday=7).save()

    def test_duplicate_block_start_is_rejected(self):
        with self.assertViolates("scheduling_workinghours_unique_start"):
            self.hours(time(9), time(10)).save()

    def test_split_shift_on_same_day_is_allowed(self):
        afternoon = self.hours(time(14), time(18))
        afternoon.full_clean()
        afternoon.save()

    def test_overlapping_block_fails_validation(self):
        with self.assertRaisesMessage(ValidationError, "overlap another block"):
            self.hours(time(12), time(16)).full_clean()

    def test_editing_a_block_does_not_overlap_itself(self):
        self.morning.end_time = time(12)
        self.morning.full_clean()


class TimeOffTests(IntegrityTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clinic = make_clinic()
        cls.dentist = make_dentist(cls.clinic)

    def test_end_must_be_after_start(self):
        with self.assertViolates("scheduling_timeoff_end_after_start"):
            TimeOff.objects.create(
                clinic=self.clinic, dentist=self.dentist, start_at=MONDAY_9AM, end_at=MONDAY_9AM
            )

    def test_clinic_wide_closure_has_no_dentist(self):
        closure = TimeOff.objects.create(
            clinic=self.clinic, start_at=MONDAY_9AM, end_at=MONDAY_9AM + timedelta(days=1)
        )
        self.assertIsNone(closure.dentist_id)
