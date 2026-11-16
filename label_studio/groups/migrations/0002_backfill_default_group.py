"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.db import migrations

from groups.functions import backfill_default_groups


class Migration(migrations.Migration):
    dependencies = [
        ('groups', '0001_initial'),
        ('organizations', '0008_organization_token_expires_at'),
        ('projects', '0038_projectimport_list_indexes_async'),
        ('users', '0014_user_is_admin'),
    ]

    operations = [
        migrations.RunPython(backfill_default_groups, migrations.RunPython.noop),
    ]
