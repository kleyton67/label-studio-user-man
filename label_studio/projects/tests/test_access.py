"""Tests for the restrictive group-based access layer (T4).

Covers:
- accessible_projects: group-granted visibility, union of groups, admin/owner sees all,
  no-group non-admin sees nothing, soft-deleted membership sees nothing.
- Project.has_permission: True for granted project, False for non-granted, True for
  project without organization.
- ProjectListAPI: 200 with only granted project for group member; empty list for
  no-group user.
"""

import pytest
from django.urls import reverse
from groups.models import UserGroup, UserGroupMember, UserGroupProject
from organizations.tests.factories import OrganizationFactory
from projects.functions.access import accessible_projects, is_admin_user, user_group_project_ids
from projects.models import Project
from projects.tests.factories import ProjectFactory
from rest_framework.test import APIClient
from users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# accessible_projects
# ---------------------------------------------------------------------------


class TestAccessibleProjects:
    def test_group_member_sees_granted_project_only(self):
        """User in a group granted project A sees A and not B."""
        org = OrganizationFactory()
        user = UserFactory(active_organization=org)
        project_a = ProjectFactory(organization=org, title='A')
        project_b = ProjectFactory(organization=org, title='B')

        group = UserGroup.objects.create(organization=org, name='DS', created_by=org.created_by)
        UserGroupMember.objects.create(group=group, user=user)
        UserGroupProject.objects.create(group=group, project=project_a)

        visible = set(accessible_projects(user).values_list('id', flat=True))
        assert project_a.id in visible
        assert project_b.id not in visible

    def test_two_groups_union(self):
        """User in two groups sees the union of their granted projects."""
        org = OrganizationFactory()
        user = UserFactory(active_organization=org)
        project_a = ProjectFactory(organization=org, title='A')
        project_b = ProjectFactory(organization=org, title='B')
        project_c = ProjectFactory(organization=org, title='C')

        g1 = UserGroup.objects.create(organization=org, name='G1', created_by=org.created_by)
        g2 = UserGroup.objects.create(organization=org, name='G2', created_by=org.created_by)
        UserGroupMember.objects.create(group=g1, user=user)
        UserGroupMember.objects.create(group=g2, user=user)
        UserGroupProject.objects.create(group=g1, project=project_a)
        UserGroupProject.objects.create(group=g2, project=project_b)

        visible = set(accessible_projects(user).values_list('id', flat=True))
        assert visible == {project_a.id, project_b.id}
        assert project_c.id not in visible

    def test_non_admin_no_group_sees_nothing(self):
        """Non-admin user with no group membership sees no projects."""
        org = OrganizationFactory()
        user = UserFactory(active_organization=org)
        ProjectFactory(organization=org, title='A')
        ProjectFactory(organization=org, title='B')

        assert accessible_projects(user).count() == 0

    def test_org_owner_sees_all_projects(self):
        """Organization owner (created_by) sees all org projects."""
        org = OrganizationFactory()
        owner = org.created_by
        owner.active_organization = org
        owner.save(update_fields=['active_organization'])
        project_a = ProjectFactory(organization=org, title='A')
        project_b = ProjectFactory(organization=org, title='B')

        visible = set(accessible_projects(owner).values_list('id', flat=True))
        assert visible == {project_a.id, project_b.id}

    def test_is_admin_flag_sees_all_projects(self):
        """User with is_admin=True sees all org projects."""
        org = OrganizationFactory()
        admin = UserFactory(active_organization=org)
        admin.is_admin = True
        admin.save(update_fields=['is_admin'])
        project_a = ProjectFactory(organization=org, title='A')
        project_b = ProjectFactory(organization=org, title='B')

        visible = set(accessible_projects(admin).values_list('id', flat=True))
        assert visible == {project_a.id, project_b.id}

    def test_soft_deleted_membership_sees_nothing(self):
        """Soft-deleted org membership sees no projects (even with group grants)."""
        org = OrganizationFactory()
        user = UserFactory(active_organization=org)
        project_a = ProjectFactory(organization=org, title='A')

        group = UserGroup.objects.create(organization=org, name='DS', created_by=org.created_by)
        UserGroupMember.objects.create(group=group, user=user)
        UserGroupProject.objects.create(group=group, project=project_a)

        user.om_through.get(organization=org).soft_delete()

        assert accessible_projects(user).count() == 0

    def test_no_active_organization_sees_nothing(self):
        """User with no active_organization sees no projects."""
        user = UserFactory(active_organization=None)
        org = OrganizationFactory()
        ProjectFactory(organization=org, title='A')

        assert accessible_projects(user).count() == 0

    def test_cross_org_project_not_included(self):
        """Projects from another org are never included."""
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        user = UserFactory(active_organization=org1)

        project_other = ProjectFactory(organization=org2, title='Other')
        group = UserGroup.objects.create(organization=org1, name='G', created_by=org1.created_by)
        UserGroupMember.objects.create(group=group, user=user)
        UserGroupProject.objects.create(group=group, project=project_other)

        visible = set(accessible_projects(user).values_list('id', flat=True))
        assert project_other.id not in visible


