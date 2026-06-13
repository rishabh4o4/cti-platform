export type RiskLabel = "low" | "medium" | "high" | "critical";

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export type Role = "admin" | "analyst" | "viewer";

export interface User {
  id: string;
  username: string;
  email: string;
  role: string;
}

export interface AuthUser {
  id: string;
  username: string;
  role: Role;
  is_active: boolean;
  last_login?: string | null;
}

export enum Permission {
  VIEW_ALL = "view_all",
  INVESTIGATE = "investigate",
  ACKNOWLEDGE_ALERTS = "acknowledge_alerts",
  ADD_NOTES = "add_notes",
  EXPORT_PDF = "export_pdf",
  INGEST_CONTENT = "ingest_content",
  TRIGGER_COLLECTION = "trigger_collection",
  MANAGE_USERS = "manage_users",
}
