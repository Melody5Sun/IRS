import { apiRequest } from "./client";
import type { ProfileOptions, SavedProfile, UserProfile } from "../types/api";

export const profileApi = {
  getOptions: () => apiRequest<ProfileOptions>("/profile/options"),
  get: () => apiRequest<SavedProfile>("/profile"),
  save: (profile: UserProfile) => apiRequest<SavedProfile>("/profile", { method: "PUT", body: JSON.stringify(profile) }),
  patch: (updates: Partial<UserProfile>) => apiRequest<SavedProfile>("/profile", { method: "PATCH", body: JSON.stringify(updates) }),
};
