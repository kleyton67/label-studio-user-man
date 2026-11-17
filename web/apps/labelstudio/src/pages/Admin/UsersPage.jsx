import { format } from "date-fns";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { DotsThreeIcon } from "@humansignal/icons";
import {
  Badge,
  Button,
  Checkbox,
  ConfirmDialog,
  DataTable,
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

const rootClass = cn("admin-users-page");

const emptyUserForm = { email: "", password: "", first_name: "", last_name: "" };

const fullName = (user) =>
  [user.first_name, user.last_name].filter(Boolean).join(" ").trim() || user.username || user.email;

const formatActivity = (value) => {
  if (!value) return "Never";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Never" : format(date, "dd MMM yyyy, HH:mm");
};

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

/**
 * Admin > Users: full account management for the active organization.
 *
 * Mounted under the AdminLayout gate, so it only ever renders for `is_admin`
 * sessions; every endpoint it calls is additionally enforced server-side by
 * `IsOrganizationAdmin`. The page itself assumes an admin context.
 */
export const UsersPage = () => {
  const api = useAPI();
  const toast = useToast();
  const { user: currentUser } = useAuth();

  const [users, setUsers] = useState(null);
  const [groups, setGroups] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [saving, setSaving] = useState(false);

  // Modal state: exactly one surface is open at a time.
  const [formModal, setFormModal] = useState(null); // {mode: "create"|"edit", user?}
  const [groupsModal, setGroupsModal] = useState(null); // {user, selected: number[]}
  const [deleteTarget, setDeleteTarget] = useState(null); // user
  const [modalError, setModalError] = useState(null);

  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const load = useCallback(async () => {
    const [usersResult, groupsResult] = await Promise.all([api.callApi("adminUsers"), api.callApi("adminGroups")]);

    if (!mountedRef.current) return;

    // callApi resolves to null after the global error handler already showed a message.
    if (!Array.isArray(usersResult)) {
      setLoadError("Could not load users.");
      return;
    }
    setUsers(usersResult);
    setGroups(Array.isArray(groupsResult) ? groupsResult : []);
    setLoadError(null);
    setActionError(null);
  }, [api]);

  useEffect(() => {
    load();
  }, [load]);

  // The T10 API does not expose an owner flag. The owner is the first admin created
  // in the organization, so the lowest id among `is_admin` users is the best
  // client-side signal; the authoritative guard stays server-side (DELETE and
  // `is_admin` PATCH return 403 for the owner).
  const ownerId = useMemo(() => {
    const adminIds = (users ?? []).filter((user) => user.is_admin).map((user) => user.id);
    return adminIds.length ? Math.min(...adminIds) : null;
  }, [users]);

  const isOwner = useCallback((user) => user.id === ownerId, [ownerId]);
  const isSelf = useCallback((user) => user.id === currentUser?.id, [currentUser]);
  const deleteBlocked = useCallback((user) => isOwner(user) || isSelf(user), [isOwner, isSelf]);

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
          await load();
          return [true, result];
        }
        return [false, failureMessage(result, "The request failed. Please try again.")];
      } catch (error) {
        return [false, error?.message ?? "The request failed. Please try again."];
      } finally {
        if (mountedRef.current) setSaving(false);
      }
    },
    [api, load, toast],
  );

  // ---------- create / edit ----------

  const openCreate = () => {
    setModalError(null);
    setFormModal({ mode: "create", values: { ...emptyUserForm } });
  };

  const openEdit = (user) => {
    setModalError(null);
    setFormModal({
      mode: "edit",
      user,
      values: {
        email: user.email ?? "",
        first_name: user.first_name ?? "",
        last_name: user.last_name ?? "",
        is_admin: !!user.is_admin,
      },
    });
  };

  const setFormValue = (key, value) => {
    setFormModal((modal) => (modal ? { ...modal, values: { ...modal.values, [key]: value } } : modal));
  };

  const submitForm = async () => {
    if (!formModal) return;
    setModalError(null);

    if (formModal.mode === "create") {
      if (!formModal.values.email.trim() || !formModal.values.password) {
        setModalError("Email and password are required.");
        return;
      }
      const [ok, failure] = await mutate(
        "createAdminUser",
        {
          body: {
            email: formModal.values.email.trim(),
            password: formModal.values.password,
            first_name: formModal.values.first_name.trim(),
            last_name: formModal.values.last_name.trim(),
          },
        },
        "User created",
      );
      if (ok) setFormModal(null);
      else setModalError(String(failure));
      return;
    }

    const { user, values } = formModal;
    if (!values.email.trim()) {
      setModalError("Email is required.");
      return;
    }
    const body = {
      email: values.email.trim(),
      first_name: values.first_name.trim(),
      last_name: values.last_name.trim(),
    };
    // The API rejects `is_admin` changes for the owner and for yourself; only send
    // it when it actually changed so untouched rows never trip a 403.
    if (values.is_admin !== !!user.is_admin && !isOwner(user) && !isSelf(user)) {
      body.is_admin = values.is_admin;
    }
    const [ok, failure] = await mutate("updateAdminUser", { params: { pk: user.id }, body }, "User updated");
    if (ok) setFormModal(null);
    else setModalError(String(failure));
  };

  // ---------- activate / deactivate ----------

  const toggleActive = async (user) => {
    setModalError(null);
    const [ok, failure] = await mutate(
      "updateAdminUser",
      { params: { pk: user.id }, body: { is_active: !user.is_active } },
      user.is_active ? "User deactivated" : "User activated",
    );
    if (!ok) {
      setActionError(String(failure));
      toast?.show({ message: String(failure), type: "error" });
    }
  };

  // ---------- delete ----------

  const requestDelete = (user) => {
    if (deleteBlocked(user)) return;
    setModalError(null);
    setDeleteTarget(user);
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setModalError(null);
    const [ok, failure] = await mutate("deleteAdminUser", { params: { pk: deleteTarget.id } }, "User deleted");
    if (!ok) {
      setModalError(String(failure));
      // Rejecting keeps ConfirmDialog open (its waiting state resets) so the
      // inline error stays visible.
      throw new Error(String(failure));
    }
  };

  // ---------- group assignment ----------

  const openGroups = async (user) => {
    setModalError(null);
    setGroupsModal({ user, selected: (user.groups ?? []).map((group) => group.id), loading: true });

    const result = await api.callApi("adminUserGroups", { params: { pk: user.id }, suppressError: true });
    if (!mountedRef.current) return;

    if (result && !result.error) {
      const fresh = Array.isArray(result.groups) ? result.groups : [];
      setGroupsModal((modal) =>
        modal && modal.user.id === user.id
          ? { ...modal, selected: fresh.map((group) => group.id), loading: false }
          : modal,
      );
    } else {
      // Keep the ids from the list payload; let the admin retry the save anyway.
      setGroupsModal((modal) => (modal ? { ...modal, loading: false } : modal));
      setModalError("Could not refresh the current groups; showing the last known assignment.");
    }
  };

  const toggleGroup = (groupId, checked) => {
    setGroupsModal((modal) => {
      if (!modal) return modal;
      const selected = checked
        ? [...new Set([...modal.selected, groupId])]
        : modal.selected.filter((id) => id !== groupId);
      return { ...modal, selected };
    });
  };

  const saveGroups = async () => {
    if (!groupsModal) return;
    setModalError(null);
    const [ok, failure] = await mutate(
      "updateAdminUserGroups",
      { params: { pk: groupsModal.user.id }, body: { groups: groupsModal.selected } },
      "Groups updated",
    );
    if (ok) setGroupsModal(null);
    else setModalError(String(failure));
  };

  // ---------- render ----------

  const rowAction = (label, onClick, { disabled = false, danger = false } = {}) => (
    <Menu.Item
      key={label}
      onClick={disabled ? undefined : onClick}
      isDangerous={danger}
      aria-disabled={disabled ? "true" : undefined}
      className={disabled ? "opacity-50 pointer-events-none" : undefined}
      data-testid={`user-action-${label.toLowerCase().replace(/\s+/g, "-")}`}
    >
      {label}
    </Menu.Item>
  );

  const columns = [
    { accessorKey: "email", header: "Email", size: 240 },
    { id: "name", accessorFn: (user) => fullName(user), header: "Name", size: 220 },
    {
      id: "groups",
      accessorFn: (user) => (user.groups?.length ? user.groups.map((group) => group.name).join(", ") : "—"),
      header: "Groups",
      size: 180,
    },
    {
      id: "status",
      header: "Status",
      size: 110,
      cell: ({ row }) => (
        <Badge variant={row.original.is_active ? "positive" : "neutral"} size="small">
          {row.original.is_active ? "Active" : "Inactive"}
        </Badge>
      ),
    },
    {
      id: "role",
      header: "Role",
      size: 110,
      cell: ({ row }) =>
        row.original.is_admin ? (
          <Badge variant="primary" size="small">
            Admin
          </Badge>
        ) : (
          <span className="text-neutral-content-subtler">Member</span>
        ),
    },
    {
      id: "lastActivity",
      accessorFn: (user) => formatActivity(user.last_activity),
      header: "Last Activity",
      size: 170,
    },
    {
      id: "actions",
      header: "",
      size: 64,
      cell: ({ row }) => {
        const user = row.original;
        return (
          <div className="flex justify-end">
            <Dropdown.Trigger
              dataTestId={`user-actions-${user.id}`}
              content={
                <Menu contextual>
                  {rowAction("Edit", () => openEdit(user))}
                  {rowAction("Assign groups", () => openGroups(user))}
                  {rowAction(user.is_active ? "Deactivate" : "Activate", () => toggleActive(user))}
                  {rowAction("Delete", () => requestDelete(user), {
                    disabled: deleteBlocked(user),
                    danger: true,
                  })}
                </Menu>
              }
            >
              <Button size="smaller" look="ghost" aria-label={`Options for ${user.email}`} waiting={saving}>
                <DotsThreeIcon />
              </Button>
            </Dropdown.Trigger>
          </div>
        );
      },
    },
  ];

  const renderBody = () => {
    if (loadError) {
      return (
        <div className="p-base" data-testid="users-load-error">
          <Message variant="negative">
            <span className="flex items-center gap-base">
              {loadError}
              <Button look="outlined" size="small" onClick={load}>
                Retry
              </Button>
            </span>
          </Message>
        </div>
      );
    }

    if (!users) {
      return (
        <div className="flex justify-center p-wider" data-testid="users-loading">
          <Spinner size={36} />
        </div>
      );
    }

    if (users.length === 0) {
      return (
        <div className="p-wider text-neutral-content-subtler" data-testid="users-empty">
          No users in this organization.
        </div>
      );
    }

    return (
      <DataTable
        data={users}
        columns={columns}
        dataTestId="users-table"
        getRowId={(user) => String(user.id)}
        enableSorting={false}
      />
    );
  };

  return (
    <div className={rootClass.toClassName()} data-testid="admin-users-page">
      <div className="flex items-end justify-between gap-base mb-base">
        <div>
          <Typography variant="headline" size="medium">
            Users
          </Typography>
          <Typography variant="body" size="small" className="text-neutral-content-subtler">
            Accounts in the active organization. Changes here take effect immediately.
          </Typography>
        </div>
        <Button variant="primary" onClick={openCreate} data-testid="create-user-button">
          Create user
        </Button>
      </div>

      {actionError && (
        <div className="mb-base" data-testid="action-error">
          <Message variant="negative">
            <span className="flex items-center gap-base">
              {actionError}
              <Button look="outlined" size="small" onClick={() => setActionError(null)}>
                Dismiss
              </Button>
            </span>
          </Message>
        </div>
      )}

      {renderBody()}

      <ModalWindow
        open={formModal !== null}
        onOpenChange={(open) => {
          if (!open) setFormModal(null);
        }}
        dataTestId="user-form-modal"
        title={formModal?.mode === "edit" ? "Edit user" : "Create user"}
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
              data-testid={formModal?.mode === "edit" ? "save-user-button" : "create-user-submit"}
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
              label="Email"
              required
              type="email"
              value={formModal.values.email}
              onChange={(e) => setFormValue("email", e.target.value)}
              data-testid="user-email-input"
              autoComplete="off"
            />
            {formModal.mode === "create" && (
              <Input
                label="Password"
                required
                type="password"
                value={formModal.values.password}
                onChange={(e) => setFormValue("password", e.target.value)}
                data-testid="user-password-input"
                autoComplete="new-password"
              />
            )}
            <Input
              label="First name"
              value={formModal.values.first_name}
              onChange={(e) => setFormValue("first_name", e.target.value)}
              data-testid="user-first-name-input"
            />
            <Input
              label="Last name"
              value={formModal.values.last_name}
              onChange={(e) => setFormValue("last_name", e.target.value)}
              data-testid="user-last-name-input"
            />
            {formModal.mode === "edit" && (
              <Checkbox
                checked={formModal.values.is_admin}
                disabled={isOwner(formModal.user) || isSelf(formModal.user)}
                onChange={(e) => setFormValue("is_admin", e.target.checked)}
                aria-label="Organization admin"
              >
                Organization admin
              </Checkbox>
            )}
          </div>
        )}
      </ModalWindow>

      <ModalWindow
        open={groupsModal !== null}
        onOpenChange={(open) => {
          if (!open) setGroupsModal(null);
        }}
        dataTestId="user-groups-modal"
        title={`Assign groups to ${groupsModal ? fullName(groupsModal.user) : ""}`}
        size="small"
        footer={
          <div className="flex justify-end gap-tight">
            <Button look="outlined" onClick={() => setGroupsModal(null)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              waiting={saving}
              disabled={groupsModal?.loading}
              onClick={saveGroups}
              data-testid="save-groups-button"
            >
              Save
            </Button>
          </div>
        }
      >
        {groupsModal &&
          (groupsModal.loading ? (
            <div className="flex justify-center p-wider">
              <Spinner size={28} />
            </div>
          ) : (
            <div className="flex flex-col gap-tight">
              {modalError && (
                <Message variant="negative" data-testid="groups-error">
                  {modalError}
                </Message>
              )}
              {groups.length === 0 ? (
                <Typography variant="body" size="small" className="text-neutral-content-subtler">
                  No groups exist in this organization yet. Groups are managed under Admin → Groups.
                </Typography>
              ) : (
                groups.map((group) => (
                  <Checkbox
                    key={group.id}
                    checked={groupsModal.selected.includes(group.id)}
                    onChange={(e) => toggleGroup(group.id, e.target.checked)}
                    data-testid={`group-option-${group.id}`}
                  >
                    {group.name}
                  </Checkbox>
                ))
              )}
            </div>
          ))}
      </ModalWindow>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteTarget(null);
            setModalError(null);
          }
        }}
        title="Delete user?"
        okText="Delete"
        buttonLook="negative"
        onOk={confirmDelete}
        dataTestId="delete-user-dialog"
      >
        <Typography variant="body" size="medium">
          You are about to permanently delete <strong>{deleteTarget?.email}</strong>. This action cannot be undone.
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

UsersPage.title = "Users";
UsersPage.path = "/users";

export default UsersPage;
