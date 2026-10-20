from django.urls import path

from . import views

app_name = "website"

urlpatterns = [
    path("clinics/<slug:clinic_slug>/", views.clinic_detail, name="clinic"),
    path("clinics/<slug:clinic_slug>/services/", views.service_list, name="services"),
    path("clinics/<slug:clinic_slug>/dentists/", views.dentist_list, name="dentists"),
    path("clinics/<slug:clinic_slug>/articles/", views.article_list, name="articles"),
    path("clinics/<slug:clinic_slug>/availability/", views.availability, name="availability"),
]
