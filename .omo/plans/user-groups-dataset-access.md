# user-groups-dataset-access - Work Plan

## TL;DR (For humans)
<!-- Fill this LAST, after the detailed plan below is written, so it summarizes the REAL plan. -->
<!-- Plain English for a non-engineer: NO file paths, NO todo numbers, NO wave/agent/tool names. -->

**Who this is for and what changes for them:** Quem administra uma instância do Label Studio passa a ter uma área admin dentro do produto para criar e desativar contas, montar grupos de usuários e decidir quais datasets cada grupo enxerga. Quem apenas anota passa a ver somente os datasets do seu grupo, sem telas quebradas; quem não é admin não vê a área admin.

**What you'll get:** Uma área admin no menu (contas, grupos e permissões de datasets), APIs protegidas para essas operações e um controle de acesso aplicado de verdade no servidor em todas as rotas de dataset — não apenas escondido na interface. Uma migração de dados cria um grupo padrão com os membros e datasets atuais, de modo que nada muda até você restringir.

**Why this approach:** "Dataset" é o Projeto (não existe entidade de dataset neste código), e os grupos são um modelo novo escopado por organização (o `Group` do Django é global e não pertence a uma organização). O gate da área admin usa um campo `is_admin` mais permissões novas, porque a resposta de "quem eu sou" devolve todas as permissões para qualquer pessoa logada — usar essa lista para liberar o admin não funcionaria.

**What it will NOT do:** Não cria papéis/permissions além do acesso a datasets, não mexe em SSO/SAML, não substitui o Django admin, não muda o modelo de organização e não recria uma entidade de dataset.

**Effort:** Large
<!-- Effort is exactly ONE band, never hours/days. Quick = single edit, minutes of agent work; Short = one focused change, a few files; Medium = multi-file feature in one session; Large = several waves, one long session; XL = multi-session or architectural work. A written duration is rewritten to a band. -->
**Risk:** High - a semântica restritiva muda quem vê o quê em várias rotas; o backfill e os testes de permissão são o que sustentam o corte.
**Decisions to sanity-check:** (1) dataset = Projeto; (2) grupos novos escopados por organização; (3) acesso restritivo com grupo padrão de backfill; (4) gate por `is_admin` + `users.manage`, não por `permissions.can`.

Your next move: aprovar o plano para eu gravar a versão final, ou pedir a revisão de alta precisão antes. A execução em si roda em sessão separada (`$ulw-execute`).

---

> TL;DR (machine): Large/High — app de grupos + acesso restritivo por grupo + APIs admin + área admin React + backfill; 14 todos + 4 verificações finais.

## Scope
### Affected user and ideal state
**Affected users:**
- **Dono/admin da organização** — hoje gerencia contas só no Django `/admin/` (`label_studio/users/admin.py`) e convida por link na página `/organization`. Passa a ter uma área admin in-app para contas, grupos e acesso a datasets.
- **Anotador/membro** — hoje vê todos os projetos da organização (`label_studio/projects/mixins.py:85`). Passa a ver exatamente os datasets concedidos aos seus grupos; sem quebra de UI e sem perda silenciosa de acesso.
- **Consumidor de API/script** — usa `/api/projects/...` com token; o bloqueio é server-side e mantém o formato 403/404 atual.

| Row | Statement | Reason |
| --- | --- | --- |
| IS-1 | Admin lista/cria/edita/desativa/exclui contas em uma área admin in-app | controle de contas sem Django admin |
| IS-2 | Admin cria grupos, renomeia e adiciona/remove membros | gestão de grupos |
| IS-3 | Admin concede/revoga acesso a datasets (projetos) por grupo | requisito central de acesso |
| IS-4 | Datasets visíveis de um membro = união dos projetos concedidos aos seus grupos, avaliado a cada request | visibilidade consistente |
| IS-5 | Enforcement server-side em todas as rotas de dataset (projects, tasks, annotations, DM, storages, resolve, import/export) | esconder na UI não é controle de acesso |
| IS-6 | Área admin e APIs admin inacessíveis a quem não é admin (403/redirect) | sem vazamento de privilégio |
| IS-7 | Membros existentes permanecem funcionando após a migração (backfill de grupo padrão) | sem regressão no corte |
| IS-8 | Admin vê infos relacionadas (membros, grupos, projetos, atividade) na mesma área | "e outras infos" |
| GAP-1 | Sem CRUD de usuários fora do Django admin; sem UI de desativar/excluir | controle de contas |
| GAP-2 | Sem modelo/APIs/UI de grupos | gestão de grupos |
| GAP-3 | Sem concessão de dataset por grupo; acesso é org-wide | acesso por grupo |
| GAP-4 | Sem área admin React (só Django admin) | área admin |
| GAP-5 | Frontend sem gate de admin; `whoami.permissions` retorna todas as permissões (`label_studio/users/serializers.py:180`) | gating real |
| GAP-6 | `accessible_projects` (`label_studio/projects/functions/access.py:8`) só escopa por organização | enforcement por grupo |

### Must have
- App Django `label_studio/groups` com `UserGroup`, `UserGroupMember`, `UserGroupProject` + migrações.
- Enforcement em `accessible_projects`, `ProjectManager.for_user`, `ProjectMixin.has_permission` e `ProjectListAPI.get_queryset`.
- APIs admin `/api/admin/*` protegidas por nova permissão de admin.
- `User.is_admin` + `is_admin` no whoami + tipo `APIUser.is_admin`.
- Área admin React registrada em `pages/index.js` + entrada no `Menubar` condicionada a `is_admin`.
- Backfill de grupo padrão por organização.
- Testes pytest (backend) e bun unit (frontend).

### Must NOT have (guardrails, anti-slop, scope boundaries)
- Não criar matriz de roles/permissões além do acesso a datasets; não adicionar SAML/SSO/LDAP/SCIM.
- Não usar `auth.Group` do Django como grupo de usuários.
- Não depender de `is_staff`/`is_superuser` para o gate da área admin (o campo `User.is_admin` + permissões `users.manage`/`groups.manage` mandam).
- Não substituir o Django admin; ele permanece como superfície secundária.
- Não inventar uma entidade nova de "dataset": dataset = `Project`.
- Não tocar em `io_storages` credenciais, no editor de anotações, nem no modelo de Organization/multi-org.
- Não quebrar autoatendimento de perfil (`PATCH /api/users/<pk>` do próprio usuário) nem o convite por link `/api/invite`.
- Não usar `as any`/`@ts-ignore` para calçar tipos.

