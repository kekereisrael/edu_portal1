"""
Views for the accounts app.
"""

from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import User, Profile, UserSession, LoginAttempt
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserSerializer,
    UserUpdateSerializer,
    ProfileSerializer,
    ChangePasswordSerializer,
    UserSessionSerializer,
)


class RegisterView(generics.CreateAPIView):
    """Register a new user account."""

    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate tokens
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                'message': 'Registration successful.',
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                },
                'user': UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """Authenticate user and return JWT tokens."""

    permission_classes = [permissions.AllowAny]
    serializer_class = UserLoginSerializer

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)

        # Get client info for logging
        ip_address = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
        email = request.data.get('email', '')

        if not serializer.is_valid():
            # Log failed attempt
            LoginAttempt.objects.create(
                email=email,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                failure_reason='invalid_credentials',
            )
            return Response(
                serializer.errors, status=status.HTTP_401_UNAUTHORIZED
            )

        user = serializer.validated_data['user']

        # Check for too many failed attempts (rate limiting)
        recent_failures = LoginAttempt.objects.filter(
            email=email,
            success=False,
            attempted_at__gte=timezone.now() - timezone.timedelta(minutes=15),
        ).count()

        if recent_failures >= 5:
            return Response(
                {'detail': 'Too many failed attempts. Please try again in 15 minutes.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Generate tokens
        refresh = RefreshToken.for_user(user)

        # Log successful attempt
        LoginAttempt.objects.create(
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
        )

        # Create session record
        device_type = self._detect_device_type(user_agent)
        UserSession.objects.create(
            user=user,
            token_jti=str(refresh['jti']),
            device_type=device_type,
            device_name=request.data.get('device_name', ''),
            ip_address=ip_address,
        )

        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        return Response(
            {
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                },
                'user': UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '127.0.0.1')

    def _detect_device_type(self, user_agent):
        user_agent_lower = user_agent.lower()
        if 'android' in user_agent_lower:
            return 'mobile_android'
        elif 'iphone' in user_agent_lower or 'ipad' in user_agent_lower:
            return 'mobile_ios'
        return 'web'


class LogoutView(APIView):
    """Logout user by blacklisting the refresh token."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                # Deactivate session
                UserSession.objects.filter(
                    token_jti=token['jti']
                ).update(is_active=False)
                # Blacklist token
                token.blacklist()
            return Response(
                {'message': 'Logout successful.'},
                status=status.HTTP_200_OK,
            )
        except Exception:
            return Response(
                {'message': 'Logout successful.'},
                status=status.HTTP_200_OK,
            )


class UserDetailView(generics.RetrieveUpdateAPIView):
    """Get or update current user details."""

    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UserUpdateSerializer
        return UserSerializer

    def get_object(self):
        return self.request.user


class ProfileView(generics.RetrieveUpdateAPIView):
    """Get or update current user's profile."""

    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile, _ = Profile.objects.get_or_create(user=self.request.user)
        return profile


class ChangePasswordView(APIView):
    """Change user password."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()

        return Response(
            {'message': 'Password changed successfully.'},
            status=status.HTTP_200_OK,
        )


class UserSessionListView(generics.ListAPIView):
    """List all active sessions for the current user."""

    serializer_class = UserSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserSession.objects.filter(
            user=self.request.user, is_active=True
        )


class RevokeSessionView(APIView):
    """Revoke a specific session."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = UserSession.objects.get(
                id=session_id, user=request.user, is_active=True
            )
            session.is_active = False
            session.save(update_fields=['is_active'])
            return Response(
                {'message': 'Session revoked successfully.'},
                status=status.HTTP_200_OK,
            )
        except UserSession.DoesNotExist:
            return Response(
                {'detail': 'Session not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )


class RevokeAllSessionsView(APIView):
    """Revoke all sessions except the current one."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        current_jti = request.data.get('current_jti')
        sessions = UserSession.objects.filter(
            user=request.user, is_active=True
        )
        if current_jti:
            sessions = sessions.exclude(token_jti=current_jti)
        sessions.update(is_active=False)

        return Response(
            {'message': 'All other sessions revoked.'},
            status=status.HTTP_200_OK,
        )
