from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete

from django.conf import settings

from .models import Video
from .tasks import convert_hls, extract_thumbnail

import os
import shutil
import django_rq

@receiver(post_save, sender=Video)
def video_post_save(sender, instance, created, **kwargs):
    print('Video saved!')
    if created:
        print('New video created')
        queue = django_rq.get_queue('default', autocommit=True)
        queue.enqueue(convert_hls, instance.video_file.path)
        queue.enqueue(extract_thumbnail, instance.id, instance.video_file.path)

@receiver(post_delete, sender=Video)
def auto_delete_video_on_delete(sender, instance, **kwargs):
    if instance.video_file:
        if os.path.isfile(instance.video_file.path):
            os.remove(instance.video_file.path)
        base_dir = os.path.dirname(instance.video_file.path)
        base_name = os.path.splitext(os.path.basename(instance.video_file.path))[0]
        hls_dir = os.path.join(base_dir, f"{base_name}_hls")
        if os.path.isdir(hls_dir):
            shutil.rmtree(hls_dir)
        thumbnail_path = os.path.join(
            os.fspath(settings.MEDIA_ROOT), "thumbnail", f"{base_name}.jpg"
        )
        if os.path.isfile(thumbnail_path):
            os.remove(thumbnail_path)
