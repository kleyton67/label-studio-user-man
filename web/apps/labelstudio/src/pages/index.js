import { ProjectsPage } from "./Projects/Projects";
import { HomePage } from "./Home/HomePage";
import { OrganizationPage } from "./Organization";
import { ModelsPage } from "./Organization/Models/ModelsPage";
import { AdminPage } from "./Admin";
import { pages } from "@humansignal/app-common";

export const Pages = [
  HomePage,
  ProjectsPage,
  OrganizationPage,
  ModelsPage,
  AdminPage,
  pages.AccountSettingsPage,
].filter(Boolean);
