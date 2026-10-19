from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.models import ClinicScopedModel


class KnowledgeCategory(models.TextChoices):
    GENERAL = "general", _("General information")
    SERVICES = "services", _("Services and treatments")
    PRICING = "pricing", _("Prices and payment")
    POLICIES = "policies", _("Policies")
    FAQ = "faq", _("Frequently asked questions")


class KnowledgeEntry(ClinicScopedModel):
    """
    Curated clinic information the future AI assistant may use to answer
    questions (opening hours, treatments, policies, ...).

    Entries are public-facing content: they must never contain patient data.
    """

    title = models.CharField(max_length=200)
    content = models.TextField()
    category = models.CharField(
        max_length=20, choices=KnowledgeCategory.choices, default=KnowledgeCategory.GENERAL
    )
    language = models.CharField(
        max_length=10, default="sq", help_text="Language code of the content, e.g. sq or en."
    )
    is_published = models.BooleanField(
        default=False, help_text="Only published entries are available to the assistant."
    )

    class Meta:
        verbose_name = "knowledge entry"
        verbose_name_plural = "knowledge entries"
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "language", "title"],
                name="knowledge_knowledgeentry_unique_title",
            ),
            models.CheckConstraint(
                condition=Q(category__in=KnowledgeCategory.values),
                name="knowledge_knowledgeentry_category_valid",
            ),
        ]

    def __str__(self):
        return self.title
