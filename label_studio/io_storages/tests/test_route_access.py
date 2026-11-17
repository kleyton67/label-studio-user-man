"""Tests for group-based access control on storage routes (T6).

Covers:
- ImportStorageListAPI: member with group access to project A cannot list storages for project B
- ExportStorageListAPI: same restriction
- ImportStorageDetailAPI: cannot retrieve/update/delete storage from project B
- ExportStorageDetailAPI: same restriction
- ImportStorageSyncAPI: cannot sync storage from project B
- ExportStorageSyncAPI: same restriction
- TaskResolveStorageUri: cannot resolve URI from task in project B
- ProjectResolveStorageUri: cannot resolve URI from project B
- Admin/owner can access all storages in their org
- No-group non-admin user is denied all storage access
"""

import base64
from unittest.mock import patch

import pytest
from django.urls import reverse
from groups.models import UserGroup, UserGroupMember, UserGroupProject
from io_storages.localfiles.models import LocalFilesExportStorage, LocalFilesImportStorage
from organizations.tests.factories import OrganizationFactory
from projects.tests.factories import ProjectFactory
from rest_framework.test import APIClient
from tasks.tests.factories import TaskFactory
from users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def org():
    return OrganizationFactory()


@pytest.fixture
def project_a(org):
    return ProjectFactory(organization=org, title='Project A')


@pytest.fixture
def project_b(org):
    return ProjectFactory(organization=org, title='Project B')


@pytest.fixture
def member_with_a(org, project_a):
    """User in a group granted access to project A only."""
    user = UserFactory(active_organization=org)
    group = UserGroup.objects.create(organization=org, name='Group A', created_by=org.created_by)
    UserGroupMember.objects.create(group=group, user=user)
    UserGroupProject.objects.create(group=group, project=project_a)
    return user


@pytest.fixture
def member_no_group(org):
    """User with no group membership."""
    return UserFactory(active_organization=org)


@pytest.fixture
def admin_user(org):
    """Organization owner (admin)."""
    owner = org.created_by
    owner.active_organization = org
    owner.save(update_fields=['active_organization'])
    return owner


@pytest.fixture
def import_storage_a(project_a):
    """Import storage in project A."""
    with patch.object(LocalFilesImportStorage, 'validate_connection', return_value=None):
        return LocalFilesImportStorage.objects.create(
            project=project_a,
            title='Import A',
            path='/tmp/test/project_a',
        )


@pytest.fixture
def import_storage_b(project_b):
    """Import storage in project B."""
    with patch.object(LocalFilesImportStorage, 'validate_connection', return_value=None):
        return LocalFilesImportStorage.objects.create(
            project=project_b,
            title='Import B',
            path='/tmp/test/project_b',
        )


@pytest.fixture
def export_storage_b(project_b):
    """Export storage in project B."""
    with patch.object(LocalFilesExportStorage, 'validate_connection', return_value=None):
        return LocalFilesExportStorage.objects.create(
            project=project_b,
            title='Export B',
            path='/tmp/test/project_b_export',
        )


# ---------------------------------------------------------------------------
# ImportStorageListAPI
# ---------------------------------------------------------------------------


class TestImportStorageListAPIAccess:
    def test_member_cannot_list_storage_from_other_project(self, member_with_a, project_b, import_storage_b):
        """Member with access to project A cannot list storages for project B."""
        client = APIClient()
        client.force_authenticate(user=member_with_a)
        url = reverse('storages:api:storage-localfiles-list')
        response = client.get(url, {'project': project_b.id})

        # Should be 403 (permission denied) or 404 (project not found)
        assert response.status_code in (403, 404), f'Expected 403/404, got {response.status_code}'

    def test_member_can_list_storage_from_granted_project(self, member_with_a, project_a, import_storage_a):
        """Member with access to project A can list storages for project A."""
        client = APIClient()
        client.force_authenticate(user=member_with_a)
        url = reverse('storages:api:storage-localfiles-list')
        response = client.get(url, {'project': project_a.id})

        assert response.status_code == 200
        storage_ids = {s['id'] for s in response.json()}
        assert import_storage_a.id in storage_ids

    def test_no_group_user_cannot_list_any_storage(self, member_no_group, project_a, import_storage_a):
        """User with no group membership cannot list storages for any project."""
        client = APIClient()
        client.force_authenticate(user=member_no_group)
        url = reverse('storages:api:storage-localfiles-list')
        response = client.get(url, {'project': project_a.id})

        assert response.status_code in (403, 404)

    def test_admin_can_list_all_storages(self, admin_user, project_b, import_storage_b):
        """Admin can list storages for any project in their org."""
        client = APIClient()
        client.force_authenticate(user=admin_user)
        url = reverse('storages:api:storage-localfiles-list')
        response = client.get(url, {'project': project_b.id})

        assert response.status_code == 200
        storage_ids = {s['id'] for s in response.json()}
        assert import_storage_b.id in storage_ids


