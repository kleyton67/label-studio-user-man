"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import time

from django.conf import settings
from django.test import TestCase
from organizations.tests.factories import OrganizationFactory
from users.tests.factories import UserFactory


def _login(client, user):
    client.force_login(user)
    session = client.session
    # InactivitySessionTimeoutMiddleWare logs out sessions without a recent last_login
    session['last_login'] = time.time()
    session.save()
    client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key


class TestAdminAreaView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.organization = OrganizationFactory()
        cls.admin = UserFactory(active_organization=cls.organization, is_admin=True)
        cls.member = UserFactory(active_organization=cls.organization)

    def _get(self, url):
        response = self.client.get(url)
        assert response.status_code in (200, 302), response.status_code
        return response

    def test_anonymous_is_redirected_to_login(self):
        for url in ['/admin/', '/admin/users/', '/admin/groups/']:
            response = self.client.get(url)
            assert response.status_code == 302, url
            assert response.url.startswith('/user/login/'), (url, response.url)

    def test_admin_gets_the_shell(self):
        _login(self.client, self.admin)

        response = self.client.get('/admin/')

        assert response.status_code == 200
        self.assertTemplateUsed(response, 'users/admin.html')

    def test_sub_paths_render_the_same_shell(self):
        _login(self.client, self.admin)

        for url in ['/admin/users/', '/admin/groups/']:
            response = self.client.get(url)
            assert response.status_code == 200, url
            self.assertTemplateUsed(response, 'users/admin.html')

    def test_non_admin_gets_the_empty_shell_not_an_error(self):
        """The page is login-gated only; the React layout redirects non-admins and the admin APIs deny them."""
        _login(self.client, self.member)

        response = self.client.get('/admin/')

        assert response.status_code == 200
        self.assertTemplateUsed(response, 'users/admin.html')

    def test_shell_breadcrumbs_target_admin(self):
        _login(self.client, self.admin)

        response = self.client.get('/admin/')

        content = response.content.decode()
        assert 'title: "Admin"' in content
