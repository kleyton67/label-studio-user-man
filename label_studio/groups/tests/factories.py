"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import factory
from core.utils.common import load_func
from django.conf import settings
from groups.models import UserGroup, UserGroupMember, UserGroupProject


class UserGroupFactory(factory.django.DjangoModelFactory):
    organization = factory.SubFactory(load_func(settings.ORGANIZATION_FACTORY))
    name = factory.Sequence(lambda n: f'user-group-{n}')
    created_by = factory.SubFactory(load_func(settings.USER_FACTORY))

    class Meta:
        model = UserGroup


class UserGroupMemberFactory(factory.django.DjangoModelFactory):
    group = factory.SubFactory(UserGroupFactory)
    user = factory.SubFactory(load_func(settings.USER_FACTORY))

    class Meta:
        model = UserGroupMember


class UserGroupProjectFactory(factory.django.DjangoModelFactory):
    group = factory.SubFactory(UserGroupFactory)
    project = factory.SubFactory(load_func(settings.PROJECT_FACTORY))

    class Meta:
        model = UserGroupProject
