"""T7: admin group API (/api/admin/groups).

Covers group CRUD, member add/remove, project grant/revoke, the admin-only gate,
active-organization scoping and idempotent duplicate handling.
"""

import pytest
from django.urls import reverse
from groups.models import UserGroup, UserGroupMember, UserGroupProject
from groups.tests.factories import UserGroupFactory
from organizations.tests.factories import OrganizationFactory
from projects.tests.factories import ProjectFactory
from rest_framework.test import APIClient
from users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def organization():
    return OrganizationFactory()


@pytest.fixture
def admin(organization):
    return UserFactory(active_organization=organization, is_admin=True)


@pytest.fixture
def member(organization):
    return UserFactory(active_organization=organization)


@pytest.fixture
def group(organization):
    return UserGroupFactory(organization=organization, created_by=organization.created_by)


@pytest.fixture
def project(organization):
    return ProjectFactory(organization=organization)


class TestAdminGroupCrud:
    def test_admin_lists_only_active_organization_groups(self, client, admin, organization):
        mine = UserGroupFactory(organization=organization, created_by=admin)
        other_organization = OrganizationFactory()
        UserGroupFactory(organization=other_organization, created_by=other_organization.created_by)

        client.force_authenticate(user=admin)
        response = client.get(reverse('admin-group-list'))

        assert response.status_code == 200
        body = response.json()
        assert [item['id'] for item in body] == [mine.id]
        assert body[0]['organization'] == organization.id
        assert body[0]['created_by'] == admin.id

    def test_admin_creates_group(self, client, admin, organization):
        client.force_authenticate(user=admin)
        response = client.post(
            reverse('admin-group-list'),
            {'name': 'Data squad', 'description': 'Dataset access'},
            format='json',
        )

        assert response.status_code == 201
        body = response.json()
        assert body['name'] == 'Data squad'
        assert body['description'] == 'Dataset access'
        assert body['organization'] == organization.id
        assert body['created_by'] == admin.id

        group = UserGroup.objects.get(pk=body['id'])
        assert group.organization_id == organization.id
        assert group.created_by_id == admin.id

    def test_duplicate_name_in_same_organization_returns_400(self, client, admin, organization):
        UserGroupFactory(organization=organization, name='Data squad', created_by=admin)
        client.force_authenticate(user=admin)
        response = client.post(
            reverse('admin-group-list'),
            {'name': 'Data squad', 'description': 'duplicate'},
            format='json',
        )

        assert response.status_code == 400
        assert 'A group with this name already exists in the organization.' in response.content.decode()
        assert UserGroup.objects.filter(organization=organization, name='Data squad').count() == 1

    def test_same_name_in_other_organization_is_allowed(self, client, admin, organization):
        other_organization = OrganizationFactory()
        UserGroupFactory(organization=other_organization, name='Data squad', created_by=other_organization.created_by)
        client.force_authenticate(user=admin)
        response = client.post(
            reverse('admin-group-list'),
            {'name': 'Data squad', 'description': 'other org'},
            format='json',
        )

        assert response.status_code == 201
        assert UserGroup.objects.filter(organization=organization, name='Data squad').count() == 1

    def test_create_ignores_client_supplied_organization_and_created_by(self, client, admin, organization):
        other_organization = OrganizationFactory()
        client.force_authenticate(user=admin)
        response = client.post(
            reverse('admin-group-list'),
            {'name': 'Nope', 'organization': other_organization.id, 'created_by': admin.id},
            format='json',
        )

        assert response.status_code == 201
        assert response.json()['organization'] == organization.id
        assert response.json()['created_by'] == admin.id

    def test_admin_renames_group(self, client, admin, group):
        client.force_authenticate(user=admin)
        response = client.patch(
            reverse('admin-group-detail', args=[group.id]),
            {'name': 'Renamed', 'description': 'New description'},
            format='json',
        )

        assert response.status_code == 200
        group.refresh_from_db()
        assert group.name == 'Renamed'
        assert group.description == 'New description'

    def test_admin_deletes_group(self, client, admin, group):
        client.force_authenticate(user=admin)
        response = client.delete(reverse('admin-group-detail', args=[group.id]))

        assert response.status_code == 204
        assert not UserGroup.objects.filter(pk=group.id).exists()

    def test_admin_gets_group_detail(self, client, admin, group):
        client.force_authenticate(user=admin)
        response = client.get(reverse('admin-group-detail', args=[group.id]))

        assert response.status_code == 200
        assert response.json()['id'] == group.id


