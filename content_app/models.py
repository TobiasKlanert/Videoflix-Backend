from django.db import models


class Video(models.Model):
    """Video entry with metadata and uploaded file stored under media/videos."""

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    thumbnail_url = models.URLField(blank=True, null=True)
    category = models.CharField(max_length=100)
    video_file = models.FileField(upload_to="videos/")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.title
