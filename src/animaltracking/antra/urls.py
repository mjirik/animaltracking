from django.urls import path

from . import views

app_name = "antra"

urlpatterns = [
    path("", views.index, name="index"),
    path("login", views.MyLoginView.as_view(), name="login"),
    # path("import_videos", views.import_videos, name="import_videos"),
    path('mediafiles/', views.MediaFileListView.as_view(), name='mediafile-list'),
    path('import_videos/', views.import_videos, name='import_videos'),

]