## Verification strategy
> Zero human intervention - all verification is agent-executed.
- Test decision: **tests-after por tarefa** (assercções de comportamento; TDD só nos pontos de enforcement) · framework: **pytest** (backend, `pytest-django`) + **bun test** (frontend). QA agent-executed em cada todo.
- Comando backend: `cd label_studio && DJANGO_DB=sqlite DJANGO_SETTINGS_MODULE=core.settings.label_studio pytest -vv <arquivo>`
- Comando frontend: `bun run ls:unit <arquivo>` (unit) · `bun run build` (typecheck/build) · `bun run lint`
- Migration check: `cd label_studio && DJANGO_DB=sqlite python manage.py migrate --plan` e `pytest` dos testes de migração.
- Evidence: `.omo/evidence/task-N-user-groups-dataset-access.<ext>` (fora de ulw-loop, `.omo/evidence/`)
- **Restrição de ports (do usuário):** a máquina já tem muitos serviços; ao subir backend/frontend para QA, usar portas **> 50000** (ex.: backend `50080`, frontend `50010`).
- Cada todo termina com evidência de teste passando + `lsp_diagnostics`/build limpo nos arquivos alterados.

## Execution strategy
### Parallel execution waves
> Target 5-8 todos per wave. Fewer than 3 (except the final) means you under-split.

- **Wave 1 — Fundação (paralelo):** T1 models/migrações, T2 permissões + `User.is_admin` + whoami, T3 backfill.
- **Wave 2 — Enforcement (paralelo, após T1/T2):** T4 camada de acesso, T5 rotas de datasets, T6 storages/resolve/import-export.
- **Wave 3 — APIs (paralelo, após T1/T2):** T7 API de grupos, T8 API admin de usuários, T9 Django admin.
- **Wave 4 — Frontend (paralelo, após T3):** T10 ApiConfig/tipos, T11 shell admin + gate, T12 página Usuários, T13 página Grupos.
- **Wave 5 — Integração:** T14 ponta a ponta + docs.
- **Final verification wave:** F1-F4 em paralelo.

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| T1 | — | T3, T4, T7, T9 | T2 |
| T2 | — | T4, T7, T8, T10, T11 | T1 |
| T3 | T1 | — | T2 |
| T4 | T1, T2 | T5, T6 | T7, T8 |
| T5 | T4 | — | T6, T7, T8 |
| T6 | T4 | — | T5, T7, T8 |
| T7 | T1, T2 | T13 | T5, T6, T8, T9 |
| T8 | T2 | T12 | T5, T6, T7, T9 |
| T9 | T1, T2 | — | T5, T6, T7, T8 |
| T10 | T2 | T11, T12, T13 | T5-T9 |
| T11 | T10 | T12, T13 | T5-T9 |
| T12 | T8, T10, T11 | — | T13 |
| T13 | T7, T10, T11 | — | T12 |
| T14 | T5, T6, T12, T13 | — | — |

## Todos
> Implementation + Test = ONE todo. Never separate.
<!-- APPEND TASK BATCHES BELOW THIS LINE WITH edit/apply_patch - never rewrite the headers above. -->

- [x] 1. App `groups`: modelos `UserGroup`/`UserGroupMember`/`UserGroupProject` + migração + testes
  What to do: criar `label_studio/groups/` (`__init__.py`, `apps.py`, `models.py`, `migrations/`, `tests/`, `admin.py` vazio, `serializers.py` e `api.py` vazios para a Wave 3). Modelos: `UserGroup` (`organization` FK CASCADE related_name `user_groups`; `name` CharField(255); `description` TextField blank default `''`; `created_by` FK SET_NULL null; `created_at`/`updated_at`; `Meta.db_table='user_group'`, `unique_together=[['organization','name']]`, `ordering=['name']`); `UserGroupMember` (`group` FK CASCADE related_name `members`; `user` FK CASCADE related_name `user_group_memberships`; `created_at`; `unique_together=[['group','user']]`); `UserGroupProject` (`group` FK CASCADE related_name `project_links`; `project` FK CASCADE related_name `user_group_links`; `created_at`; `unique_together=[['group','project']]`). `UserGroup.has_permission(user)` → `user.active_organization_id == self.organization_id`. Registrar o app em `INSTALLED_APPS` (`core/settings/base.py:230-256`). Migração `0001_initial` via `makemigrations groups`, com `dependencies` explícitas em `('organizations', '0008_...')`, `('projects', '<mais recente>')` e `('users', '0013_...')` (use `showmigrations` para confirmar os nomes atuais).
  Must NOT: não usar `django.contrib.auth.models.Group`; não adicionar campo de role; não adicionar `organization` opcional no `UserGroupProject` (o projeto já tem org).
  Closes: GAP-2
  Parallelization: Wave 1 | Blocked by: — | Blocks: T3, T4, T7, T9
  References: `label_studio/organizations/models.py:34` (OrganizationMember), `:107` (Organization), `:187` (add_user), `:47` (soft delete); `label_studio/projects/models.py:1471` (ProjectMember); `label_studio/core/settings/base.py:230-256` (INSTALLED_APPS); `label_studio/organizations/migrations/0005_organizationmember_deleted_at.py` (estilo de migração); `label_studio/projects/tests/factories.py`; `label_studio/users/tests/factories.py`; `label_studio/organizations/tests/factories.py`.
  Acceptance criteria (agent-executable): `cd label_studio && DJANGO_DB=sqlite DJANGO_SETTINGS_MODULE=core.settings.label_studio pytest -vv groups/tests` passa; `python manage.py makemigrations --check --dry-run` não reporta alterações pendentes; testes cobrem: criar grupo, duplicar `name` na mesma org levanta IntegrityError, duplicar membro/leva IntegrityError, `has_permission` True para membro da org e False para outra org.
  QA scenarios: happy — `pytest groups/tests/test_models.py -vv` (cria grupo+membro+link); failure — `pytest groups/tests/test_models.py -vv -k duplicate` (uniqões). Evidence `.omo/evidence/task-1-user-groups-dataset-access.txt`
  Commit: Y | feat(groups): add user group, membership and project grant models
  Recommended task executor category: unspecified-high — app Django novo com modelos, migração e testes.

