---
slug: user-groups-dataset-access
status: approved
intent: clear
review_required: false
pending-action: write .omo/plans/user-groups-dataset-access.md
approach: New org-scoped UserGroup model + group-project access with RESTRICTIVE semantics (group membership defines dataset access), enforced server-side in the existing project-access layer, plus a React in-app admin area (pages/Admin/*, pages/index.js + Menubar) gated by new users.manage/groups.manage permissions; user CRUD APIs added to the users app. Django admin kept as a secondary surface. One-time backfill creates a default group so existing access is preserved until an admin restricts it.
---

# Draft: user-groups-dataset-access

## Affected user and ideal state

Users touched:
- **Instance owner / organization admin** — today manages accounts only through Django `/admin/` (users/admin.py) and invites via the org People page (invite link only; no create-user, no remove UI, no role change). Wants one branded admin area for accounts, groups and dataset access.
- **Annotator / member** — today every active org member sees every project in the org (`ProjectMixin.has_permission` = membership not revoked). After: sees exactly the datasets granted to their group(s). Must not lose access silently, must not see a broken/empty UI.
- **API/script consumer** — uses `/api/projects/...` with a token. After: group scoping enforced server-side; denied access returns the same 403/404 shape it does today.

| id | Ideal-state property | reason |
|---|---|---|
| IS-1 | Admin can list / create / edit / deactivate / delete user accounts from one in-app admin area | account control without Django admin |
| IS-2 | Admin can create groups, rename them, add/remove members | group management |
| IS-3 | Admin can grant/revoke dataset (project) access per group | the core access requirement |
| IS-4 | A member's visible datasets = union of projects granted to their groups, evaluated on every request | consistent visibility |
| IS-5 | Enforcement is server-side on every dataset route (project list/detail, tasks, annotations, DM, storages, resolve) | UI hiding is not access control |
| IS-6 | Admin area is reachable only by authorized admins (regular members get 403/redirect) | no privilege leak |
| IS-7 | Existing members with no group keep working; no forced migration of current data | no regression |
| IS-8 | Admin sees related org info (memberships, groups, project counts) in the same area | "e outras infos" |

| id | Gap from today | reason | closed by |
|---|---|---|---|
| GAP-1 | No user CRUD outside Django admin; no invite-by-email, no disable/delete UI | account control | C1 |
| GAP-2 | No group model, no group APIs, no group UI | groups | C2 |
| GAP-3 | No dataset-per-group grant; project access is org-wide | access by group | C3 |
| GAP-4 | No React admin area; Django admin only | admin area | C4 |
| GAP-5 | Frontend has zero superuser/staff gating; all named perms are `is_authenticated` | gating | C4 |
| GAP-6 | No server-side hook that maps a user to an allowed project set beyond org | enforcement | C3 |

## Components (topology ledger)

| id | outcome (one line) | status | evidence |
|---|---|---|---|
| C1 | User management: CRUD accounts + disable/delete via API and admin UI | active | users/api.py, users/admin.py |
| C2 | User groups: CRUD groups + membership via API and admin UI | active | organizations/models.py (no group), projects/models.py:1471 (ProjectMember pattern) |
| C3 | Dataset (project) access by group: grant model + server-side enforcement | active | projects/mixins.py:85, projects/functions/access.py |
| C4 | Admin area shell + gating (nav, pages, permission) | active | pages/index.js, Menubar.jsx, core/permissions.py |
| C5 | Optional "other info" dashboards (activity, counts) | deferred | HomePage.tsx, data_manager |

## Open assumptions (announced defaults)

| assumption | adopted default | rationale | reversible? |
|---|---|---|---|
| "dataset" means | **Project** (org-owned container of tasks) | no Dataset model in OSS; `io_storages/README.md` says Dataset Storages are enterprise/deprecated; DM calls tasks "samples in the dataset" | yes (mapping layer) |
| group storage | new org-scoped `UserGroup` + `UserGroupMember` app | Django `auth.Group` is global, unregistered from admin, has no org FK; org-scoping matches `OrganizationMember` | yes |
| group-project link | `UserGroupProject` (group FK, project FK) + helper `accessible_projects` extension | mirrors `ProjectMember`; hooks the existing `ACCESSIBLE_PROJECTS_FUNCTION` extension point | yes |
| admin surface | React in-app admin area (Django admin left as secondary) | user asked for "área admin"; frontend already React; owner already has People page | yes |
| admin gate | new `users.manage` / `groups.manage` permission + frontend `permissions.can(...)` gate | reuses AuthProvider permission checker; no staff dependency | yes |
| test strategy | pytest (backend) + bun unit tests (frontend); agent-executed QA | repo already uses both | n/a |

## Findings (cited - path:lines)

- User model: `label_studio/users/models.py:103` (`User`, db_table `htx_user`, `active_organization` FK at :140, `own_organization` :184, token created on save :238).
- Membership: `label_studio/organizations/models.py:34` (`OrganizationMember`, `deleted_at` soft delete, `is_owner` :70); `Organization` :107 (`created_by` owner :124, `users` M2M :122, `has_permission` :184, `add_user` chokepoint :187).
- No roles in OSS: `organizations/migrations/0002_auto_20210310_2044.py` removed `OrganizationMember.role`; owner is `Organization.created_by`.
- Project = dataset container: `label_studio/projects/models.py:164` (`organization` FK :194, `created_by` :251, `ProjectMember` :1471); `ProjectManager.for_user` :112 filters `organization=active_organization`.
- Access layer: `label_studio/projects/mixins.py:85` `has_permission` = not soft-deleted membership; `label_studio/projects/functions/access.py:8` `accessible_projects` (settings hook `ACCESSIBLE_PROJECTS_FUNCTION`, base.py:1156); `filter_accessible` :21; `get_permitted_project` :32.
- Permissions: `label_studio/core/permissions.py:84` registers every named perm as `rules.is_authenticated`; defaults `core/settings/base.py:300-303` = `HasObjectPermission` + `IsAuthenticated`; `MemberHasOwnerPermission` `core/api_permissions.py:9`.
- `permission_required = ViewClassPermission(...)` on views is declarative; no reader found in the repo (enforcement = defaults + object `has_permission` + queryset scoping).
- Django admin: `label_studio/users/admin.py:208-217` registers User/Project/Task/Annotation/Prediction/Organization/OrganizationMember; `Group` unregistered :220; mounted `core/urls.py:99`.
- Frontend: page registry `web/apps/labelstudio/src/pages/index.js`; nav `components/Menubar/Menubar.jsx:237`; API registry `config/ApiConfig.js`; auth `web/libs/core/src/providers/AuthProvider.tsx` + `web/libs/core/src/atoms/user.ts`; no superuser/is_staff references anywhere in `web/`.
- Org members UI: `pages/Organization/PeoplePage/PeopleList.jsx` (GET memberships, hardcoded pk 1), `SelectedUser.jsx` (read-only), `InviteLink.tsx`; no remove/role UI; no role-change endpoint (`OrganizationMemberDetailAPI` http_method_names = ['delete','get'], organizations/api.py:280).
- Enterprise extension points (OSS no-ops): `USER_MIXIN`, `ORGANIZATION_MIXIN`, `ORGANIZATION_MEMBER_MIXIN`, `MEMBER_PERM`, `ACCESSIBLE_PROJECTS_FUNCTION`, `DATA_MANAGER_CHECK_ACTION_PERMISSION`, `ANNOTATOR_REVIEWER_FIREWALL` (base.py:796-856).

## Decisions (with rationale)

- D1 dataset = Project (see assumptions). D2 new org-scoped group app. D3 group-project link + `accessible_projects` hook. D4 React in-app admin area primary (Django admin secondary). D5 new `users.manage`/`groups.manage` permissions gate the admin area.
- D6 **RESTRICTIVE** (user decision at the gate): when group-based access is active, a user's dataset visibility is defined by the projects granted to their groups. Members with no group lose project access. A one-time backfill (default group with all current members + projects) preserves today's behavior until an admin restricts it, so the cutover is explicit and reversible.
- D7 test strategy: per-task TDD/tests-after + agent-executed QA (pytest backend, bun unit frontend).

## Scope IN

- New Django app `label_studio/groups` (models, migrations, APIs, serializers, admin, tests).
- User management APIs + serializers in `users` app.
- Group-project access model + enforcement in `projects/functions/access.py` / `ProjectMixin.has_permission` / `ProjectManager.for_user`.
- Frontend admin page set (`pages/Admin/*`), registration in `pages/index.js`, Menubar entry, ApiConfig endpoints, permission gating.
- Tests: pytest backend (models, APIs, enforcement, migrations), bun unit tests for new components/hooks.
- Docs: short admin-area doc if a docs page exists for org settings.

## Scope OUT (Must NOT have)

- Roles/permission matrix beyond dataset access; SAML/SSO/LDAP/SCIM.
- Enterprise workforces, billing, cloud features.
- Replacing the Organization model or moving to multi-org.
- Mobile UI; changing the annotation editor.
- Removing/disabling Django admin.
- Inventing a new dataset entity; touching `io_storages` cloud credentials.

## Open questions (resolved at the gate)

- Q1 Admin surface → **React in-app** (chosen).
- Q2 Admin gate → **novas permissões `users.manage`/`groups.manage`** (chosen).
- Q3 Access semantics → **restritivo** (chosen; backfill preserva o acesso atual até restrição explícita).

## Constraints sweep
| axis | classification | note |
|---|---|---|
| budget/spend | explored | sem custo novo: usa Django/React/Bun já existentes; nenhuma dependência paga |
| mandated stack | explored | Django + DRF + regras + React/Vite/Jotai/Bun, já no repo |
| expected scale | defaulted | OSS é single-org por design (`ALLOW_ORGANIZATION_CREATION=False`); grupos por org; query de grupo por request é um JOIN simples, mitigado em F2 |
| target audience / compliance | defaulted | sem requisito regulatório informado; gate de admin e auditoria de acesso follows o modelo existing |

## Metis / reviewer status
- Metis (gap analysis) falhou 2x por erro de plataforma: `Model mimo-v2.5 has been deprecated. Use mimo-v2.6-flash instead.` — indisponível. A análise de lacunas foi feita pelo planner com as evidências do draft; nada ficou aberto sem dono.

## Approval gate
status: approved
<!-- User answered the three forks at the gate = approval. Proceeding to plan generation. -->
