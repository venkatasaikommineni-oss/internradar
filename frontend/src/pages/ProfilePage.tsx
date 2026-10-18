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

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.profile.update({
        full_name: fullName.trim() || null,
        mobile: mobile.trim() || null,
        gender: gender || null,
        location: location.trim() || null,
        college: college.trim() || null,
        degree: degree.trim() || null,
        branch: branch.trim() || null,
        graduation_year: graduationYear !== "" ? Number(graduationYear) : null,
        cgpa: cgpa !== "" ? Number(cgpa) : null,
        bio: bio.trim() || null,
        linkedin_url: linkedinUrl.trim() || null,
        github_url: githubUrl.trim() || null,
        portfolio_url: portfolioUrl.trim() || null,
        skills,
        desired_roles: desiredRoles,
        specializations,
        work_types: workTypes,
      });
      await refreshProfile();
      success("Profile Updated", "Your student profile and matching preferences have been saved.");
    } catch (err: any) {
      error("Save Failed", err.message || "Failed to update profile.");
    } finally {
      setSaving(false);
    }
  };

  const handleResumeFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingResume(true);
    try {
      const updatedUser = await api.profile.uploadResume(file);
      await refreshProfile();
      setSkills(updatedUser.skills || []);
      success(
        "Resume Uploaded",
        `Extracted skills and merged ${updatedUser.resume_skills?.length || 0} technical proficiencies into your profile.`
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

  const toggleWorkType = (wt: string) => {
    if (workTypes.includes(wt)) {
      setWorkTypes(workTypes.filter((w) => w !== wt));
    } else {
      setWorkTypes([...workTypes, wt]);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Header */}
      <div className="border-b border-slate-200 pb-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900">
            Profile
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1 leading-relaxed">
            Update your education, skills, and internship preferences.
          </p>
        </div>

        <Button variant="outline" size="sm" onClick={onOpenChangePassword} className="text-xs h-8">
          <Lock className="h-3.5 w-3.5 mr-1.5" /> Change Password
        </Button>
      </div>

      <form onSubmit={handleSaveProfile} className="space-y-6">
        {/* ── Section 1: Resume Upload ────────────────────────────────────── */}
        <div className="p-5 rounded-md border border-slate-200 bg-white shadow-sm space-y-4">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                <FileText className="h-4 w-4 text-blue-600" />
                Resume
              </h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Upload a PDF or DOCX to auto-populate skills in your profile.
              </p>
            </div>

            <input
              type="file"
              ref={fileInputRef}
              onChange={handleResumeFileChange}
              accept=".pdf,.docx,.txt"
              className="hidden"
            />
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

          {user?.resume_skills && user.resume_skills.length > 0 && (
            <div className="pt-3 border-t border-slate-100">
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
              <label className="text-xs font-medium text-slate-700 block mb-1">Full Name</label>
              <Input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Full name"
                required
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">Email</label>
              <Input type="email" value={user?.email || ""} disabled className="bg-slate-50 text-slate-500" />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">Mobile</label>
              <Input
                type="tel"
                value={mobile}
                onChange={(e) => setMobile(e.target.value)}
                placeholder="+91 XXXXX XXXXX"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">Gender</label>
              <select
                value={gender}
                onChange={(e) => setGender(e.target.value)}
                className="w-full h-9 rounded-md border border-slate-300 bg-white px-3 text-xs sm:text-sm text-slate-800"
              >
                <option value="">Prefer not to state</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Non-binary">Non-binary</option>
              </select>
            </div>

            <div className="sm:col-span-2 relative">
              <label className="text-xs font-medium text-slate-700 block mb-1">Location / City</label>
              <Input
                type="text"
                value={location}
                onChange={(e) => {
                  setLocation(e.target.value);
                  setShowLocationList(true);
                }}
                onFocus={() => setShowLocationList(true)}
                placeholder="e.g. Bengaluru, Hyderabad, Pune, Mumbai, Delhi"
              />
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
              <label className="text-xs font-medium text-slate-700 block mb-1">Bio</label>
              <textarea
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                rows={3}
                placeholder="Brief summary of your background, projects, or interests..."
                className="w-full rounded-md border border-slate-300 p-2.5 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-600"
              />
            </div>
          </div>
        </div>

        {/* ── Section 3: Education ───────────────────────────────────────────── */}
        <div className="p-5 rounded-md border border-slate-200 bg-white shadow-sm space-y-4">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-2.5">
            <GraduationCap className="h-4 w-4 text-blue-600" />
            Education
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="sm:col-span-2">
              <label className="text-xs font-medium text-slate-700 block mb-1">College / University</label>
              <Input
                type="text"
                value={college}
                onChange={(e) => setCollege(e.target.value)}
                placeholder="e.g. IIT Bombay, BITS Pilani, NIT Trichy"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">Degree</label>
              <Input
                type="text"
                value={degree}
                onChange={(e) => setDegree(e.target.value)}
                placeholder="e.g. B.Tech, BCA, MCA, M.Tech"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">Branch / Major</label>
              <Input
                type="text"
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                placeholder="e.g. Computer Science, Electrical Engineering"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">Graduation Year</label>
              <Input
                type="number"
                value={graduationYear}
                onChange={(e) => setGraduationYear(e.target.value ? Number(e.target.value) : "")}
                placeholder="e.g. 2026"
                min={2020}
                max={2032}
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">CGPA</label>
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

        {/* ── Section 4: Skills & Preferences ─────────────────────────────────── */}
        <div className="p-5 rounded-md border border-slate-200 bg-white shadow-sm space-y-5">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-2.5">
            <Briefcase className="h-4 w-4 text-blue-600" />
            Skills & Matching Preferences
          </h3>

          {/* Technical Skills */}
          <div>
            <label className="text-xs font-medium text-slate-700 block mb-1.5">
              Skills ({skills.length})
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

          {/* Desired Roles */}
          <div>
            <label className="text-xs font-medium text-slate-700 block mb-1.5">
              Target Roles ({desiredRoles.length})
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
          </div>

          {/* Specializations */}
          <div>
            <label className="text-xs font-medium text-slate-700 block mb-1.5">
              Specializations ({specializations.length})
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
              Work Modes
            </label>
            <div className="flex gap-4 text-xs">
              {["remote", "hybrid", "onsite"].map((wt) => (
                <label key={wt} className="flex items-center gap-2 cursor-pointer capitalize text-slate-700">
                  <input
                    type="checkbox"
                    checked={workTypes.includes(wt)}
                    onChange={() => toggleWorkType(wt)}
                    className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                  {wt}
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* ── Section 5: Online Profiles ────────────────────────────────────── */}
        <div className="p-5 rounded-md border border-slate-200 bg-white shadow-sm space-y-4">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2 border-b border-slate-100 pb-2.5">
            <Globe className="h-4 w-4 text-blue-600" />
            Links
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">LinkedIn</label>
              <Input
                type="url"
                value={linkedinUrl}
                onChange={(e) => setLinkedinUrl(e.target.value)}
                placeholder="https://linkedin.com/in/username"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">GitHub</label>
              <Input
                type="url"
                value={githubUrl}
                onChange={(e) => setGithubUrl(e.target.value)}
                placeholder="https://github.com/username"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">Portfolio</label>
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
          <Button type="submit" loading={saving} className="h-9 px-5 text-xs font-medium">
            <Save className="h-3.5 w-3.5 mr-1.5" /> Save Profile
          </Button>
        </div>
      </form>
    </div>
  );
};
