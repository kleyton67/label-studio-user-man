"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from groups.models import UserGroup, UserGroupMember, UserGroupProject
from projects.models import Project
from rest_framework import serializers
from users.models import User


class UserGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserGroup
        fields = ['id', 'organization', 'name', 'description', 'created_by', 'created_at', 'updated_at']
        read_only_fields = ['id', 'organization', 'created_by', 'created_at', 'updated_at']

    def validate(self, attrs):
        # organization is read-only (set in perform_create), so UniqueTogetherValidator
        # cannot see it and would reject every create as "This field is required." --
        # resolve it from the request context and enforce unique_together here.
        name = attrs.get('name')
        if not name:
            return attrs

        organization = attrs.get('organization')
        if organization is None:
            request = self.context.get('request')
            organization = getattr(getattr(request, 'user', None), 'active_organization', None)
        if organization is None:
            return attrs

        conflicts = UserGroup.objects.filter(organization=organization, name=name)
        if self.instance is not None:
            conflicts = conflicts.exclude(pk=self.instance.pk)
        if conflicts.exists():
            raise serializers.ValidationError(
                {'name': 'A group with this name already exists in the organization.'}
            )
        return attrs


class UserGroupMemberSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = UserGroupMember
        fields = ['id', 'group', 'user', 'user_email', 'user_name', 'created_at']
        read_only_fields = ['id', 'group', 'created_at']

    def get_user_name(self, member) -> str:
        return member.user.name_or_email()


class UserGroupProjectSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    project_title = serializers.SerializerMethodField()

    class Meta:
        model = UserGroupProject
        fields = ['id', 'group', 'project', 'project_title', 'created_at']
        read_only_fields = ['id', 'group', 'created_at']

    def get_project_title(self, link) -> str:
        return link.project.title