# ---------------------------------------------------------------------------
# is_admin_user / user_group_project_ids helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_is_admin_user_superuser(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = UserFactory()
        user.is_superuser = True
        user.save(update_fields=['is_superuser'])
        assert is_admin_user(user) is True

    def test_is_admin_user_flag(self):
        user = UserFactory()
        user.is_admin = True
        user.save(update_fields=['is_admin'])
        assert is_admin_user(user) is True

    def test_is_admin_user_org_owner(self):
        org = OrganizationFactory()
        assert is_admin_user(org.created_by) is True

    def test_is_admin_user_plain_member(self):
        org = OrganizationFactory()
        user = UserFactory(active_organization=org)
        assert is_admin_user(user) is False

    def test_user_group_project_ids_returns_granted_ids(self):
        org = OrganizationFactory()
        user = UserFactory(active_organization=org)
        p1 = ProjectFactory(organization=org)
        p2 = ProjectFactory(organization=org)
        group = UserGroup.objects.create(organization=org, name='G', created_by=org.created_by)
        UserGroupMember.objects.create(group=group, user=user)
        UserGroupProject.objects.create(group=group, project=p1)
        UserGroupProject.objects.create(group=group, project=p2)

        ids = set(user_group_project_ids(user, org.id))
        assert ids == {p1.id, p2.id}


# ---------------------------------------------------------------------------
# Project.has_permission
# ---------------------------------------------------------------------------


class TestProjectHasPermission:
    def test_granted_project_returns_true(self):
        org = OrganizationFactory()
        user = UserFactory(active_organization=org)
        project = ProjectFactory(organization=org)

        group = UserGroup.objects.create(organization=org, name='G', created_by=org.created_by)
        UserGroupMember.objects.create(group=group, user=user)
        UserGroupProject.objects.create(group=group, project=project)

        assert project.has_permission(user) is True

    def test_non_granted_project_returns_false(self):
        org = OrganizationFactory()
        user = UserFactory(active_organization=org)
        project = ProjectFactory(organization=org)

        assert project.has_permission(user) is False

    def test_project_without_organization_returns_true(self):
        project = Project.objects.create(title='No organization')
        user = UserFactory()

        assert project.has_permission(user) is True


# ---------------------------------------------------------------------------
# ProjectListAPI (DRF)
# ---------------------------------------------------------------------------


class TestProjectListAPIAccess:
    def test_group_member_sees_only_granted_project(self):
        """ProjectListAPI returns 200 with only the granted project for a group member."""
        org = OrganizationFactory()
        user = UserFactory(active_organization=org)
        project_a = ProjectFactory(organization=org, title='A')
        ProjectFactory(organization=org, title='B')

        group = UserGroup.objects.create(organization=org, name='DS', created_by=org.created_by)
        UserGroupMember.objects.create(group=group, user=user)
        UserGroupProject.objects.create(group=group, project=project_a)

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get(reverse('projects:api:project-list'))

        assert response.status_code == 200
        ids = {p['id'] for p in response.json()['results']}
        assert ids == {project_a.id}

    def test_no_group_user_sees_empty_list(self):
        """ProjectListAPI returns 200 with empty results for a no-group user."""
        org = OrganizationFactory()
        user = UserFactory(active_organization=org)
        ProjectFactory(organization=org, title='A')
        ProjectFactory(organization=org, title='B')

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get(reverse('projects:api:project-list'))

        assert response.status_code == 200
        assert response.json()['results'] == []

    def test_admin_sees_all_projects(self):
        """ProjectListAPI returns all org projects for the org owner."""
        org = OrganizationFactory()
        owner = org.created_by
        owner.active_organization = org
        owner.save(update_fields=['active_organization'])
        project_a = ProjectFactory(organization=org, title='A')
        project_b = ProjectFactory(organization=org, title='B')

        client = APIClient()
        client.force_authenticate(user=owner)
        response = client.get(reverse('projects:api:project-list'))

        assert response.status_code == 200
        ids = {p['id'] for p in response.json()['results']}
        assert ids == {project_a.id, project_b.id}


# ---------------------------------------------------------------------------
# ProjectManager.for_user
# ---------------------------------------------------------------------------


class TestProjectManagerForUser:
    def test_for_user_scopes_by_group_access(self):
        org = OrganizationFactory()
        user = UserFactory(active_organization=org)
        project_a = ProjectFactory(organization=org, title='A')
        ProjectFactory(organization=org, title='B')

        group = UserGroup.objects.create(organization=org, name='G', created_by=org.created_by)
        UserGroupMember.objects.create(group=group, user=user)
        UserGroupProject.objects.create(group=group, project=project_a)

        visible = set(Project.objects.for_user(user).values_list('id', flat=True))
        assert visible == {project_a.id}

    def test_for_user_empty_for_no_group(self):
        org = OrganizationFactory()
        user = UserFactory(active_organization=org)
        ProjectFactory(organization=org, title='A')

        assert Project.objects.for_user(user).count() == 0
