import {
  AuthTokens,
  Connection,
  Internship,
  InternshipPage,
  PublicUser,
  RecommendationPage,
  SavedInternship,
  ActivityPage,
  AdminUserDetail,
  AdminUserListItem,
  AdminUserPage,
  StatsResponse,
  User,
  WorkType,
} from "../types";

const API_BASE = "";

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

// Token management in localStorage
export function getAccessToken(): string | null {
  return localStorage.getItem("ir_access_token");
}

export function getRefreshToken(): string | null {
  return localStorage.getItem("ir_refresh_token");
}

export function setTokens(tokens: AuthTokens): void {
  localStorage.setItem("ir_access_token", tokens.access_token);
  localStorage.setItem("ir_refresh_token", tokens.refresh_token);
  localStorage.setItem("ir_user_id", String(tokens.user_id));
}

export function clearTokens(): void {
  localStorage.removeItem("ir_access_token");
  localStorage.removeItem("ir_refresh_token");
  localStorage.removeItem("ir_user_id");
}

let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

function onRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const token = getAccessToken();

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (token && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // Set default JSON Content-Type unless body is FormData
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  // Handle 401 and try refresh
  if (response.status === 401 && retry) {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      if (!isRefreshing) {
        isRefreshing = true;
        try {
          const res = await fetch(`${API_BASE}/api/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: refreshToken }),
          });
          if (res.ok) {
            const data: AuthTokens = await res.json();
            setTokens(data);
            isRefreshing = false;
            onRefreshed(data.access_token);
            return request<T>(endpoint, options, false);
          } else {
            clearTokens();
            isRefreshing = false;
          }
        } catch {
          clearTokens();
          isRefreshing = false;
        }
      } else {
        return new Promise<T>((resolve) => {
          refreshSubscribers.push((newToken) => {
            headers["Authorization"] = `Bearer ${newToken}`;
            resolve(request<T>(endpoint, { ...options, headers }, false));
          });
        });
      }
    }
  }

  if (response.status === 204) {
    return {} as T;
  }

  let data: any = null;
  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    let msg = `HTTP ${response.status}`;
    if (typeof data === "string") {
      msg = data;
    } else if (data?.detail) {
      if (typeof data.detail === "string") {
        msg = data.detail;
      } else if (Array.isArray(data.detail)) {
        msg = data.detail.map((e: any) => e.msg || e).join(", ");
      } else if (typeof data.detail === "object") {
        msg = Object.values(data.detail).join("; ");
      }
    }
    throw new ApiError(response.status, msg, data);
  }

  return data as T;
}

export async function downloadBlobWithAuth(
  endpoint: string,
  defaultFilename = "resume.pdf",
  openInNewTab = false
): Promise<void> {
  const token = getAccessToken();
  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    let msg = "Failed to download file";
    try {
      const j = await res.json();
      msg = j.detail || msg;
    } catch {}
    throw new ApiError(res.status, msg);
  }
  const disposition = res.headers.get("Content-Disposition");
  let filename = defaultFilename;
  if (disposition) {
    const match = disposition.match(/filename="?([^";]+)"?/i);
    if (match && match[1]) filename = match[1];
  }
  const blob = await res.blob();
  const blobUrl = URL.createObjectURL(blob);
  if (openInNewTab) {
    window.open(blobUrl, "_blank");
  } else {
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }
  setTimeout(() => URL.revokeObjectURL(blobUrl), 10000);
}

export const api = {
  // ── Authentication ──────────────────────────────────────────────────────────
  auth: {
    register: (body: { email: string; full_name?: string; password: string; confirm_password: string }) =>
      request<AuthTokens>("/api/auth/register", {
        method: "POST",
        body: JSON.stringify(body),
      }),

    login: (body: { email: string; password: string }) =>
      request<AuthTokens>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify(body),
      }),

    logout: () => {
      const refreshToken = getRefreshToken();
      clearTokens();
      if (refreshToken) {
        return request<void>("/api/auth/logout", {
          method: "POST",
          body: JSON.stringify({ refresh_token: refreshToken }),
        }).catch(() => {});
      }
      return Promise.resolve();
    },

    changePassword: (body: { current_password: string; new_password: string }) =>
      request<{ detail: string }>("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },

  // ── Internships ─────────────────────────────────────────────────────────────
  internships: {
    search: (params: {
      q?: string;
      skills?: string;
      skills_match?: "any" | "all";
      location?: string;
      work_type?: WorkType;
      min_stipend?: number;
      company?: string;
      status?: string;
      include_expired?: boolean;
      sort?: "newest" | "deadline" | "stipend";
      limit?: number;
      offset?: number;
    }) => {
      const sp = new URLSearchParams();
      if (params.q) sp.set("q", params.q);
      if (params.skills) sp.set("skills", params.skills);
      if (params.skills_match) sp.set("skills_match", params.skills_match);
      if (params.location) sp.set("location", params.location);
      if (params.work_type) sp.set("work_type", params.work_type);
      if (params.min_stipend != null) sp.set("min_stipend", String(params.min_stipend));
      if (params.company) sp.set("company", params.company);
      if (params.status) sp.set("status", params.status);
      if (params.include_expired) sp.set("include_expired", "true");
      if (params.sort) sp.set("sort", params.sort);
      sp.set("limit", String(params.limit ?? 20));
      sp.set("offset", String(params.offset ?? 0));
      return request<InternshipPage>(`/api/internships?${sp.toString()}`);
    },

    getById: (id: number) => request<Internship>(`/api/internships/${id}`),
    refresh: () => request<{ message: string }>("/api/internships/refresh", { method: "POST" }),
  },

  // ── Recommendations (Matches) ───────────────────────────────────────────────
  recommendations: {
    get: (params: {
      limit?: number;
      offset?: number;
      min_score?: number;
      include_ineligible?: boolean;
      work_type?: string;
      location?: string;
    } = {}) => {
      const sp = new URLSearchParams();
      if (params.limit != null) sp.set("limit", String(params.limit));
      if (params.offset != null) sp.set("offset", String(params.offset));
      if (params.min_score != null) sp.set("min_score", String(params.min_score));
      if (params.include_ineligible) sp.set("include_ineligible", "true");
      if (params.work_type) sp.set("work_type", params.work_type);
      if (params.location) sp.set("location", params.location);
      return request<RecommendationPage>(`/api/recommendations?${sp.toString()}`);
    },
  },

  // ── Saved / Bookmarks ───────────────────────────────────────────────────────
  saved: {
    list: () => request<SavedInternship[]>("/api/saved"),
    save: (internshipId: number, notes?: string) =>
      request<void>(`/api/saved/${internshipId}${notes ? `?notes=${encodeURIComponent(notes)}` : ""}`, {
        method: "PUT",
      }),
    unsave: (internshipId: number) =>
      request<void>(`/api/saved/${internshipId}`, {
        method: "DELETE",
      }),
  },

  // ── Activity Tracking ───────────────────────────────────────────────────────
  activity: {
    trackView: (internshipId: number) =>
      request<void>(`/api/activity/view/${internshipId}`, { method: "POST" }),
    trackApply: (internshipId: number) =>
      request<void>(`/api/activity/apply/${internshipId}`, { method: "POST" }),
    list: (params: { action?: string; limit?: number; offset?: number } = {}) => {
      const sp = new URLSearchParams();
      if (params.action) sp.set("action", params.action);
      if (params.limit) sp.set("limit", String(params.limit));
      if (params.offset) sp.set("offset", String(params.offset));
      return request<ActivityPage>(`/api/activity?${sp.toString()}`);
    },
    getApplied: (limit = 50, offset = 0) =>
      request<ActivityPage>(`/api/activity/applied?limit=${limit}&offset=${offset}`),
  },

  // ── User Profile & Resume ───────────────────────────────────────────────────
  profile: {
    get: () => request<User>("/api/profile"),
    update: (data: Partial<User>) =>
      request<User>("/api/profile", {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    uploadResume: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return request<User>("/api/profile/resume", {
        method: "POST",
        body: fd,
      });
    },
    downloadResume: (download = false) => {
      return downloadBlobWithAuth(`/api/profile/resume?download=${download}`, "resume.pdf", !download);
    },
    deleteResume: () =>
      request<User>("/api/profile/resume", {
        method: "DELETE",
      }),
    uploadPhoto: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return request<User>("/api/profile/photo", {
        method: "POST",
        body: fd,
      });
    },
  },

  // ── Metadata & Suggestions ──────────────────────────────────────────────────
  meta: {
    skills: (q = "", limit = 20) =>
      request<string[]>(`/api/meta/skills?q=${encodeURIComponent(q)}&limit=${limit}`),
    locations: (q = "", limit = 15) =>
      request<string[]>(`/api/meta/locations?q=${encodeURIComponent(q)}&limit=${limit}`),
    roles: (q = "", limit = 20) =>
      request<string[]>(`/api/meta/roles?q=${encodeURIComponent(q)}&limit=${limit}`),
    specializations: (q = "", limit = 20) =>
      request<string[]>(`/api/meta/specializations?q=${encodeURIComponent(q)}&limit=${limit}`),
    allRoles: () => request<string[]>("/api/meta/all-roles"),
    allSpecializations: () => request<string[]>("/api/meta/all-specializations"),
    stats: () => request<StatsResponse>("/api/stats"),
  },

  // ── Peer Networking & Connections ───────────────────────────────────────────
  network: {
    searchStudents: (params: { q?: string; skills?: string; location?: string; limit?: number; offset?: number } = {}) => {
      const sp = new URLSearchParams();
      if (params.q) sp.set("q", params.q);
      if (params.skills) sp.set("skills", params.skills);
      if (params.location) sp.set("location", params.location);
      if (params.limit) sp.set("limit", String(params.limit));
      if (params.offset) sp.set("offset", String(params.offset));
      return request<PublicUser[]>(`/api/users?${sp.toString()}`);
    },
    getUser: (userId: number) => request<PublicUser>(`/api/users/${userId}`),
    listConnections: (status?: string) =>
      request<Connection[]>(`/api/connections${status ? `?status=${status}` : ""}`),
    sendRequest: (addresseeId: number, message?: string) =>
      request<Connection>("/api/connections", {
        method: "POST",
        body: JSON.stringify({ addressee_id: addresseeId, message }),
      }),
    respondRequest: (connectionId: number, action: "accept" | "reject" | "block") =>
      request<Connection>(`/api/connections/${connectionId}?action=${action}`, {
        method: "PUT",
      }),
    removeConnection: (connectionId: number) =>
      request<void>(`/api/connections/${connectionId}`, {
        method: "DELETE",
      }),
  },

  // ── Private Administrator Management ────────────────────────────────────────
  admin: {
    users: {
      list: (params: {
        q?: string;
        skills?: string;
        grad_year?: number;
        completion?: string;
        resume?: string;
        limit?: number;
        offset?: number;
      } = {}) => {
        const sp = new URLSearchParams();
        if (params.q) sp.set("q", params.q);
        if (params.skills) sp.set("skills", params.skills);
        if (params.grad_year != null) sp.set("grad_year", String(params.grad_year));
        if (params.completion) sp.set("completion", params.completion);
        if (params.resume) sp.set("resume", params.resume);
        if (params.limit != null) sp.set("limit", String(params.limit));
        if (params.offset != null) sp.set("offset", String(params.offset));
        return request<AdminUserPage>(`/api/admin/users?${sp.toString()}`);
      },
      getById: (userId: number) => request<AdminUserDetail>(`/api/admin/users/${userId}`),
      downloadResume: (userId: number, download = false) => {
        return downloadBlobWithAuth(`/api/admin/users/${userId}/resume?download=${download}`, `resume_${userId}.pdf`, !download);
      },
    },
  },
};
