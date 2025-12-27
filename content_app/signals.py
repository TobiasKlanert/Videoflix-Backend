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
    """
    Handle post-save events for the Video model.

    Parameters:
    sender
        The model class that sent the signal (expected: Video).
    instance
        The saved Video instance.
    created : bool
        True if a new instance was created.
    **kwargs
        Extra keyword arguments passed by Django's signal dispatcher.

    Behavior:
        - Prints a short indication that a Video was saved.
        - If a new Video was created:
        - Obtains the 'default' django-rq queue (autocommit=True).
        - Enqueues `convert_hls` with the video's file system path to generate HLS renditions.
        - Enqueues `extract_thumbnail` with the instance ID and file path to generate a thumbnail.

    Notes:
        - Requires instance.video_file and instance.video_file.path to be present.
        - Keeps expensive processing out of the request/response cycle by delegating to background jobs.
    """
    print('Video saved!')
    if created:
        print('New video created')
        queue = django_rq.get_queue('default', autocommit=True)
        queue.enqueue(convert_hls, instance.video_file.path)
        queue.enqueue(extract_thumbnail, instance.id, instance.video_file.path)


@receiver(post_delete, sender=Video)
def auto_delete_video_on_delete(sender, instance, **kwargs):
    """
    Signal receiver that cleans up disk files related to a Video instance when it is deleted.

    This function is intended to be connected to Django's post_delete signal for the Video model.
    When a Video instance is removed, it performs the following cleanup actions if the
    corresponding files/directories exist:
        - Removes the video file at instance.video_file.path.
        - Removes an associated HLS directory named "<base_filename>_hls" next to the video file.
        - Removes a generated thumbnail at MEDIA_ROOT/thumbnail/<base_filename>.jpg.

    Parameters:
    sender
        The model class sending the signal (unused by this function).
    instance
        The Video model instance that was deleted. Expected to have a FileField-like
        attribute `video_file` with a `.path` property.
    **kwargs
        Additional keyword arguments provided by Django's signal framework (unused).

    Side effects:
        Performs filesystem operations (os.path checks, os.remove, shutil.rmtree). These operations
        may raise OSError or subclasses if files cannot be accessed or removed; callers should
        ensure appropriate permissions and error handling if needed.

    Notes:
        - This receiver assumes instance.video_file is present and has a valid filesystem path.
        - The thumbnail location is constructed using settings.MEDIA_ROOT and the base filename.
        - sender and kwargs are accepted to match the signal signature but are not used.
"""
    if instance.video_file:
        if os.path.isfile(instance.video_file.path):
            os.remove(instance.video_file.path)
        base_dir = os.path.dirname(instance.video_file.path)
        base_name = os.path.splitext(
            os.path.basename(instance.video_file.path))[0]
        hls_dir = os.path.join(base_dir, f"{base_name}_hls")
        if os.path.isdir(hls_dir):
            shutil.rmtree(hls_dir)
        thumbnail_path = os.path.join(
            os.fspath(settings.MEDIA_ROOT), "thumbnail", f"{base_name}.jpg"
        )
        if os.path.isfile(thumbnail_path):
            os.remove(thumbnail_path)
