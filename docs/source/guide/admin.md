---
title: Admin area, user groups and dataset access
short: Admin area
tier: opensource
type: guide
order: 373
order_enterprise: 0
meta_title: Admin area, user groups and dataset access
meta_description: Manage accounts, user groups and per-group dataset access from the Label Studio admin area
section: "Manage Your Organization"
date: 2026-11-17 00:00:00
---

The admin area is an in-product surface for organization administration. It is available at `/admin` and is linked from the main menu as **Admin**. The menu entry and the pages are shown only to admins; every admin API rejects other users with `403`.

An admin is one of the following:

- the organization owner (the user who created the organization);
- a user with the **admin** flag set on their account;
- a Django superuser.

## Users

The **Users** page lists the members of the active organization. From there an admin can:

- create an account (email, password, first and last name); the new user joins the active organization;
- edit an account;
- activate or deactivate an account;
- delete an account;
- assign a user to groups.

The organization owner and the signed-in admin cannot be deleted through this page.

## Groups and dataset access

The **Groups** page manages user groups and the datasets each group can access. A group belongs to one organization and has a unique name within it. For each group an admin can:

- create, rename and delete the group;
- add and remove members (only active members of the organization can be added);
- grant and revoke access to datasets.

A dataset is a Label Studio project. The group's dataset list shows every project in the active organization with a toggle to grant or revoke access; changes apply immediately.

### Restrictive semantics

Visibility is evaluated on every request and enforced on the server, not only hidden in the interface:

- a non-admin member sees exactly the union of the projects granted to the groups they belong to;
- a non-admin member with no group sees no projects;
- the owner and admins see every project in the organization;
- a soft-deleted organization membership sees no projects, even if group grants remain.

The same rules apply to the API routes that read or change datasets: projects, tasks, annotations, the Data Manager, cloud storage, import and export. A project that was not granted returns `403`/`404` on those routes.

### Default group on upgrade

When the group feature is introduced, a migration creates a default group named **All members** in every organization and links it to all active members and all projects. Existing members therefore keep their current visibility until an admin grants or revokes access explicitly.

## Admin API

The admin area is backed by the `/api/admin/` endpoints, protected by the same admin rule:

| Endpoint | Purpose |
| --- | --- |
| `/api/admin/users/` | List and create accounts |
| `/api/admin/users/<id>/` | Retrieve, edit, deactivate or delete an account |
| `/api/admin/users/<id>/groups/` | Read or replace the groups of a user |
| `/api/admin/groups/` | List and create groups |
| `/api/admin/groups/<id>/` | Retrieve, rename or delete a group |
| `/api/admin/groups/<id>/members/` | List and add members |
| `/api/admin/groups/<id>/members/<user_id>/` | Remove a member |
| `/api/admin/groups/<id>/projects/` | List and grant datasets |
| `/api/admin/groups/<id>/projects/<project_id>/` | Revoke a dataset |

Requests that name a group, user or project from another organization are rejected (`400` or `404`).
