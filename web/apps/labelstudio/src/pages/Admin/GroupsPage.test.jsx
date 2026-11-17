import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ToastProvider } from "@humansignal/ui";
import { ApiContext } from "../../providers/ApiProvider";
import GroupsPage from "./GroupsPage";

// MenuItem reads the bare `location` global for active-state checks; bun's
// --dom exposes window.location but not the implicit global binding
// (same shim as AdminPage.test.jsx / UsersPage.test.jsx).
if (typeof globalThis.location === "undefined") {
  Object.defineProperty(globalThis, "location", { value: window.location, configurable: true });
}

const GROUPS = [
  { id: 1, name: "Annotators", description: "Gold tier labeling" },
  { id: 2, name: "Reviewers", description: "" },
];
const USERS = [
  { id: 10, email: "ana@example.com", username: "ana", first_name: "Ana", last_name: "Sousa" },
  { id: 11, email: "bruno@example.com", username: "bruno", first_name: "Bruno", last_name: "Lima" },
  { id: 12, email: "carla@example.com", username: "carla", first_name: "Carla", last_name: "Moraes" },
];
const PROJECTS = [
  { id: 100, title: "Signals QA" },
  { id: 200, title: "Support Tickets" },
  { id: 300, title: "Docs Snippets" },
];

const memberRow = (group, user) => ({
  id: 900 + user.id,
  group,
  user: user.id,
  user_email: user.email,
  user_name: `${user.first_name} ${user.last_name}`,
});

// Stateful fake of `useAPI().callApi`: mutations edit the same in-memory rows
// the list endpoints serve, so refresh-after-write is observable in tests.
// Mirrors the real contract: success -> object (204 -> {ok:true}),
// failure with suppressError -> {error: string}, failure without -> null.
function makeApi(overrides = {}) {
  const groups = GROUPS.map((group) => ({ ...group }));
  const members = { 1: [memberRow(1, USERS[0])], 2: [] };
  const grants = { 1: [100], 2: [] };
  const calls = [];
  let nextGroupId = 3;
  let nextMemberId = 990;

  const callApi = mock(async (endpoint, options = {}) => {
    calls.push({ endpoint, options });

    if (endpoint in overrides) {
      const handler = overrides[endpoint];
      return typeof handler === "function" ? handler(options) : handler;
    }

    switch (endpoint) {
      case "adminGroups":
        return groups.map((group) => ({ ...group }));
      case "createAdminGroup": {
        const created = { id: nextGroupId++, name: options.body.name, description: options.body.description };
        groups.push(created);
        members[created.id] = [];
        grants[created.id] = [];
        return { ...created };
      }
      case "updateAdminGroup": {
        const group = groups.find((row) => row.id === Number(options.params.pk));
        Object.assign(group, options.body);
        return { ...group };
      }
      case "deleteAdminGroup": {
        const pk = Number(options.params.pk);
        groups.splice(
          groups.findIndex((row) => row.id === pk),
          1,
        );
        delete members[pk];
        delete grants[pk];
        return { ok: true };
      }
      case "adminGroupMembers":
        return (members[Number(options.params.pk)] ?? []).map((row) => ({ ...row }));
      case "addAdminGroupMember": {
        const pk = Number(options.params.pk);
        const user = USERS.find((row) => row.id === Number(options.body.user));
        const row = {
          id: nextMemberId++,
          group: pk,
          user: user.id,
          user_email: user.email,
          user_name: `${user.first_name} ${user.last_name}`,
        };
        members[pk] = [...(members[pk] ?? []), row];
        return { ...row };
      }
      case "deleteAdminGroupMember": {
        const pk = Number(options.params.pk);
        const userPk = Number(options.params.userPk);
        members[pk] = (members[pk] ?? []).filter((row) => row.user !== userPk);
        return { ok: true };
      }
      case "adminGroupProjects":
        return (grants[Number(options.params.pk)] ?? []).map((projectId) => {
          const project = PROJECTS.find((row) => row.id === projectId);
          return {
            id: 500 + projectId,
            group: Number(options.params.pk),
            project: projectId,
            project_title: project?.title,
          };
        });
      case "addAdminGroupProject": {
        const pk = Number(options.params.pk);
        grants[pk] = [...new Set([...(grants[pk] ?? []), Number(options.body.project)])];
        return { id: 1, group: pk, project: Number(options.body.project) };
      }
      case "deleteAdminGroupProject": {
        const pk = Number(options.params.pk);
        grants[pk] = (grants[pk] ?? []).filter((id) => id !== Number(options.params.projectPk));
        return { ok: true };
      }
      case "adminUsers":
        return USERS.map((user) => ({ ...user, is_active: true, is_admin: false }));
      case "projects":
        return {
          count: PROJECTS.length,
          next: null,
          previous: null,
          results: PROJECTS.map((project) => ({ ...project })),
        };
      default:
        return { ok: true };
    }
  });

  return { callApi, calls, groups, members, grants };
}

