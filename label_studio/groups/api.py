"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from core.api_permissions import IsOrganizationAdmin
from groups.models import UserGroup, UserGroupMember, UserGroupProject
from groups.serializers import UserGroupMemberSerializer, UserGroupProjectSerializer, UserGroupSerializer
from organizations.models import OrganizationMember
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class AdminGroupMixin:
    """Shared admin gate and active-organization group lookup for the group admin API."""

    permission_classes = [IsAuthenticated, IsOrganizationAdmin]

    def get_group(self):
        return get_object_or_404(
            UserGroup.objects.filter(organization=self.request.user.active_organization),
            pk=self.kwargs['pk'],
        )


class AdminGroupListAPI(AdminGroupMixin, generics.ListCreateAPIView):
    serializer_class = UserGroupSerializer

    def get_queryset(self):
        return UserGroup.objects.filter(
            organization=self.request.user.active_organization
        ).select_related('created_by')

    def perform_create(self, serializer):
        serializer.save(
            organization=self.request.user.active_organization,
            created_by=self.request.user,
        )


class AdminGroupDetailAPI(AdminGroupMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserGroupSerializer

    def get_queryset(self):
        return UserGroup.objects.filter(
            organization=self.request.user.active_organization
        ).select_related('created_by')


class AdminGroupMemberListAPI(AdminGroupMixin, generics.ListCreateAPIView):
    serializer_class = UserGroupMemberSerializer

    def get_queryset(self):
        return self.get_group().members.select_related('user')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = self._get_or_create_member(serializer.validated_data['user'])
        return Response(self.get_serializer(member).data, status=status.HTTP_201_CREATED)

    def _get_or_create_member(self, user):
        organization = self.request.user.active_organization
        is_active_member = OrganizationMember.objects.filter(
            user=user, organization=organization, deleted_at__isnull=True
        ).exists()
        if not is_active_member:
            raise ValidationError({'user': 'User is not an active member of the organization.'})

        member, _created = UserGroupMember.objects.get_or_create(group=self.get_group(), user=user)
        return member


class AdminGroupMemberDetailAPI(AdminGroupMixin, generics.DestroyAPIView):
    serializer_class = UserGroupMemberSerializer

    def get_queryset(self):
        return self.get_group().members.select_related('user')

    def get_object(self):
        return get_object_or_404(self.get_queryset(), user_id=self.kwargs['user_pk'])


class AdminGroupProjectListAPI(AdminGroupMixin, generics.ListCreateAPIView):
    serializer_class = UserGroupProjectSerializer

    def get_queryset(self):
        return self.get_group().project_links.select_related('project')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        link = self._get_or_create_link(serializer.validated_data['project'])
        return Response(self.get_serializer(link).data, status=status.HTTP_201_CREATED)

    def _get_or_create_link(self, project):
        organization = self.request.user.active_organization
        if project.organization_id != organization.id:
            raise ValidationError({'project': 'Project does not belong to the organization.'})

        link, _created = UserGroupProject.objects.get_or_create(group=self.get_group(), project=project)
        return link


class AdminGroupProjectDetailAPI(AdminGroupMixin, generics.DestroyAPIView):
    serializer_class = UserGroupProjectSerializer

    def get_queryset(self):
        return self.get_group().project_links.select_related('project')

    def get_object(self):
        return get_object_or_404(self.get_queryset(), project_id=self.kwargs['project_pk'])
