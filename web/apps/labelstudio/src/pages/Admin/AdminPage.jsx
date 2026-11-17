import { useEffect } from "react";
import { useHistory } from "react-router";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { SidebarMenu } from "../../components/SidebarMenu/SidebarMenu";
import { GroupsPage } from "./GroupsPage";
import { UsersPage } from "./UsersPage";

// Sub-paths are mounted by their own pages (T12: /admin/users, T13: /admin/groups).
// The layout gates every route under /admin, so the entries can ship before the pages do.
const menuItems = [
  { title: "Users", path: "/users" },
  { title: "Groups", path: "/groups" },
];

export const AdminLayout = ({ children, ...routeProps }) => {
  const { user, isLoading } = useAuth();
  const history = useHistory();
  const isAdmin = user?.is_admin === true;

  useEffect(() => {
    if (!isLoading && !isAdmin) {
      history.replace("/");
    }
  }, [isLoading, isAdmin, history]);

  // Render nothing while the session is unknown and for every non-admin:
  // the shell never flashes before the redirect lands. Data access stays
  // gated server-side by the admin API permissions.
  if (isLoading || !isAdmin) return null;

  return <SidebarMenu menuItems={menuItems} path={routeProps.match.url} children={children} />;
};

export const AdminPage = {
  title: "Admin",
  path: "/admin",
  exact: true,
  layout: AdminLayout,
  pages: { UsersPage, GroupsPage },
};