- [x] 2. Permissões de admin + `User.is_admin` + `is_admin` no whoami + testes
  What to do: (a) adicionar `is_admin = models.BooleanField(default=False, db_default=False)` em `User` (`label_studio/users/models.py:103`) + migração `users/0014_user_is_admin.py`; NÃO renomear o método stub `is_organization_admin` (`users/models.py:174`). (b) Em `core/permissions.py` adicionar em `AllPermissions`: `users_manage='users.manage'`, `groups_view='groups.view'`, `groups_create='groups.create'`, `groups_change='groups.change'`, `groups_delete='groups.delete'` e registrar esses cinco com predicado de admin em vez de `rules.is_authenticated` (helper `is_org_admin(user)` em `core/permissions.py`: `user.is_superuser or user.is_admin or user.active_organization_id == org.created_by_id`). (c) Em `core/api_permissions.py` adicionar `IsOrganizationAdmin(BasePermission)` (`has_permission` → `request.user.has_perm('users.manage')`). (d) Em `users/serializers.py` `BaseWhoAmIUserSerializer` adicionar `is_admin = SerializerMethodField()` ao `fields` e `get_is_admin` → `user.has_perm('users.manage')`. (e) Em `web/libs/core/src/types/user.ts` adicionar `is_admin: boolean` a `APIUser`.
  Must NOT: não usar `is_staff`/`is_superuser` como único gate (o campo `is_admin` + permissão mandam); não alterar `get_permissions` (retorna todas as perms de propósito); não quebrar `ABILITY` existente.
  Closes: GAP-5, IS-6
  Parallelization: Wave 1 | Blocked by: — | Blocks: T4, T7, T8, T10, T11
  References: `label_studio/users/models.py:103,174`; `label_studio/core/permissions.py:13-85`; `label_studio/core/api_permissions.py:1-14`; `label_studio/users/serializers.py:174-181`; `label_studio/core/settings/base.py:338-342` (AUTHENTICATION_BACKENDS rules); `web/libs/core/src/types/user.ts:1-27`.
  Acceptance criteria: `pytest label_studio/users/tests/test_serializers.py label_studio/core/tests -vv` passa; teste novo: `whoami` retorna `is_admin=True` para `is_admin=True`/owner e `False` para membro comum; `IsOrganizationAdmin` nega anônimo/comum e permite admin.
  QA scenarios: happy — `pytest label_studio/users/tests/test_authz_api.py -vv` (whoami is_admin); failure — `pytest label_studio/users/tests/test_authz_api.py -vv -k non_admin` (403 em endpoint protegido). Evidence `.omo/evidence/task-2-user-groups-dataset-access.txt`
  Commit: Y | feat(users): add is_admin flag, admin permissions and whoami is_admin
  Recommended task executor category: unspecified-high — vários arquivos (modelo, migração, permissões, serializer, tipo frontend).

- [x] 3. Backfill: grupo padrão por organização (membros ativos + todos os projetos) + testes
  What to do: migração de dados `groups/0002_backfill_default_group.py` (ou `0002` se T1 criar `0001`): para cada `Organization`, criar `UserGroup(name='All members', organization=org, created_by=org.created_by)`, adicionar todos os `OrganizationMember` com `deleted_at__isnull=True` e fazer link de todos os `Project` da org. Usar `apps.get_model` históricos; `bulk_create` em lotes; idempotente (se já existe grupo com esse nome na org, pular). Reverse: não-fazer (ou deletar o grupo padrão e seus links).
  Must NOT: não criar grupos para organizações sem dono; não deletar dados no reverse de forma destrutiva sem aviso.
  Closes: IS-7, GAP-3
  Parallelization: Wave 1 | Blocked by: T1 | Blocks: —
  References: `label_studio/organizations/models.py:156-165` (find_by_user), `:47` (deleted_at); `label_studio/projects/models.py:194` (organization FK); `label_studio/organizations/migrations/0005_organizationmember_deleted_at.py`; `label_studio/groups/migrations/0001_initial.py` (de T1).
  Acceptance criteria: `pytest label_studio/groups/tests/test_migrations.py -vv` passa; teste roda a migração num banco com 2 orgs, membros ativos/inativos e projetos, e asserta: 2 grupos padrão, todos os membros ativos no grupo da sua org, todos os projetos linkados, membro inativo fora.
  QA scenarios: happy — `pytest groups/tests/test_migrations.py -vv`; failure — assert de quantidade de links falha se um projeto não linkado. Evidence `.omo/evidence/task-3-user-groups-dataset-access.txt`
  Commit: Y | feat(groups): backfill default group with members and projects
  Recommended task executor category: quick — migração de dados única + teste.

