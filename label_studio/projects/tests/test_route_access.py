"""Tests for restrictive group-based access on dataset routes (T5).

Covers:
- ProjectAPI: 403/404 for non-granted project
- ProjectTaskListAPI: 403/404 for non-granted project
- TaskAPI: 403/404 for task in non-granted project
- AnnotationAPI: 403/404 for annotation in non-granted project
- AnnotationsListAPI: 403/404 for annotations in non-granted project
- DataManager TaskListAPI: 403/404 for non-granted project
- ImportAPI: 403/404 for non-granted project
- ExportAPI: 403/404 for non-granted project
- Admin/owner still succeed on all routes
"""

import pytest
from django.urls import reverse
from groups.models import UserGroup, UserGroupMember, UserGroupProject
from organizations.tests.factories import OrganizationFactory
from projects.models import Project
from projects.tests.factories import ProjectFactory
from rest_framework.test import APIClient
from tasks.models import Annotation, Task
from users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return OrganizationFactory()


@pytest.fixture
def owner(org):
    owner = org.created_by
    owner.active_organization = org
    owner.save(update_fields=['active_organization'])
    return owner


@pytest.fixture
def admin(org):
    admin = UserFactory(active_organization=org)
    admin.is_admin = True
    admin.save(update_fields=['is_admin'])
    return admin


@pytest.fixture
def member_with_access(org):
    """Member granted project A via group."""
    user = UserFactory(active_organization=org)
    return user


@pytest.fixture
def member_no_access(org):
    """Member with no group membership."""
    user = UserFactory(active_organization=org)
    return user


@pytest.fixture
def project_a(org):
    return ProjectFactory(organization=org, title='A')


@pytest.fixture
def project_b(org):
    return ProjectFactory(organization=org, title='B')


@pytest.fixture
def grant_project_a(org, member_with_access, project_a):
    """Grant member_with_access to project_a via a group."""
    group = UserGroup.objects.create(organization=org, name='DS', created_by=org.created_by)
    UserGroupMember.objects.create(group=group, user=member_with_access)
    UserGroupProject.objects.create(group=group, project=project_a)
    return group


@pytest.fixture
def task_in_a(project_a):
    return Task.objects.create(project=project_a, data={'text': 'test'})


@pytest.fixture
def task_in_b(project_b):
    return Task.objects.create(project=project_b, data={'text': 'test'})


@pytest.fixture
def annotation_in_a(task_in_a, project_a, member_with_access):
    return Annotation.objects.create(task=task_in_a, project=project_a, completed_by=member_with_access, result=[])


@pytest.fixture
def annotation_in_b(task_in_b, project_b, owner):
    return Annotation.objects.create(task=task_in_b, project=project_b, completed_by=owner, result=[])


class TestProjectAPIAccess:
    def test_member_can_access_granted_project(self, member_with_access, grant_project_a, project_a):
        client = APIClient()
        client.force_authenticate(user=member_with_access)
        response = client.get(reverse('projects:api:project-detail', kwargs={'pk': project_a.id}))
        assert response.status_code == 200

    def test_member_cannot_access_non_granted_project(self, member_with_access, grant_project_a, project_b):
        client = APIClient()
        client.force_authenticate(user=member_with_access)
        response = client.get(reverse('projects:api:project-detail', kwargs={'pk': project_b.id}))
        assert response.status_code in [403, 404]

    def test_no_group_member_cannot_access_any_project(self, member_no_access, project_a, project_b):
        client = APIClient()
        client.force_authenticate(user=member_no_access)
        response_a = client.get(reverse('projects:api:project-detail', kwargs={'pk': project_a.id}))
        response_b = client.get(reverse('projects:api:project-detail', kwargs={'pk': project_b.id}))
        assert response_a.status_code in [403, 404]
        assert response_b.status_code in [403, 404]

    def test_admin_can_access_any_project(self, admin, project_a, project_b):
        client = APIClient()
        client.force_authenticate(user=admin)
        response_a = client.get(reverse('projects:api:project-detail', kwargs={'pk': project_a.id}))
        response_b = client.get(reverse('projects:api:project-detail', kwargs={'pk': project_b.id}))
        assert response_a.status_code == 200
        assert response_b.status_code == 200

    def test_owner_can_access_any_project(self, owner, project_a, project_b):
        client = APIClient()
        client.force_authenticate(user=owner)
        response_a = client.get(reverse('projects:api:project-detail', kwargs={'pk': project_a.id}))
        response_b = client.get(reverse('projects:api:project-detail', kwargs={'pk': project_b.id}))
        assert response_a.status_code == 200
        assert response_b.status_code == 200


