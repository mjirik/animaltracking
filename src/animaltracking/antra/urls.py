from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),

    path("login", views.MyLoginView.as_view(), name="login"),
]