- [x] 4. Camada de acesso restritiva por grupo (`accessible_projects`, `for_user`, `has_permission`) + testes
  What to do: em `label_studio/projects/functions/access.py` reescrever `accessible_projects(user)`: org None ou membership revogado → `Project.objects.none()`; admin (`user.is_superuser or user.is_admin or org.created_by_id == user.id`) → todos os projetos da org; senão → projetos linkados aos grupos do usuário (`UserGroupMember` → `UserGroupProject`). Adicionar `is_admin_user(user)` e `user_group_project_ids(user)` reutilizáveis. Em `projects/models.py:112` `ProjectManager.for_user` → `self.get_queryset().filter(pk__in=accessible_projects(user).values('pk'))`. Em `projects/mixins.py:85` `ProjectMixin.has_permission` → manter `organization_id is None` True; admin True; senão `accessible_projects(user).filter(pk=self.pk).exists()` (cobre org mismatch, membership revogado e grupo). Em `projects/api.py:180` `ProjectListAPI.get_queryset` trocar o filtro org direto por `accessible_projects(self.request.user)` (mantendo order/annotations). Confirmar `projects/functions/access.py:32 get_permitted_project` e `filter_accessible` continuam coerentes.
  Must NOT: não incluir projetos de outra org; não retornar todos para membro sem grupo (restritivo); não quebrar o caso `organization is None`; não introduzir import circular (`accessible_projects` importa `Project` no topo; `ProjectManager.for_user` importa dentro do método).
  Closes: GAP-3, GAP-6, IS-4, IS-5
  Parallelization: Wave 2 | Blocked by: T1, T2 | Blocks: T5, T6
  References: `label_studio/projects/functions/access.py:8-42`; `label_studio/projects/models.py:76-154` (ProjectManager/ProjectVisibleManager), `:112`; `label_studio/projects/mixins.py:85-89`; `label_studio/projects/api.py:174-206`; `label_studio/data_manager/functions.py:24-30`; `label_studio/projects/tests/test_models.py:129-150`; `label_studio/projects/tests/test_soft_delete_manager.py`.
  Acceptance criteria: `pytest label_studio/projects/tests label_studio/data_manager/tests -vv` passa; testes novos: (a) usuário em grupo com projeto A vê A e não vê B; (b) usuário sem grupo não vê nenhum projeto (não-admin); (c) admin/owner vê todos; (d) membro com membership revogado não vê; (e) `ProjectListAPI` de um usuário sem grupo retorna lista vazia com 200.
  QA scenarios: happy — `pytest label_studio/projects/tests/test_access.py -vv`; failure — `pytest label_studio/projects/tests/test_access.py -vv -k no_group` (lista vazia/403). Evidence `.omo/evidence/task-4-user-groups-dataset-access.txt`
  Commit: Y | feat(projects): scope accessible projects by user groups
  Recommended task executor category: deep-low — raciocínio cross-module (manager, mixin, API, import cycle) que o executor resolve lendo o código.

- [x] 5. Enforcement nas rotas de datasets (projects/tasks/annotations/DM/import/export) + testes
  What to do: auditar e fechar cada rota que carrega `Project` sem escopo de grupo. Garantir que usam `accessible_projects`/`for_user`/`has_permission`: `projects/api.py` (ProjectAPI :628, ProjectTaskListAPI :964, ProjectNextTaskAPI/LabelStreamHistoryAPI via object permission), `tasks/api.py` (TaskListAPI :198/:1139/:1252, AnnotationAPI :994, AnnotationsListAPI :1120), `data_manager/api.py` (:248/:275/:293 e TaskListAPI que carrega `Project` por pk), `data_import/api.py` (:274/:901), `data_export/api.py` (:311/:391/:502/:571). Onde houver `get_object_or_404(Project, pk=...)` sem escopo, trocar por `accessible_projects(user)`/`get_permitted_project`. Adicionar testes por rota.
  Must NOT: não confiar em `permission_required` (declarativo); não alterar contratos de resposta; não mudar `Project.has_permission` para aceitar projeto de outra org.
  Closes: IS-5
  Parallelization: Wave 2 | Blocked by: T4 | Blocks: —
  References: `label_studio/projects/api.py:145-214,628,964`; `label_studio/tasks/api.py:198,317,994,1120,1139,1252`; `label_studio/data_manager/api.py:248,275,293,376,440`; `label_studio/data_import/api.py:274,901`; `label_studio/data_export/api.py:311,391,502,571`; `label_studio/projects/functions/access.py:32`.
  Acceptance criteria: `pytest label_studio/projects/tests label_studio/tasks/tests label_studio/data_manager/tests label_studio/data_import/tests label_studio/data_export/tests -vv` passa; teste deCada rota: usuário sem acesso ao projeto recebe 403/404 (não 200 com dados).
  QA scenarios: happy — `pytest label_studio/tests/test_api.py -vv`; failure — `pytest label_studio/projects/tests/test_access.py -vv -k cross_project` (403). Evidence `.omo/evidence/task-5-user-groups-dataset-access.txt`
  Commit: Y | fix(projects): enforce group access on dataset routes
  Recommended task executor category: deep-low — auditoria e correção em várias rotas com raciocínio de escopo.

- [x] 6. Enforcement em storages/resolve/proxy + testes
  What to do: garantir que `io_storages` e o proxy respeitem o escopo de grupo: `io_storages/api.py` (list/detail/sync) e `io_storages/proxy_api.py` (`resolve` usa `project.has_permission`); `io_storages/functions.py:check_storage_project_permission`; `tasks/.../resolve` endpoints. Como o objeto storage delega para `project.has_permission` (`ProjectStorageMixin`), o T4 já cobre; aqui adicionar testes de que um usuário sem acesso ao projeto não lista/resolve storage, e que `?project=` de projeto não acessado dá 403/404.
  Must NOT: não expor credenciais; não alterar o fluxo de presign.
  Closes: IS-5
  Parallelization: Wave 2 | Blocked by: T4 | Blocks: —
  References: `label_studio/io_storages/api.py:38-139`; `label_studio/io_storages/proxy_api.py:76,323`; `label_studio/io_storages/functions.py` (check_storage_project_permission); `label_studio/io_storages/base_models.py:889` (ProjectStorageMixin).
  Acceptance criteria: `pytest label_studio/io_storages/tests label_studio/tests/test_presign_storage_data.py -vv` passa; teste: usuário fora do grupo não lista storage de projeto alheio (403) e `resolve` de URI de projeto alheio é negado.
  QA scenarios: happy — `pytest label_studio/io_storages/tests -vv`; failure — `pytest label_studio/tests/test_presign_storage_data.py -vv -k forbidden`. Evidence `.omo/evidence/task-6-user-groups-dataset-access.txt`
  Commit: Y | fix(io_storages): enforce group access on storage list and resolve
  Recommended task executor category: deep-low — verificação de superfícies que delegam a `project.has_permission`.

