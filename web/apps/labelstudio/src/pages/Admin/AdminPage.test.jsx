import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route } from "react-router-dom";
import * as authProvider from "@humansignal/core/providers/AuthProvider";
import { AdminLayout, AdminPage } from "./AdminPage";

let useAuthSpy = null;

// MenuItem reads the bare `location` global for active-state checks; bun's
// --dom exposes window.location but not the implicit global binding.
if (typeof globalThis.location === "undefined") {
  Object.defineProperty(globalThis, "location", { value: window.location, configurable: true });
}

function mockAuth(authState) {
  useAuthSpy = spyOn(authProvider, "useAuth").mockImplementation(() => authState);
}

afterEach(() => {
  useAuthSpy?.mockRestore();
  useAuthSpy = null;
});

// Mirrors how RoutesProvider mounts the page set: the layout wraps every
// /admin path and a static fallback owns "/".
function renderAdminShell() {
  return render(
    <MemoryRouter initialEntries={["/admin"]}>
      <Route exact path="/admin" render={(props) => <AdminLayout {...props}>admin child content</AdminLayout>} />
      <Route exact path="/" render={() => <div>Home page</div>} />
    </MemoryRouter>,
  );
}

describe("AdminPage page set", () => {
  it("registers the /admin route with the gated layout", () => {
    expect(AdminPage.path).toBe("/admin");
    expect(AdminPage.title).toBe("Admin");
    expect(AdminPage.layout).toBe(AdminLayout);
  });
});

describe("AdminLayout gate", () => {
  it("renders the shell with Users and Groups entries for an admin", () => {
    mockAuth({ user: { id: 1, is_admin: true }, isLoading: false });

    renderAdminShell();

    expect(screen.getByText("Users")).toBeInTheDocument();
    expect(screen.getByText("Groups")).toBeInTheDocument();
    expect(screen.getByText("admin child content")).toBeInTheDocument();
    expect(screen.queryByText("Home page")).not.toBeInTheDocument();
  });

  it("points the sidebar entries at /admin/users and /admin/groups", () => {
    mockAuth({ user: { id: 1, is_admin: true }, isLoading: false });

    renderAdminShell();

    expect(screen.getByText("Users").closest("a")).toHaveAttribute("href", "/admin/users");
    expect(screen.getByText("Groups").closest("a")).toHaveAttribute("href", "/admin/groups");
  });

  it("renders nothing and redirects home for a non-admin", () => {
    mockAuth({ user: { id: 2, is_admin: false }, isLoading: false });

    renderAdminShell();

    // Effects are flushed by act() around render: the shell never appears,
    // not even before the redirect settles.
    expect(screen.queryByText("Users")).not.toBeInTheDocument();
    expect(screen.queryByText("Groups")).not.toBeInTheDocument();
    expect(screen.queryByText("admin child content")).not.toBeInTheDocument();

    return waitFor(() => expect(screen.getByText("Home page")).toBeInTheDocument());
  });

  it("renders nothing and redirects home when there is no authenticated user", () => {
    mockAuth({ user: null, isLoading: false });

    renderAdminShell();

    expect(screen.queryByText("Users")).not.toBeInTheDocument();

    return waitFor(() => expect(screen.getByText("Home page")).toBeInTheDocument());
  });

  it("waits for the session without flashing the shell or redirecting while loading", () => {
    mockAuth({ user: null, isLoading: true });

    renderAdminShell();

    // useAuth resolves before effects run, so a premature redirect would
    // already be visible here.
    expect(screen.queryByText("Users")).not.toBeInTheDocument();
    expect(screen.queryByText("Home page")).not.toBeInTheDocument();
  });
});
