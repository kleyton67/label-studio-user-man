"""T2: `User.is_admin`, admin permissions and `is_admin` in whoami."""

import pytest
from core.api_permissions import IsOrganizationAdmin
from django.contrib.auth.models import AnonymousUser
from organizations.tests.factories import OrganizationFactory
from rest_framework.test import APIClient
from users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


class _StubRequest:
    def __init__(self, user):
        self.user = user


def _has_admin_permission(user) -> bool:
    return IsOrganizationAdmin().has_permission(_StubRequest(user), view=None)


@pytest.fixture
def client():
    return APIClient()


def _whoami(client, user):
    client.force_authenticate(user)
    return client.get('/api/current-user/whoami')


def test_whoami_is_admin_true_for_admin_flag(client):
    organization = OrganizationFactory()
    admin = UserFactory(active_organization=organization, is_admin=True)

    response = _whoami(client, admin)

    assert response.status_code == 200
    assert response.json()['is_admin'] is True


def test_whoami_is_admin_true_for_org_creator(client):
    organization = OrganizationFactory()

    response = _whoami(client, organization.created_by)

    assert response.status_code == 200
    assert response.json()['is_admin'] is True


def test_whoami_is_admin_false_for_plain_member(client):
    organization = OrganizationFactory()
    member = UserFactory(active_organization=organization)

    response = _whoami(client, member)

    assert response.status_code == 200
    assert response.json()['is_admin'] is False


def test_whoami_is_admin_false_without_active_organization(client):
    user = UserFactory(active_organization=None)

    response = _whoami(client, user)

    assert response.status_code == 200
    assert response.json()['is_admin'] is False


def test_is_organization_admin_allows_admin_flag():
    organization = OrganizationFactory()
    admin = UserFactory(active_organization=organization, is_admin=True)

    assert _has_admin_permission(admin) is True


def test_is_organization_admin_allows_org_creator():
    organization = OrganizationFactory()

    assert _has_admin_permission(organization.created_by) is True


def test_is_organization_admin_denies_plain_member():
    organization = OrganizationFactory()
    member = UserFactory(active_organization=organization)

    assert _has_admin_permission(member) is False


def test_is_organization_admin_denies_anonymous():
    assert _has_admin_permission(AnonymousUser()) is False