- [x] 7. API de grupos `/api/admin/groups` + testes
  What to do: em `label_studio/groups/api.py` + `groups/urls.py`: `GroupListAPI` (GET lista da active org, POST cria), `GroupDetailAPI` (GET/PATCH/DELETE), `GroupMemberListAPI` (GET/POST; POST body `user` pk; valida que o usuário é membro ativo da org), `GroupMemberDetailAPI` (DELETE), `GroupProjectListAPI` (GET/POST; POST body `project` pk; valida que o projeto é da org), `GroupProjectDetailAPI` (DELETE). Serializers em `groups/serializers.py`. Todas as views com `permission_classes = [IsAuthenticated, IsOrganizationAdmin]` (ou `groups.change` para escrita e `groups.view` para leitura, via `IsOrganizationAdmin` que já encapsula `users.manage`). Rotas sob `/api/admin/groups/` (prefixo em `groups/urls.py` incluído em `core/urls.py`).
  Must NOT: não permitir grupo/projeto de outra org; não listar grupos de outra org; não usar `permission_required` declarativo como única defesa.
  Closes: GAP-2, GAP-3, IS-2, IS-3
  Parallelization: Wave 3 | Blocked by: T1, T2 | Blocks: T13
  References: `label_studio/organizations/api.py:125-323` (padrão de list/detail/membros); `label_studio/organizations/urls.py:16-39`; `label_studio/core/api_permissions.py` (IsOrganizationAdmin de T2); `label_studio/core/permissions.py`; `label_studio/core/urls.py:59-70` (includes).
  Acceptance criteria: `pytest label_studio/groups/tests/test_api.py -vv` passa; testes: admin cria grupo/lista/renomeia/deleta; adiciona/remove membro; concede/revoga projeto; membro comum recebe 403; org cruzada 404.
  QA scenarios: happy — `pytest label_studio/groups/tests/test_api.py -vv -k admin`; failure — `pytest label_studio/groups/tests/test_api.py -vv -k forbidden`. Evidence `.omo/evidence/task-7-user-groups-dataset-access.txt`
  Commit: Y | feat(groups): add admin group, member and project APIs
  Recommended task executor category: unspecified-high — APIs CRUD multi-arquivo com permissões e testes.

- [x] 8. API admin de usuários `/api/admin/users` + testes
  What to do: em `label_studio/users/api.py` + `users/urls.py`: `AdminUserListAPI` (GET lista da active org, POST cria conta com email/password e envia definições), `AdminUserDetailAPI` (GET/PATCH/DELETE; PATCH permite `is_active`, `is_admin`, `first_name`, `last_name`, `email`; DELETE bloqueia o dono da org), `AdminUserGroupsAPI` (GET grupos do usuário; PUT substitui a lista de grupos). Serializer `AdminUserSerializer` (campos: id, email, username, first_name, last_name, is_active, is_admin, date_joined, last_activity, groups). `permission_classes = [IsAuthenticated, IsOrganizationAdmin]`. Rotas `/api/admin/users/` e `/api/admin/users/<pk>/groups/`.
  Must NOT: não permitir que admin exclua o próprio owner nem se auto-promova de forma inconsistente; não expor hash de senha; não quebrar `PATCH /api/users/<pk>` de autoatendimento.
  Closes: GAP-1, IS-1, IS-8
  Parallelization: Wave 3 | Blocked by: T2 | Blocks: T12
  References: `label_studio/users/api.py:128-216` (UserAPI), `:178-180` (perform_create adiciona à org), `:208-215` (perform_destroy owner); `label_studio/users/serializers.py:69-171`; `label_studio/users/urls.py:13-33`; `label_studio/core/api_permissions.py`.
  Acceptance criteria: `pytest label_studio/users/tests/test_admin_api.py -vv` passa; testes: admin cria/lista/edita/desativa/exclui; dono não pode ser excluído; membro comum 403; `AdminUserGroupsAPI` GET/PUT reflete nos grupos do usuário.
  QA scenarios: happy — `pytest label_studio/users/tests/test_admin_api.py -vv -k admin`; failure — `pytest label_studio/users/tests/test_admin_api.py -vv -k owner_delete`. Evidence `.omo/evidence/task-8-user-groups-dataset-access.txt`
  Commit: Y | feat(users): add admin user management and group assignment APIs
  Recommended task executor category: unspecified-high — APIs de conta com regras de owner e testes.

- [x] 9. Django admin: registrar grupos e `User.is_admin` + testes
  What to do: em `label_studio/users/admin.py` (registry central): adicionar `is_admin` ao `UserAdminShort.list_display`/`list_filter`/`fieldsets`; registrar `UserGroup` (list_display org/name/created_at, search, filter org), `UserGroupMember` (list_display group/user, search), `UserGroupProject` (list_display group/project). Opcional: inlines de membros/projetos em `UserGroupAdmin`. Em `label_studio/groups/admin.py` NÃO duplicar registro (seguir o padrão de `organizations/admin.py` vazio). Atualizar `label_studio/users/tests/test_admin_async_migrations_action.py`? Não; adicionar `users/tests/test_admin_groups.py`.
  Must NOT: não registrar duas vezes; não remover `Group` do unregister.
  Closes: IS-1, IS-8
  Parallelization: Wave 3 | Blocked by: T1, T2 | Blocks: —
  References: `label_studio/users/admin.py:16-63,168-220`; `label_studio/organizations/admin.py`; `label_studio/ml_models/admin.py` (exemplo de ModelAdmin completo).
  Acceptance criteria: `pytest label_studio/users/tests/test_admin_groups.py -vv` passa; teste verifica `admin.site.is_registered(UserGroup)` e presença de `is_admin` em `UserAdminShort.list_display`.
  QA scenarios: happy — `pytest label_studio/users/tests/test_admin_groups.py -vv`; failure — assert de unregister/registro. Evidence `.omo/evidence/task-9-user-groups-dataset-access.txt`
  Commit: Y | feat(admin): register group models and is_admin in Django admin
  Recommended task executor category: quick — edição concentrada em `admin.py` + teste.

