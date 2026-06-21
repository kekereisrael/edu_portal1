"""
Serializers for the accounts app.
"""

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, Profile, UserSession


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""

    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'role',
            'phone', 'password', 'password_confirm',
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError(
                {'password_confirm': 'Passwords do not match.'}
            )
        # Only allow student, teacher, parent, school_admin registration
        allowed_roles = [
            User.Role.STUDENT, User.Role.TEACHER,
            User.Role.PARENT, User.Role.SCHOOL_ADMIN,
        ]
        if attrs.get('role') and attrs['role'] not in allowed_roles:
            raise serializers.ValidationError(
                {'role': 'Invalid role for registration.'}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        # Create profile automatically
        Profile.objects.create(user=user)
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login."""

    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        user = authenticate(email=email, password=password)
        if not user:
            raise serializers.ValidationError(
                {'detail': 'Invalid email or password.'}
            )
        if not user.is_active:
            raise serializers.ValidationError(
                {'detail': 'Account is deactivated.'}
            )

        attrs['user'] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user details."""

    full_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'role', 'phone', 'avatar', 'is_verified',
            'is_platform_admin', 'date_joined',
        ]
        read_only_fields = ['id', 'email', 'is_verified', 'is_platform_admin', 'date_joined']


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile."""

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'avatar']


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile."""

    class Meta:
        model = Profile
        fields = [
            'id', 'bio', 'date_of_birth', 'address',
            'city', 'state', 'country',
        ]
        read_only_fields = ['id']


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change."""

    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(
        required=True, write_only=True, validators=[validate_password]
    )
    new_password_confirm = serializers.CharField(required=True, write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError(
                {'new_password_confirm': 'New passwords do not match.'}
            )
        return attrs


class UserSessionSerializer(serializers.ModelSerializer):
    """Serializer for user sessions."""

    class Meta:
        model = UserSession
        fields = [
            'id', 'device_type', 'device_name',
            'ip_address', 'is_active', 'created_at', 'last_activity',
        ]
        read_only_fields = fields


class TokenResponseSerializer(serializers.Serializer):
    """Serializer for token response."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()
