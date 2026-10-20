from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/chat/", include("apps.chatbot.urls")),
    path("api/public/", include("apps.website.urls")),
]