const crossOrgUserRejection = () => ({
  status: 400,
  error: "Bad Request",
  response: {
    detail: "Validation error",
    validation_errors: { user: ["User is not an active member of the organization."] },
  },
});
const crossOrgProjectRejection = () => ({
  status: 400,
  error: "Bad Request",
  response: {
    detail: "Validation error",
    validation_errors: { project: ["Project does not belong to the organization."] },
  },
});

function renderPage(api = makeApi()) {
  render(
    <ApiContext.Provider value={api}>
      <ToastProvider>
        <GroupsPage />
      </ToastProvider>
    </ApiContext.Provider>,
  );
  return api;
}

async function openGroupMenu(name) {
  fireEvent.click(await screen.findByLabelText(`Options for ${name}`));
}

async function openMemberPicker() {
  await waitFor(() => expect(screen.getByTestId("add-member-button")).toBeEnabled());
  fireEvent.click(screen.getByTestId("add-member-button"));
}

describe("GroupsPage listing", () => {
  it("lists groups, auto-selects the first and shows its members and dataset grants", async () => {
    const api = renderPage();

    expect(await screen.findByTestId("group-item-1")).toBeInTheDocument();
    expect(screen.getByText("Reviewers")).toBeInTheDocument();
    expect(screen.getByTestId("group-item-1")).toHaveAttribute("aria-current", "true");
    expect(screen.getByTestId("group-item-2")).not.toHaveAttribute("aria-current");

    // Group 1 fixture: Ana is a member and project 100 is granted.
    expect(await screen.findByText("Ana Sousa")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("dataset-toggle-100")).toBeChecked());
    expect(screen.getByTestId("dataset-toggle-200")).not.toBeChecked();
    expect(screen.getByTestId("dataset-toggle-300")).not.toBeChecked();

    expect(api.calls.some(({ endpoint, options }) => endpoint === "adminGroupMembers" && options.params.pk === 1)).toBe(
      true,
    );
    expect(
      api.calls.some(({ endpoint, options }) => endpoint === "adminGroupProjects" && options.params.pk === 1),
    ).toBe(true);
    expect(api.calls.some(({ endpoint }) => endpoint === "projects")).toBe(true);
    expect(api.calls.some(({ endpoint }) => endpoint === "adminUsers")).toBe(true);
  });

  it("swaps the detail panel when another group is selected", async () => {
    const api = renderPage();
    await screen.findByTestId("group-item-1");
    await screen.findByText("Ana Sousa");

    fireEvent.click(await screen.findByTestId("group-item-2"));

    await waitFor(() =>
      expect(
        api.calls.some(({ endpoint, options }) => endpoint === "adminGroupMembers" && options.params.pk === 2),
      ).toBe(true),
    );
    expect(await screen.findByTestId("members-empty")).toBeInTheDocument();
    expect(screen.getByTestId("dataset-toggle-100")).not.toBeChecked();
  });

  it("shows the empty state when the organization has no groups", async () => {
    renderPage(makeApi({ adminGroups: [] }));

    expect(await screen.findByTestId("groups-empty")).toBeInTheDocument();
    expect(screen.getByTestId("group-detail-placeholder")).toBeInTheDocument();
  });

  it("surfaces a retryable message when the list call fails, without crashing", async () => {
    let fail = true;
    const api = makeApi({
      adminGroups: () => (fail ? null : GROUPS.map((group) => ({ ...group }))),
    });
    renderPage(api);

    const error = await screen.findByTestId("groups-load-error");
    expect(error).toHaveTextContent("Could not load groups.");

    fail = false;
    fireEvent.click(within(error).getByText("Retry"));

    expect(await screen.findByTestId("group-item-1")).toBeInTheDocument();
    expect(screen.queryByTestId("groups-load-error")).not.toBeInTheDocument();
  });

  it("registers as the /admin/groups page of the Admin set", () => {
    expect(GroupsPage.path).toBe("/groups");
    expect(GroupsPage.title).toBe("Groups");
  });
});

