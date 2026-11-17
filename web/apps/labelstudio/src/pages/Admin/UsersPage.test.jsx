import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import * as authProvider from "@humansignal/core/providers/AuthProvider";
import { ToastProvider } from "@humansignal/ui";
import { ApiContext } from "../../providers/ApiProvider";
import UsersPage from "./UsersPage";

let useAuthSpy = null;

// MenuItem reads the bare `location` global for active-state checks; bun's
// --dom exposes window.location but not the implicit global binding
// (same shim as AdminPage.test.jsx).
if (typeof globalThis.location === "undefined") {
  Object.defineProperty(globalThis, "location", { value: window.location, configurable: true });
}

const OWNER = {
  id: 1,
  email: "owner@example.com",
  username: "owner",
  first_name: "Org",
  last_name: "Owner",
  is_active: true,
  is_admin: true,
  last_activity: "2026-11-16T10:00:00Z",
  groups: [],
};
const SELF = {
  id: 2,
  email: "admin@example.com",
  username: "admin",
  first_name: "Ada",
  last_name: "Admin",
  is_active: true,
  is_admin: true,
  last_activity: "2026-11-16T11:00:00Z",
  groups: [{ id: 1, name: "Annotators" }],
};
const MEMBER = {
  id: 3,
  email: "member@example.com",
  username: "member",
  first_name: "Mo",
  last_name: "Member",
  is_active: true,
  is_admin: false,
  last_activity: "2026-11-15T09:00:00Z",
  groups: [],
};
const GROUPS = [
  { id: 1, name: "Annotators" },
  { id: 2, name: "Reviewers" },
];

// Stateful fake of `useAPI().callApi`: mutations edit the same in-memory rows
// the list endpoint serves, so refresh-after-write is observable in tests.
// Mirrors the real contract: success -> object (204 -> {ok:true}),
// failure with suppressError -> {error: string}, failure without -> null.
function makeApi(overrides = {}) {
  const users = [OWNER, SELF, MEMBER].map((user) => ({ ...user, groups: [...user.groups] }));
  const calls = [];

  const callApi = mock(async (endpoint, options = {}) => {
    calls.push({ endpoint, options });

    if (endpoint in overrides) {
      const handler = overrides[endpoint];
      return typeof handler === "function" ? handler(options) : handler;
    }

    switch (endpoint) {
      case "adminUsers":
        return users.map((user) => ({ ...user, groups: [...user.groups] }));
      case "adminGroups":
        return GROUPS.map((group) => ({ ...group }));
      case "createAdminUser": {
        const created = {
          id: 100 + users.length,
          email: options.body.email,
          username: options.body.email.split("@")[0],
          first_name: options.body.first_name ?? "",
          last_name: options.body.last_name ?? "",
          is_active: true,
          is_admin: false,
          last_activity: null,
          groups: [],
        };
        users.push(created);
        return created;
      }
      case "updateAdminUser": {
        const user = users.find((row) => row.id === Number(options.params.pk));
        Object.assign(user, options.body);
        return { ...user };
      }
      case "deleteAdminUser": {
        const index = users.findIndex((row) => row.id === Number(options.params.pk));
        users.splice(index, 1);
        return { ok: true };
      }
      case "adminUserGroups": {
        const user = users.find((row) => row.id === Number(options.params.pk));
        return { groups: user.groups.map(({ id, name }) => ({ id, name })) };
      }
      case "updateAdminUserGroups": {
        const user = users.find((row) => row.id === Number(options.params.pk));
        user.groups = GROUPS.filter((group) => options.body.groups.includes(group.id)).map(({ id, name }) => ({
          id,
          name,
        }));
        return { groups: user.groups };
      }
      default:
        return { ok: true };
    }
  });

  return { callApi, calls, users };
}

function renderPage(api = makeApi(), currentUser = { id: SELF.id, email: SELF.email, is_admin: true }) {
  useAuthSpy = spyOn(authProvider, "useAuth").mockReturnValue({ user: currentUser, isLoading: false });
  render(
    <ApiContext.Provider value={api}>
      <ToastProvider>
        <UsersPage />
      </ToastProvider>
    </ApiContext.Provider>,
  );
  return api;
}

async function openRowMenu(email) {
  fireEvent.click(await screen.findByLabelText(`Options for ${email}`));
}

async function runAction(email, actionTestId) {
  await openRowMenu(email);
  fireEvent.click(await screen.findByTestId(actionTestId));
}

