export type WorkType = "remote" | "hybrid" | "onsite";
export type InternshipStatus = "open" | "closing_soon" | "expired" | "unverified";

export interface Internship {
  id: number;
  title: string;
  company: string;
  company_website?: string | null;
  description?: string | null;
  skills: string[];
  eligibility?: string | null;
  grad_years: number[];
  location?: string | null;
  city?: string | null;
  work_type?: WorkType | null;
  stipend_text?: string | null;
  stipend_min?: number | null;
  stipend_max?: number | null;
  duration_text?: string | null;
  duration_months?: number | null;
  deadline?: string | null;
  application_url: string;
  source_url?: string | null;
  source_name: string;
  status: InternshipStatus;
  status_basis: string;
  link_ok?: boolean | null;
  validation_status: string;
  collected_at?: string;
  updated_at?: string;
  view_count?: number;
  apply_click_count?: number;
}

export interface InternshipPage {
  total: number;
  limit: number;
  offset: number;
  items: Internship[];
}

export interface Recommendation {
  internship: Internship;
  score: number;
  matched_skills: string[];
  missing_skills: string[];
  eligible: boolean;
  reasons: string[];
  resume_boost: boolean;
}

export interface RecommendationPage {
  total: number;
  items: Recommendation[];
  notes: string[];
}

export interface SavedInternship {
  saved_at: string;
  notes?: string | null;
  internship: Internship;
}

export interface Activity {
  id: number;
  internship_id: number;
  action: "viewed" | "apply_clicked" | "bookmarked" | "unbookmarked";
  detail?: string | null;
  timestamp: string;
  internship?: Internship | null;
}

export interface ActivityPage {
  total: number;
  items: Activity[];
}

export interface User {
  id: number;
  full_name?: string | null;
  email: string;
  gender?: string | null;
  location?: string | null;
  college?: string | null;
  mobile?: string | null;
  linkedin_url?: string | null;
  github_url?: string | null;
  portfolio_url?: string | null;
  bio?: string | null;
  profile_photo?: string | null;
  skills: string[];
  specializations: string[];
  desired_roles: string[];
  work_types: string[];
  graduation_year?: number | null;
  degree?: string | null;
  branch?: string | null;
  cgpa?: number | null;
  resume_skills: string[];
  resume_path?: string | null;
  resume_filename?: string | null;
  resume_content_type?: string | null;
  resume_size_bytes?: number | null;
  resume_uploaded_at?: string | null;
  is_admin?: boolean;
  email_verified: boolean;
  is_active: boolean;
  is_onboarded: boolean;
  notify_new_matches: boolean;
  notify_deadline: boolean;
  created_at: string;
}

export interface PublicUser {
  id: number;
  full_name?: string | null;
  college?: string | null;
  location?: string | null;
  skills: string[];
  desired_roles: string[];
  degree?: string | null;
  branch?: string | null;
  graduation_year?: number | null;
  linkedin_url?: string | null;
  github_url?: string | null;
  bio?: string | null;
}

export interface Connection {
  id: number;
  requester_id: number;
  addressee_id: number;
  status: "pending" | "accepted" | "rejected" | "blocked";
  message?: string | null;
  created_at: string;
  other_user?: PublicUser | null;
}

export interface StatsResponse {
  internships: Record<string, number>;
  total_open: number;
  sources: Record<string, {
    status: string;
    finished_at?: string;
    error?: string;
    fetched: number;
    created: number;
  }>;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  user_id: number;
  is_onboarded: boolean;
  is_admin?: boolean;
}

export interface AdminUserListItem {
  id: number;
  full_name: string | null;
  email: string | null;
  college: string | null;
  degree: string | null;
  graduation_year: number | null;
  location: string | null;
  skills: string[];
  desired_roles: string[];
  work_types: string[];
  is_admin: boolean;
  is_active: boolean;
  is_onboarded: boolean;
  has_resume: boolean;
  resume_filename: string | null;
  resume_size_bytes: number | null;
  resume_uploaded_at: string | null;
  missing_fields: string[];
  created_at: string;
  updated_at: string;
  last_login: string | null;
}

export interface AdminUserDetail extends AdminUserListItem {
  mobile: string | null;
  gender: string | null;
  branch: string | null;
  cgpa: number | null;
  bio: string | null;
  linkedin_url: string | null;
  github_url: string | null;
  portfolio_url: string | null;
  resume_content_type: string | null;
  resume_skills: string[];
  email_verified: boolean;
  saved_count: number;
  activity_count: number;
  connections_count: number;
}

export interface AdminUserPage {
  total: number;
  limit: number;
  offset: number;
  items: AdminUserListItem[];
}