describe("GroupsPage create", () => {
  it("creates a group through the modal, refreshes the list and selects it", async () => {
    const api = renderPage();
    await screen.findByTestId("group-item-1");

    fireEvent.click(screen.getByTestId("create-group-button"));

    const dialog = await screen.findByTestId("group-form-modal");
    fireEvent.change(within(dialog).getByTestId("group-name-input"), { target: { value: "Data squad" } });
    fireEvent.change(within(dialog).getByTestId("group-description-input"), { target: { value: "Dataset access" } });
    fireEvent.click(within(dialog).getByTestId("create-group-submit"));

    await waitFor(() => {
      const call = api.calls.find(({ endpoint }) => endpoint === "createAdminGroup");
      expect(call).toBeDefined();
      expect(call.options.body).toEqual({ name: "Data squad", description: "Dataset access" });
    });

    expect(await screen.findByTestId("group-item-3")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("group-item-3")).toHaveAttribute("aria-current", "true"));
    expect(within(screen.getByTestId("group-detail-3")).getByText("Data squad")).toBeInTheDocument();
    expect(screen.queryByTestId("group-form-modal")).not.toBeInTheDocument();
  });

  it("requires a name before submitting", async () => {
    const api = renderPage();
    await screen.findByTestId("group-item-1");

    fireEvent.click(screen.getByTestId("create-group-button"));
    const dialog = await screen.findByTestId("group-form-modal");
    fireEvent.click(within(dialog).getByTestId("create-group-submit"));

    expect(await within(dialog).findByTestId("form-error")).toHaveTextContent("Group name is required.");
    expect(api.calls.some(({ endpoint }) => endpoint === "createAdminGroup")).toBe(false);
  });

  it("keeps the modal open with the API message when creation fails", async () => {
    renderPage(
      makeApi({
        createAdminGroup: () => ({ error: "Group with this name already exists." }),
      }),
    );
    await screen.findByTestId("group-item-1");

    fireEvent.click(screen.getByTestId("create-group-button"));
    const dialog = await screen.findByTestId("group-form-modal");
    fireEvent.change(within(dialog).getByTestId("group-name-input"), { target: { value: "Annotators" } });
    fireEvent.click(within(dialog).getByTestId("create-group-submit"));

    expect(await within(dialog).findByTestId("form-error")).toHaveTextContent("Group with this name already exists.");
    expect(screen.getByTestId("group-form-modal")).toBeInTheDocument();
  });
});

describe("GroupsPage rename", () => {
  it("prefills the modal and patches the group, reflecting the new name", async () => {
    const api = renderPage();
    await screen.findByTestId("group-item-1");

    await openGroupMenu("Annotators");
    fireEvent.click(await screen.findByTestId("group-action-rename-1"));

    const dialog = await screen.findByTestId("group-form-modal");
    expect(within(dialog).getByTestId("group-name-input")).toHaveValue("Annotators");

    fireEvent.change(within(dialog).getByTestId("group-name-input"), { target: { value: "Annotators EU" } });
    fireEvent.click(within(dialog).getByTestId("save-group-button"));

    await waitFor(() => {
      const call = api.calls.find(({ endpoint }) => endpoint === "updateAdminGroup");
      expect(call.options.params).toEqual({ pk: 1 });
      expect(call.options.body.name).toBe("Annotators EU");
    });
    expect(await screen.findByTestId("group-item-1")).toHaveTextContent("Annotators EU");
  });
});

