"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

DEFAULT_GROUP_NAME = 'All members'
BATCH_SIZE = 500


def backfill_default_groups(apps, schema_editor):
    """Create a default 'All members' group per organization.

    Preserves today's access until an admin restricts it: every organization gets one
    group containing all of its active members and all of its projects.

    Uses only historical models via ``apps.get_model`` so it is safe to run from a
    data migration, and is idempotent: organizations that already have an
    'All members' group are skipped entirely.
    """
    Organization = apps.get_model('organizations', 'Organization')
    OrganizationMember = apps.get_model('organizations', 'OrganizationMember')
    Project = apps.get_model('projects', 'Project')
    UserGroup = apps.get_model('groups', 'UserGroup')
    UserGroupMember = apps.get_model('groups', 'UserGroupMember')
    UserGroupProject = apps.get_model('groups', 'UserGroupProject')

    for organization in Organization.objects.all().iterator():
        if UserGroup.objects.filter(organization=organization, name=DEFAULT_GROUP_NAME).exists():
            continue

        group = UserGroup.objects.create(
            organization=organization,
            name=DEFAULT_GROUP_NAME,
            created_by=organization.created_by,
        )

        active_member_user_ids = OrganizationMember.objects.filter(
            organization=organization, deleted_at__isnull=True
        ).values_list('user_id', flat=True)
        UserGroupMember.objects.bulk_create(
            [UserGroupMember(group=group, user_id=user_id) for user_id in active_member_user_ids],
            batch_size=BATCH_SIZE,
            ignore_conflicts=True,
        )

        project_ids = Project.objects.filter(organization=organization).values_list('id', flat=True)
        UserGroupProject.objects.bulk_create(
            [UserGroupProject(group=group, project_id=project_id) for project_id in project_ids],
            batch_size=BATCH_SIZE,
            ignore_conflicts=True,
        )
