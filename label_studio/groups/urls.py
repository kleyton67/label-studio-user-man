"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

from django.urls import path
from groups import api

urlpatterns = [
    path('api/admin/groups/', api.AdminGroupListAPI.as_view(), name='admin-group-list'),
    path('api/admin/groups/<int:pk>/', api.AdminGroupDetailAPI.as_view(), name='admin-group-detail'),
    path(
        'api/admin/groups/<int:pk>/members/',
        api.AdminGroupMemberListAPI.as_view(),
        name='admin-group-member-list',
    ),
    path(
        'api/admin/groups/<int:pk>/members/<int:user_pk>/',
        api.AdminGroupMemberDetailAPI.as_view(),
        name='admin-group-member-detail',
    ),
    path(
        'api/admin/groups/<int:pk>/projects/',
        api.AdminGroupProjectListAPI.as_view(),
        name='admin-group-project-list',
    ),
    path(
        'api/admin/groups/<int:pk>/projects/<int:project_pk>/',
        api.AdminGroupProjectDetailAPI.as_view(),
        name='admin-group-project-detail',
    ),
]
