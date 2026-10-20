import React, { useState, useEffect, useRef } from "react";
import {
  User as UserIcon,
  Upload,
  FileText,
  CheckCircle2,
  X,
  Plus,
  Briefcase,
  GraduationCap,
  Globe,
  MapPin,
  Lock,
  Save,
  Check,
  Eye,
  Download,
  Trash2,
  AlertCircle,
  Info,
  Calendar,
  HardDrive,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";

interface ProfilePageProps {
  onOpenChangePassword: () => void;
}

export const ProfilePage: React.FC<ProfilePageProps> = ({ onOpenChangePassword }) => {
  const { user, refreshProfile } = useAuth();
  const { success, error, info } = useToast();

  const [saving, setSaving] = useState(false);
  const [uploadingResume, setUploadingResume] = useState(false);
  const [deletingResume, setDeletingResume] = useState(false);
  const [downloadingResume, setDownloadingResume] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Form states
  const [fullName, setFullName] = useState("");
  const [mobile, setMobile] = useState("");
  const [gender, setGender] = useState("");
  const [location, setLocation] = useState("");
  const [college, setCollege] = useState("");
  const [degree, setDegree] = useState("");
  const [branch, setBranch] = useState("");
  const [graduationYear, setGraduationYear] = useState<number | "">("");
  const [cgpa, setCgpa] = useState<number | "">("");
  const [bio, setBio] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [portfolioUrl, setPortfolioUrl] = useState("");

  const [skills, setSkills] = useState<string[]>([]);
  const [desiredRoles, setDesiredRoles] = useState<string[]>([]);
  const [specializations, setSpecializations] = useState<string[]>([]);
  const [workTypes, setWorkTypes] = useState<string[]>([]);

  // Validation errors
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  // Autocomplete inputs
  const [skillInput, setSkillInput] = useState("");
  const [skillSuggestions, setSkillSuggestions] = useState<string[]>([]);

  const [roleInput, setRoleInput] = useState("");
  const [roleSuggestions, setRoleSuggestions] = useState<string[]>([]);

  const [specInput, setSpecInput] = useState("");
  const [specSuggestions, setSpecSuggestions] = useState<string[]>([]);

  const [locationSuggestions, setLocationSuggestions] = useState<string[]>([]);
  const [showLocationList, setShowLocationList] = useState(false);

  useEffect(() => {
    if (user) {
      setFullName(user.full_name || "");
      setMobile(user.mobile || "");
      setGender(user.gender || "");
      setLocation(user.location || "");
      setCollege(user.college || "");
      setDegree(user.degree || "");
      setBranch(user.branch || "");
      setGraduationYear(user.graduation_year ?? "");
      setCgpa(user.cgpa ?? "");
      setBio(user.bio || "");
      setLinkedinUrl(user.linkedin_url || "");
      setGithubUrl(user.github_url || "");
      setPortfolioUrl(user.portfolio_url || "");

      setSkills(user.skills || []);
      setDesiredRoles(user.desired_roles || []);
      setSpecializations(user.specializations || []);
      setWorkTypes(user.work_types || []);
    }
  }, [user]);

  // Skill suggestion
  useEffect(() => {
    if (!skillInput.trim()) {
      setSkillSuggestions([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await api.meta.skills(skillInput, 6);
        setSkillSuggestions(res.filter((s) => !skills.includes(s)));
      } catch {
        setSkillSuggestions([]);
      }
    }, 200);
    return () => clearTimeout(timer);
  }, [skillInput, skills]);

  // Role suggestion
  useEffect(() => {
    if (!roleInput.trim()) {
      setRoleSuggestions([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await api.meta.roles(roleInput, 6);
        setRoleSuggestions(res.filter((r) => !desiredRoles.includes(r)));
      } catch {
        setRoleSuggestions([]);
      }
    }, 200);
    return () => clearTimeout(timer);
  }, [roleInput, desiredRoles]);

  // Specialization suggestion
  useEffect(() => {
    if (!specInput.trim()) {
      setSpecSuggestions([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await api.meta.specializations(specInput, 6);
        setSpecSuggestions(res.filter((s) => !specializations.includes(s)));
      } catch {
        setSpecSuggestions([]);
      }
    }, 200);
    return () => clearTimeout(timer);
  }, [specInput, specializations]);

  // Location suggestion
  useEffect(() => {
    if (!location.trim()) {
      setLocationSuggestions([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await api.meta.locations(location, 5);
        setLocationSuggestions(res);
      } catch {
        setLocationSuggestions([]);
      }
    }, 200);
    return () => clearTimeout(timer);
  }, [location]);

  const validate = (): boolean => {
    const errs: Record<string, string> = {};

    if (!fullName.trim()) {
      errs.fullName = "Full name is required and cannot be empty.";
    }
    if (!college.trim()) {
      errs.college = "College or university is required.";
    }
    if (!degree.trim()) {
      errs.degree = "Degree is required (e.g. B.Tech, BCA, MCA).";
    }
    if (graduationYear === "" || Number(graduationYear) < 2020 || Number(graduationYear) > 2035) {
      errs.graduationYear = "A valid graduation year between 2020 and 2035 is required.";
    }
    if (!location.trim()) {
      errs.location = "Location / City is required.";
    }
    if (skills.length === 0) {
      errs.skills = "At least one technical skill is required.";
    }
    if (desiredRoles.length === 0) {
      errs.desiredRoles = "At least one target internship role is required.";
    }
    if (workTypes.length === 0) {
      errs.workTypes = "At least one preferred work mode (Remote/Hybrid/Onsite) is required.";
    }

    setValidationErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) {
      error("Incomplete Profile", "Please fill in all mandatory fields marked with an asterisk (*).");
      return;
    }

    setSaving(true);
    try {
      await api.profile.update({
        full_name: fullName.trim(),
        mobile: mobile.trim() || null,
        gender: (gender as any) || null,
        location: location.trim(),
        college: college.trim(),
        degree: degree.trim(),
        branch: branch.trim() || null,
        graduation_year: Number(graduationYear),
        cgpa: cgpa !== "" ? Number(cgpa) : null,
        bio: bio.trim() || null,
        linkedin_url: linkedinUrl.trim() || null,
        github_url: githubUrl.trim() || null,
        portfolio_url: portfolioUrl.trim() || null,
        skills,
        desired_roles: desiredRoles,
        specializations,
        work_types: workTypes as any,
      });
      await refreshProfile();
      setValidationErrors({});
      success("Profile Updated", "Your essential profile details and matching preferences have been successfully saved.");
    } catch (err: any) {
      error("Save Failed", err.message || "Failed to update profile.");
    } finally {
      setSaving(false);
    }
  };

  const handleResumeFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 5 * 1024 * 1024) {
      error("File Too Large", "Resume must be under 5 MB in size.");
      return;
    }

    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!["pdf", "docx", "txt"].includes(ext || "")) {
      error("Invalid File Type", "Only PDF, DOCX, and TXT files are accepted.");
      return;
    }

    setUploadingResume(true);
    try {
      const updatedUser = await api.profile.uploadResume(file);
      await refreshProfile();
      setSkills(updatedUser.skills || []);
      success(
        "Resume Uploaded",
        `Extracted skills and updated your resume file (${file.name}).`
      );
    } catch (err: any) {
      error("Upload Failed", err.message || "Failed to parse resume.");
    } finally {
      setUploadingResume(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleViewResume = async () => {
    try {
      setDownloadingResume(true);
      await api.profile.downloadResume(false);
    } catch (err: any) {
      error("Preview Failed", err.message || "Unable to view resume.");
    } finally {
      setDownloadingResume(false);
    }
  };

  const handleDownloadResume = async () => {
    try {
      setDownloadingResume(true);
      await api.profile.downloadResume(true);
      success("Download Started", "Your resume file is being downloaded.");
    } catch (err: any) {
      error("Download Failed", err.message || "Unable to download resume.");
    } finally {
      setDownloadingResume(false);
    }
  };

  const handleDeleteResume = async () => {
    if (!window.confirm("Are you sure you want to delete your stored resume? This action cannot be undone.")) {
      return;
    }
    setDeletingResume(true);
    try {
      await api.profile.deleteResume();
      await refreshProfile();
      success("Resume Deleted", "Your resume file has been permanently removed.");
    } catch (err: any) {
      error("Delete Failed", err.message || "Failed to delete resume.");
    } finally {
      setDeletingResume(false);
    }
  };

  const toggleWorkType = (wt: string) => {
    if (workTypes.includes(wt)) {
      setWorkTypes(workTypes.filter((w) => w !== wt));
    } else {
      setWorkTypes([...workTypes, wt]);
    }
  };

  const formatFileSize = (bytes?: number | null) => {
    if (!bytes) return "";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  const formatDate = (dateStr?: string | null) => {
    if (!dateStr) return "";
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

  // Determine missing fields for banner
  const isProfileComplete = Boolean(
    user?.full_name &&
    user?.college &&
    user?.degree &&
    user?.graduation_year &&
    user?.location &&
    user?.skills?.length &&
    user?.desired_roles?.length &&
    user?.work_types?.length
  );

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="border-b border-slate-200 pb-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900">
            Student Profile
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1 leading-relaxed">
            Manage your academic credentials, verified skills, and match preferences.
          </p>
        </div>

        <Button variant="outline" size="sm" onClick={onOpenChangePassword} className="text-xs h-8">
          <Lock className="h-3.5 w-3.5 mr-1.5" /> Change Password
        </Button>
      </div>

      {/* Profile Incomplete Banner for legacy or new users */}
      {!isProfileComplete && (
        <div className="p-4 rounded-lg bg-amber-50 border border-amber-200 text-amber-900 flex items-start gap-3 shadow-xs">
          <AlertCircle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <span className="font-semibold block text-amber-950">
              Profile Incomplete — Mandatory Information Needed
            </span>
            <p className="text-amber-800 leading-relaxed">
              To match accurately with company internships and enable vetted employer applications, all essential fields marked with an asterisk (<span className="text-rose-600 font-bold">*</span>) are mandatory. Please fill in your education, skills, target roles, and work mode preferences below.
            </p>
          </div>
        </div>
      )}


      <form onSubmit={handleSaveProfile} className="space-y-6">
        {/* ── Section 1: Resume Upload & Management ───────────────────────── */}
        <div className="p-5 rounded-md border border-slate-200 bg-white shadow-sm space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                <FileText className="h-4 w-4 text-blue-600" />
                Resume Document
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Upload your latest resume (PDF, DOCX, or TXT under 5 MB) for automated skill extraction and administrative vetting.
              </p>
            </div>

            <input
              type="file"
              ref={fileInputRef}
              onChange={handleResumeFileChange}
              accept=".pdf,.docx,.txt"
              className="hidden"
            />

            <div className="flex items-center gap-2 flex-wrap">
              <Button
                type="button"
                variant="outline"
                size="sm"
                loading={uploadingResume}
                onClick={() => fileInputRef.current?.click()}
                className="text-xs shrink-0"
              >
                <Upload className="h-3.5 w-3.5 mr-1.5" />
                {user?.resume_path ? "Replace Resume" : "Upload Resume"}
              </Button>
            </div>
          </div>

          {/* Stored resume details & action buttons */}
          {user?.resume_path ? (
            <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className="h-9 w-9 rounded-md bg-blue-100 text-blue-700 flex items-center justify-center shrink-0">
                  <FileText className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <span className="text-xs font-semibold text-slate-900 block truncate">
                    {user.resume_filename || "Stored Resume"}
                  </span>
                  <div className="flex items-center gap-2 text-[11px] text-slate-500 mt-0.5">
                    {user.resume_size_bytes && (
                      <span className="flex items-center gap-1">
                        <HardDrive className="h-3 w-3" />
                        {formatFileSize(user.resume_size_bytes)}
                      </span>
                    )}
                    {user.resume_uploaded_at && (
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        Uploaded {formatDate(user.resume_uploaded_at)}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleViewResume}
                  loading={downloadingResume}
                  className="text-xs h-7.5 px-2.5"
                  title="Preview resume in new tab"
                >
                  <Eye className="h-3.5 w-3.5 mr-1 text-slate-600" /> Preview
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleDownloadResume}
                  loading={downloadingResume}
                  className="text-xs h-7.5 px-2.5"
                  title="Download resume file"
                >
                  <Download className="h-3.5 w-3.5 mr-1 text-slate-600" /> Download
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleDeleteResume}
                  loading={deletingResume}
                  className="text-xs h-7.5 px-2.5 text-rose-600 hover:text-rose-700 hover:bg-rose-50 border-rose-200"
                  title="Delete resume"
                >
                  <Trash2 className="h-3.5 w-3.5 mr-1" /> Delete
                </Button>
              </div>
            </div>
          ) : (
            <div className="p-3 text-xs text-slate-500 bg-slate-50 rounded-md border border-dashed border-slate-200 flex items-center gap-2">
              <Info className="h-4 w-4 text-slate-400 shrink-0" />
              <span>No resume uploaded yet. Uploading a resume auto-extracts your skills and improves matching.</span>
            </div>
          )}

          {user?.resume_skills && user.resume_skills.length > 0 && (
            <div className="pt-2">
              <span className="text-[11px] font-medium text-slate-500 block mb-1.5">
                Skills extracted from your resume ({user.resume_skills.length}):
              </span>
              <div className="flex flex-wrap gap-1.5">
                {user.resume_skills.map((s) => (
                  <span
                    key={s}
                    className="text-xs px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 font-medium"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── Section 2: Personal Details ──────────────────────────────────── */}
        <div className="p-5 rounded-md border border-slate-200 bg-white shadow-sm space-y-4">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-2.5">
            <UserIcon className="h-4 w-4 text-blue-600" />
            Personal Details
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">
                Full Name <span className="text-rose-600 font-bold">*</span>
              </label>
              <Input
                type="text"
                value={fullName}
                onChange={(e) => {
                  setFullName(e.target.value);
                  if (validationErrors.fullName) {
                    setValidationErrors((prev) => ({ ...prev, fullName: "" }));
                  }
                }}
                placeholder="e.g. Aditi Sharma"
                className={validationErrors.fullName ? "border-rose-400 focus:ring-rose-500" : ""}
                required
              />
              {validationErrors.fullName && (
                <p className="text-[11px] text-rose-600 mt-1">{validationErrors.fullName}</p>
              )}
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">
                Email Address <span className="text-rose-600 font-bold">*</span>
              </label>
              <Input type="email" value={user?.email || ""} disabled className="bg-slate-50 text-slate-500" />
              <p className="text-[10px] text-slate-400 mt-0.5">Verified registration email</p>
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">
                Mobile Number <span className="text-slate-400 text-[10px] font-normal">(Optional)</span>
              </label>
              <Input
                type="tel"
                value={mobile}
                onChange={(e) => setMobile(e.target.value)}
                placeholder="+91 98765 43210"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">
                Gender <span className="text-slate-400 text-[10px] font-normal">(Optional)</span>
              </label>
              <select
                value={gender}
                onChange={(e) => setGender(e.target.value)}
                className="w-full h-9 rounded-md border border-slate-300 bg-white px-3 text-xs sm:text-sm text-slate-800"
              >
                <option value="">Prefer not to state</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="non_binary">Non-binary</option>
                <option value="prefer_not_to_say">Prefer not to say</option>
              </select>
            </div>

            <div className="sm:col-span-2 relative">
              <label className="text-xs font-medium text-slate-700 block mb-1">
                Location / City <span className="text-rose-600 font-bold">*</span>
              </label>
              <Input
                type="text"
                value={location}
                onChange={(e) => {
                  setLocation(e.target.value);
                  setShowLocationList(true);
                  if (validationErrors.location) {
                    setValidationErrors((prev) => ({ ...prev, location: "" }));
                  }
                }}
                onFocus={() => setShowLocationList(true)}
                placeholder="e.g. Bengaluru, Hyderabad, Pune, Mumbai, Delhi, Remote"
                className={validationErrors.location ? "border-rose-400 focus:ring-rose-500" : ""}
                required
              />
              {validationErrors.location && (
                <p className="text-[11px] text-rose-600 mt-1">{validationErrors.location}</p>
              )}
              {showLocationList && locationSuggestions.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-md z-30 py-1">
                  {locationSuggestions.map((loc) => (
                    <button
                      key={loc}
                      type="button"
                      onClick={() => {
                        setLocation(loc);
                        setShowLocationList(false);
                      }}
                      className="w-full text-left px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
                    >
                      {loc}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="sm:col-span-2">
              <label className="text-xs font-medium text-slate-700 block mb-1">
                Bio / Summary <span className="text-slate-400 text-[10px] font-normal">(Optional)</span>
              </label>
              <textarea
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                rows={3}
                placeholder="Brief summary of your background, projects, or primary interests..."
                className="w-full rounded-md border border-slate-300 p-2.5 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-600"
              />
            </div>
          </div>
        </div>

        {/* ── Section 3: Academic Background ───────────────────────────────── */}
        <div className="p-5 rounded-md border border-slate-200 bg-white shadow-sm space-y-4">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-2.5">
            <GraduationCap className="h-4 w-4 text-blue-600" />
            Academic Background
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="sm:col-span-2">
              <label className="text-xs font-medium text-slate-700 block mb-1">
                College / University <span className="text-rose-600 font-bold">*</span>
              </label>
              <Input
                type="text"
                value={college}
                onChange={(e) => {
                  setCollege(e.target.value);
                  if (validationErrors.college) {
                    setValidationErrors((prev) => ({ ...prev, college: "" }));
                  }
                }}
                placeholder="e.g. IIT Bombay, BITS Pilani, NIT Trichy, Anna University"
                className={validationErrors.college ? "border-rose-400 focus:ring-rose-500" : ""}
                required
              />
              {validationErrors.college && (
                <p className="text-[11px] text-rose-600 mt-1">{validationErrors.college}</p>
              )}
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">
                Degree <span className="text-rose-600 font-bold">*</span>
              </label>
              <Input
                type="text"
                value={degree}
                onChange={(e) => {
                  setDegree(e.target.value);
                  if (validationErrors.degree) {
                    setValidationErrors((prev) => ({ ...prev, degree: "" }));
                  }
                }}
                placeholder="e.g. B.Tech, BCA, MCA, M.Tech, B.Sc"
                className={validationErrors.degree ? "border-rose-400 focus:ring-rose-500" : ""}
                required
              />
              {validationErrors.degree && (
                <p className="text-[11px] text-rose-600 mt-1">{validationErrors.degree}</p>
              )}
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">
                Branch / Major <span className="text-slate-400 text-[10px] font-normal">(Optional)</span>
              </label>
              <Input
                type="text"
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                placeholder="e.g. Computer Science, Electrical Engineering"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">
                Graduation Year <span className="text-rose-600 font-bold">*</span>
              </label>
              <Input
                type="number"
                value={graduationYear}
                onChange={(e) => {
                  setGraduationYear(e.target.value ? Number(e.target.value) : "");
                  if (validationErrors.graduationYear) {
                    setValidationErrors((prev) => ({ ...prev, graduationYear: "" }));
                  }
                }}
                placeholder="e.g. 2026"
                min={2020}
                max={2035}
                className={validationErrors.graduationYear ? "border-rose-400 focus:ring-rose-500" : ""}
                required
              />
              {validationErrors.graduationYear && (
                <p className="text-[11px] text-rose-600 mt-1">{validationErrors.graduationYear}</p>
              )}
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">
                CGPA / Percentage <span className="text-slate-400 text-[10px] font-normal">(Optional)</span>
              </label>
              <Input
                type="number"
                step="0.01"
                min="0"
                max="10"
                value={cgpa}
                onChange={(e) => setCgpa(e.target.value ? Number(e.target.value) : "")}
                placeholder="e.g. 8.5"
              />
            </div>
          </div>
        </div>

        {/* ── Section 4: Skills & Matching Preferences ─────────────────────── */}
        <div className="p-5 rounded-md border border-slate-200 bg-white shadow-sm space-y-5">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-2.5">
            <Briefcase className="h-4 w-4 text-blue-600" />
            Skills & Matching Preferences
          </h3>

          {/* Technical Skills */}
          <div>
            <label className="text-xs font-medium text-slate-700 block mb-1.5">
              Technical Skills <span className="text-rose-600 font-bold">*</span> ({skills.length})
            </label>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {skills.map((skill) => (
                <span
                  key={skill}
                  className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded border border-blue-200 bg-blue-50 text-blue-800 text-xs font-medium"
                >
                  {skill}
                  <button
                    type="button"
                    onClick={() => setSkills(skills.filter((s) => s !== skill))}
                    className="hover:text-blue-950"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
            <div className="relative max-w-sm">
              <Input
                type="text"
                value={skillInput}
                onChange={(e) => setSkillInput(e.target.value)}
                placeholder="Add skill (e.g. React, Python, Docker)..."
                className="h-8 text-xs"
              />
              {skillSuggestions.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-md z-30 py-1">
                  {skillSuggestions.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => {
                        setSkills([...skills, s]);
                        setSkillInput("");
                        setSkillSuggestions([]);
                        setValidationErrors((prev) => ({ ...prev, skills: "" }));
                      }}
                      className="w-full text-left px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 flex items-center justify-between"
                    >
                      <span>{s}</span>
                      <Plus className="h-3 w-3 text-slate-400" />
                    </button>
                  ))}
                </div>
              )}
            </div>
            {validationErrors.skills && (
              <p className="text-[11px] text-rose-600 mt-1.5">{validationErrors.skills}</p>
            )}
          </div>

          {/* Desired Roles */}
          <div>
            <label className="text-xs font-medium text-slate-700 block mb-1.5">
              Target Internship Roles <span className="text-rose-600 font-bold">*</span> ({desiredRoles.length})
            </label>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {desiredRoles.map((role) => (
                <span
                  key={role}
                  className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded border border-slate-300 bg-slate-100 text-slate-800 text-xs"
                >
                  {role}
                  <button
                    type="button"
                    onClick={() => setDesiredRoles(desiredRoles.filter((r) => r !== role))}
                    className="hover:text-slate-950"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
            <div className="relative max-w-sm">
              <Input
                type="text"
                value={roleInput}
                onChange={(e) => setRoleInput(e.target.value)}
                placeholder="Add target role (e.g. Backend Developer Intern)..."
                className="h-8 text-xs"
              />
              {roleSuggestions.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-md z-30 py-1">
                  {roleSuggestions.map((r) => (
                    <button
                      key={r}
                      type="button"
                      onClick={() => {
                        setDesiredRoles([...desiredRoles, r]);
                        setRoleInput("");
                        setRoleSuggestions([]);
                        setValidationErrors((prev) => ({ ...prev, desiredRoles: "" }));
                      }}
                      className="w-full text-left px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 flex items-center justify-between"
                    >
                      <span>{r}</span>
                      <Plus className="h-3 w-3 text-slate-400" />
                    </button>
                  ))}
                </div>
              )}
            </div>
            {validationErrors.desiredRoles && (
              <p className="text-[11px] text-rose-600 mt-1.5">{validationErrors.desiredRoles}</p>
            )}
          </div>

          {/* Specializations */}
          <div>
            <label className="text-xs font-medium text-slate-700 block mb-1.5">
              Specializations <span className="text-slate-400 text-[10px] font-normal">(Optional)</span> ({specializations.length})
            </label>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {specializations.map((spec) => (
                <span
                  key={spec}
                  className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded border border-slate-300 bg-slate-100 text-slate-800 text-xs"
                >
                  {spec}
                  <button
                    type="button"
                    onClick={() => setSpecializations(specializations.filter((s) => s !== spec))}
                    className="hover:text-slate-950"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
            <div className="relative max-w-sm">
              <Input
                type="text"
                value={specInput}
                onChange={(e) => setSpecInput(e.target.value)}
                placeholder="Add specialization (e.g. AI, Cloud, Embedded)..."
                className="h-8 text-xs"
              />
              {specSuggestions.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-md z-30 py-1">
                  {specSuggestions.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => {
                        setSpecializations([...specializations, s]);
                        setSpecInput("");
                        setSpecSuggestions([]);
                      }}
                      className="w-full text-left px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 flex items-center justify-between"
                    >
                      <span>{s}</span>
                      <Plus className="h-3 w-3 text-slate-400" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Preferred Work Modes */}
          <div>
            <label className="text-xs font-medium text-slate-700 block mb-1.5">
              Preferred Work Modes <span className="text-rose-600 font-bold">*</span>
            </label>
            <div className="flex gap-4 text-xs">
              {["remote", "hybrid", "onsite"].map((wt) => (
                <label key={wt} className="flex items-center gap-2 cursor-pointer capitalize text-slate-700">
                  <input
                    type="checkbox"
                    checked={workTypes.includes(wt)}
                    onChange={() => {
                      toggleWorkType(wt);
                      setValidationErrors((prev) => ({ ...prev, workTypes: "" }));
                    }}
                    className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                  {wt}
                </label>
              ))}
            </div>
            {validationErrors.workTypes && (
              <p className="text-[11px] text-rose-600 mt-1.5">{validationErrors.workTypes}</p>
            )}
          </div>
        </div>

        {/* ── Section 5: Secondary Links (Strictly Optional) ──────────────── */}
        <div className="p-5 rounded-md border border-slate-200 bg-white shadow-sm space-y-4">
          <div className="border-b border-slate-100 pb-2.5 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <Globe className="h-4 w-4 text-blue-600" />
              External Links & Portfolios
            </h3>
            <span className="text-[11px] text-slate-400 font-normal">Optional</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">
                LinkedIn Profile <span className="text-slate-400 text-[10px] font-normal">(Optional)</span>
              </label>
              <Input
                type="url"
                value={linkedinUrl}
                onChange={(e) => setLinkedinUrl(e.target.value)}
                placeholder="https://linkedin.com/in/username"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">
                GitHub Profile <span className="text-slate-400 text-[10px] font-normal">(Optional)</span>
              </label>
              <Input
                type="url"
                value={githubUrl}
                onChange={(e) => setGithubUrl(e.target.value)}
                placeholder="https://github.com/username"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">
                Personal Portfolio <span className="text-slate-400 text-[10px] font-normal">(Optional)</span>
              </label>
              <Input
                type="url"
                value={portfolioUrl}
                onChange={(e) => setPortfolioUrl(e.target.value)}
                placeholder="https://yourname.dev"
              />
            </div>
          </div>
        </div>

        {/* Submit Bar */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <Button type="submit" loading={saving} className="h-9 px-6 text-xs font-medium shadow-xs">
            <Save className="h-3.5 w-3.5 mr-1.5" /> Save Profile
          </Button>
        </div>
      </form>
    </div>
  );
};
