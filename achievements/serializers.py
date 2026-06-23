"""
Serializers for the achievements app.
Phase 6D: Leaderboards, Badges & Achievements.

Serializers:
  - BadgeSerializer
  - StudentBadgeSerializer
  - LeaderboardEntrySerializer
  - AchievementPageSerializer   — combined view: badges + rank + progress
  - ReportQuerySerializer       — query params for report generation
"""

from rest_framework import serializers

from achievements.models import Badge, StudentBadge, LeaderboardEntry


# ─────────────────────────────────────────────────────────────────────────────
# Badge
# ─────────────────────────────────────────────────────────────────────────────

class BadgeSerializer(serializers.ModelSerializer):
    tier_display = serializers.CharField(source='get_tier_display', read_only=True)
    badge_type_display = serializers.CharField(source='get_badge_type_display', read_only=True)

    class Meta:
        model = Badge
        fields = [
            'id', 'name', 'badge_type', 'badge_type_display',
            'tier', 'tier_display', 'description', 'icon',
            'criteria', 'is_global', 'is_active',
        ]
        read_only_fields = ['id']


# ─────────────────────────────────────────────────────────────────────────────
# StudentBadge
# ─────────────────────────────────────────────────────────────────────────────

class StudentBadgeSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)
    student_name = serializers.CharField(source='student.full_name', read_only=True)

    class Meta:
        model = StudentBadge
        fields = [
            'id', 'badge', 'student_name',
            'awarded_for', 'awarded_at', 'is_seen',
        ]
        read_only_fields = ['id', 'awarded_at']


class StudentBadgeMarkSeenSerializer(serializers.Serializer):
    """Used to mark one or all badges as seen."""
    badge_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        help_text='List of StudentBadge IDs to mark seen. Omit to mark all.',
    )


# ─────────────────────────────────────────────────────────────────────────────
# LeaderboardEntry
# ─────────────────────────────────────────────────────────────────────────────

class LeaderboardEntrySerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_id = serializers.UUIDField(source='student.id', read_only=True)
    leaderboard_type_display = serializers.CharField(
        source='get_leaderboard_type_display', read_only=True
    )
    classroom_name = serializers.SerializerMethodField()
    subject_name = serializers.SerializerMethodField()
    term_name = serializers.SerializerMethodField()

    class Meta:
        model = LeaderboardEntry
        fields = [
            'id', 'rank',
            'student_id', 'student_name',
            'leaderboard_type', 'leaderboard_type_display',
            'classroom_name', 'subject_name', 'term_name',
            'highest_score', 'average_score',
            'total_exams', 'total_practice', 'activity_score',
            'calculated_at',
        ]
        read_only_fields = fields

    def get_classroom_name(self, obj):
        return obj.classroom.name if obj.classroom else None

    def get_subject_name(self, obj):
        return obj.subject.name if obj.subject else None

    def get_term_name(self, obj):
        return obj.term.name if obj.term else None


# ─────────────────────────────────────────────────────────────────────────────
# Achievement Page — combined student view
# ─────────────────────────────────────────────────────────────────────────────

class AchievementPageSerializer(serializers.Serializer):
    """
    Read-only combined serializer for the student achievement page.
    Returns badges earned, school rank, class rank, and progress stats.
    """
    # Badges
    total_badges = serializers.IntegerField(read_only=True)
    unseen_badges = serializers.IntegerField(read_only=True)
    badges = StudentBadgeSerializer(many=True, read_only=True)

    # Rankings
    school_rank = serializers.IntegerField(allow_null=True, read_only=True)
    class_rank = serializers.IntegerField(allow_null=True, read_only=True)
    total_students_in_school = serializers.IntegerField(read_only=True)

    # Performance summary
    average_score = serializers.FloatField(read_only=True)
    highest_score = serializers.FloatField(read_only=True)
    total_exams = serializers.IntegerField(read_only=True)
    total_practice = serializers.IntegerField(read_only=True)
    activity_score = serializers.FloatField(read_only=True)

    # Badge breakdown by tier
    bronze_count = serializers.IntegerField(read_only=True)
    silver_count = serializers.IntegerField(read_only=True)
    gold_count = serializers.IntegerField(read_only=True)
    platinum_count = serializers.IntegerField(read_only=True)


# ─────────────────────────────────────────────────────────────────────────────
# Report query params
# ─────────────────────────────────────────────────────────────────────────────

class ReportQuerySerializer(serializers.Serializer):
    """Query parameters for report generation endpoints."""
    term_id = serializers.UUIDField(
        required=False, allow_null=True,
        help_text='Filter report by term UUID. Omit for all-time report.',
    )
    subject_id = serializers.UUIDField(
        required=False, allow_null=True,
        help_text='Required for subject report.',
    )
    classroom_id = serializers.UUIDField(
        required=False, allow_null=True,
        help_text='Required for class report.',
    )
    student_id = serializers.UUIDField(
        required=False, allow_null=True,
        help_text='Required for student report when called by admin/teacher.',
    )


class LeaderboardQuerySerializer(serializers.Serializer):
    """Query params for leaderboard endpoints."""
    term_id = serializers.UUIDField(required=False, allow_null=True)
    limit = serializers.IntegerField(
        required=False, default=20, min_value=1, max_value=100
    )
    rebuild = serializers.BooleanField(
        required=False, default=False,
        help_text='Set true to force a leaderboard rebuild (admin/teacher only).',
    )
