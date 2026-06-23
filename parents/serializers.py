"""
Serializers for the parents app.
"""

from rest_framework import serializers

from .models import ParentProfile


class ParentProfileSerializer(serializers.ModelSerializer):
    """Full parent profile serializer."""

    user_id    = serializers.UUIDField(source='user.id', read_only=True)
    email      = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name  = serializers.CharField(source='user.last_name', read_only=True)
    full_name  = serializers.SerializerMethodField()
    phone      = serializers.CharField(source='user.phone', read_only=True, default=None)

    class Meta:
        model = ParentProfile
        fields = [
            'id', 'user_id', 'email', 'first_name', 'last_name', 'full_name', 'phone',
            'phone_alt', 'home_address', 'city', 'state', 'country',
            'date_of_birth', 'profile_picture', 'occupation', 'employer_name',
            'national_id', 'receive_sms_alerts', 'receive_email_alerts',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user_id', 'email', 'first_name', 'last_name', 'full_name', 'phone', 'created_at', 'updated_at']

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.email


class UpdateParentProfileSerializer(serializers.ModelSerializer):
    """Serializer for updating a parent's own profile."""

    class Meta:
        model = ParentProfile
        fields = [
            'phone_alt', 'home_address', 'city', 'state', 'country',
            'date_of_birth', 'profile_picture', 'occupation', 'employer_name',
            'national_id', 'receive_sms_alerts', 'receive_email_alerts',
        ]


class CreateParentSerializer(serializers.Serializer):
    """Create or invite a parent to the school."""

    email      = serializers.EmailField()
    first_name = serializers.CharField(max_length=100)
    last_name  = serializers.CharField(max_length=100)
    phone      = serializers.CharField(max_length=20, required=False, allow_blank=True)
    send_welcome_email = serializers.BooleanField(default=True)


class ParentStudentLinkSerializer(serializers.Serializer):
    """
    Serializer for creating a parent-student link.
    Used by school admins to link a parent to a student.
    """

    student_id   = serializers.UUIDField()
    relationship = serializers.CharField(max_length=50, default='parent')


class ParentStudentLinkDetailSerializer(serializers.Serializer):
    """Read serializer for a parent-student link."""

    id           = serializers.UUIDField(read_only=True)
    student_id   = serializers.UUIDField(source='student.id', read_only=True)
    student_name = serializers.SerializerMethodField()
    student_email = serializers.EmailField(source='student.email', read_only=True)
    relationship = serializers.CharField(read_only=True)
    status       = serializers.CharField(read_only=True)
    created_at   = serializers.DateTimeField(read_only=True)

    def get_student_name(self, obj):
        return obj.student.get_full_name() or obj.student.email


class ParentMembershipSerializer(serializers.Serializer):
    """
    Detailed parent record for school admin parent-management views.
    Includes user fields + linked children.
    """

    id         = serializers.UUIDField(read_only=True)
    user_id    = serializers.SerializerMethodField()
    email      = serializers.SerializerMethodField()
    first_name = serializers.SerializerMethodField()
    last_name  = serializers.SerializerMethodField()
    full_name  = serializers.SerializerMethodField()
    phone      = serializers.SerializerMethodField()
    role       = serializers.CharField(read_only=True)
    joined_at  = serializers.DateTimeField(read_only=True)
    is_active  = serializers.BooleanField(read_only=True)
    children   = serializers.SerializerMethodField()

    def get_user_id(self, obj):
        return str(obj.user.id)

    def get_email(self, obj):
        return obj.user.email

    def get_first_name(self, obj):
        return obj.user.first_name

    def get_last_name(self, obj):
        return obj.user.last_name

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.email

    def get_phone(self, obj):
        return obj.user.phone

    def get_children(self, obj):
        from schools.models import ParentStudentLink
        links = ParentStudentLink.objects.filter(
            school=obj.school,
            parent=obj.user,
            status=ParentStudentLink.Status.APPROVED,
        ).select_related('student')
        return [
            {
                'student_id': str(link.student.id),
                'student_name': link.student.get_full_name(),
                'student_email': link.student.email,
                'relationship': link.relationship,
                'link_id': str(link.id),
            }
            for link in links
        ]