describe("GroupsPage delete", () => {
  it("asks for confirmation and removes the group from the list", async () => {
    const api = renderPage();
    await screen.findByTestId("group-item-1");

    await openGroupMenu("Reviewers");
    fireEvent.click(await screen.findByTestId("group-action-delete-2"));

    const dialog = await screen.findByTestId("delete-group-dialog");
    expect(dialog).toHaveTextContent("You are about to delete Reviewers");

    fireEvent.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      const call = api.calls.find(({ endpoint }) => endpoint === "deleteAdminGroup");
      expect(call.options.params).toEqual({ pk: 2 });
    });
    await waitFor(() => expect(screen.queryByTestId("group-item-2")).not.toBeInTheDocument());
    // The selected group (1) is untouched by deleting an unselected row.
    expect(screen.getByTestId("group-item-1")).toHaveAttribute("aria-current", "true");
  });

  it("clears the panel when the selected group is deleted", async () => {
    renderPage();
    await screen.findByTestId("group-item-1");

    await openGroupMenu("Annotators");
    fireEvent.click(await screen.findByTestId("group-action-delete-1"));

    const dialog = await screen.findByTestId("delete-group-dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => expect(screen.queryByTestId("group-item-1")).not.toBeInTheDocument());
    expect(await screen.findByTestId("group-detail-placeholder")).toBeInTheDocument();
  });

  it("keeps the dialog open with the server message when deletion fails", async () => {
    renderPage(
      makeApi({
        deleteAdminGroup: () => ({ error: "Groups in use cannot be deleted" }),
      }),
    );
    await screen.findByTestId("group-item-1");

    await openGroupMenu("Reviewers");
    fireEvent.click(await screen.findByTestId("group-action-delete-2"));

    const dialog = await screen.findByTestId("delete-group-dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete" }));

    expect(await within(dialog).findByTestId("delete-error")).toHaveTextContent("Groups in use cannot be deleted");
    expect(screen.getByTestId("delete-group-dialog")).toBeInTheDocument();
  });
});

describe("GroupsPage members", () => {
  it("opens a picker listing org users who are not members yet and adds one", async () => {
    const api = renderPage();
    await screen.findByText("Ana Sousa");

    await openMemberPicker();

    const dialog = await screen.findByTestId("member-picker-modal");
    await waitFor(() => expect(within(dialog).getByTestId("pick-user-11")).toBeInTheDocument());
    // Ana is already a member of group 1 and must not be offered again.
    expect(within(dialog).queryByTestId("pick-user-10")).not.toBeInTheDocument();

    fireEvent.click(within(dialog).getByTestId("pick-user-11"));

    await waitFor(() => {
      const call = api.calls.find(({ endpoint }) => endpoint === "addAdminGroupMember");
      expect(call.options.params).toEqual({ pk: 1 });
      expect(call.options.body).toEqual({ user: 11 });
    });
    await waitFor(() => expect(screen.queryByTestId("member-picker-modal")).not.toBeInTheDocument());
    expect(await screen.findByText("Bruno Lima")).toBeInTheDocument();
  });

  it("filters picker candidates by the search query", async () => {
    renderPage();
    await screen.findByText("Ana Sousa");

    await openMemberPicker();
    const dialog = await screen.findByTestId("member-picker-modal");
    await waitFor(() => expect(within(dialog).getByTestId("pick-user-11")).toBeInTheDocument());

    fireEvent.change(within(dialog).getByTestId("member-search-input"), { target: { value: "carla" } });

    expect(within(dialog).getByTestId("pick-user-12")).toBeInTheDocument();
    expect(within(dialog).queryByTestId("pick-user-11")).not.toBeInTheDocument();
  });

  it("surfaces the server rejection when adding a user outside the organization", async () => {
    const api = renderPage(
      makeApi({
        addAdminGroupMember: crossOrgUserRejection,
      }),
    );
    await screen.findByText("Ana Sousa");

    await openMemberPicker();
    const dialog = await screen.findByTestId("member-picker-modal");
    await waitFor(() => expect(within(dialog).getByTestId("pick-user-11")).toBeInTheDocument());

    fireEvent.click(within(dialog).getByTestId("pick-user-11"));

    expect(await within(dialog).findByTestId("picker-error")).toHaveTextContent(
      "User is not an active member of the organization.",
    );
    // The picker stays open and the member list keeps its server truth.
    expect(screen.getByTestId("member-picker-modal")).toBeInTheDocument();
    expect(within(screen.getByTestId("members-list")).queryByText("Bruno Lima")).not.toBeInTheDocument();
    expect(api.calls.filter(({ endpoint }) => endpoint === "addAdminGroupMember")).toHaveLength(1);
  });

  it("removes a member and refreshes the list", async () => {
    const api = renderPage();
    await screen.findByText("Ana Sousa");

    fireEvent.click(screen.getByTestId("remove-member-10"));

    await waitFor(() => {
      const call = api.calls.find(({ endpoint }) => endpoint === "deleteAdminGroupMember");
      expect(call.options.params).toEqual({ pk: 1, userPk: 10 });
    });
    await waitFor(() => expect(screen.getByTestId("members-empty")).toBeInTheDocument());
  });

  it("shows an inline error when the member list fails to load", async () => {
    renderPage(
      makeApi({
        adminGroupMembers: () => ({ error: "Could not load the group members." }),
      }),
    );
    await screen.findByTestId("group-item-1");

    expect(await screen.findByTestId("detail-error")).toHaveTextContent("Could not load the group members.");
  });
});

