# Área de administração do Label Studio

Este README descreve, na prática, como operar a área de administração incluída no Label Studio (OSS): gestão de contas, grupos de usuários, acesso por grupo a datasets e a API de admin. Ele é voltado a operadores e administradores que precisam configurar quem acessa o quê, sem substituir o guia técnico em `docs/source/guide/admin.md`. Todos os comportamentos descritos aqui são aplicados no servidor; esconder um item na interface não altera a regra.

Sumário:

- [Quem pode acessar](#quem-pode-acessar)
- [Onde fica](#onde-fica)
- [Gestão de usuários](#gestão-de-usuários)
- [Grupos e acesso a datasets](#grupos-e-acesso-a-datasets)
- [Grupo padrão na migração](#grupo-padrão-na-migração)
- [Desabilitar novos logins](#desabilitar-novos-logins)
- [API de admin](#api-de-admin)
- [Deploy e portas](#deploy-e-portas)
- [Migração e requisitos](#migração-e-requisitos)

## Quem pode acessar

Um admin é qualquer um destes casos:

- o dono da organização, ou seja, o usuário que criou a organização;
- um usuário com a flag **admin** (`is_admin`) definida na conta;
- um superusuário do Django.

Para promover alguém a admin, use um destes caminhos:

- no Django admin (`/admin/users/user/`), marque a flag **admin** (`is_admin`) do usuário;
- ou envie `PATCH /api/admin/users/<id>/` com o corpo `{"is_admin": true}`.

Quem não é admin não vê a entrada de menu nem as páginas da área, e toda chamada às APIs de admin é recusada com `403`.

## Onde fica

- endereço direto: `/admin`;
- no menu principal, a entrada aparece como **Admin**;
- a entrada de menu e as páginas são visíveis apenas para admins.

## Gestão de usuários

Na página **Users** (`/admin/users`) o admin pode:

- criar uma conta com email, senha, nome e sobrenome; o novo usuário entra na organização ativa;
- editar uma conta existente;
- ativar ou desativar uma conta;
- excluir uma conta;
- atribuir o usuário a grupos.

Restrições da página:

- o dono da organização não pode ser excluído;
- o admin autenticado no momento não pode ser excluído.

## Grupos e acesso a datasets

Na página **Groups** (`/admin/groups`) o admin pode:

- criar, renomear e excluir um grupo;
- adicionar membros ao grupo, somente membros ativos da organização;
- remover membros do grupo;
- conceder e revogar acesso a datasets.

Regras do grupo:

- um grupo pertence a uma única organização;
- o nome do grupo é único dentro da organização;
- dataset é um **project** do Label Studio;
- a página lista todos os projetos da organização ativa, cada um com um toggle;
- as mudanças de acesso valem imediatamente.

Semântica restritiva, avaliada em toda requisição e imposta no servidor, não apenas na interface:

- um membro não-admin vê exatamente a união dos projetos concedidos aos grupos a que pertence;
- um membro não-admin sem grupo não vê nenhum projeto;
- o dono e os admins veem todos os projetos da organização;
- uma membership da organização removida de forma soft delete não vê nenhum projeto, mesmo que as concessões de grupo continuem valendo.

As mesmas regras valem para as rotas de projetos, tasks, annotations, Data Manager, cloud storage, importação e exportação: um projeto não concedido devolve `403`/`404` nessas rotas.

## Grupo padrão na migração

A migração `groups/0002_backfill_default_group` cria, em cada organização, um grupo padrão chamado **All members**. Esse grupo é ligado a todos os membros ativos e a todos os projetos, de modo que a visibilidade existente é preservada até um admin conceder ou revogar acesso explicitamente.

## Desabilitar novos logins

Isso **não está na interface de admin**. A configuração é feita por variável de ambiente e exige alteração de ambiente e restart do serviço:

- `DISABLE_SIGNUP_WITHOUT_LINK` (padrão `false`): lida em `label_studio/core/settings/base.py` e aplicada em `label_studio/users/views.py` no fluxo de signup. Quando `true`, só usuários com um link de convite válido para a organização podem se cadastrar.
- `ALLOW_ORGANIZATION_CREATION` (padrão `false`): bloqueia a criação de novas organizações.

## API de admin

Toda a API fica sob `/api/admin/` e é restrita a admins:

| Endpoint | Uso |
| --- | --- |
| `GET\|POST /api/admin/users/` | Listar e criar contas |
| `GET\|PATCH\|DELETE /api/admin/users/<id>/` | Ler, editar, desativar ou excluir uma conta |
| `GET\|PUT /api/admin/users/<id>/groups/` | Ler ou substituir os grupos de um usuário |
| `GET\|POST /api/admin/groups/` | Listar e criar grupos |
| `GET\|PATCH\|DELETE /api/admin/groups/<id>/` | Ler, renomear ou excluir um grupo |
| `GET\|POST /api/admin/groups/<id>/members/` | Listar e adicionar membros |
| `DELETE /api/admin/groups/<id>/members/<user_id>/` | Remover um membro |
| `GET\|POST /api/admin/groups/<id>/projects/` | Listar e conceder datasets |
| `DELETE /api/admin/groups/<id>/projects/<project_id>/` | Revogar um dataset |

Notas de uso:

- chamadas de não-admin recebem `403`;
- ids de grupo, usuário ou projeto pertencentes a outra organização são rejeitados com `400` ou `404`.

## Deploy e portas

Stack docker-compose:

- o app (uWSGI) escuta em **8000**;
- o nginx escuta em **8085** (HTTP) e **8086** (SSL) e faz proxy de `/` para o app;
- o host expõe **8080** (mapeado para 8085) e **8081** (mapeado para 8086).

Execução em contêiner único (`docker run heartexlabs/label-studio`):

- o Django escuta em **8080**;
- não há nginx nessa modalidade.

## Migração e requisitos

Aplique as migrações antes de usar a área de admin:

```bash
python label_studio/manage.py migrate
```

O comando cria as tabelas do app `groups` e o grupo padrão **All members** em cada organização.