# ---------------------------------------------------------------------------
# ExportStorageListAPI
# ---------------------------------------------------------------------------


class TestExportStorageListAPIAccess:
    def test_member_cannot_list_export_storage_from_other_project(self, member_with_a, project_b, export_storage_b):
        """Member with access to project A cannot list export storages for project B."""
        client = APIClient()
        client.force_authenticate(user=member_with_a)
        url = reverse('storages:api:export-storage-localfiles-list')
        response = client.get(url, {'project': project_b.id})

        assert response.status_code in (403, 404)

    def test_admin_can_list_all_export_storages(self, admin_user, project_b, export_storage_b):
        """Admin can list export storages for any project."""
        client = APIClient()
        client.force_authenticate(user=admin_user)
        url = reverse('storages:api:export-storage-localfiles-list')
        response = client.get(url, {'project': project_b.id})

        assert response.status_code == 200
        storage_ids = {s['id'] for s in response.json()}
        assert export_storage_b.id in storage_ids


# ---------------------------------------------------------------------------
# ImportStorageDetailAPI
# ---------------------------------------------------------------------------


class TestImportStorageDetailAPIAccess:
    def test_member_cannot_retrieve_storage_from_other_project(self, member_with_a, import_storage_b):
        """Member with access to project A cannot retrieve storage from project B."""
        client = APIClient()
        client.force_authenticate(user=member_with_a)
        url = reverse('storages:api:storage-localfiles-detail', kwargs={'pk': import_storage_b.id})
        response = client.get(url)

        assert response.status_code in (403, 404)

    def test_member_cannot_update_storage_from_other_project(self, member_with_a, import_storage_b):
        """Member with access to project A cannot update storage from project B."""
        client = APIClient()
        client.force_authenticate(user=member_with_a)
        url = reverse('storages:api:storage-localfiles-detail', kwargs={'pk': import_storage_b.id})
        response = client.patch(url, {'title': 'Hacked'}, format='json')

        assert response.status_code in (403, 404)

    def test_member_cannot_delete_storage_from_other_project(self, member_with_a, import_storage_b):
        """Member with access to project A cannot delete storage from project B."""
        client = APIClient()
        client.force_authenticate(user=member_with_a)
        url = reverse('storages:api:storage-localfiles-detail', kwargs={'pk': import_storage_b.id})
        response = client.delete(url)

        assert response.status_code in (403, 404)

    def test_member_can_retrieve_storage_from_granted_project(self, member_with_a, import_storage_a):
        """Member with access to project A can retrieve storage from project A."""
        client = APIClient()
        client.force_authenticate(user=member_with_a)
        url = reverse('storages:api:storage-localfiles-detail', kwargs={'pk': import_storage_a.id})
        response = client.get(url)

        assert response.status_code == 200
        assert response.json()['id'] == import_storage_a.id

    def test_admin_can_retrieve_any_storage(self, admin_user, import_storage_b):
        """Admin can retrieve storage from any project."""
        client = APIClient()
        client.force_authenticate(user=admin_user)
        url = reverse('storages:api:storage-localfiles-detail', kwargs={'pk': import_storage_b.id})
        response = client.get(url)

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# ExportStorageDetailAPI
# ---------------------------------------------------------------------------


