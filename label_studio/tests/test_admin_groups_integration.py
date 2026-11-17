"""T14: end-to-end integration of admin group management and per-group dataset access.

The test drives the real HTTP surfaces only: an admin creates a group, adds a member and
grants a project through ``/api/admin/groups/*``; the member then sees exactly that project
in ``/api/projects/`` and in the Data Manager task list (``/api/tasks/?project=...``).
Revoking the grant (or the membership) removes access again. A member with no group sees
nothing, while the organization owner and admins always see every project in the org.
Plain members are denied on every admin endpoint.

Dataset == Project in this codebase; "DM task list" is the Data Manager task list.
"""

import pytest
from django.urls import reverse
from groups.models import UserGroup, UserGroupMember, UserGroupProject
from organizations.tests.factories import OrganizationFactory
from projects.tests.factories import ProjectFactory
from rest_framework.test import APIClient
from tasks.tests.factories import TaskFactory
from users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def organization():
    return OrganizationFactory()


@pytest.fixture
def owner(organization):
    return organization.created_by


@pytest.fixture
def admin(organization):
    return UserFactory(active_organization=organization, is_admin=True)


@pytest.fixture
def member(organization):
    return UserFactory(active_organization=organization)


@pytest.fixture
def loner(organization):
    """Member of the same organization with no group membership."""
    return UserFactory(active_organization=organization)


@pytest.fixture
def project_a(organization):
    return ProjectFactory(organization=organization, title='Dataset A')


@pytest.fixture
def project_b(organization):
    return ProjectFactory(organization=organization, title='Dataset B')


@pytest.fixture
def admin_client(admin):
    client = APIClient()
    client.force_authenticate(user=admin)
    return client


@pytest.fixture
def member_client(member):
    client = APIClient()
    client.force_authenticate(user=member)
    return client


@pytest.fixture
def loner_client(loner):
    client = APIClient()
    client.force_authenticate(user=loner)
    return client


@pytest.fixture
def owner_client(owner):
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


def create_group(client, name='Data squad'):
    response = client.post(reverse('admin-group-list'), {'name': name}, format='json')
    assert response.status_code == 201, response.json()
    return response.json()['id']


def add_member(client, group_id, user_id):
    response = client.post(reverse('admin-group-member-list', args=[group_id]), {'user': user_id}, format='json')
    assert response.status_code == 201, response.json()


def grant_project(client, group_id, project_id):
    response = client.post(
        reverse('admin-group-project-list', args=[group_id]), {'project': project_id}, format='json'
    )
    assert response.status_code == 201, response.json()


def visible_project_ids(client):
    response = client.get(reverse('projects:api:project-list'))
    assert response.status_code == 200, response.json()
    return {project['id'] for project in response.json()['results']}


def dm_task_ids(client, project_id):
    response = client.get(reverse('tasks:api:task-list'), {'project': project_id})
    return response


class TestAdminGrantFlow:
    def test_member_sees_exactly_the_granted_project(self, admin_client, member_client, member, project_a, project_b):
        """Admin creates a group, adds a member, grants project A; the member sees only A."""
        group_id = create_group(admin_client)
        add_member(admin_client, group_id, member.id)
        grant_project(admin_client, group_id, project_a.id)

        assert visible_project_ids(member_client) == {project_a.id}

        # The grant is stored as a real membership + project link.
        group = UserGroup.objects.get(pk=group_id)
        assert UserGroupMember.objects.filter(group=group, user=member).exists()
        assert UserGroupProject.objects.filter(group=group, project=project_a).exists()

    def test_member_dm_task_list_shows_granted_project_tasks(
        self, admin_client, member_client, member, project_a, project_b
    ):
        """The member's Data Manager task list returns the granted project's tasks only."""
        task_a = TaskFactory(project=project_a, data={'text': 'a'})
        TaskFactory(project=project_b, data={'text': 'b'})

        group_id = create_group(admin_client)
        add_member(admin_client, group_id, member.id)
        grant_project(admin_client, group_id, project_a.id)

        response = dm_task_ids(member_client, project_a.id)
        assert response.status_code == 200, response.json()
        body = response.json()
        assert body['total'] == 1
        assert {task['id'] for task in body['tasks']} == {task_a.id}

        # A project the member has no grant for is not reachable through the DM list.
        assert dm_task_ids(member_client, project_b.id).status_code == 404

    def test_revoke_project_grant_removes_member_access(
        self, admin_client, member_client, member, project_a, project_b
    ):
        """After the admin revokes the grant, the member no longer sees the project."""
        group_id = create_group(admin_client)
        add_member(admin_client, group_id, member.id)
        grant_project(admin_client, group_id, project_a.id)
        assert visible_project_ids(member_client) == {project_a.id}

        revoke = admin_client.delete(reverse('admin-group-project-detail', args=[group_id, project_a.id]))
        assert revoke.status_code == 204

        assert visible_project_ids(member_client) == set()
        assert dm_task_ids(member_client, project_a.id).status_code == 404

    def test_remove_member_removes_access(self, admin_client, member_client, member, project_a):
        """Removing the member from the group removes their access to the granted project."""
        group_id = create_group(admin_client)
        add_member(admin_client, group_id, member.id)
        grant_project(admin_client, group_id, project_a.id)
        assert visible_project_ids(member_client) == {project_a.id}

        remove = admin_client.delete(reverse('admin-group-member-detail', args=[group_id, member.id]))
        assert remove.status_code == 204

        assert visible_project_ids(member_client) == set()


