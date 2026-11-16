"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import time

from django.conf import settings
from django.contrib import admin as dj_admin
from django.contrib.auth.models import Group
from django.test import TestCase
from groups.models import UserGroup, UserGroupMember, UserGroupProject
from users.admin import UserAdminShort
from users.models import User


def _login(client, user):
    client.force_login(user)
    session = client.session
    # InactivitySessionTimeoutMiddleWare logs out sessions without a recent last_login
    session['last_login'] = time.time()
    session.save()
    client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key


class TestGroupAdminRegistration(TestCase):
    def test_user_group_registered(self):
        assert dj_admin.site.is_registered(UserGroup)

    def test_user_group_member_registered(self):
        assert dj_admin.site.is_registered(UserGroupMember)

    def test_user_group_project_registered(self):
        assert dj_admin.site.is_registered(UserGroupProject)

    def test_django_auth_group_stays_unregistered(self):
        assert not dj_admin.site.is_registered(Group)

    def test_is_admin_in_user_admin_short_display_filter_and_fieldsets(self):
        # UserAdminShort assigns list_display/list_filter/fieldsets in __init__, so read from an instance
        instance = UserAdminShort(User, dj_admin.site)
        assert 'is_admin' in instance.list_display
        assert 'is_admin' in instance.list_filter
        permissions_fieldsets = [fs for fs in instance.fieldsets if fs[0] == 'Permissions']
        assert permissions_fieldsets
        assert 'is_admin' in permissions_fieldsets[0][1]['fields']


class TestGroupAdminPages(TestCase):
    urls = ('/admin/groups/usergroup/', '/admin/groups/usergroupmember/', '/admin/groups/usergroupproject/')

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='t9-superuser',
            email='t9-superuser@example.com',
            password='pass',
        )
        self.non_staff = User.objects.create_user(
            username='t9-nonstaff',
            email='t9-nonstaff@example.com',
            password='pass',
        )

    def test_usergroup_changelist_as_superuser(self):
        _login(self.client, self.superuser)
        response = self.client.get('/admin/groups/usergroup/')
        assert response.status_code == 200

    def test_usergroupmember_changelist_as_superuser(self):
        _login(self.client, self.superuser)
        response = self.client.get('/admin/groups/usergroupmember/')
        assert response.status_code == 200

    def test_usergroupproject_changelist_as_superuser(self):
        _login(self.client, self.superuser)
        response = self.client.get('/admin/groups/usergroupproject/')
        assert response.status_code == 200

    def test_admin_pages_denied_for_non_staff(self):
        _login(self.client, self.non_staff)
        for url in self.urls:
            response = self.client.get(url)
            assert response.status_code in (302, 403), f'{url} returned {response.status_code}'
            assert response.status_code != 200
