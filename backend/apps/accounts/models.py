from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Login account for clinic staff and platform administrators.

    Defined from the start (even without extra fields) because Django cannot
    easily switch AUTH_USER_MODEL once migrations have been applied.
    """