class TestVisibilityMatrix:
    def test_member_without_group_sees_no_projects(
        self, loner_client, project_a, project_b, admin_client, member, organization
    ):
        """A non-admin member with no group membership sees no projects at all."""
        # A grant exists for somebody else: it must not leak to the group-less member.
        group_id = create_group(admin_client)
        add_member(admin_client, group_id, member.id)
        grant_project(admin_client, group_id, project_a.id)

        assert visible_project_ids(loner_client) == set()
        assert dm_task_ids(loner_client, project_a.id).status_code == 404

    def test_owner_sees_all_projects(self, owner_client, project_a, project_b):
        """The organization owner always sees every project in the organization."""
        assert visible_project_ids(owner_client) == {project_a.id, project_b.id}

    def test_admin_sees_all_projects(self, admin_client, project_a, project_b):
        """An admin (is_admin flag) always sees every project in the organization."""
        assert visible_project_ids(admin_client) == {project_a.id, project_b.id}

    def test_admin_grant_does_not_leak_across_organizations(self, admin_client, member_client, member, organization):
        """A grant made by another organization's admin does not reach this member."""
        other_organization = OrganizationFactory()
        other_admin = UserFactory(active_organization=other_organization, is_admin=True)
        other_project = ProjectFactory(organization=other_organization, title='Other org dataset')

        other_client = APIClient()
        other_client.force_authenticate(user=other_admin)
        other_group_id = create_group(other_client, name='Other squad')
        # The other admin cannot add a member from a different organization.
        outsider_add = other_client.post(
            reverse('admin-group-member-list', args=[other_group_id]),
            {'user': member.id},
            format='json',
        )
        assert outsider_add.status_code == 400
        grant_project(other_client, other_group_id, other_project.id)

        assert visible_project_ids(member_client) == set()


class TestAdminApiGate:
    def test_plain_member_is_forbidden_on_group_admin_endpoints(self, member_client, admin_client, member, project_a):
        """A plain member gets 403 on every /api/admin/groups endpoint."""
        group_id = create_group(admin_client)
        add_member(admin_client, group_id, member.id)

        calls = [
            ('get', reverse('admin-group-list'), {}),
            ('post', reverse('admin-group-list'), {'name': 'Nope'}),
            ('get', reverse('admin-group-detail', args=[group_id]), {}),
            ('patch', reverse('admin-group-detail', args=[group_id]), {'name': 'Nope'}),
            ('delete', reverse('admin-group-detail', args=[group_id]), {}),
            ('get', reverse('admin-group-member-list', args=[group_id]), {}),
            ('post', reverse('admin-group-member-list', args=[group_id]), {'user': member.id}),
            ('delete', reverse('admin-group-member-detail', args=[group_id, member.id]), {}),
            ('get', reverse('admin-group-project-list', args=[group_id]), {}),
            ('post', reverse('admin-group-project-list', args=[group_id]), {'project': project_a.id}),
            (
                'delete',
                reverse('admin-group-project-detail', args=[group_id, project_a.id]),
                {},
            ),
        ]

        for method, url, payload in calls:
            response = getattr(member_client, method)(url, payload, format='json')
            assert response.status_code == 403, (method, url, response.status_code)

    def test_plain_member_is_forbidden_on_user_admin_endpoints(self, member_client, owner):
        """A plain member gets 403 on every /api/admin/users endpoint."""
        calls = [
            ('get', '/api/admin/users/'),
            ('post', '/api/admin/users/'),
            ('get', f'/api/admin/users/{owner.id}/'),
            ('patch', f'/api/admin/users/{owner.id}/'),
            ('delete', f'/api/admin/users/{owner.id}/'),
            ('get', f'/api/admin/users/{owner.id}/groups/'),
            ('put', f'/api/admin/users/{owner.id}/groups/'),
        ]

        for method, url in calls:
            payload = (
                {'email': 'x@example.com', 'password': 'StrongPassw0rd!'}
                if method == 'post'
                else ({'groups': []} if method == 'put' else {})
            )
            response = getattr(member_client, method)(url, payload, format='json')
            assert response.status_code == 403, (method, url, response.status_code)

    def test_anonymous_is_rejected_on_admin_endpoints(self):
        """Anonymous callers are rejected (401/403) on the admin endpoints."""
        client = APIClient()
        assert client.get(reverse('admin-group-list')).status_code in (401, 403)
        assert client.get('/api/admin/users/').status_code in (401, 403)
