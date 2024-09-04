from django.urls import path

from . import views
app_name = "antra"

urlpatterns = [
    path("", views.index, name="index"),
    path("login", views.MyLoginView.as_view(), name="login"),
]
