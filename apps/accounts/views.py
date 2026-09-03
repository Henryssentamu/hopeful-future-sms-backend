from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import LoginSerializer, UserSerializer


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/ — {username, password} -> {access, refresh, user}."""

    serializer_class = LoginSerializer


class MeView(APIView):
    """GET /api/auth/me/ — the current authenticated user's profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)
