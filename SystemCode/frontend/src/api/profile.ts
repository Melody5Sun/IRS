import { apiRequest } from "./client";
import type { UserProfile } from "../types/api";

export const profileApi = {
  getOptions: () => apiRequest<{ target_role_categories: Record<string, string[]>; target_industries: string[] }>("/profile/options"),
  get: () => apiRequest<UserProfile>("/profile"),
  save: (profile: UserProfile) => apiRequest<UserProfile>("/profile", { method: "PUT", body: JSON.stringify(profile) }),
  patch: (updates: Partial<UserProfile>) => apiRequest<UserProfile>("/profile", { method: "PATCH", body: JSON.stringify(updates) }),
};
