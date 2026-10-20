import React, { useState, useEffect } from "react";
import {
  Shield,
  Search,
  Filter,
  CheckCircle2,
  AlertCircle,
  FileText,
  Eye,
  Download,
  Calendar,
  GraduationCap,
  Briefcase,
  MapPin,
  Mail,
  Phone,
  Globe,
  ChevronLeft,
  ChevronRight,
  UserCheck,
  UserX,
  X,
  ExternalLink,
  HardDrive,
  RefreshCw,
  Lock,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { api } from "../lib/api";
import { AdminUserDetail, AdminUserListItem, AdminUserPage } from "../types";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";

export const AdminUsersPage: React.FC = () => {
  const { user, isAdmin, loading: authLoading } = useAuth();
  const { error: toastError, success: toastSuccess } = useToast();

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<AdminUserPage>({
    total: 0,
    limit: 20,
    offset: 0,
    items: [],
  });

  // Filters & search
  const [query, setQuery] = useState("");
  const [skillFilter, setSkillFilter] = useState("");
  const [gradYearFilter, setGradYearFilter] = useState<number | "">("");
  const [completionFilter, setCompletionFilter] = useState<string>("all");
  const [resumeFilter, setResumeFilter] = useState<string>("all");
  const [pageOffset, setPageOffset] = useState(0);
  const limit = 20;

  // Selected user for inspection drawer/modal
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [selectedUserDetail, setSelectedUserDetail] = useState<AdminUserDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [downloadingResume, setDownloadingResume] = useState(false);

  // Set noindex robots tag for administrative privacy
  useEffect(() => {
    let metaTag = document.querySelector('meta[name="robots"]');
    if (!metaTag) {
      metaTag = document.createElement("meta");
      metaTag.setAttribute("name", "robots");
      document.head.appendChild(metaTag);
    }
    metaTag.setAttribute("content", "noindex, nofollow");

    return () => {
      metaTag?.setAttribute("content", "index, follow");
    };
  }, []);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const res = await api.admin.users.list({
        q: query.trim() || undefined,
        skills: skillFilter.trim() || undefined,
        grad_year: gradYearFilter !== "" ? Number(gradYearFilter) : undefined,
        completion: completionFilter !== "all" ? completionFilter : undefined,
        resume: resumeFilter !== "all" ? resumeFilter : undefined,
        limit,
        offset: pageOffset,
      });
      setData(res);
    } catch (err: any) {
      toastError("Failed to Load Users", err.message || "Admin authorization required.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAdmin) {
      fetchUsers();
    }
  }, [isAdmin, pageOffset, completionFilter, resumeFilter, gradYearFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPageOffset(0);
    fetchUsers();
  };

  const handleInspectUser = async (userId: number) => {
    setSelectedUserId(userId);
    setLoadingDetail(true);
    try {
      const detail = await api.admin.users.getById(userId);
      setSelectedUserDetail(detail);
    } catch (err: any) {
      toastError("Inspection Error", err.message || "Failed to load detailed profile.");
      setSelectedUserId(null);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleDownloadResume = async (userId: number, download = false) => {
    setDownloadingResume(true);
    try {
      await api.admin.users.downloadResume(userId, download);
      if (download) {
        toastSuccess("Download Started", "Resume file download triggered.");
      }
    } catch (err: any) {
      toastError("Resume Access Failed", err.message || "Unable to download resume file.");
    } finally {
      setDownloadingResume(false);
    }
  };

  const formatFileSize = (bytes?: number | null) => {
    if (!bytes) return "";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  const formatDate = (dateStr?: string | null) => {
    if (!dateStr) return "—";
    try {
      return new Date(dateStr).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
      });
    } catch {
      return dateStr;
    }
  };

  // Guard: Not an administrator
  if (!authLoading && !isAdmin) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-16 text-center space-y-4">
        <div className="h-16 w-16 mx-auto rounded-full bg-rose-50 text-rose-600 flex items-center justify-center">
          <Lock className="h-8 w-8" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900">403 Forbidden — Administrator Access Only</h1>
        <p className="text-sm text-slate-600 max-w-md mx-auto leading-relaxed">
          The user-management dashboard is restricted to authorized platform administrators. Your current account does not have administrative privileges.
        </p>
      </div>
    );
  }

  const currentPage = Math.floor(pageOffset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(data.total / limit));

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-indigo-100 text-indigo-800 uppercase tracking-wider">
              Private Admin Portal
            </span>
            <span className="text-xs text-slate-400">• Authenticated as {user?.email}</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 mt-1 flex items-center gap-2">
            <Shield className="h-6 w-6 text-indigo-600" />
            User Profile & Resume Management
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
            Audit registered student profiles, verify mandatory educational details, and securely access resumes.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={fetchUsers}
          loading={loading}
          className="text-xs h-8.5 shrink-0"
        >
          <RefreshCw className="h-3.5 w-3.5 mr-1.5" /> Refresh List
        </Button>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-4 rounded-lg bg-white border border-slate-200 shadow-xs space-y-3">
        <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {/* Query search */}
          <div className="lg:col-span-2 relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <Input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by name, email, or college..."
              className="pl-9 h-9 text-xs"
            />
          </div>

          {/* Skill filter */}
          <div>
            <Input
              type="text"
              value={skillFilter}
              onChange={(e) => setSkillFilter(e.target.value)}
              placeholder="Filter by skill (e.g. React)..."
              className="h-9 text-xs"
            />
          </div>

          {/* Grad Year filter */}
          <div>
            <Input
              type="number"
              value={gradYearFilter}
              onChange={(e) => setGradYearFilter(e.target.value ? Number(e.target.value) : "")}
              placeholder="Graduation Year..."
              className="h-9 text-xs"
              min={2020}
              max={2035}
            />
          </div>

          {/* Search Button */}
          <div>
            <Button type="submit" loading={loading} className="w-full h-9 text-xs">
              <Search className="h-3.5 w-3.5 mr-1.5" /> Apply Filters
            </Button>
          </div>
        </form>

        {/* Quick Filter Selectors */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-100 text-xs">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-1.5">
              <span className="text-slate-500 font-medium">Completeness:</span>
              <select
                value={completionFilter}
                onChange={(e) => {
                  setCompletionFilter(e.target.value);
                  setPageOffset(0);
                }}
                className="h-7 rounded border border-slate-300 bg-white px-2 text-xs text-slate-700"
              >
                <option value="all">All Profiles</option>
                <option value="complete">Complete (8/8 Required)</option>
                <option value="incomplete">Incomplete / Missing Fields</option>
              </select>
            </div>

            <div className="flex items-center gap-1.5">
              <span className="text-slate-500 font-medium">Resume:</span>
              <select
                value={resumeFilter}
                onChange={(e) => {
                  setResumeFilter(e.target.value);
                  setPageOffset(0);
                }}
                className="h-7 rounded border border-slate-300 bg-white px-2 text-xs text-slate-700"
              >
                <option value="all">All</option>
                <option value="with_resume">Has Uploaded Resume</option>
                <option value="without_resume">No Resume</option>
              </select>
            </div>
          </div>

          <div className="text-slate-500">
            Showing <strong className="text-slate-900">{data.items.length}</strong> of{" "}
            <strong className="text-slate-900">{data.total}</strong> total users
          </div>
        </div>
      </div>

      {/* User Records Table */}
      <div className="bg-white border border-slate-200 rounded-lg shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-slate-600 font-semibold">
                <th className="py-3 px-4">User Details</th>
                <th className="py-3 px-4">Academic Background</th>
                <th className="py-3 px-4">Skills & Roles</th>
                <th className="py-3 px-4">Status & Mandatory Fields</th>
                <th className="py-3 px-4">Resume</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {loading && data.items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-400">
                    <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2 text-indigo-600" />
                    Loading user records...
                  </td>
                </tr>
              ) : data.items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-500">
                    No registered users matched the active filters.
                  </td>
                </tr>
              ) : (
                data.items.map((u) => {
                  const isComplete = u.missing_fields.length === 0;
                  return (
                    <tr key={u.id} className="hover:bg-slate-50/80 transition-colors">
                      {/* Name & Email */}
                      <td className="py-3 px-4">
                        <div className="font-semibold text-slate-900 flex items-center gap-1.5">
                          {u.full_name || <span className="text-slate-400 italic">No name provided</span>}
                          {u.is_admin && (
                            <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-indigo-100 text-indigo-700">
                              ADMIN
                            </span>
                          )}
                        </div>
                        <div className="text-slate-500 flex items-center gap-1 mt-0.5">
                          <Mail className="h-3 w-3 text-slate-400" />
                          {u.email}
                        </div>
                        <div className="text-[11px] text-slate-400 mt-0.5">
                          Registered: {formatDate(u.created_at)}
                        </div>
                      </td>

                      {/* College & Degree */}
                      <td className="py-3 px-4">
                        <div className="font-medium text-slate-800">
                          {u.college || <span className="text-amber-600 italic">Missing College</span>}
                        </div>
                        <div className="text-slate-500 text-[11px] mt-0.5">
                          {u.degree || "—"} {u.graduation_year ? `(${u.graduation_year})` : ""}
                        </div>
                        {u.location && (
                          <div className="text-[11px] text-slate-400 flex items-center gap-1 mt-0.5">
                            <MapPin className="h-3 w-3 text-slate-400" />
                            {u.location}
                          </div>
                        )}
                      </td>

                      {/* Skills & Roles */}
                      <td className="py-3 px-4 max-w-xs">
                        <div className="flex flex-wrap gap-1 mb-1">
                          {u.skills.slice(0, 3).map((s) => (
                            <span
                              key={s}
                              className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-50 text-blue-700 border border-blue-100"
                            >
                              {s}
                            </span>
                          ))}
                          {u.skills.length > 3 && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] text-slate-500 bg-slate-100">
                              +{u.skills.length - 3}
                            </span>
                          )}
                        </div>
                        {u.desired_roles.length > 0 && (
                          <div className="text-[11px] text-slate-500 truncate" title={u.desired_roles.join(", ")}>
                            Target: {u.desired_roles[0]}
                            {u.desired_roles.length > 1 && ` (+${u.desired_roles.length - 1})`}
                          </div>
                        )}
                      </td>

                      {/* Profile Status & Missing Fields */}
                      <td className="py-3 px-4">
                        {isComplete ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 className="h-3 w-3" /> Complete (8/8)
                          </span>
                        ) : (
                          <div className="space-y-1">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                              <AlertCircle className="h-3 w-3" /> Incomplete ({8 - u.missing_fields.length}/8)
                            </span>
                            <div className="text-[10px] text-rose-600 leading-tight">
                              Missing: {u.missing_fields.join(", ")}
                            </div>
                          </div>
                        )}
                      </td>

                      {/* Resume Status */}
                      <td className="py-3 px-4">
                        {u.has_resume ? (
                          <div className="space-y-1">
                            <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700">
                              <FileText className="h-3.5 w-3.5 text-emerald-600" />
                              {u.resume_filename || "Uploaded"}
                            </span>
                            <div className="text-[10px] text-slate-400">
                              {formatFileSize(u.resume_size_bytes)} • {formatDate(u.resume_uploaded_at)}
                            </div>
                          </div>
                        ) : (
                          <span className="text-[11px] text-slate-400 italic">No resume</span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {u.has_resume && (
                            <>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleDownloadResume(u.id, false)}
                                className="h-7 px-2 text-[11px]"
                                title="Preview resume in new tab"
                              >
                                <Eye className="h-3 w-3 mr-1 text-slate-500" /> View
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleDownloadResume(u.id, true)}
                                className="h-7 px-2 text-[11px]"
                                title="Download resume file"
                              >
                                <Download className="h-3 w-3 text-slate-500" />
                              </Button>
                            </>
                          )}
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handleInspectUser(u.id)}
                            className="h-7 px-2.5 text-[11px] font-medium"
                          >
                            Inspect
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="px-4 py-3 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-xs text-slate-600">
          <div>
            Page <strong className="text-slate-900">{currentPage}</strong> of{" "}
            <strong className="text-slate-900">{totalPages}</strong>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={pageOffset === 0 || loading}
              onClick={() => setPageOffset(Math.max(0, pageOffset - limit))}
              className="h-7 text-xs px-2"
            >
              <ChevronLeft className="h-3.5 w-3.5 mr-0.5" /> Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={pageOffset + limit >= data.total || loading}
              onClick={() => setPageOffset(pageOffset + limit)}
              className="h-7 text-xs px-2"
            >
              Next <ChevronRight className="h-3.5 w-3.5 ml-0.5" />
            </Button>
          </div>
        </div>
      </div>

      {/* ── Inspection Drawer / Modal ─────────────────────────────────────── */}
      {selectedUserId && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex justify-end">
          <div className="w-full max-w-2xl bg-white h-full shadow-2xl flex flex-col overflow-hidden animate-in slide-in-from-right duration-200">
            {/* Drawer Header */}
            <div className="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <div>
                <span className="text-[11px] font-semibold uppercase tracking-wider text-indigo-700">
                  User Detail Inspection
                </span>
                <h2 className="text-lg font-bold text-slate-900">
                  {selectedUserDetail?.full_name || `User #${selectedUserId}`}
                </h2>
              </div>
              <button
                type="button"
                onClick={() => {
                  setSelectedUserId(null);
                  setSelectedUserDetail(null);
                }}
                className="h-8 w-8 rounded-full hover:bg-slate-200 flex items-center justify-center text-slate-500"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Drawer Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6 text-xs">
              {loadingDetail || !selectedUserDetail ? (
                <div className="py-20 text-center text-slate-400">
                  <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-indigo-600" />
                  Loading comprehensive user profile...
                </div>
              ) : (
                <>
                  {/* Completeness Badge */}
                  <div
                    className={`p-3.5 rounded-lg border ${
                      selectedUserDetail.missing_fields.length === 0
                        ? "bg-emerald-50 border-emerald-200 text-emerald-900"
                        : "bg-amber-50 border-amber-200 text-amber-900"
                    }`}
                  >
                    <div className="flex items-center justify-between font-semibold">
                      <span className="flex items-center gap-1.5">
                        {selectedUserDetail.missing_fields.length === 0 ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                        ) : (
                          <AlertCircle className="h-4 w-4 text-amber-600" />
                        )}
                        Profile Status:{" "}
                        {selectedUserDetail.missing_fields.length === 0
                          ? "Complete (8 of 8 Essential Fields)"
                          : "Incomplete Profile"}
                      </span>
                      <span>ID #{selectedUserDetail.id}</span>
                    </div>
                    {selectedUserDetail.missing_fields.length > 0 && (
                      <p className="text-[11px] mt-1 text-rose-700">
                        Missing mandatory fields: {selectedUserDetail.missing_fields.join(", ")}
                      </p>
                    )}
                  </div>

                  {/* Resume Section */}
                  <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 space-y-3">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-600 flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <FileText className="h-4 w-4 text-indigo-600" /> User Resume Document
                      </span>
                      {selectedUserDetail.has_resume ? (
                        <span className="text-emerald-700 font-bold">Uploaded</span>
                      ) : (
                        <span className="text-slate-400 font-normal">Not Uploaded</span>
                      )}
                    </h3>

                    {selectedUserDetail.has_resume ? (
                      <div className="space-y-3">
                        <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-600">
                          <div>
                            <span className="text-slate-400 block">Filename:</span>
                            <span className="font-medium text-slate-900">
                              {selectedUserDetail.resume_filename || "resume"}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-400 block">Size:</span>
                            <span className="font-medium text-slate-900">
                              {formatFileSize(selectedUserDetail.resume_size_bytes)}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-400 block">Uploaded At:</span>
                            <span className="font-medium text-slate-900">
                              {formatDate(selectedUserDetail.resume_uploaded_at)}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-400 block">Content Type:</span>
                            <span className="font-medium text-slate-900">
                              {selectedUserDetail.resume_content_type || "application/octet-stream"}
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 pt-1">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            loading={downloadingResume}
                            onClick={() => handleDownloadResume(selectedUserDetail.id, false)}
                            className="h-8 text-xs px-3"
                          >
                            <Eye className="h-3.5 w-3.5 mr-1.5 text-slate-600" /> Preview in New Tab
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            loading={downloadingResume}
                            onClick={() => handleDownloadResume(selectedUserDetail.id, true)}
                            className="h-8 text-xs px-3"
                          >
                            <Download className="h-3.5 w-3.5 mr-1.5 text-slate-600" /> Download File
                          </Button>
                        </div>

                        {selectedUserDetail.resume_skills.length > 0 && (
                          <div className="pt-2 border-t border-slate-200">
                            <span className="text-[11px] text-slate-500 block mb-1">
                              Resume Parsed Skills ({selectedUserDetail.resume_skills.length}):
                            </span>
                            <div className="flex flex-wrap gap-1">
                              {selectedUserDetail.resume_skills.map((s) => (
                                <span
                                  key={s}
                                  className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-50 text-emerald-800 border border-emerald-200"
                                >
                                  {s}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="text-[11px] text-slate-500 italic">
                        This user has not uploaded any resume file.
                      </p>
                    )}
                  </div>

                  {/* Personal & Contact Information */}
                  <div className="space-y-2">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                      Personal & Contact Details
                    </h3>
                    <div className="grid grid-cols-2 gap-3 p-3.5 rounded-lg border border-slate-200 bg-white">
                      <div>
                        <span className="text-slate-400 block text-[10px]">Full Name</span>
                        <span className="font-semibold text-slate-900">{selectedUserDetail.full_name || "—"}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Email Address</span>
                        <span className="font-medium text-slate-900">{selectedUserDetail.email || "—"}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Mobile Phone</span>
                        <span className="text-slate-900">{selectedUserDetail.mobile || "—"}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Gender</span>
                        <span className="capitalize text-slate-900">{selectedUserDetail.gender || "—"}</span>
                      </div>
                      <div className="col-span-2">
                        <span className="text-slate-400 block text-[10px]">Location</span>
                        <span className="text-slate-900">{selectedUserDetail.location || "—"}</span>
                      </div>
                      {selectedUserDetail.bio && (
                        <div className="col-span-2">
                          <span className="text-slate-400 block text-[10px]">Biography</span>
                          <p className="text-slate-800 leading-relaxed mt-0.5">{selectedUserDetail.bio}</p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Academic Background */}
                  <div className="space-y-2">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                      Academic Background
                    </h3>
                    <div className="grid grid-cols-2 gap-3 p-3.5 rounded-lg border border-slate-200 bg-white">
                      <div className="col-span-2">
                        <span className="text-slate-400 block text-[10px]">College / University</span>
                        <span className="font-semibold text-slate-900">{selectedUserDetail.college || "—"}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Degree</span>
                        <span className="text-slate-900">{selectedUserDetail.degree || "—"}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Branch / Major</span>
                        <span className="text-slate-900">{selectedUserDetail.branch || "—"}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">Graduation Year</span>
                        <span className="text-slate-900">{selectedUserDetail.graduation_year || "—"}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-[10px]">CGPA / Marks</span>
                        <span className="text-slate-900">
                          {selectedUserDetail.cgpa != null ? selectedUserDetail.cgpa : "—"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Skills & Preferences */}
                  <div className="space-y-2">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                      Skills & Preferences
                    </h3>
                    <div className="p-3.5 rounded-lg border border-slate-200 bg-white space-y-3">
                      <div>
                        <span className="text-slate-400 block text-[10px] mb-1">
                          Profile Skills ({selectedUserDetail.skills.length})
                        </span>
                        <div className="flex flex-wrap gap-1">
                          {selectedUserDetail.skills.map((s) => (
                            <span
                              key={s}
                              className="px-2 py-0.5 rounded text-[11px] font-medium bg-blue-50 text-blue-800 border border-blue-200"
                            >
                              {s}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div>
                        <span className="text-slate-400 block text-[10px] mb-1">Target Roles</span>
                        <div className="flex flex-wrap gap-1">
                          {selectedUserDetail.desired_roles.map((r) => (
                            <span
                              key={r}
                              className="px-2 py-0.5 rounded text-[11px] bg-slate-100 text-slate-800 border border-slate-200"
                            >
                              {r}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div>
                        <span className="text-slate-400 block text-[10px] mb-1">Work Modes</span>
                        <div className="flex flex-wrap gap-1">
                          {selectedUserDetail.work_types.map((w) => (
                            <span
                              key={w}
                              className="px-2 py-0.5 rounded text-[11px] capitalize bg-slate-100 text-slate-800"
                            >
                              {w}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* External Links */}
                  {(selectedUserDetail.linkedin_url || selectedUserDetail.github_url || selectedUserDetail.portfolio_url) && (
                    <div className="space-y-2">
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                        External Links
                      </h3>
                      <div className="p-3.5 rounded-lg border border-slate-200 bg-white space-y-2">
                        {selectedUserDetail.linkedin_url && (
                          <div className="flex items-center gap-2">
                            <span className="text-slate-400 text-[10px] w-16">LinkedIn:</span>
                            <a
                              href={selectedUserDetail.linkedin_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-blue-600 hover:underline truncate flex items-center gap-1"
                            >
                              {selectedUserDetail.linkedin_url} <ExternalLink className="h-3 w-3 shrink-0" />
                            </a>
                          </div>
                        )}
                        {selectedUserDetail.github_url && (
                          <div className="flex items-center gap-2">
                            <span className="text-slate-400 text-[10px] w-16">GitHub:</span>
                            <a
                              href={selectedUserDetail.github_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-blue-600 hover:underline truncate flex items-center gap-1"
                            >
                              {selectedUserDetail.github_url} <ExternalLink className="h-3 w-3 shrink-0" />
                            </a>
                          </div>
                        )}
                        {selectedUserDetail.portfolio_url && (
                          <div className="flex items-center gap-2">
                            <span className="text-slate-400 text-[10px] w-16">Portfolio:</span>
                            <a
                              href={selectedUserDetail.portfolio_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-blue-600 hover:underline truncate flex items-center gap-1"
                            >
                              {selectedUserDetail.portfolio_url} <ExternalLink className="h-3 w-3 shrink-0" />
                            </a>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Activity Stats */}
                  <div className="grid grid-cols-3 gap-3">
                    <div className="p-3 rounded-lg border border-slate-200 bg-slate-50 text-center">
                      <span className="text-slate-500 text-[10px] block">Saved Listings</span>
                      <span className="text-base font-bold text-slate-900">{selectedUserDetail.saved_count}</span>
                    </div>
                    <div className="p-3 rounded-lg border border-slate-200 bg-slate-50 text-center">
                      <span className="text-slate-500 text-[10px] block">Activity Events</span>
                      <span className="text-base font-bold text-slate-900">{selectedUserDetail.activity_count}</span>
                    </div>
                    <div className="p-3 rounded-lg border border-slate-200 bg-slate-50 text-center">
                      <span className="text-slate-500 text-[10px] block">Connections</span>
                      <span className="text-base font-bold text-slate-900">{selectedUserDetail.connections_count}</span>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