afterEach(() => {
  useAuthSpy?.mockRestore();
  useAuthSpy = null;
});

describe("UsersPage listing", () => {
  it("renders email, name, status, role and last activity for every user", async () => {
    const api = renderPage();

    expect(await screen.findByText("owner@example.com")).toBeInTheDocument();
    expect(screen.getByText("admin@example.com")).toBeInTheDocument();
    expect(screen.getByText("member@example.com")).toBeInTheDocument();
    expect(screen.getByText("Org Owner")).toBeInTheDocument();
    expect(screen.getByText("Ada Admin")).toBeInTheDocument();
    expect(screen.getAllByText("Active")).toHaveLength(3);
    expect(screen.getAllByText("Admin")).toHaveLength(2); // two role badges, not counting the page header
    expect(screen.getByText("Member")).toBeInTheDocument();
    expect(screen.getByText("16 Nov 2026, 10:00")).toBeInTheDocument();
    expect(api.calls.some(({ endpoint }) => endpoint === "adminUsers")).toBe(true);
    expect(api.calls.some(({ endpoint }) => endpoint === "adminGroups")).toBe(true);
  });

  it("shows the assigned group names in the table", async () => {
    renderPage();

    expect(await screen.findByText("Annotators")).toBeInTheDocument();
  });

  it("surfaces a retryable message when the list call fails, without crashing", async () => {
    let fail = true;
    const api = makeApi({
      adminUsers: () => (fail ? null : [{ ...OWNER }, { ...SELF }, { ...MEMBER }]),
      adminGroups: () => [],
    });
    renderPage(api);

    const error = await screen.findByTestId("users-load-error");
    expect(error).toHaveTextContent("Could not load users.");

    fail = false;
    fireEvent.click(within(error).getByText("Retry"));

    expect(await screen.findByText("owner@example.com")).toBeInTheDocument();
    expect(screen.queryByTestId("users-load-error")).not.toBeInTheDocument();
  });

  it("registers as the /admin/users page of the Admin set", () => {
    expect(UsersPage.path).toBe("/users");
    expect(UsersPage.title).toBe("Users");
  });
});

describe("UsersPage create", () => {
  it("creates a user through the modal and refreshes the table", async () => {
    const api = renderPage();
    await screen.findByText("owner@example.com");

    fireEvent.click(screen.getByTestId("create-user-button"));

    const dialog = await screen.findByTestId("user-form-modal");
    fireEvent.change(within(dialog).getByTestId("user-email-input"), { target: { value: "new@example.com" } });
    fireEvent.change(within(dialog).getByTestId("user-password-input"), { target: { value: "Str0ngPassw0rd!" } });
    fireEvent.change(within(dialog).getByTestId("user-first-name-input"), { target: { value: "New" } });
    fireEvent.change(within(dialog).getByTestId("user-last-name-input"), { target: { value: "User" } });

    fireEvent.click(within(dialog).getByTestId("create-user-submit"));

    await waitFor(() => {
      const call = api.calls.find(({ endpoint }) => endpoint === "createAdminUser");
      expect(call).toBeDefined();
      expect(call.options.body).toEqual({
        email: "new@example.com",
        password: "Str0ngPassw0rd!",
        first_name: "New",
        last_name: "User",
      });
    });
    expect(await screen.findByText("new@example.com")).toBeInTheDocument();
    expect(screen.queryByTestId("user-form-modal")).not.toBeInTheDocument();
  });

  it("requires email and password before submitting", async () => {
    const api = renderPage();
    await screen.findByText("owner@example.com");

    fireEvent.click(screen.getByTestId("create-user-button"));
    const dialog = await screen.findByTestId("user-form-modal");
    fireEvent.click(within(dialog).getByTestId("create-user-submit"));

    expect(await within(dialog).findByTestId("form-error")).toHaveTextContent("Email and password are required.");
    expect(api.calls.some(({ endpoint }) => endpoint === "createAdminUser")).toBe(false);
  });

  it("keeps the modal open with the API message when creation fails", async () => {
    renderPage(
      makeApi({
        createAdminUser: () => ({ error: "Password is too weak" }),
      }),
    );
    await screen.findByText("owner@example.com");

    fireEvent.click(screen.getByTestId("create-user-button"));
    const dialog = await screen.findByTestId("user-form-modal");
    fireEvent.change(within(dialog).getByTestId("user-email-input"), { target: { value: "weak@example.com" } });
    fireEvent.change(within(dialog).getByTestId("user-password-input"), { target: { value: "123" } });
    fireEvent.click(within(dialog).getByTestId("create-user-submit"));

    expect(await within(dialog).findByTestId("form-error")).toHaveTextContent("Password is too weak");
    expect(screen.getByTestId("user-form-modal")).toBeInTheDocument();
  });

  it("shows the server field message for a 400 validation error", async () => {
    renderPage(
      makeApi({
        createAdminUser: () => ({
          status: 400,
          error: "Bad Request",
          response: {
            detail: "Validation error",
            validation_errors: { email: ["user with this email address already exists."] },
          },
        }),
      }),
    );
    await screen.findByText("owner@example.com");

    fireEvent.click(screen.getByTestId("create-user-button"));
    const dialog = await screen.findByTestId("user-form-modal");
    fireEvent.change(within(dialog).getByTestId("user-email-input"), { target: { value: "member@example.com" } });
    fireEvent.change(within(dialog).getByTestId("user-password-input"), { target: { value: "Str0ngPassw0rd!" } });
    fireEvent.click(within(dialog).getByTestId("create-user-submit"));

    expect(await within(dialog).findByTestId("form-error")).toHaveTextContent(
      "user with this email address already exists.",
    );
  });
});

