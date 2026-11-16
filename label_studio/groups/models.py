"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserGroup(models.Model):
    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.CASCADE, related_name='user_groups'
    )
    name = models.CharField(_('name'), max_length=255)
    description = models.TextField(_('description'), blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_user_groups',
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        db_table = 'user_group'
        unique_together = [['organization', 'name']]
        ordering = ['name']

    def has_permission(self, user):
        return user.active_organization_id == self.organization_id


class UserGroupMember(models.Model):
    group = models.ForeignKey(UserGroup, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_group_memberships'
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        unique_together = [['group', 'user']]


class UserGroupProject(models.Model):
    group = models.ForeignKey(UserGroup, on_delete=models.CASCADE, related_name='project_links')
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='user_group_links')
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        unique_together = [['group', 'project']]