- [x] 10. Frontend: ApiConfig + tipos `APIUser.is_admin` + tipos de grupo + testes
  What to do: em `web/apps/labelstudio/src/config/ApiConfig.js` adicionar endpoints: `adminUsers: "/admin/users"`, `adminUser: "/admin/users/:pk"`, `adminUserGroups: "/admin/users/:pk/groups"`, `updateAdminUser: "PATCH:/admin/users/:pk"`, `deleteAdminUser: "DELETE:/admin/users/:pk"`, `createAdminUser: "POST:/admin/users"`, `adminGroups: "/admin/groups"`, `adminGroup: "/admin/groups/:pk"`, `updateAdminGroup: "PATCH:/admin/groups/:pk"`, `deleteAdminGroup: "DELETE:/admin/groups/:pk"`, `createAdminGroup: "POST:/admin/groups"`, `adminGroupMembers: "/admin/groups/:pk/members"`, `addAdminGroupMember: "POST:/admin/groups/:pk/members"`, `deleteAdminGroupMember: "DELETE:/admin/groups/:pk/members/:userPk"`, `adminGroupProjects: "/admin/groups/:pk/projects"`, `addAdminGroupProject: "POST:/admin/groups/:pk/projects"`, `deleteAdminGroupProject: "DELETE:/admin/groups/:pk/projects/:projectPk"`. Em `web/libs/core/src/types/user.ts` garantir `is_admin: boolean`. Criar tipos de grupo em `web/apps/labelstudio/src/types/` (ex.: `admin.ts`: `AdminUser`, `UserGroup`, `GroupMember`, `GroupProject`). Testes de config/tipos (bun).
  Must NOT: não usar `permissions.can('users.manage')` para o gate (o whoami retorna todas as perms); usar `user.is_admin`.
  Closes: GAP-5
  Parallelization: Wave 4 | Blocked by: T2 | Blocks: T11, T12, T13
  References: `web/apps/labelstudio/src/config/ApiConfig.js:1-100`; `web/libs/core/src/types/user.ts:1-27`; `web/libs/core/src/atoms/user.ts:1-27`; `web/libs/core/src/providers/AuthProvider.tsx:1-120`.
  Acceptance criteria: `bun run ls:unit src/config` (ou arquivo de teste novo) passa; `bun run build` limpo; tipo `APIUser` inclui `is_admin`.
  QA scenarios: happy — `bun run ls:unit src/config/__tests__ -vv`; failure — typecheck falha se `is_admin` ausente. Evidence `.omo/evidence/task-10-user-groups-dataset-access.txt`
  Commit: Y | feat(admin): add admin API endpoints and frontend types
  Recommended task executor category: quick — config/tipos + teste.

- [x] 11. Frontend: shell da área admin (layout, rotas, Menubar, gate) + testes
  What to do: criar `web/apps/labelstudio/src/pages/Admin/` com `AdminPage.jsx` (layout, `path='/admin'`, `title='Admin'`, SidebarMenu com itens Users/Groups), `index.js` exportando `AdminPage`. Registrar em `pages/index.js` (`Pages = [HomePage, ProjectsPage, OrganizationPage, ModelsPage, AdminPage, pages.AccountSettingsPage]`). Adicionar item no `Menubar.jsx` (`Menu.Item label="Admin" to="/admin"`) **somente se** `user?.is_admin`. Gate: `AdminPage` verifica `useAuth().user?.is_admin`; se não, `history.replace('/')` e não renderiza as páginas filhas. Adicionar view Django `admin_view` em `users/views.py` renderizando novo template `users/admin.html` (estende `base.html`, bloco `content` vazio) e URLs `admin/`, `admin/users/`, `admin/groups/` em `users/urls.py`.
  Must NOT: não mostrar a entrada Admin para não-admin; não confiar só no gate de frontend (backend já nega).
  Closes: GAP-4, IS-6
  Parallelization: Wave 4 | Blocked by: T10 | Blocks: T12, T13
  References: `web/apps/labelstudio/src/pages/index.js:1-7`; `web/apps/labelstudio/src/pages/Organization/index.jsx`; `web/apps/labelstudio/src/components/Menubar/Menubar.jsx:237-240`; `web/apps/labelstudio/src/components/SidebarMenu/SidebarMenu.jsx`; `web/apps/labelstudio/src/providers/RoutesProvider.jsx:50-56`; `web/apps/labelstudio/src/routes/RouteWithStaticFallback.jsx`; `web/apps/labelstudio/src/utils/routeHelpers.jsx`; `label_studio/users/views.py:150-189`; `label_studio/users/urls.py:16-33`; `label_studio/users/templates/users/user_account.html:1-20`; `label_studio/organizations/views.py:12-14`; `label_studio/organizations/urls.py:31-35`.
  Acceptance criteria: `bun run ls:unit src/pages/Admin -vv` passa; teste: com `is_admin=true` renderiza Admin e o item no Menubar; com `is_admin=false` redireciona e não renderiza; `bun run build` limpo; `pytest label_studio/users/tests/test_admin_view.py -vv` passa (GET `/admin/` 200 para autenticado).
  QA scenarios: happy — `bun run ls:unit src/pages/Admin -vv`; failure — `bun run ls:unit src/pages/Admin -vv -k denied`. Evidence `.omo/evidence/task-11-user-groups-dataset-access.txt`
  Commit: Y | feat(admin): add admin area shell, menu entry and route guard
  Recommended task executor category: visual-engineering — UI/roteamento/gate.

- [x] 12. Frontend: página Admin de Usuários (listar/criar/editar/desativar/excluir/atribuir grupos) + testes
  What to do: `web/apps/labelstudio/src/pages/Admin/UsersPage.jsx` (`path='/admin/users'`): tabela de usuários via `adminUsers`; ações: criar (modal com email/senha/nome), editar (modal), ativar/desativar (`updateAdminUser` PATCH `is_active`), excluir (confirmação; não permite excluir o owner), atribuir grupos (`adminUserGroups` GET + PUT). Usar `@humansignal/ui` (Table/Button/Modal/Dropdown) e `useAPI().callApi`/`API.invoke`. Testes bun com mocks de API.
  Must NOT: não permitir ações sem `is_admin`; não expor tokens; não duplicar a UI de PeoplePage (a página antiga continua).
  Closes: GAP-1, IS-1
  Parallelization: Wave 4 | Blocked by: T8, T10, T11 | Blocks: —
  References: `web/apps/labelstudio/src/pages/Organization/PeoplePage/PeopleList.jsx`; `.../PeoplePage/SelectedUser.jsx`; `web/apps/labelstudio/src/config/ApiConfig.js`; `web/apps/labelstudio/src/pages/Settings/DangerZone.jsx` (padrão de confirmação); `web/libs/ui/src` (componentes).
  Acceptance criteria: `bun run ls:unit src/pages/Admin -vv` passa; testes: lista usuários, cria, edita, desativa, exclui (com confirmação), atribui grupos; botões desabilitados/ocultos para não-admin.
  QA scenarios: happy — `bun run ls:unit src/pages/Admin -vv -k users.happy`; failure — `bun run ls:unit src/pages/Admin -vv -k users.forbidden`. Evidence `.omo/evidence/task-12-user-groups-dataset-access.txt`
  Commit: Y | feat(admin): add admin users management page
  Recommended task executor category: visual-engineering — página CRUD com modais e testes.

