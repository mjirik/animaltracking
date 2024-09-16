from django.db import models

# Create your models here.

class MediaFile(models.Model):
    file = models.FileField(upload_to="media/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name

class Camera(models.Model):
    name = models.CharField(max_length=100)
    ip = models.GenericIPAddressField()
    port = models.IntegerField()
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    mediafile_dir = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Animal(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class AnimalEnclosure(models.Model):
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE)
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE)
    enclosure = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.animal.name} - {self.camera.name} - {self.enclosure}"

class Track(models.Model):
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE)
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE)
    json_track = models.JSONField()
    media_file = models.ForeignKey(MediaFile, on_delete=models.CASCADE)
    
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    def __str__(self):
        return f"{self.animal.name} - {self.camera.name} - {self.start_time} - {self.end_time}"