class TestAdminGroupMembers:
    def test_add_list_and_remove_member(self, client, admin, group, member):
        client.force_authenticate(user=admin)
        add = client.post(
            reverse('admin-group-member-list', args=[group.id]),
            {'user': member.id},
            format='json',
        )

        assert add.status_code == 201
        body = add.json()
        assert body['group'] == group.id
        assert body['user'] == member.id
        assert body['user_email'] == member.email
        assert body['user_name'] == member.name_or_email()

        listing = client.get(reverse('admin-group-member-list', args=[group.id]))
        assert listing.status_code == 200
        assert [item['user'] for item in listing.json()] == [member.id]

        remove = client.delete(reverse('admin-group-member-detail', args=[group.id, member.id]))
        assert remove.status_code == 204
        assert not UserGroupMember.objects.filter(group=group, user=member).exists()

    def test_add_member_requires_active_organization_membership(self, client, admin, group):
        outsider = UserFactory(active_organization=OrganizationFactory())
        client.force_authenticate(user=admin)
        response = client.post(
            reverse('admin-group-member-list', args=[group.id]),
            {'user': outsider.id},
            format='json',
        )

        assert response.status_code == 400
        assert not UserGroupMember.objects.filter(group=group, user=outsider).exists()

    def test_add_member_is_idempotent(self, client, admin, group, member):
        client.force_authenticate(user=admin)
        url = reverse('admin-group-member-list', args=[group.id])

        first = client.post(url, {'user': member.id}, format='json')
        second = client.post(url, {'user': member.id}, format='json')

        assert first.status_code == 201
        assert second.status_code == 201
        assert UserGroupMember.objects.filter(group=group, user=member).count() == 1

    def test_remove_missing_member_is_404(self, client, admin, group, member):
        client.force_authenticate(user=admin)
        response = client.delete(reverse('admin-group-member-detail', args=[group.id, member.id]))

        assert response.status_code == 404


class TestAdminGroupProjects:
    def test_grant_list_and_revoke_project(self, client, admin, group, project):
        client.force_authenticate(user=admin)
        grant = client.post(
            reverse('admin-group-project-list', args=[group.id]),
            {'project': project.id},
            format='json',
        )

        assert grant.status_code == 201
        body = grant.json()
        assert body['group'] == group.id
        assert body['project'] == project.id
        assert body['project_title'] == project.title

        listing = client.get(reverse('admin-group-project-list', args=[group.id]))
        assert listing.status_code == 200
        assert [item['project'] for item in listing.json()] == [project.id]

        revoke = client.delete(reverse('admin-group-project-detail', args=[group.id, project.id]))
        assert revoke.status_code == 204
        assert not UserGroupProject.objects.filter(group=group, project=project).exists()

    def test_grant_project_must_belong_to_active_organization(self, client, admin, group):
        other_project = ProjectFactory(organization=OrganizationFactory())
        client.force_authenticate(user=admin)
        response = client.post(
            reverse('admin-group-project-list', args=[group.id]),
            {'project': other_project.id},
            format='json',
        )

        assert response.status_code == 400
        assert not UserGroupProject.objects.filter(group=group, project=other_project).exists()

    def test_grant_project_is_idempotent(self, client, admin, group, project):
        client.force_authenticate(user=admin)
        url = reverse('admin-group-project-list', args=[group.id])

        first = client.post(url, {'project': project.id}, format='json')
        second = client.post(url, {'project': project.id}, format='json')

        assert first.status_code == 201
        assert second.status_code == 201
        assert UserGroupProject.objects.filter(group=group, project=project).count() == 1

    def test_revoke_missing_project_link_is_404(self, client, admin, group, project):
        client.force_authenticate(user=admin)
        response = client.delete(reverse('admin-group-project-detail', args=[group.id, project.id]))

        assert response.status_code == 404


class TestAdminGroupPermissions:
    def test_plain_member_is_forbidden_on_every_endpoint(self, client, member, group, project):
        client.force_authenticate(user=member)
        calls = [
            ('get', reverse('admin-group-list')),
            ('post', reverse('admin-group-list')),
            ('get', reverse('admin-group-detail', args=[group.id])),
            ('patch', reverse('admin-group-detail', args=[group.id])),
            ('delete', reverse('admin-group-detail', args=[group.id])),
            ('get', reverse('admin-group-member-list', args=[group.id])),
            ('post', reverse('admin-group-member-list', args=[group.id])),
            ('delete', reverse('admin-group-member-detail', args=[group.id, member.id])),
            ('get', reverse('admin-group-project-list', args=[group.id])),
            ('post', reverse('admin-group-project-list', args=[group.id])),
            ('delete', reverse('admin-group-project-detail', args=[group.id, project.id])),
        ]

        for method, url in calls:
            response = getattr(client, method)(url, {'user': member.id, 'project': project.id}, format='json')
            assert response.status_code == 403, (method, url, response.status_code)

    def test_anonymous_is_rejected(self, client):
        response = client.get(reverse('admin-group-list'))

        assert response.status_code in (401, 403)


class TestAdminGroupCrossOrganization:
    def test_other_organization_group_is_404(self, client, admin):
        other_organization = OrganizationFactory()
        other_group = UserGroupFactory(organization=other_organization, created_by=other_organization.created_by)
        client.force_authenticate(user=admin)

        assert client.get(reverse('admin-group-detail', args=[other_group.id])).status_code == 404
        assert (
            client.patch(
                reverse('admin-group-detail', args=[other_group.id]), {'name': 'x'}, format='json'
            ).status_code
            == 404
        )
        assert client.delete(reverse('admin-group-detail', args=[other_group.id])).status_code == 404
        assert client.get(reverse('admin-group-member-list', args=[other_group.id])).status_code == 404
        assert client.get(reverse('admin-group-project-list', args=[other_group.id])).status_code == 404

    def test_cross_organization_project_link_is_404(self, client, admin, group):
        other_project = ProjectFactory(organization=OrganizationFactory())
        client.force_authenticate(user=admin)
        response = client.delete(reverse('admin-group-project-detail', args=[group.id, other_project.id]))

        assert response.status_code == 404
