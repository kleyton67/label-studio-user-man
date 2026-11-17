import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DotsThreeIcon } from "@humansignal/icons";
import {
  Avatar,
  Badge,
  Button,
  Checkbox,
  ConfirmDialog,
  Dropdown,
  Message,
  ModalWindow,
  Spinner,
  Typography,
  useToast,
} from "@humansignal/ui";
import { Menu } from "../../components/Menu/Menu";
import Input from "../../components/Form/Elements/Input/Input";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";

const rootClass = cn("admin-groups-page");

// Extracts a readable message from the api-proxy error object ({status, error, response}).
const failureMessage = (result, fallback) => {
  const body = result?.response;
  if (typeof body === "string" && body.trim()) return body.trim();
  if (body && typeof body === "object") {
    const firstString = (source) =>
      Object.values(source)
        .flat()
        .find((value) => typeof value === "string" && value.trim());
    if (body.validation_errors && typeof body.validation_errors === "object") {
      const validation = firstString(body.validation_errors);
      if (validation) return validation;
    }
    if (typeof body.detail === "string" && body.detail.trim()) return body.detail;
    const field = firstString(body);
    if (field) return field;
  }
  return result?.error ?? fallback;
};

const emptyGroupForm = { name: "", description: "" };

// `/api/projects/` is paginated (max page_size 100); walk the pages so the
// datasets panel always lists every project of the active organization.
const fetchAllProjects = async (api) => {
  const collected = [];
  let page = 1;

  while (page <= 50) {
    const data = await api.callApi("projects", {
      params: { page, page_size: 100 },
      suppressError: true,
    });

    if (!Array.isArray(data?.results)) return null;
    collected.push(...data.results);

    const more = Boolean(data.next) && collected.length < (data.count ?? collected.length);
    if (!more) return collected;
    page += 1;
  }
  return collected;
};

/**
 * Admin > Groups: manage the active organization's groups, their members, and
 * which datasets (projects) each group can access.
 *
 * Mounted under the AdminLayout gate, so it only ever renders for `is_admin`
 * sessions; every endpoint it calls is additionally enforced server-side by
 * `IsOrganizationAdmin`, and cross-organization members/projects are rejected
 * by the API — the page surfaces those server errors inline.
 */
