from groups.models import UserGroupMember
from groups.tests.factories import UserGroupFactory
from organizations.tests.factories import OrganizationFactory
from rest_framework.test import APITestCase
from users.models import User
from users.tests.factories import UserFactory


class TestAdminUserListAPI(APITestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.owner = self.organization.created_by
        self.admin = UserFactory(active_organization=self.organization, is_admin=True)
        self.member = UserFactory(active_organization=self.organization)
        self.outside_member = UserFactory(active_organization=OrganizationFactory())

    def test_admin_lists_users_scoped_to_active_organization(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get('/api/admin/users/')

        assert response.status_code == 200
        payload = response.json()
        ids = {user['id'] for user in payload}
        assert ids == {self.owner.id, self.admin.id, self.member.id}
        assert self.outside_member.id not in ids
        by_id = {user['id']: user for user in payload}
        assert by_id[self.admin.id]['is_admin'] is True
        assert by_id[self.member.id]['is_admin'] is False
        assert by_id[self.member.id]['email'] == self.member.email
        assert 'password' not in by_id[self.member.id]

    def test_owner_lists_users(self):
        self.client.force_authenticate(self.owner)

        response = self.client.get('/api/admin/users/')

        assert response.status_code == 200
        assert self.owner.id in {user['id'] for user in response.json()}

    def test_admin_creates_user_in_active_organization(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            '/api/admin/users/',
            {
                'email': 'newbie@example.com',
                'password': 'StrongPassw0rd!',
                'first_name': 'New',
                'last_name': 'Bie',
            },
            format='json',
        )

        assert response.status_code == 201, response.json()
        user = User.objects.get(email='newbie@example.com')
        assert user.active_organization_id == self.organization.id
        assert user.check_password('StrongPassw0rd!')
        assert user.username == 'newbie'
        assert user.first_name == 'New'
        assert user.last_name == 'Bie'
        assert user.get_token() is not None
        assert self.organization.users.filter(pk=user.pk).exists()
        assert response.json()['id'] == user.id
        assert 'password' not in response.json()

    def test_admin_create_rejects_duplicate_email(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            '/api/admin/users/',
            {'email': self.member.email, 'password': 'StrongPassw0rd!'},
            format='json',
        )

        assert response.status_code == 400

    def test_admin_create_requires_password(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post('/api/admin/users/', {'email': 'no-password@example.com'}, format='json')

        assert response.status_code == 400
        assert not User.objects.filter(email='no-password@example.com').exists()


class TestAdminUserDetailAPI(APITestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.owner = self.organization.created_by
        self.admin = UserFactory(active_organization=self.organization, is_admin=True)
        self.member = UserFactory(active_organization=self.organization)

    def test_admin_retrieves_user(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get(f'/api/admin/users/{self.member.id}/')

        assert response.status_code == 200
        assert response.json()['id'] == self.member.id
        assert 'password' not in response.json()

    def test_admin_patches_user(self):
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f'/api/admin/users/{self.member.id}/',
            {'first_name': 'Patched', 'last_name': 'Member', 'email': 'patched@example.com'},
            format='json',
        )

        assert response.status_code == 200, response.json()
        self.member.refresh_from_db()
        assert self.member.first_name == 'Patched'
        assert self.member.last_name == 'Member'
        assert self.member.email == 'patched@example.com'

    def test_admin_deactivates_user(self):
        self.client.force_authenticate(self.admin)

        response = self.client.patch(f'/api/admin/users/{self.member.id}/', {'is_active': False}, format='json')

        assert response.status_code == 200
        self.member.refresh_from_db()
        assert self.member.is_active is False

    def test_admin_patch_rejects_unsupported_field(self):
        self.client.force_authenticate(self.admin)

        response = self.client.patch(f'/api/admin/users/{self.member.id}/', {'username': 'hacked'}, format='json')

        assert response.status_code == 400
        self.member.refresh_from_db()
        assert self.member.username != 'hacked'

    def test_admin_deletes_member(self):
        self.client.force_authenticate(self.admin)

        response = self.client.delete(f'/api/admin/users/{self.member.id}/')

        assert response.status_code == 204
        assert not User.objects.filter(pk=self.member.id).exists()

    def test_organization_owner_cannot_be_deleted(self):
        self.client.force_authenticate(self.admin)

        response = self.client.delete(f'/api/admin/users/{self.owner.id}/')

        assert response.status_code == 403
        assert User.objects.filter(pk=self.owner.id).exists()
        self.organization.refresh_from_db()
        assert self.organization.created_by_id == self.owner.id

    def test_admin_cannot_delete_self(self):
        self.client.force_authenticate(self.admin)

        response = self.client.delete(f'/api/admin/users/{self.admin.id}/')

        assert response.status_code == 403
        assert User.objects.filter(pk=self.admin.id).exists()


class TestAdminUserForbidden(APITestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.owner = self.organization.created_by
        self.member = UserFactory(active_organization=self.organization)

    def test_plain_member_is_denied_every_admin_endpoint(self):
        self.client.force_authenticate(self.member)

        assert self.client.get('/api/admin/users/').status_code == 403
        assert (
            self.client.post(
                '/api/admin/users/',
                {'email': 'x@example.com', 'password': 'StrongPassw0rd!'},
                format='json',
            ).status_code
            == 403
        )
        assert self.client.get(f'/api/admin/users/{self.owner.id}/').status_code == 403
        assert (
            self.client.patch(f'/api/admin/users/{self.owner.id}/', {'is_active': False}, format='json').status_code
            == 403
        )
        assert self.client.delete(f'/api/admin/users/{self.owner.id}/').status_code == 403
        assert self.client.get(f'/api/admin/users/{self.owner.id}/groups/').status_code == 403
        assert (
            self.client.put(f'/api/admin/users/{self.owner.id}/groups/', {'groups': []}, format='json').status_code
            == 403
        )

    def test_anonymous_is_denied(self):
        assert self.client.get('/api/admin/users/').status_code == 401


class TestAdminUserGroupsAPI(APITestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.owner = self.organization.created_by
        self.member = UserFactory(active_organization=self.organization)
        self.group = UserGroupFactory(organization=self.organization, name='Reviewers')
        self.other_group = UserGroupFactory(organization=OrganizationFactory(), name='Outside')

    def test_get_groups_empty(self):
        self.client.force_authenticate(self.owner)

        response = self.client.get(f'/api/admin/users/{self.member.id}/groups/')

        assert response.status_code == 200
        assert response.json()['groups'] == []

    def test_put_assigns_groups_and_reflects_in_membership(self):
        self.client.force_authenticate(self.owner)

        response = self.client.put(
            f'/api/admin/users/{self.member.id}/groups/', {'groups': [self.group.id]}, format='json'
        )

        assert response.status_code == 200
        assert response.json()['groups'] == [{'id': self.group.id, 'name': 'Reviewers'}]
        assert list(UserGroupMember.objects.filter(user=self.member).values_list('group_id', flat=True)) == [
            self.group.id
        ]

        detail = self.client.get(f'/api/admin/users/{self.member.id}/')
        assert detail.status_code == 200
        assert detail.json()['groups'] == [{'id': self.group.id, 'name': 'Reviewers'}]

    def test_put_replaces_groups(self):
        UserGroupMember.objects.create(user=self.member, group=self.group)
        replacement = UserGroupFactory(organization=self.organization, name='Replacers')
        self.client.force_authenticate(self.owner)

        response = self.client.put(
            f'/api/admin/users/{self.member.id}/groups/', {'groups': [replacement.id]}, format='json'
        )

        assert response.status_code == 200
        assert {group['id'] for group in response.json()['groups']} == {replacement.id}
        assert list(UserGroupMember.objects.filter(user=self.member).values_list('group_id', flat=True)) == [
            replacement.id
        ]

    def test_put_empty_list_clears_groups(self):
        UserGroupMember.objects.create(user=self.member, group=self.group)
        self.client.force_authenticate(self.owner)

        response = self.client.put(f'/api/admin/users/{self.member.id}/groups/', {'groups': []}, format='json')

        assert response.status_code == 200
        assert response.json()['groups'] == []
        assert not UserGroupMember.objects.filter(user=self.member).exists()

    def test_put_rejects_group_from_another_organization(self):
        self.client.force_authenticate(self.owner)

        response = self.client.put(
            f'/api/admin/users/{self.member.id}/groups/', {'groups': [self.other_group.id]}, format='json'
        )

        assert response.status_code == 400
        assert not UserGroupMember.objects.filter(user=self.member).exists()

    def test_put_rejects_non_list_body(self):
        self.client.force_authenticate(self.owner)

        response = self.client.put(
            f'/api/admin/users/{self.member.id}/groups/', {'groups': self.group.id}, format='json'
        )

        assert response.status_code == 400
        assert not UserGroupMember.objects.filter(user=self.member).exists()


class TestSelfServiceUserAPIUnchanged(APITestCase):
    def setUp(self):
        self.organization = OrganizationFactory()
        self.member = UserFactory(active_organization=self.organization)

    def test_member_can_still_patch_self(self):
        self.client.force_authenticate(self.member)

        response = self.client.patch(
            f'/api/users/{self.member.id}/', {'first_name': 'Self', 'last_name': 'Service'}, format='json'
        )

        assert response.status_code == 200, response.json()
        self.member.refresh_from_db()
        assert self.member.first_name == 'Self'
        assert self.member.last_name == 'Service'
