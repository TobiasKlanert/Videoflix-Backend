from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .serializers import VideoSerializer
from content_app.models import Video

class VideoListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        videos = Video.objects.all()
        serializer = VideoSerializer(videos, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)