class TestExportStorageDetailAPIAccess:
    def test_member_cannot_retrieve_export_storage_from_other_project(self, member_with_a, export_storage_b):
        """Member with access to project A cannot retrieve export storage from project B."""
        client = APIClient()
        client.force_authenticate(user=member_with_a)
        url = reverse('storages:api:export-storage-localfiles-detail', kwargs={'pk': export_storage_b.id})
        response = client.get(url)

        assert response.status_code in (403, 404)

    def test_admin_can_retrieve_any_export_storage(self, admin_user, export_storage_b):
        """Admin can retrieve export storage from any project."""
        client = APIClient()
        client.force_authenticate(user=admin_user)
        url = reverse('storages:api:export-storage-localfiles-detail', kwargs={'pk': export_storage_b.id})
        response = client.get(url)

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# ImportStorageSyncAPI
# ---------------------------------------------------------------------------


class TestImportStorageSyncAPIAccess:
    def test_member_cannot_sync_storage_from_other_project(self, member_with_a, import_storage_b):
        """Member with access to project A cannot sync storage from project B."""
        client = APIClient()
        client.force_authenticate(user=member_with_a)
        url = reverse('storages:api:storage-localfiles-sync', kwargs={'pk': import_storage_b.id})

        with patch.object(LocalFilesImportStorage, 'validate_connection', return_value=None):
            with patch.object(LocalFilesImportStorage, 'sync', return_value=None):
                response = client.post(url)

        assert response.status_code in (403, 404)

    def test_member_can_sync_storage_from_granted_project(self, member_with_a, import_storage_a):
        """Member with access to project A can sync storage from project A."""
        client = APIClient()
        client.force_authenticate(user=member_with_a)
        url = reverse('storages:api:storage-localfiles-sync', kwargs={'pk': import_storage_a.id})

        with patch.object(LocalFilesImportStorage, 'validate_connection', return_value=None):
            with patch.object(LocalFilesImportStorage, 'sync', return_value=None):
                response = client.post(url)

        # Should succeed (200) or fail with storage-specific error (400), not permission error
        assert response.status_code not in (403, 404)

    def test_admin_can_sync_any_storage(self, admin_user, import_storage_b):
        """Admin can sync storage from any project."""
        client = APIClient()
        client.force_authenticate(user=admin_user)
        url = reverse('storages:api:storage-localfiles-sync', kwargs={'pk': import_storage_b.id})

        with patch.object(LocalFilesImportStorage, 'validate_connection', return_value=None):
            with patch.object(LocalFilesImportStorage, 'sync', return_value=None):
                response = client.post(url)

        assert response.status_code not in (403, 404)


# ---------------------------------------------------------------------------
# ExportStorageSyncAPI
# ---------------------------------------------------------------------------


class TestExportStorageSyncAPIAccess:
    def test_member_cannot_sync_export_storage_from_other_project(self, member_with_a, export_storage_b):
        """Member with access to project A cannot sync export storage from project B."""
        client = APIClient()
        client.force_authenticate(user=member_with_a)
        url = reverse('storages:api:export-storage-localfiles-sync', kwargs={'pk': export_storage_b.id})

        with patch.object(LocalFilesExportStorage, 'validate_connection', return_value=None):
            with patch.object(LocalFilesExportStorage, 'sync', return_value=None):
                response = client.post(url)

        assert response.status_code in (403, 404)

    def test_admin_can_sync_any_export_storage(self, admin_user, export_storage_b):
        """Admin can sync export storage from any project."""
        client = APIClient()
        client.force_authenticate(user=admin_user)
        url = reverse('storages:api:export-storage-localfiles-sync', kwargs={'pk': export_storage_b.id})

        with patch.object(LocalFilesExportStorage, 'validate_connection', return_value=None):
            with patch.object(LocalFilesExportStorage, 'sync', return_value=None):
                response = client.post(url)

        assert response.status_code not in (403, 404)


# ---------------------------------------------------------------------------
# TaskResolveStorageUri
# ---------------------------------------------------------------------------