describe("UsersPage edit", () => {
  it("patches the editable fields of a member", async () => {
    const api = renderPage();
    await screen.findByText("owner@example.com");

    await runAction("member@example.com", "user-action-edit");

    const dialog = await screen.findByTestId("user-form-modal");
    expect(within(dialog).getByTestId("modal-window-title")).toHaveTextContent("Edit user");
    expect(within(dialog).getByTestId("user-email-input")).toHaveValue("member@example.com");

    fireEvent.change(within(dialog).getByTestId("user-first-name-input"), { target: { value: "Mia" } });
    fireEvent.click(within(dialog).getByTestId("save-user-button"));

    await waitFor(() => {
      const call = api.calls.find(({ endpoint }) => endpoint === "updateAdminUser");
      expect(call).toBeDefined();
      expect(call.options.params).toEqual({ pk: 3 });
      expect(call.options.body).toEqual({
        email: "member@example.com",
        first_name: "Mia",
        last_name: "Member",
      });
    });
    expect(await screen.findByText("Mia Member")).toBeInTheDocument();
  });

  it("does not touch is_admin for the owner or for yourself", async () => {
    const api = renderPage();
    await screen.findByText("owner@example.com");

    await runAction("owner@example.com", "user-action-edit");
    const dialog = await screen.findByTestId("user-form-modal");
    expect(within(dialog).getByRole("checkbox", { name: "Organization admin" })).toBeDisabled();
    fireEvent.click(within(dialog).getByTestId("save-user-button"));

    await waitFor(() => {
      const call = api.calls.find(({ endpoint }) => endpoint === "updateAdminUser");
      expect(call.options.body.is_admin).toBeUndefined();
    });
  });
});

describe("UsersPage activate/deactivate", () => {
  it("deactivates through a PATCH of is_active and reflects it immediately", async () => {
    const api = renderPage();
    await screen.findByText("owner@example.com");

    await runAction("member@example.com", "user-action-deactivate");

    await waitFor(() => {
      const call = api.calls.find(
        ({ endpoint, options }) => endpoint === "updateAdminUser" && options.body.is_active === false,
      );
      expect(call).toBeDefined();
      expect(call.options.params).toEqual({ pk: 3 });
    });
    expect(await screen.findByText("Inactive")).toBeInTheDocument();
  });

  it("surfaces a failed toggle as a message instead of a crash", async () => {
    renderPage(
      makeApi({
        updateAdminUser: () => ({ error: "Cannot deactivate this account" }),
      }),
    );
    await screen.findByText("owner@example.com");

    await runAction("member@example.com", "user-action-deactivate");

    expect(await screen.findByTestId("action-error")).toHaveTextContent("Cannot deactivate this account");
    expect(screen.getByText("owner@example.com")).toBeInTheDocument();
  });
});