- [x] 13. Frontend: página Admin de Grupos (CRUD + membros + acesso a datasets) + testes
  What to do: `web/apps/labelstudio/src/pages/Admin/GroupsPage.jsx` (`path='/admin/groups'`): lista grupos via `adminGroups`; criar/renomear/excluir; selecionar grupo → painel com membros (`adminGroupMembers` add/remove) e datasets (`adminGroupProjects` lista de projetos da org com toggle conceder/revogar). Usar `@humansignal/ui`. Testes bun.
  Must NOT: não conceder projeto de outra org; não permitir ações sem `is_admin`.
  Closes: GAP-2, GAP-3, IS-2, IS-3
  Parallelization: Wave 4 | Blocked by: T7, T10, T11 | Blocks: —
  References: `web/apps/labelstudio/src/pages/Organization/PeoplePage/InviteLink.tsx` (modal); `web/apps/labelstudio/src/pages/Settings/StorageSettings/StorageCard.jsx` (padrão de card/seleção); `web/apps/labelstudio/src/config/ApiConfig.js`; `web/libs/ui/src`.
  Acceptance criteria: `bun run ls:unit src/pages/Admin -vv` passa; testes: cria/renomeia/exclui grupo, adiciona/remove membro, concede/revoga dataset, reflete imediatamente na lista.
  QA scenarios: happy — `bun run ls:unit src/pages/Admin -vv -k groups.happy`; failure — `bun run ls:unit src/pages/Admin -vv -k groups.forbidden`. Evidence `.omo/evidence/task-13-user-groups-dataset-access.txt`
  Commit: Y | feat(admin): add admin groups page with members and dataset access
  Recommended task executor category: visual-engineering — página com seleção e painéis.

- [x] 14. Integração ponta a ponta + docs + verificação final
  What to do: teste de integração que sobe o backend (sqlite) e exercita: admin cria grupo → adiciona membro → concede projeto → membro vê o projeto em `/api/projects/` e no DM → admin remove acesso → membro não vê; membro sem grupo não vê nada; dono/admin sempre vê. Rodar `bun run build` e `bun run lint`. Adicionar documento curto `docs/source/guide/admin.md` (ou página existente de organização) descrevendo a área admin, grupos e acesso a datasets. NÃO incluir texto de marketing; só fatos operacionais.
  Must NOT: não pular o build/lint; não documentar fora do escopo.
  Closes: IS-4, IS-5, IS-7, IS-8
  Parallelization: Wave 5 | Blocked by: T5, T6, T12, T13 | Blocks: —
  References: `label_studio/tests/test_organizations.py`; `label_studio/tests/test_invites.py`; `docs/source/guide/` (estrutura existing); `web/README.md` (comandos).
  Acceptance criteria: `pytest label_studio/groups/tests label_studio/users/tests label_studio/projects/tests -vv` passa; `bun run build` e `bun run lint` limpos; teste E2E descrito passa.
  QA scenarios: happy — `pytest label_studio/tests/test_admin_groups_integration.py -vv`; failure — assert de visibilidade após revoga. Evidence `.omo/evidence/task-14-user-groups-dataset-access.txt`
  Commit: Y | test(admin): add end-to-end group access integration and docs
  Recommended task executor category: unspecified-high — integração multi-superfície + docs.

- [x] 15. Follow-up (T13): validador de unicidade em `UserGroupSerializer` (organization+name) para 400 em vez de 500
  What to do: em `label_studio/groups/serializers.py` `UserGroupSerializer` adicionar `validators = [UniqueTogetherValidator(queryset=UserGroup.objects.all(), fields=('organization', 'name'), message='...')]` (import de `rest_framework.validators`). Atualizar o teste para assertar 400 (não 500) e a mensagem.
  Must NOT: não quebrar a criação normal; não alterar outros serializers.
  Closes: nota do verificador T13 (500 em nome duplicado)
  Parallelization: Wave 5 | Blocked by: — | Blocks: —
  References: `label_studio/groups/serializers.py`; `label_studio/groups/tests/test_api.py`; `rest_framework.validators.UniqueTogetherValidator`.
  Acceptance criteria: `pytest label_studio/groups/tests -vv` verde; teste novo: criar grupo com nome duplicado na mesma org retorna 400 com mensagem (não 500).
  QA scenarios: happy — `pytest label_studio/groups/tests/test_api.py -k duplicate`; failure — assert de status 400. Evidence `.omo/evidence/task-15-user-groups-dataset-access.txt`
  Commit: Y | fix(groups): validate unique group name per organization
  Recommended task executor category: quick — validador de serializer + teste.

- [x] 16. Follow-up (T14): corrigir a regressão dos testes de hotkeys + format do Admin
  What to do: (a) `label_studio/users/tests/test_hotkeys_api.py::ProjectHotkeysAPITestCase` cria usuário com `active_organization` mas sem grupo; com o acesso restritivo, `get_hotkey_project` (`users/hotkeys.py:23`) nega com 403. Conceder acesso ao projeto via grupo (mesmo padrão de `data_manager/tests/test_api.py`) em `setUp`/nos testes que criam usuários, e adicionar um teste que asserta 403 para membro sem grupo. (b) Rodar o formatador nos arquivos Admin apontados pelo verificador T14 (`web/apps/labelstudio/src/pages/Admin/GroupsPage.jsx`, `GroupsPage.test.jsx`, `index.js`) e confirmar `biome check` limpo.
  Must NOT: enfraquecer asserções; mudar produto (apenas testes + format).
  Closes: regressão existente (5 falhas em `ProjectHotkeysAPITestCase`) + 3 erros de format
  Parallelization: Wave 5 | Blocked by: — | Blocks: —
  References: `label_studio/users/hotkeys.py:9-25`; `label_studio/users/tests/test_hotkeys_api.py:131-235`; `label_studio/data_manager/tests/test_api.py` (padrão de grant); `web/apps/labelstudio/src/pages/Admin/*`.
  Acceptance criteria: `pytest label_studio/users/tests/test_hotkeys_api.py -vv` verde (5 que falhavam agora passam) + teste de 403 para sem-grupo; `biome check` limpo nos arquivos Admin.
  QA scenarios: happy — `pytest label_studio/users/tests/test_hotkeys_api.py -vv`; failure — assert 403 para membro sem grupo. Evidence `.omo/evidence/task-16-user-groups-dataset-access.txt`
  Commit: Y | fix(users): grant group access in hotkey project tests and format admin files
  Recommended task executor category: quick — fixtures de teste + format.