class TestTaskResolveStorageUriAccess:
    def test_member_cannot_resolve_uri_from_task_in_other_project(self, member_with_a, project_b, import_storage_b):
        """Member with access to project A cannot resolve URI from task in project B."""
        task = TaskFactory(project=project_b, data={'image': 's3://bucket/file.jpg'})
        client = APIClient()
        client.force_authenticate(user=member_with_a)

        fileuri = base64.urlsafe_b64encode(b's3://bucket/file.jpg').decode()
        url = f'/tasks/{task.id}/resolve/'
        response = client.get(url, {'fileuri': fileuri})

        assert response.status_code in (403, 404)

    def test_member_can_resolve_uri_from_task_in_granted_project(self, member_with_a, project_a, import_storage_a):
        """Member with access to project A can attempt to resolve URI from task in project A."""
        task = TaskFactory(project=project_a, data={'image': '/data/local-files/?d=test.jpg'})
        client = APIClient()
        client.force_authenticate(user=member_with_a)

        fileuri = base64.urlsafe_b64encode(b'/data/local-files/?d=test.jpg').decode()
        url = f'/tasks/{task.id}/resolve/'

        with patch.object(LocalFilesImportStorage, 'generate_http_url', return_value='http://example.com/test.jpg'):
            response = client.get(url, {'fileuri': fileuri})

        # Should not be 403 (permission denied). 404 is acceptable if storage can't resolve URI.
        assert response.status_code != 403

    def test_admin_can_resolve_uri_from_any_task(self, admin_user, project_b, import_storage_b):
        """Admin can attempt to resolve URI from task in any project."""
        task = TaskFactory(project=project_b, data={'image': '/data/local-files/?d=test.jpg'})
        client = APIClient()
        client.force_authenticate(user=admin_user)

        fileuri = base64.urlsafe_b64encode(b'/data/local-files/?d=test.jpg').decode()
        url = f'/tasks/{task.id}/resolve/'

        with patch.object(LocalFilesImportStorage, 'generate_http_url', return_value='http://example.com/test.jpg'):
            response = client.get(url, {'fileuri': fileuri})

        assert response.status_code != 403


# ---------------------------------------------------------------------------
# ProjectResolveStorageUri
# ---------------------------------------------------------------------------


class TestProjectResolveStorageUriAccess:
    def test_member_cannot_resolve_uri_from_other_project(self, member_with_a, project_b, import_storage_b):
        """Member with access to project A cannot resolve URI from project B."""
        client = APIClient()
        client.force_authenticate(user=member_with_a)

        fileuri = base64.urlsafe_b64encode(b'/data/local-files/?d=test.jpg').decode()
        url = f'/projects/{project_b.id}/resolve/'
        response = client.get(url, {'fileuri': fileuri})

        assert response.status_code in (403, 404)

    def test_member_can_resolve_uri_from_granted_project(self, member_with_a, project_a, import_storage_a):
        """Member with access to project A can attempt to resolve URI from project A."""
        client = APIClient()
        client.force_authenticate(user=member_with_a)

        fileuri = base64.urlsafe_b64encode(b'/data/local-files/?d=test.jpg').decode()
        url = f'/projects/{project_a.id}/resolve/'

        with patch.object(LocalFilesImportStorage, 'generate_http_url', return_value='http://example.com/test.jpg'):
            response = client.get(url, {'fileuri': fileuri})

        assert response.status_code != 403

    def test_admin_can_resolve_uri_from_any_project(self, admin_user, project_b, import_storage_b):
        """Admin can attempt to resolve URI from any project."""
        client = APIClient()
        client.force_authenticate(user=admin_user)

        fileuri = base64.urlsafe_b64encode(b'/data/local-files/?d=test.jpg').decode()
        url = f'/projects/{project_b.id}/resolve/'

        with patch.object(LocalFilesImportStorage, 'generate_http_url', return_value='http://example.com/test.jpg'):
            response = client.get(url, {'fileuri': fileuri})

        assert response.status_code != 403


# ---------------------------------------------------------------------------
# Cross-org access
# ---------------------------------------------------------------------------


class TestCrossOrgAccess:
    def test_member_cannot_access_storage_from_other_org(self, member_with_a):
        """Member cannot access storage from a project in another organization."""
        other_org = OrganizationFactory()
        other_project = ProjectFactory(organization=other_org, title='Other Org Project')
        with patch.object(LocalFilesImportStorage, 'validate_connection', return_value=None):
            other_storage = LocalFilesImportStorage.objects.create(
                project=other_project,
                title='Other Storage',
                path='/tmp/test/other',
            )

        client = APIClient()
        client.force_authenticate(user=member_with_a)
        url = reverse('storages:api:storage-localfiles-detail', kwargs={'pk': other_storage.id})
        response = client.get(url)

        assert response.status_code in (403, 404)
