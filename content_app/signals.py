from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete

from .models import Video
from .tasks import convert_hls, extract_thumbnail

import os
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