- [x] 17. Follow-up (F2): limpar lint/format dos arquivos novos
  What to do: rodar `uvx ruff check --fix` e `uvx ruff format` nos arquivos Python novos/alterados (app `groups`, `users/tests/test_admin_api.py`, `users/tests/test_admin_groups.py`, `users/tests/test_hotkeys_api.py`, `projects/tests/test_access.py`, `projects/tests/test_route_access.py`, `io_storages/tests/test_route_access.py`, `tests/test_admin_groups_integration.py`) e `bunx biome check --write` nos arquivos frontend novos/alterados (`apps/labelstudio/src/pages/Admin/*`, `src/config/ApiConfig*.ts`, `src/types/admin.ts`). Depois re-rodar os testes afetados.
  Must NOT: não formatar arquivos fora do escopo; não mudar comportamento; não editar produto fora de imports/format.
  Closes: F2 minor (4 ruff errors, 6 format, 1 biome warning)
  Parallelization: Final | Blocked by: — | Blocks: —
  References: `/root/workspace/projetos/label-studio/.omo/evidence/f2-code-quality.txt`.
  Acceptance criteria: `ruff check` e `ruff format --check` limpos nos arquivos; `biome check` limpo; testes afetados verdes.
  QA scenarios: happy — `pytest` dos apps + `bun run ls:unit src/pages/Admin`; failure — lint error. Evidence `.omo/evidence/task-17-user-groups-dataset-access.txt`
  Commit: Y | style: fix lint and formatting in new admin files
  Recommended task executor category: quick — lint/format + re-teste.

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface results and wait for the user's explicit okay before declaring complete.
- [x] F1. Plan compliance audit — conferir que cada `- [ ] N.` do `## Todos` existe, tem Referências/Aceite/QA/Commit/categoria, e que nenhum arquivo fora do escopo foi alterado (`git status`/`git diff --stat`). Evidence `.omo/evidence/f1-plan-compliance.txt`. Categoria: unspecified-high.
- [x] F2. Code quality review — rodar `cd label_studio && DJANGO_DB=sqlite DJANGO_SETTINGS_MODULE=core.settings.label_studio pytest -vv` (suíte relevante) + `bun run lint` + `bun run build`; revisar `as any`/`@ts-ignore`, imports circulares e N+1 nas queries de grupo. Evidence `.omo/evidence/f2-code-quality.txt`. Categoria: deep-low.
- [x] F3. Real manual QA executada por agente — subir `python label_studio/manage.py runserver` (sqlite) + `bun run ls:watch`, e exercer: login de admin, criar grupo, adicionar membro, conceder projeto, login do membro ver só aquele projeto, revogar, página em branco para sem grupo, admin sem item no menu para não-admin. Evidence `.omo/evidence/f3-manual-qa.txt`. Categoria: deep-low.
- [x] F4. Ideal-state fidelity — conferir 1:1 cada IS-1..IS-8 contra o comportamento entregue; qualquer lacuna vira novo `- [ ] N.`. Evidence `.omo/evidence/f4-ideal-state.txt`. Categoria: unspecified-high.

## Commit strategy
- Um commit atômico por todo (T1-T14), mensagens convencionais já indicadas em cada todo.
- Escopos: `groups`, `users`, `projects`, `io_storages`, `admin`, `web`.
- Sem merge commit, sem squash, sem segredos. `make fmt`/`bun run lint` antes de cada commit.
- Migrações commitadas junto com o modelo (T1) e o backfill (T3).

## Success criteria
> One row per IS row. The plan is complete only when every IS row has a delivering todo and a proving QA scenario; F4 checks the delivered behavior against these rows 1:1, and a shortfall becomes new `- [ ] N.` rows, never a note.
| IS | Delivering todo(s) | Proving QA scenario | Evidence |
| --- | --- | --- | --- |
| IS-1 | T8, T9, T12 | T8 `test_admin_api.py -k admin`; T12 `ls:unit -k users.happy` | `.omo/evidence/task-8-...txt`, `.omo/evidence/task-12-...txt` |
| IS-2 | T1, T7, T13 | T7 `test_api.py -k admin`; T13 `ls:unit -k groups.happy` | `.omo/evidence/task-7-...txt`, `.omo/evidence/task-13-...txt` |
| IS-3 | T1, T7, T13 | T7 concede/revoga; T13 `ls:unit -k groups.happy` | `.omo/evidence/task-7-...txt`, `.omo/evidence/task-13-...txt` |
| IS-4 | T4, T14 | T4 `test_access.py` (união de grupos); T14 integração | `.omo/evidence/task-4-...txt`, `.omo/evidence/task-14-...txt` |
| IS-5 | T4, T5, T6, T14 | T5 `test_access.py -k cross_project` (403); T6 presign proibido | `.omo/evidence/task-5-...txt`, `.omo/evidence/task-6-...txt` |
| IS-6 | T2, T7, T8, T11 | T2 `test_authz_api.py -k non_admin` (403); T11 `ls:unit -k denied` | `.omo/evidence/task-2-...txt`, `.omo/evidence/task-11-...txt` |
| IS-7 | T3, T14 | T3 `test_migrations.py`; T14 integração | `.omo/evidence/task-3-...txt`, `.omo/evidence/task-14-...txt` |
| IS-8 | T8, T9, T12, T13 | T9 `test_admin_groups.py`; T12/T13 páginas | `.omo/evidence/task-9-...txt`, `.omo/evidence/task-12-...txt` |