export const GroupsPage = () => {
  const api = useAPI();
  const toast = useToast();

  const [groups, setGroups] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [saving, setSaving] = useState(false);

  // Detail-panel state for the selected group; `null` means "still loading".
  const [members, setMembers] = useState(null);
  const [grantedProjectIds, setGrantedProjectIds] = useState(null);
  const [orgProjects, setOrgProjects] = useState(null);
  const [orgUsers, setOrgUsers] = useState(null);
  const [detailError, setDetailError] = useState(null);

  // Modal state: exactly one surface is open at a time.
  const [formModal, setFormModal] = useState(null); // {mode: "create"|"edit", group?, values}
  const [deleteTarget, setDeleteTarget] = useState(null); // group
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerSearch, setPickerSearch] = useState("");
  const [modalError, setModalError] = useState(null);

  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Guards against stale async writes after the admin switches groups mid-flight.
  const selectedIdRef = useRef(null);
  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);

  // The org-wide lists are requested once per page life; refs keep rapid group
  // switching from firing duplicate fetches while a request is in flight.
  const orgProjectsRequestedRef = useRef(false);
  const orgUsersRequestedRef = useRef(false);

  const loadGroups = useCallback(
    async ({ initial = false } = {}) => {
      const result = await api.callApi("adminGroups");

      if (!mountedRef.current) return null;

      // callApi resolves to null after the global error handler already showed a message.
      if (!Array.isArray(result)) {
        setLoadError("Could not load groups.");
        return null;
      }

      setGroups(result);
      setLoadError(null);

      setSelectedId((current) => {
        // Keep the selection when the group still exists; on the first load fall
        // back to the first group, after a deletion to the empty placeholder.
        const next = result.some((group) => group.id === current) ? current : initial ? (result[0]?.id ?? null) : null;
        selectedIdRef.current = next;
        return next;
      });

      return result;
    },
    [api],
  );

  useEffect(() => {
    loadGroups({ initial: true });
  }, [loadGroups]);

  const loadMembers = useCallback(
    async (groupId) => {
      const result = await api.callApi("adminGroupMembers", { params: { pk: groupId }, suppressError: true });
      if (!mountedRef.current || selectedIdRef.current !== groupId) return;

      if (Array.isArray(result)) {
        setMembers(result);
      } else {
        setMembers([]);
        setDetailError(failureMessage(result, "Could not load the group members."));
      }
    },
    [api],
  );

  const loadGroupProjects = useCallback(
    async (groupId) => {
      const result = await api.callApi("adminGroupProjects", { params: { pk: groupId }, suppressError: true });
      if (!mountedRef.current || selectedIdRef.current !== groupId) return;

      if (Array.isArray(result)) {
        setGrantedProjectIds(new Set(result.map((link) => link.project)));
      } else {
        setGrantedProjectIds(new Set());
        setDetailError(failureMessage(result, "Could not load the group datasets."));
      }
    },
    [api],
  );

  useEffect(() => {
    setMembers(null);
    setGrantedProjectIds(null);
    setDetailError(null);

    if (selectedId === null) return;

    loadMembers(selectedId);
    loadGroupProjects(selectedId);

    if (!orgProjectsRequestedRef.current) {
      orgProjectsRequestedRef.current = true;
      fetchAllProjects(api).then((result) => {
        if (!mountedRef.current) return;
        if (result === null) setDetailError("Could not load the organization projects.");
        else setOrgProjects(result);
      });
    }
    if (!orgUsersRequestedRef.current) {
      orgUsersRequestedRef.current = true;
      api
        .callApi("adminUsers", { suppressError: true })
        .then((result) => {
          if (!mountedRef.current) return;
          if (Array.isArray(result)) setOrgUsers(result);
          else setDetailError(failureMessage(result, "Could not load the organization users."));
        })
        .catch(() => {
          if (mountedRef.current) setDetailError("Could not load the organization users.");
        });
    }
  }, [selectedId, loadMembers, loadGroupProjects, api]);

  const selectedGroup = useMemo(
    () => (groups ?? []).find((group) => group.id === selectedId) ?? null,
    [groups, selectedId],
  );

  /**
   * Runs a mutation with `suppressError` so this page owns the failure surface:
   * returns `[ok, result]`; on failure `message` is an inline-ready string.
   */
  const mutate = useCallback(
    async (endpoint, options, successMessage) => {
      setSaving(true);
      try {
        const result = await api.callApi(endpoint, { ...options, suppressError: true });
        if (result && !result.error) {
          toast?.show({ message: successMessage });
          return [true, result];
        }
        return [false, failureMessage(result, "The request failed. Please try again.")];
      } catch (error) {
        return [false, error?.message ?? "The request failed. Please try again."];
      } finally {
        if (mountedRef.current) setSaving(false);
      }
    },
    [api, toast],
  );

  // ---------- create / rename ----------

  const openCreate = () => {
    setModalError(null);
    setFormModal({ mode: "create", values: { ...emptyGroupForm } });
  };

  const openRename = (group) => {
    setModalError(null);
    setFormModal({
      mode: "edit",
      group,
      values: { name: group.name ?? "", description: group.description ?? "" },
    });
  };

  const setFormValue = (key, value) => {
    setFormModal((modal) => (modal ? { ...modal, values: { ...modal.values, [key]: value } } : modal));
  };

  const submitForm = async () => {
    if (!formModal) return;
    setModalError(null);

    const name = formModal.values.name.trim();
    if (!name) {
      setModalError("Group name is required.");
      return;
    }
    const body = { name, description: formModal.values.description.trim() };

    if (formModal.mode === "create") {
      const [ok, created] = await mutate("createAdminGroup", { body }, "Group created");
      if (!ok) {
        setModalError(String(created));
        return;
      }
      setFormModal(null);
      await loadGroups();
      if (created?.id !== undefined) {
        selectedIdRef.current = created.id;
        setSelectedId(created.id);
      }
      return;
    }

    const [ok, failure] = await mutate(
      "updateAdminGroup",
      { params: { pk: formModal.group.id }, body },
      "Group updated",
    );
    if (!ok) {
      setModalError(String(failure));
      return;
    }
    setFormModal(null);
    await loadGroups();
  };

  // ---------- delete ----------

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setModalError(null);
    const [ok, failure] = await mutate("deleteAdminGroup", { params: { pk: deleteTarget.id } }, "Group deleted");
    if (!ok) {
      setModalError(String(failure));
      // Rejecting keeps ConfirmDialog open (its waiting state resets) so the
      // inline error stays visible.
      throw new Error(String(failure));
    }
    setDeleteTarget(null);
    await loadGroups();
  };

  // ---------- members ----------

  const memberIds = useMemo(() => new Set((members ?? []).map((member) => member.user)), [members]);

  const openPicker = () => {
    setModalError(null);
    setPickerSearch("");
    setPickerOpen(true);
  };

  const addMember = async (user) => {
    const groupId = selectedId;
    if (groupId === null) return;
    setModalError(null);
    // The backend rejects users from another organization with a validation
    // error; surface it inside the picker instead of pretending success.
    const [ok, failure] = await mutate(
      "addAdminGroupMember",
      { params: { pk: groupId }, body: { user: user.id } },
      "Member added",
    );
    if (!ok) {
      setModalError(String(failure));
      return;
    }
    setPickerOpen(false);
    loadMembers(groupId);
  };

  const removeMember = async (member) => {
    const groupId = selectedId;
    if (groupId === null) return;
    setDetailError(null);
    const [ok, failure] = await mutate(
      "deleteAdminGroupMember",
      { params: { pk: groupId, userPk: member.user } },
      "Member removed",
    );
    if (!ok) {
      setDetailError(String(failure));
      return;
    }
    loadMembers(groupId);
  };

  // ---------- datasets ----------

  const toggleProject = async (project, checked) => {
    const groupId = selectedId;
    if (groupId === null) return;
    setDetailError(null);

    // No optimistic flip: the checkbox reflects the server, so a rejected grant
    // (e.g. a project that left the organization) cannot leave stale state.
    const [ok, failure] = checked
      ? await mutate(
          "addAdminGroupProject",
          { params: { pk: groupId }, body: { project: project.id } },
          "Access granted",
        )
      : await mutate("deleteAdminGroupProject", { params: { pk: groupId, projectPk: project.id } }, "Access revoked");

    if (!ok) {
      setDetailError(String(failure));
      loadGroupProjects(groupId);
      return;
    }
    loadGroupProjects(groupId);
  };

  // ---------- render ----------

  const renderGroupList = () => {
    if (loadError) {
      return (
        <div data-testid="groups-load-error">
          <Message variant="negative">
            <span className="flex items-center gap-base">
              {loadError}
              <Button look="outlined" size="small" onClick={() => loadGroups({ initial: true })}>
                Retry
              </Button>
            </span>
          </Message>
        </div>
      );
    }

    if (!groups) {
      return (
        <div className="flex justify-center p-wider" data-testid="groups-loading">
          <Spinner size={36} />
        </div>
      );
    }

    if (groups.length === 0) {
      return (
        <div className="p-wider text-neutral-content-subtler" data-testid="groups-empty">
          No groups in this organization yet. Create one to start granting dataset access.
        </div>
      );
    }

    return (
      <ul className="flex flex-col gap-tight" data-testid="groups-list" aria-label="Groups">
        {groups.map((group) => {
          const selected = group.id === selectedId;
          return (
            <li key={group.id} className="flex items-stretch">
              <button
                type="button"
                onClick={() => setSelectedId(group.id)}
                aria-current={selected ? "true" : undefined}
                data-testid={`group-item-${group.id}`}
                className={[
                  "flex-1 text-left rounded-tight border-0 px-base py-tight cursor-pointer",
                  selected
                    ? "bg-primary-emphasis-subtle text-neutral-content"
                    : "bg-transparent text-neutral-content hover:bg-neutral-emphasis-subtle",
                ].join(" ")}
              >
                <Typography variant="title" size="small">
                  {group.name}
                </Typography>
                {group.description ? (
                  <div className="text-neutral-content-subtler text-sm truncate">{group.description}</div>
                ) : null}
              </button>
              <div className="flex items-center">
                <Dropdown.Trigger
                  align="right"
                  dataTestId={`group-actions-trigger-${group.id}`}
                  content={
                    <Menu contextual>
                      <Menu.Item onClick={() => openRename(group)} data-testid={`group-action-rename-${group.id}`}>
                        Rename
                      </Menu.Item>
                      <Menu.Item
                        isDangerous
                        onClick={() => {
                          setModalError(null);
                          setDeleteTarget(group);
                        }}
                        data-testid={`group-action-delete-${group.id}`}
                      >
                        Delete
                      </Menu.Item>
                    </Menu>
                  }
                >
                  <Button
                    size="smaller"
                    look="ghost"
                    variant="neutral"
                    aria-label={`Options for ${group.name}`}
                    waiting={saving}
                  >
                    <DotsThreeIcon />
                  </Button>
                </Dropdown.Trigger>
              </div>
            </li>
          );
        })}
      </ul>
    );
  };

  const renderMembers = () => {
    if (members === null) {
      return (
        <div className="flex justify-center p-wider" data-testid="members-loading">
          <Spinner size={24} />
        </div>
      );
    }

    if (members.length === 0) {
      return (
        <Typography variant="body" size="small" className="text-neutral-content-subtler" data-testid="members-empty">
          No members in this group yet.
        </Typography>
      );
    }

    return (
      <ul className="flex flex-col gap-tight" data-testid="members-list" aria-label="Group members">
        {members.map((member) => (
          <li key={member.id ?? member.user} className="flex items-center gap-tight">
            <Avatar user={{ email: member.user_email, username: member.user_name }} size="small" />
            <span className="flex-1 min-w-0">
              <span className="block truncate">{member.user_name || member.user_email}</span>
              {member.user_name && member.user_email ? (
                <span className="block truncate text-sm text-neutral-content-subtler">{member.user_email}</span>
              ) : null}
            </span>
            <Button
              size="smaller"
              look="outlined"
              variant="negative"
              onClick={() => removeMember(member)}
              disabled={saving}
              data-testid={`remove-member-${member.user}`}
            >
              Remove
            </Button>
          </li>
        ))}
      </ul>
    );
  };

  const renderDatasets = () => {
    if (grantedProjectIds === null || orgProjects === null) {
      return (
        <div className="flex justify-center p-wider" data-testid="datasets-loading">
          <Spinner size={24} />
        </div>
      );
    }

    if (orgProjects.length === 0) {
      return (
        <Typography variant="body" size="small" className="text-neutral-content-subtler" data-testid="datasets-empty">
          No projects exist in this organization yet.
        </Typography>
      );
    }

    return (
      <ul className="flex flex-col gap-tight" data-testid="datasets-list" aria-label="Dataset access">
        {orgProjects.map((project) => (
          <li key={project.id} className="flex items-center gap-tight">
            <Checkbox
              checked={grantedProjectIds.has(project.id)}
              disabled={saving}
              onChange={(event) => toggleProject(project, event.target.checked)}
              data-testid={`dataset-toggle-${project.id}`}
              aria-label={`Grant ${project.title || `Project #${project.id}`} access to this group`}
            >
              {project.title || `Project #${project.id}`}
            </Checkbox>
          </li>
        ))}
      </ul>
    );
  };

  const pickerCandidates = useMemo(() => {
    const query = pickerSearch.trim().toLowerCase();
    return (orgUsers ?? [])
      .filter((user) => !memberIds.has(user.id))
      .filter((user) =>
        query
          ? [user.email, user.first_name, user.last_name, user.username]
              .filter(Boolean)
              .some((value) => String(value).toLowerCase().includes(query))
          : true,
      );
  }, [orgUsers, memberIds, pickerSearch]);

  const renderDetail = () => {
    if (!selectedGroup) {
      return (
        <div className="p-wider text-neutral-content-subtler" data-testid="group-detail-placeholder">
          {groups === null || groups.length > 0
            ? "Select a group to manage its members and dataset access."
            : "Create a group to start managing members and dataset access."}
        </div>
      );
    }

    return (
      <div data-testid={`group-detail-${selectedGroup.id}`}>
        <div className="flex items-center justify-between gap-base mb-base">
          <div className="min-w-0">
            <Typography variant="headline" size="small">
              {selectedGroup.name}
            </Typography>
            {selectedGroup.description ? (
              <Typography variant="body" size="small" className="text-neutral-content-subtler">
                {selectedGroup.description}
              </Typography>
            ) : null}
          </div>
          <Badge variant="primary" size="small">
            {members === null ? "…" : `${members.length} ${members.length === 1 ? "member" : "members"}`}
          </Badge>
        </div>

        {detailError && (
          <div className="mb-base" data-testid="detail-error">
            <Message variant="negative">
              <span className="flex items-center gap-base">
                {detailError}
                <Button look="outlined" size="small" onClick={() => setDetailError(null)}>
                  Dismiss
                </Button>
              </span>
            </Message>
          </div>
        )}

        <section className="mb-wider" aria-label="Members">
          <div className="flex items-center justify-between mb-tight">
            <Typography variant="title" size="medium">
              Members
            </Typography>
            <Button
              size="small"
              variant="primary"
              onClick={openPicker}
              disabled={orgUsers === null}
              data-testid="add-member-button"
            >
              Add member
            </Button>
          </div>
          {renderMembers()}
        </section>

        <section aria-label="Datasets">
          <div className="flex items-center justify-between mb-tight">
            <Typography variant="title" size="medium">
              Datasets
            </Typography>
            <Typography variant="body" size="small" className="text-neutral-content-subtler">
              Grant or revoke this group&apos;s access to organization projects.
            </Typography>
          </div>
          {renderDatasets()}
        </section>
      </div>
    );
  };

  return (
    <div className={rootClass.toClassName()} data-testid="admin-groups-page">
      <div className="flex items-end justify-between gap-base mb-base">
        <div>
          <Typography variant="headline" size="medium">
            Groups
          </Typography>
          <Typography variant="body" size="small" className="text-neutral-content-subtler">
            Groups and their dataset access for the active organization. Changes here take effect immediately.
          </Typography>
        </div>
        <Button variant="primary" onClick={openCreate} data-testid="create-group-button">
          Create group
        </Button>
      </div>

      <div className="grid grid-cols-[minmax(220px,280px)_1fr] gap-wider items-start">
        <aside aria-label="Group list">{renderGroupList()}</aside>
        <main className={rootClass.elem("detail").toClassName()}>{renderDetail()}</main>
      </div>

      <ModalWindow
        open={formModal !== null}
        onOpenChange={(open) => {
          if (!open) setFormModal(null);
        }}
        dataTestId="group-form-modal"
        title={formModal?.mode === "edit" ? "Rename group" : "Create group"}
        size="small"
        footer={
          <div className="flex justify-end gap-tight">
            <Button look="outlined" onClick={() => setFormModal(null)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              waiting={saving}
              onClick={submitForm}
              data-testid={formModal?.mode === "edit" ? "save-group-button" : "create-group-submit"}
            >
              {formModal?.mode === "edit" ? "Save" : "Create"}
            </Button>
          </div>
        }
      >
        {formModal && (
          <div className="flex flex-col gap-base">
            {modalError && (
              <Message variant="negative" data-testid="form-error">
                {modalError}
              </Message>
            )}
            <Input
              label="Name"
              required
              value={formModal.values.name}
              onChange={(event) => setFormValue("name", event.target.value)}
              data-testid="group-name-input"
              autoComplete="off"
            />
            <Input
              label="Description"
              value={formModal.values.description}
              onChange={(event) => setFormValue("description", event.target.value)}
              data-testid="group-description-input"
              autoComplete="off"
            />
          </div>
        )}
      </ModalWindow>

      <ModalWindow
        open={pickerOpen}
        onOpenChange={(open) => {
          if (!open) setPickerOpen(false);
        }}
        dataTestId="member-picker-modal"
        title={`Add member to ${selectedGroup?.name ?? ""}`}
        size="small"
      >
        <div className="flex flex-col gap-base">
          {modalError && (
            <Message variant="negative" data-testid="picker-error">
              {modalError}
            </Message>
          )}
          <Input
            label="Search users"
            value={pickerSearch}
            onChange={(event) => setPickerSearch(event.target.value)}
            data-testid="member-search-input"
            placeholder="Name, username or email"
            autoComplete="off"
          />
          {orgUsers === null ? (
            <div className="flex justify-center p-wider" data-testid="picker-loading">
              <Spinner size={24} />
            </div>
          ) : pickerCandidates.length === 0 ? (
            <Typography variant="body" size="small" className="text-neutral-content-subtler" data-testid="picker-empty">
              No eligible users left in this organization.
            </Typography>
          ) : (
            <ul
              className="flex flex-col gap-tight max-h-[320px] overflow-y-auto"
              aria-label="Users to add"
              data-testid="picker-list"
            >
              {pickerCandidates.map((user) => (
                <li key={user.id} className="flex items-center gap-tight">
                  <Avatar user={user} size="small" />
                  <span className="flex-1 min-w-0">
                    <span className="block truncate">
                      {[user.first_name, user.last_name].filter(Boolean).join(" ").trim() ||
                        user.username ||
                        user.email}
                    </span>
                    <span className="block truncate text-sm text-neutral-content-subtler">{user.email}</span>
                  </span>
                  <Button
                    size="smaller"
                    look="outlined"
                    waiting={saving}
                    onClick={() => addMember(user)}
                    data-testid={`pick-user-${user.id}`}
                  >
                    Add
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </ModalWindow>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteTarget(null);
            setModalError(null);
          }
        }}
        title="Delete group?"
        okText="Delete"
        buttonLook="negative"
        onOk={confirmDelete}
        dataTestId="delete-group-dialog"
      >
        <Typography variant="body" size="medium">
          You are about to delete <strong>{deleteTarget?.name}</strong>. Its members stay in the organization but lose
          the dataset access granted through this group. This action cannot be undone.
        </Typography>
        {modalError && (
          <Message variant="negative" data-testid="delete-error">
            {modalError}
          </Message>
        )}
      </ConfirmDialog>
    </div>
  );
};

GroupsPage.title = "Groups";
GroupsPage.path = "/groups";

export default GroupsPage;
