import type { APIUser } from "@humansignal/core/types/user";

export type AdminUser = Pick<
  APIUser,
  "id" | "email" | "username" | "first_name" | "last_name" | "date_joined" | "last_activity" | "is_admin"
> & {
  is_active: boolean;
  groups: Array<{ id: number; name: string }>;
};

export type UserGroup = {
  id: number;
  organization: number;
  name: string;
  description: string;
  created_by: number | null;
  created_at: string;
  updated_at: string;
};

export type GroupMember = {
  id: number;
  group: number;
  user: number;
  user_email: string;
  user_name: string;
  created_at: string;
};

export type GroupProject = {
  id: number;
  group: number;
  project: number;
  project_title: string;
  created_at: string;
};
