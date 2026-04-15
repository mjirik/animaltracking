from django.contrib import admin

from .models import Animal, AnimalEnclosure, Camera, MediaFile, Pen, PenState, Track


@admin.register(MediaFile)
class MediaFileAdmin(admin.ModelAdmin):
    list_display = ("id", "file", "uploaded_at")
    search_fields = ("file",)


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "ip", "port", "mediafile_dir")
    search_fields = ("name", "ip")


@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(AnimalEnclosure)
class AnimalEnclosureAdmin(admin.ModelAdmin):
    list_display = ("id", "animal", "camera", "enclosure")
    search_fields = ("animal__name", "camera__name", "enclosure")


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ("id", "animal", "camera", "start_time", "end_time")
    search_fields = ("animal__name", "camera__name")


class PenStateInline(admin.StackedInline):
    model = PenState
    can_delete = False
    extra = 0


@admin.register(Pen)
class PenAdmin(admin.ModelAdmin):
    list_display = ("id", "key", "name", "camera_id", "pen_index", "image_height_m", "is_active", "updated_at")
    list_filter = ("camera_id", "is_active")
    search_fields = ("key", "name")
    inlines = [PenStateInline]


@admin.register(PenState)
class PenStateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "pen",
        "snapshot_relative_path",
        "snapshot_updated_at",
        "today_distance_m",
        "yesterday_distance_m",
        "last_7_days_distance_m",
        "updated_at",
    )
    search_fields = ("pen__key", "pen__name", "snapshot_relative_path")
