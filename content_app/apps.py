from django.apps import AppConfig


class ContentConfig(AppConfig):
    name = 'content_app'

    def ready(self):
        import content_app.signals