describe("GroupsPage datasets", () => {
  it("grants access by toggling a project and reflects it immediately", async () => {
    const api = renderPage();
    await waitFor(() => expect(screen.getByTestId("dataset-toggle-200")).toBeInTheDocument());
    expect(screen.getByTestId("dataset-toggle-200")).not.toBeChecked();

    fireEvent.click(screen.getByTestId("dataset-toggle-200"));

    await waitFor(() => {
      const call = api.calls.find(({ endpoint }) => endpoint === "addAdminGroupProject");
      expect(call.options.params).toEqual({ pk: 1 });
      expect(call.options.body).toEqual({ project: 200 });
    });
    await waitFor(() => expect(screen.getByTestId("dataset-toggle-200")).toBeChecked());
  });

  it("revokes access by untoggling a granted project", async () => {
    const api = renderPage();
    await waitFor(() => expect(screen.getByTestId("dataset-toggle-100")).toBeChecked());

    fireEvent.click(screen.getByTestId("dataset-toggle-100"));

    await waitFor(() => {
      const call = api.calls.find(({ endpoint }) => endpoint === "deleteAdminGroupProject");
      expect(call.options.params).toEqual({ pk: 1, projectPk: 100 });
    });
    await waitFor(() => expect(screen.getByTestId("dataset-toggle-100")).not.toBeChecked());
  });

  it("surfaces the server rejection for a cross-org project and keeps the checkbox unchecked", async () => {
    const api = renderPage(
      makeApi({
        addAdminGroupProject: crossOrgProjectRejection,
      }),
    );
    await waitFor(() => expect(screen.getByTestId("dataset-toggle-300")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("dataset-toggle-300"));

    expect(await screen.findByTestId("detail-error")).toHaveTextContent("Project does not belong to the organization.");
    // No optimistic state survives the rejection: the panel re-reads the server.
    await waitFor(() => expect(screen.getByTestId("dataset-toggle-300")).not.toBeChecked());
    expect(api.grants[1]).toEqual([100]);
  });

  it("keeps checkboxes in server state while a grant is in flight (no stale success)", async () => {
    let resolveGrant;
    const api = makeApi({
      addAdminGroupProject: () =>
        new Promise((resolve) => {
          resolveGrant = (row) => {
            api.grants[1] = [...new Set([...api.grants[1], 200])];
            resolve(row);
          };
        }),
    });
    renderPage(api);
    await waitFor(() => expect(screen.getByTestId("dataset-toggle-200")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("dataset-toggle-200"));
    await waitFor(() => expect(api.calls.some(({ endpoint }) => endpoint === "addAdminGroupProject")).toBe(true));

    // While the request is pending the checkbox is disabled and still unchecked.
    expect(screen.getByTestId("dataset-toggle-200")).toBeDisabled();
    expect(screen.getByTestId("dataset-toggle-200")).not.toBeChecked();

    resolveGrant({ id: 1, group: 1, project: 200 });
    await waitFor(() => expect(screen.getByTestId("dataset-toggle-200")).toBeChecked());
  });
});