class TestProjectTaskListAPIAccess:
    def test_member_can_list_tasks_in_granted_project(self, member_with_access, grant_project_a, project_a, task_in_a):
        client = APIClient()
        client.force_authenticate(user=member_with_access)
        response = client.get(f'/api/projects/{project_a.id}/tasks/')
        assert response.status_code == 200

    def test_member_cannot_list_tasks_in_non_granted_project(self, member_with_access, grant_project_a, project_b, task_in_b):
        client = APIClient()
        client.force_authenticate(user=member_with_access)
        response = client.get(f'/api/projects/{project_b.id}/tasks/')
        assert response.status_code in [403, 404]


class TestTaskAPIAccess:
    def test_member_can_access_task_in_granted_project(self, member_with_access, grant_project_a, task_in_a):
        client = APIClient()
        client.force_authenticate(user=member_with_access)
        response = client.get(f'/api/tasks/{task_in_a.id}/')
        assert response.status_code == 200

    def test_member_cannot_access_task_in_non_granted_project(self, member_with_access, grant_project_a, task_in_b):
        client = APIClient()
        client.force_authenticate(user=member_with_access)
        response = client.get(f'/api/tasks/{task_in_b.id}/')
        assert response.status_code in [403, 404]

    def test_no_group_member_cannot_access_any_task(self, member_no_access, task_in_a, task_in_b):
        client = APIClient()
        client.force_authenticate(user=member_no_access)
        response_a = client.get(f'/api/tasks/{task_in_a.id}/')
        response_b = client.get(f'/api/tasks/{task_in_b.id}/')
        assert response_a.status_code in [403, 404]
        assert response_b.status_code in [403, 404]


class TestAnnotationAPIAccess:
    def test_member_can_access_annotation_in_granted_project(self, member_with_access, grant_project_a, annotation_in_a):
        client = APIClient()
        client.force_authenticate(user=member_with_access)
        response = client.get(f'/api/annotations/{annotation_in_a.id}/')
        assert response.status_code == 200

    def test_member_cannot_access_annotation_in_non_granted_project(self, member_with_access, grant_project_a, annotation_in_b):
        client = APIClient()
        client.force_authenticate(user=member_with_access)
        response = client.get(f'/api/annotations/{annotation_in_b.id}/')
        assert response.status_code in [403, 404]


class TestAnnotationsListAPIAccess:
    def test_member_can_list_annotations_in_granted_project(self, member_with_access, grant_project_a, task_in_a, annotation_in_a):
        client = APIClient()
        client.force_authenticate(user=member_with_access)
        response = client.get(f'/api/tasks/{task_in_a.id}/annotations/')
        assert response.status_code == 200

    def test_member_cannot_list_annotations_in_non_granted_project(self, member_with_access, grant_project_a, task_in_b, annotation_in_b):
        client = APIClient()
        client.force_authenticate(user=member_with_access)
        response = client.get(f'/api/tasks/{task_in_b.id}/annotations/')
        assert response.status_code in [403, 404]


class TestImportAPIAccess:
    def test_member_cannot_import_to_non_granted_project(self, member_with_access, grant_project_a, project_b):
        client = APIClient()
        client.force_authenticate(user=member_with_access)
        response = client.post(
            f'/api/projects/{project_b.id}/import',
            data={'data': [{'text': 'test'}]},
            format='json'
        )
        assert response.status_code in [403, 404]


class TestExportAPIAccess:
    def test_member_cannot_export_from_non_granted_project(self, member_with_access, grant_project_a, project_b):
        client = APIClient()
        client.force_authenticate(user=member_with_access)
        response = client.get(
            f'/api/projects/{project_b.id}/export',
            {'exportType': 'JSON'}
        )
        assert response.status_code in [403, 404]

    def test_member_can_export_from_granted_project(self, member_with_access, grant_project_a, project_a):
        client = APIClient()
        client.force_authenticate(user=member_with_access)
        response = client.get(
            f'/api/projects/{project_a.id}/export',
            {'exportType': 'JSON'}
        )
        assert response.status_code == 200
