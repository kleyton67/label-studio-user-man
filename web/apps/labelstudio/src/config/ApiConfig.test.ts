import type { APIUser } from "@humansignal/core/types/user";
import { API_CONFIG } from "./ApiConfig";

const ADMIN_ENDPOINTS: Record<string, string> = {
  adminUsers: "/admin/users",
  adminUser: "/admin/users/:pk",
  createAdminUser: "POST:/admin/users",
  updateAdminUser: "PATCH:/admin/users/:pk",
  deleteAdminUser: "DELETE:/admin/users/:pk",
  adminUserGroups: "/admin/users/:pk/groups",
  updateAdminUserGroups: "PUT:/admin/users/:pk/groups",
  adminGroups: "/admin/groups",
  adminGroup: "/admin/groups/:pk",
  createAdminGroup: "POST:/admin/groups",
  updateAdminGroup: "PATCH:/admin/groups/:pk",
  deleteAdminGroup: "DELETE:/admin/groups/:pk",
  adminGroupMembers: "/admin/groups/:pk/members",
  addAdminGroupMember: "POST:/admin/groups/:pk/members",
  deleteAdminGroupMember: "DELETE:/admin/groups/:pk/members/:userPk",
  adminGroupProjects: "/admin/groups/:pk/projects",
  addAdminGroupProject: "POST:/admin/groups/:pk/projects",
  deleteAdminGroupProject: "DELETE:/admin/groups/:pk/projects/:projectPk",
};

const ENDPOINTS: Record<string, string> = API_CONFIG.endpoints;

describe("API_CONFIG admin endpoints", () => {
  it("registers all 18 admin endpoint keys", () => {
    const missing = Object.keys(ADMIN_ENDPOINTS).filter((key) => !(key in ENDPOINTS));
    expect(missing).toEqual([]);
    expect(Object.keys(ADMIN_ENDPOINTS)).toHaveLength(18);
  });

  for (const [key, value] of Object.entries(ADMIN_ENDPOINTS)) {
    it(`endpoints.${key} resolves to ${value}`, () => {
      expect(ENDPOINTS[key]).toBe(value);
    });
  }

  it("keeps adminUsers on the API gateway prefix", () => {
    expect(API_CONFIG.gateway.endsWith("/api")).toBe(true);
    expect(`${API_CONFIG.gateway}${ENDPOINTS.adminUsers}`).toBe(`${API_CONFIG.gateway}/admin/users`);
  });
});

// Type-level gate only: bun strips types here, so `tsc -p apps/labelstudio/tsconfig.spec.json`
// is what fails when `APIUser.is_admin` is removed or stops being a boolean.
type ApiUserIsAdmin = Pick<APIUser, "is_admin">["is_admin"];
const apiUserHasIsAdmin: ApiUserIsAdmin = true;
void apiUserHasIsAdmin;
