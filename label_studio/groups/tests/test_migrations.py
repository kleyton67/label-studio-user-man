"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import pytest
from django.apps import apps
from django.utils import timezone
from groups.functions import backfill_default_groups
from groups.models import UserGroup, UserGroupMember, UserGroupProject
from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from projects.tests.factories import ProjectFactory
from users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def default_group(organization):
    return UserGroup.objects.get(organization=organization, name='All members')


def test_backfill_creates_default_group_for_each_organization():
    org_a = OrganizationFactory()
    org_b = OrganizationFactory()

    backfill_default_groups(apps, None)

    groups = UserGroup.objects.filter(name='All members')
    assert groups.count() == 2
    assert set(groups.values_list('organization_id', flat=True)) == {org_a.id, org_b.id}
    for organization in (org_a, org_b):
        assert UserGroup.objects.filter(organization=organization, name='All members').count() == 1


def test_backfill_uses_organization_created_by():
    org = OrganizationFactory()

    backfill_default_groups(apps, None)

    group = default_group(org)
    assert group.created_by_id is not None
    assert group.created_by_id == org.created_by_id


def test_backfill_adds_active_members_and_skips_soft_deleted_members():
    org = OrganizationFactory()  # owner created_by gets an active membership too
    active_member = UserFactory(active_organization=org)
    removed_member = UserFactory(active_organization=org)
    OrganizationMember.objects.filter(user=removed_member, organization=org).update(deleted_at=timezone.now())

    backfill_default_groups(apps, None)

    group = default_group(org)
    member_ids = set(UserGroupMember.objects.filter(group=group).values_list('user_id', flat=True))
    assert org.created_by_id in member_ids
    assert active_member.id in member_ids
    assert removed_member.id not in member_ids
    assert UserGroupMember.objects.filter(group=group).count() == 2


def test_backfill_links_all_projects_of_each_organization():
    org_a = OrganizationFactory()
    org_b = OrganizationFactory()
    project_a1 = ProjectFactory(organization=org_a)
    project_a2 = ProjectFactory(organization=org_a)
    project_b1 = ProjectFactory(organization=org_b)

    backfill_default_groups(apps, None)

    group_a = default_group(org_a)
    group_b = default_group(org_b)
    linked_a = set(UserGroupProject.objects.filter(group=group_a).values_list('project_id', flat=True))
    linked_b = set(UserGroupProject.objects.filter(group=group_b).values_list('project_id', flat=True))
    assert linked_a == {project_a1.id, project_a2.id}
    assert linked_b == {project_b1.id}


def test_backfill_is_idempotent_when_called_twice():
    org = OrganizationFactory()
    member = UserFactory(active_organization=org)
    ProjectFactory(organization=org)
    ProjectFactory(organization=org)

    backfill_default_groups(apps, None)
    first_group_id = default_group(org).id
    first_member_count = UserGroupMember.objects.filter(group__organization=org).count()
    first_link_count = UserGroupProject.objects.filter(group__organization=org).count()

    backfill_default_groups(apps, None)

    assert UserGroup.objects.filter(organization=org).count() == 1
    assert default_group(org).id == first_group_id
    assert UserGroupMember.objects.filter(group__organization=org).count() == first_member_count
    assert UserGroupProject.objects.filter(group__organization=org).count() == first_link_count
    assert UserGroupMember.objects.filter(group__organization=org, user=member).count() == 1
