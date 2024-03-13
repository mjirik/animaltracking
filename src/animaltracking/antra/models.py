from django.db import models

# Create your models here.

class Camera(models.Model):
    name = models.CharField(max_length=100)
    ip = models.GenericIPAddressField()
    port = models.IntegerField()
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    mediafile_dir = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class MediaFile(models.Model):
    file = models.FileField(upload_to="media/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name