describe("UsersPage delete", () => {
  it("asks for confirmation and deletes the confirmed user", async () => {
    const api = renderPage();
    await screen.findByText("owner@example.com");

    await runAction("member@example.com", "user-action-delete");

    const dialog = await screen.findByTestId("delete-user-dialog");
    expect(dialog).toHaveTextContent("You are about to permanently delete member@example.com");

    fireEvent.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      const call = api.calls.find(({ endpoint }) => endpoint === "deleteAdminUser");
      expect(call.options.params).toEqual({ pk: 3 });
    });
    await waitFor(() => expect(screen.queryByText("member@example.com")).not.toBeInTheDocument());
  });

  it("does not delete when the confirmation is cancelled", async () => {
    const api = renderPage();
    await screen.findByText("owner@example.com");

    await runAction("member@example.com", "user-action-delete");

    const dialog = await screen.findByTestId("delete-user-dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));

    await waitFor(() => expect(screen.queryByTestId("delete-user-dialog")).not.toBeInTheDocument());
    expect(api.calls.some(({ endpoint }) => endpoint === "deleteAdminUser")).toBe(false);
    expect(screen.getByText("member@example.com")).toBeInTheDocument();
  });

  it("disables deleting the organization owner", async () => {
    const api = renderPage();
    await screen.findByText("owner@example.com");

    await openRowMenu("owner@example.com");
    const item = await screen.findByTestId("user-action-delete");
    expect(item).toHaveAttribute("aria-disabled", "true");

    fireEvent.click(item);
    expect(screen.queryByTestId("delete-user-dialog")).not.toBeInTheDocument();
    expect(api.calls.some(({ endpoint }) => endpoint === "deleteAdminUser")).toBe(false);
  });

  it("disables deleting your own account", async () => {
    await renderPage();
    await screen.findByText("owner@example.com");

    await openRowMenu("admin@example.com");
    expect(await screen.findByTestId("user-action-delete")).toHaveAttribute("aria-disabled", "true");
  });

  it("keeps the dialog open with the server message when deletion fails", async () => {
    renderPage(
      makeApi({
        deleteAdminUser: () => ({ error: "The organization owner cannot be deleted" }),
      }),
    );
    await screen.findByText("owner@example.com");

    await runAction("member@example.com", "user-action-delete");
    const dialog = await screen.findByTestId("delete-user-dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete" }));

    expect(await within(dialog).findByTestId("delete-error")).toHaveTextContent(
      "The organization owner cannot be deleted",
    );
    expect(screen.getByTestId("delete-user-dialog")).toBeInTheDocument();
  });
});

describe("UsersPage group assignment", () => {
  it("loads current groups, saves the new selection and shows it in the table", async () => {
    const api = renderPage();
    await screen.findByText("owner@example.com");

    await runAction("admin@example.com", "user-action-assign-groups");

    const getCall = api.calls.find(({ endpoint }) => endpoint === "adminUserGroups");
    expect(getCall.options.params).toEqual({ pk: 2 });

    const dialog = await screen.findByTestId("user-groups-modal");
    await waitFor(() => expect(within(dialog).getByTestId("group-option-1")).toBeChecked());
    expect(within(dialog).getByTestId("group-option-2")).not.toBeChecked();

    fireEvent.click(within(dialog).getByTestId("group-option-2"));
    fireEvent.click(within(dialog).getByTestId("save-groups-button"));

    await waitFor(() => {
      const call = api.calls.find(({ endpoint }) => endpoint === "updateAdminUserGroups");
      expect(call.options.params).toEqual({ pk: 2 });
      expect(call.options.body).toEqual({ groups: [1, 2] });
    });
    expect(await screen.findByText("Annotators, Reviewers")).toBeInTheDocument();
  });

  it("falls back to the last known assignment when the refresh call fails", async () => {
    renderPage(
      makeApi({
        adminUserGroups: () => ({ error: "Could not load groups" }),
      }),
    );
    await screen.findByText("owner@example.com");

    await runAction("admin@example.com", "user-action-assign-groups");

    const dialog = await screen.findByTestId("user-groups-modal");
    expect(await within(dialog).findByTestId("groups-error")).toHaveTextContent("Could not refresh the current groups");
    expect(within(dialog).getByTestId("group-option-1")).toBeChecked();
  });
});

describe("UsersPage admin-context assumption", () => {
  // The non-admin gate lives in AdminLayout (see AdminPage.test.jsx): a
  // non-admin never reaches this component, so the page renders its full
  // action set unconditionally and the server re-checks every call.
  it("renders the admin action set for the admin session it assumes", async () => {
    renderPage();
    await screen.findByText("owner@example.com");

    expect(screen.getByTestId("create-user-button")).toBeInTheDocument();
    expect(screen.getByLabelText("Options for member@example.com")).toBeInTheDocument();
  });
});
