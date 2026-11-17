"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import pytest
from django.db import IntegrityError, transaction
from groups.models import UserGroup
from groups.tests.factories import UserGroupFactory, UserGroupMemberFactory, UserGroupProjectFactory
from organizations.tests.factories import OrganizationFactory
from users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_create_group():
    group = UserGroupFactory()

    assert group.pk is not None
    assert group.name
    assert group.description == ''
    assert group.organization_id is not None
    assert group.created_by_id is not None
    assert group.created_at is not None
    assert group.updated_at is not None
    assert UserGroup.objects.filter(pk=group.pk).exists()


def test_duplicate_name_in_same_organization_raises_integrity_error():
    organization = OrganizationFactory()
    UserGroupFactory(organization=organization, name='duplicate')

    with pytest.raises(IntegrityError), transaction.atomic():
        UserGroupFactory(organization=organization, name='duplicate')


def test_same_name_allowed_in_different_organizations():
    first_organization = OrganizationFactory()
    second_organization = OrganizationFactory()

    first = UserGroupFactory(organization=first_organization, name='shared-name')
    second = UserGroupFactory(organization=second_organization, name='shared-name')

    assert first.pk != second.pk


def test_duplicate_member_raises_integrity_error():
    membership = UserGroupMemberFactory()

    with pytest.raises(IntegrityError), transaction.atomic():
        UserGroupMemberFactory(group=membership.group, user=membership.user)


def test_duplicate_project_link_raises_integrity_error():
    link = UserGroupProjectFactory()

    with pytest.raises(IntegrityError), transaction.atomic():
        UserGroupProjectFactory(group=link.group, project=link.project)


def test_has_permission_true_for_user_in_organization():
    organization = OrganizationFactory()
    user = UserFactory(active_organization=organization)
    group = UserGroupFactory(organization=organization)

    assert group.has_permission(user) is True


def test_has_permission_false_for_user_in_another_organization():
    organization = OrganizationFactory()
    other_organization = OrganizationFactory()
    user = UserFactory(active_organization=other_organization)
    group = UserGroupFactory(organization=organization)

    assert group.has_permission(user) is False
