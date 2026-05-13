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


class Pen(models.Model):
    key = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    camera_id = models.PositiveIntegerField()
    pen_index = models.PositiveIntegerField()
    roi_xyxy_norm_in_camroi = models.JSONField(default=list, blank=True)
    image_height_m = models.FloatField(default=2.0)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["camera_id", "pen_index"]

    def __str__(self):
        return self.name


class PenState(models.Model):
    pen = models.OneToOneField(Pen, on_delete=models.CASCADE, related_name="state")
    snapshot_relative_path = models.CharField(max_length=255, blank=True)
    snapshot_updated_at = models.DateTimeField(null=True, blank=True)
    detections_json = models.JSONField(default=list, blank=True)
    tracking_state_json = models.JSONField(default=dict, blank=True)
    daily_distance_json = models.JSONField(default=dict, blank=True)
    today_distance_m = models.FloatField(default=0.0)
    yesterday_distance_m = models.FloatField(default=0.0)
    last_7_days_distance_m = models.FloatField(default=0.0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pen state"
        verbose_name_plural = "Pen states"

    def __str__(self):
        return f"State for {self.pen.name}"


class PenActivityQuarterHour(models.Model):
    pen = models.ForeignKey(Pen, on_delete=models.CASCADE, related_name="quarter_hour_activities")
    label = models.CharField(max_length=64)
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    distance_total_m = models.FloatField(default=0.0)
    distance_mean_per_track_m = models.FloatField(default=0.0)
    distance_variance_per_track_m = models.FloatField(default=0.0)
    present = models.BooleanField(default=False)
    presence_seconds = models.FloatField(default=0.0)
    first_seen_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    track_count = models.PositiveIntegerField(default=0)
    detection_count = models.PositiveIntegerField(default=0)
    track_distance_json = models.JSONField(default=dict, blank=True)
    seen_track_ids_json = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-window_start", "pen_id", "label"]
        unique_together = ("pen", "label", "window_start")

    def __str__(self):
        return f"{self.pen.name} {self.label} {self.window_start}"
