import React, { useState, useEffect, useCallback } from "react";
import {
  Search,
  MapPin,
  Filter,
  X,
  RotateCcw,
  Briefcase,
  ChevronLeft,
  ChevronRight,
  SlidersHorizontal,
  DollarSign,
  Building,
  RefreshCw,
  Sparkles,
  CheckCircle2,
  Clock,
  Code,
  Layers,
  ArrowRight,
} from "lucide-react";
import { Internship, WorkType, InternshipStatus, Recommendation } from "../types";
import { api } from "../lib/api";
import { InternshipCard } from "../components/InternshipCard";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { useAuth } from "../context/AuthContext";

interface DiscoverPageProps {
  onViewDetails: (internship: Internship) => void;
  savedIds: Set<number>;
  onSavedChange: (internshipId: number, saved: boolean) => void;
}

const CATEGORIES = [
  { id: undefined, label: "All Opportunities" },
  { id: "software", label: "Software Engineering" },
  { id: "frontend", label: "Frontend" },
  { id: "backend", label: "Backend" },
  { id: "fullstack", label: "Full Stack" },
  { id: "data_ai", label: "AI / ML & Data" },
  { id: "cloud_devops", label: "Cloud & DevOps" },
  { id: "qa", label: "QA & Testing" },
  { id: "cybersecurity", label: "Cybersecurity" },
  { id: "design", label: "UI/UX & Design" },
];

export const DiscoverPage: React.FC<DiscoverPageProps> = ({
  onViewDetails,
  savedIds,
  onSavedChange,
}) => {
  const { user, isAuthenticated } = useAuth();

  const [internships, setInternships] = useState<Internship[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // Recommendations state (Recommended for You section)
  const [recommendedItems, setRecommendedItems] = useState<Recommendation[]>([]);
  const [recommendedLoading, setRecommendedLoading] = useState(false);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | undefined>(undefined);
  const [location, setLocation] = useState("");
  const [workType, setWorkType] = useState<WorkType | undefined>(undefined);
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const [skillsMatch, setSkillsMatch] = useState<"all" | "any">("all");
  const [minStipend, setMinStipend] = useState<number | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState<string>("open");
  const [sort, setSort] = useState<"newest" | "deadline" | "stipend">("newest");
  const [page, setPage] = useState(1);
  const limit = 12;

  // Typeahead suggestions
  const [skillInput, setSkillInput] = useState("");
  const [skillSuggestions, setSkillSuggestions] = useState<string[]>([]);
  const [locationSuggestions, setLocationSuggestions] = useState<string[]>([]);
  const [showLocationSuggestions, setShowLocationSuggestions] = useState(false);

  // Advanced filters drawer on mobile/tablet
  const [showFilters, setShowFilters] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState<string | null>(null);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string | null>(null);

  // Fetch personalized recommendations — only for authenticated users with a meaningful profile
  const userHasProfile = Boolean(
    isAuthenticated &&
      user &&
      ((user.skills && user.skills.length > 0) ||
        (user.desired_roles && user.desired_roles.length > 0) ||
        user.resume_path)
  );

  const fetchRecommendations = useCallback(async () => {
    // Only fetch if the user is logged in and has personalization data
    if (!userHasProfile) {
      setRecommendedItems([]);
      setRecommendedLoading(false);
      return;
    }
    setRecommendedLoading(true);
    try {
      const res = await api.recommendations.get({ limit: 3 });
      setRecommendedItems(res.items && res.items.length > 0 ? res.items : []);
    } catch {
      setRecommendedItems([]);
    } finally {
      setRecommendedLoading(false);
    }
  }, [userHasProfile]);

  // Fetch refresh status on mount
  useEffect(() => {
    api.internships
      .refreshStatus()
      .then((st) => {
        if (st.last_run_at) {
          setLastRefreshedAt(st.last_run_at);
        }
      })
      .catch(() => {});
  }, []);

  // Fetch internships list
  const fetchInternships = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.internships.search({
        q: searchQuery.trim() || undefined,
        location: location.trim() || undefined,
        work_type: workType,
        skills: selectedSkills.length > 0 ? selectedSkills.join(",") : undefined,
        skills_match: skillsMatch,
        min_stipend: minStipend,
        status: statusFilter === "all" ? undefined : statusFilter,
        category: selectedCategory,
        sort,
        limit,
        offset: (page - 1) * limit,
      });
      setInternships(data.items);
      setTotal(data.total);
    } catch {
      setInternships([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, location, workType, selectedSkills, skillsMatch, minStipend, statusFilter, selectedCategory, sort, page]);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    setRefreshMessage(null);
    try {
      const res = await api.internships.refresh();
      setRefreshMessage(res.message);
      if (res.last_run_at) {
        setLastRefreshedAt(res.last_run_at);
      }
      // Re-fetch current listings immediately
      await fetchInternships();
      await fetchRecommendations();
    } catch (err: any) {
      setRefreshMessage("Could not retrieve fresh results. Preserving current opportunities.");
    } finally {
      setRefreshing(false);
      setTimeout(() => setRefreshMessage(null), 5000);
    }
  }, [fetchInternships, fetchRecommendations]);

  useEffect(() => {
    fetchInternships();
  }, [fetchInternships]);

  useEffect(() => {
    fetchRecommendations();
  }, [fetchRecommendations]);

  // Skill autocomplete
  useEffect(() => {
    if (!skillInput.trim()) {
      setSkillSuggestions([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await api.meta.skills(skillInput, 8);
        setSkillSuggestions(res.filter((s) => !selectedSkills.includes(s)));
      } catch {
        setSkillSuggestions([]);
      }
    }, 200);
    return () => clearTimeout(timer);
  }, [skillInput, selectedSkills]);

  // Location autocomplete
  useEffect(() => {
    if (!location.trim()) {
      setLocationSuggestions([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await api.meta.locations(location, 6);
        setLocationSuggestions(res);
      } catch {
        setLocationSuggestions([]);
      }
    }, 200);
    return () => clearTimeout(timer);
  }, [location]);

  const handleAddSkill = (skill: string) => {
    if (!selectedSkills.includes(skill)) {
      setSelectedSkills([...selectedSkills, skill]);
      setPage(1);
    }
    setSkillInput("");
    setSkillSuggestions([]);
  };

  const handleRemoveSkill = (skill: string) => {
    setSelectedSkills(selectedSkills.filter((s) => s !== skill));
    setPage(1);
  };

  const handleClearAllFilters = () => {
    setSearchQuery("");
    setSelectedCategory(undefined);
    setLocation("");
    setWorkType(undefined);
    setSelectedSkills([]);
    setMinStipend(undefined);
    setStatusFilter("open");
    setSort("newest");
    setPage(1);
  };

  const totalPages = Math.ceil(total / limit) || 1;

  const activeFilterCount =
    (searchQuery ? 1 : 0) +
    (selectedCategory ? 1 : 0) +
    (location ? 1 : 0) +
    (workType ? 1 : 0) +
    selectedSkills.length +
    (minStipend ? 1 : 0) +
    (statusFilter !== "open" ? 1 : 0);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Page Header */}
      <div className="border-b border-slate-200 pb-5 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
              <Sparkles className="h-3 w-3" /> 70% Software & Tech Focus
            </span>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
              <CheckCircle2 className="h-3 w-3" /> Verified Open Applications
            </span>
          </div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900">
            Internship Discovery
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-2xl leading-relaxed">
            Genuine opportunities aggregated from employer career pages across India.
          </p>
        </div>

        {/* Refresh status action */}
        <div className="flex items-center gap-3 text-xs text-slate-500">
          {lastRefreshedAt && (
            <span className="flex items-center gap-1 text-[11px] text-slate-400">
              <Clock className="h-3 w-3" /> Updated {new Date(lastRefreshedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={refreshing}
            className="h-8 text-xs font-medium flex items-center gap-1.5 bg-white border-slate-200 text-slate-700 hover:bg-slate-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 text-blue-600 ${refreshing ? "animate-spin" : ""}`} />
            {refreshing ? "Refreshing…" : "Refresh Listings"}
          </Button>
        </div>
      </div>

      {/* Refresh alert notification if active */}
      {refreshMessage && (
        <div className="p-3 bg-blue-50 border border-blue-200 rounded text-xs text-blue-800 flex items-center justify-between animate-in fade-in">
          <span>{refreshMessage}</span>
          <button onClick={() => setRefreshMessage(null)} className="text-blue-500 hover:text-blue-800">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* ── Section: Recommended for You (shown only when user has a profile with skills/roles) ── */}
      {page === 1 && !searchQuery && !selectedCategory && userHasProfile && recommendedItems.length > 0 && (
        <div className="bg-gradient-to-r from-slate-900 to-slate-800 rounded-lg p-5 sm:p-6 text-white shadow-sm border border-slate-700 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-700 pb-3">
            <div className="flex items-center gap-2">
              <div className="h-7 w-7 rounded bg-blue-500/20 text-blue-400 flex items-center justify-center">
                <Sparkles className="h-4 w-4" />
              </div>
              <div>
                <h2 className="text-sm sm:text-base font-semibold tracking-tight text-white flex items-center gap-2">
                  Recommended for You
                </h2>
                <p className="text-[11px] text-slate-400">
                  Ranked based on your profile skills, desired roles, and preferences
                </p>
              </div>
            </div>
            <a
              href="#matches"
              className="text-xs text-blue-400 hover:text-blue-300 font-medium flex items-center gap-1 self-start sm:self-auto"
            >
              View all matches <ArrowRight className="h-3.5 w-3.5" />
            </a>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {recommendedItems.map((rec) => (
              <div
                key={rec.internship.id}
                onClick={() => onViewDetails(rec.internship)}
                className="bg-slate-800/80 hover:bg-slate-800 border border-slate-700 hover:border-slate-600 rounded-md p-4 flex flex-col justify-between transition-all cursor-pointer group"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <span className="text-[11px] font-medium text-blue-400 truncate">
                      {rec.internship.company}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-blue-900/60 text-blue-300 border border-blue-700/50 font-semibold">
                      {rec.score}% Match
                    </span>
                  </div>
                  <h3 className="font-medium text-xs sm:text-sm text-white group-hover:text-blue-300 line-clamp-1 transition-colors">
                    {rec.internship.title}
                  </h3>
                  <div className="text-[11px] text-slate-400 mt-1 flex items-center gap-2">
                    <span>{rec.internship.city || "India"}</span>
                    <span>•</span>
                    <span className="capitalize">{rec.internship.work_type || "Hybrid"}</span>
                  </div>
                </div>

                <div className="mt-3 pt-3 border-t border-slate-700/60 flex items-center justify-between text-[11px]">
                  <span className="text-slate-300 font-medium truncate">
                    {rec.internship.stipend_text || "Competitive stipend"}
                  </span>
                  <span className="text-blue-400 group-hover:underline">View Details →</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Category Pills (Fast Software-focused Discovery) ── */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-2 scrollbar-none text-xs">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.label}
            onClick={() => {
              setSelectedCategory(cat.id);
              setPage(1);
            }}
            className={`whitespace-nowrap px-3 py-1.5 rounded-full text-xs font-medium transition-colors border ${
              selectedCategory === cat.id
                ? "bg-slate-900 text-white border-slate-900 shadow-sm"
                : "bg-white text-slate-600 border-slate-200 hover:bg-slate-100 hover:text-slate-900"
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Primary Search Bar */}
      <div className="bg-white p-2.5 rounded-md border border-slate-200 shadow-sm flex flex-col sm:flex-row gap-2 items-center">
        {/* Keyword Search */}
        <div className="relative flex-1 w-full">
          <Search className="h-4 w-4 text-slate-400 absolute left-3 top-2.5" />
          <Input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
            placeholder="Search by role, company, or keyword..."
            className="pl-9 h-9 text-xs sm:text-sm"
          />
        </div>

        {/* Location with Auto-Suggest */}
        <div className="relative w-full sm:w-64">
          <MapPin className="h-4 w-4 text-slate-400 absolute left-3 top-2.5" />
          <Input
            type="text"
            value={location}
            onChange={(e) => {
              setLocation(e.target.value);
              setShowLocationSuggestions(true);
              setPage(1);
            }}
            onFocus={() => setShowLocationSuggestions(true)}
            placeholder="City (e.g. Bengaluru)"
            className="pl-9 h-9 text-xs sm:text-sm"
          />
          {showLocationSuggestions && locationSuggestions.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-md z-30 py-1">
              {locationSuggestions.map((loc) => (
                <button
                  key={loc}
                  onClick={() => {
                    setLocation(loc);
                    setShowLocationSuggestions(false);
                    setPage(1);
                  }}
                  className="w-full text-left px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
                >
                  {loc}
                </button>
              ))}
            </div>
          )}
        </div>

        <Button
          variant="outline"
          onClick={() => setShowFilters(!showFilters)}
          className="h-9 px-3 text-xs font-medium sm:w-auto w-full flex items-center justify-center gap-1.5"
        >
          <SlidersHorizontal className="h-3.5 w-3.5 text-slate-500" />
          Filters {activeFilterCount > 0 && `(${activeFilterCount})`}
        </Button>
      </div>

      {/* Collapsible Filter Panel */}
      {showFilters && (
        <div className="p-5 bg-white rounded border border-slate-200 shadow-sm space-y-4 animate-in fade-in duration-150">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-800">
              Filter Listings
            </h3>
            {activeFilterCount > 0 && (
              <button
                onClick={handleClearAllFilters}
                className="text-xs text-blue-600 hover:underline flex items-center gap-1 font-medium"
              >
                <RotateCcw className="h-3 w-3" /> Clear All Filters
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Work Mode */}
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1.5">Work Mode</label>
              <div className="flex flex-wrap gap-1.5">
                {[
                  { id: undefined, label: "All" },
                  { id: "remote", label: "Remote" },
                  { id: "hybrid", label: "Hybrid" },
                  { id: "onsite", label: "Onsite" },
                ].map((item) => (
                  <button
                    key={item.label}
                    onClick={() => {
                      setWorkType(item.id as WorkType);
                      setPage(1);
                    }}
                    className={`text-xs px-2.5 py-1 rounded border transition-colors ${
                      workType === item.id
                        ? "bg-blue-600 text-white border-blue-600 font-medium"
                        : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Minimum Stipend */}
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1.5">
                Minimum Monthly Stipend
              </label>
              <select
                value={minStipend ?? ""}
                onChange={(e) => {
                  setMinStipend(e.target.value ? Number(e.target.value) : undefined);
                  setPage(1);
                }}
                className="w-full h-8 text-xs rounded border border-slate-300 bg-white px-2.5 text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-600"
              >
                <option value="">Any Amount</option>
                <option value="15000">₹15,000+ / mo</option>
                <option value="30000">₹30,000+ / mo</option>
                <option value="50000">₹50,000+ / mo</option>
                <option value="75000">₹75,000+ / mo</option>
                <option value="100000">₹1,00,000+ / mo</option>
              </select>
            </div>

            {/* Status Filter */}
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1.5">Listing Status</label>
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full h-8 text-xs rounded border border-slate-300 bg-white px-2.5 text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-600"
              >
                <option value="open">Open Listings Only</option>
                <option value="closing_soon">Closing Soon (within 7 days)</option>
                <option value="all">Include Closed / Expired</option>
              </select>
            </div>

            {/* Sort Filter */}
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1.5">Sort By</label>
              <select
                value={sort}
                onChange={(e) => {
                  setSort(e.target.value as any);
                  setPage(1);
                }}
                className="w-full h-8 text-xs rounded border border-slate-300 bg-white px-2.5 text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-600"
              >
                <option value="newest">Newest First (Software Prioritized)</option>
                <option value="deadline">Earliest Deadline</option>
                <option value="stipend">Highest Stipend</option>
              </select>
            </div>
          </div>

          {/* Skill Filter & Typeahead */}
          <div className="pt-2 border-t border-slate-100">
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-slate-700">Filter by Specific Skills</label>
              {selectedSkills.length > 1 && (
                <div className="flex items-center gap-2 text-xs text-slate-600">
                  <label className="inline-flex items-center gap-1">
                    <input
                      type="radio"
                      name="skillsMatch"
                      checked={skillsMatch === "all"}
                      onChange={() => setSkillsMatch("all")}
                      className="text-blue-600"
                    />
                    Match All
                  </label>
                  <label className="inline-flex items-center gap-1">
                    <input
                      type="radio"
                      name="skillsMatch"
                      checked={skillsMatch === "any"}
                      onChange={() => setSkillsMatch("any")}
                      className="text-blue-600"
                    />
                    Match Any
                  </label>
                </div>
              )}
            </div>

            <div className="relative max-w-md">
              <Input
                type="text"
                value={skillInput}
                onChange={(e) => setSkillInput(e.target.value)}
                placeholder="Type a skill (e.g. React, Python, Docker)..."
                className="h-8 text-xs"
              />
              {skillSuggestions.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-md z-30 py-1">
                  {skillSuggestions.map((s) => (
                    <button
                      key={s}
                      onClick={() => handleAddSkill(s)}
                      className="w-full text-left px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
                    >
                      + {s}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {selectedSkills.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2.5">
                {selectedSkills.map((skill) => (
                  <span
                    key={skill}
                    className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded bg-blue-50 border border-blue-200 text-blue-800 text-xs font-medium"
                  >
                    {skill}
                    <button
                      onClick={() => handleRemoveSkill(skill)}
                      className="hover:text-blue-900"
                      aria-label={`Remove ${skill}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Results Header */}
      <div className="flex items-center justify-between text-xs text-slate-500 pt-1">
        <span>
          Showing <strong className="text-slate-800">{internships.length}</strong> of{" "}
          <strong className="text-slate-800">{total}</strong> internships
        </span>

        <div className="flex items-center gap-3">
          {activeFilterCount > 0 && (
            <button onClick={handleClearAllFilters} className="text-blue-600 hover:underline">
              Reset filters ({activeFilterCount})
            </button>
          )}
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-1 text-slate-500 hover:text-slate-800 disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`h-3 w-3 ${refreshing ? "animate-spin" : ""}`} />
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>

      {/* Main Grid or Loading State */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="rounded-md border border-slate-200 bg-white p-4 sm:p-5 space-y-3 animate-pulse"
            >
              <div className="flex justify-between items-start">
                <div className="h-4 w-28 bg-slate-200 rounded" />
                <div className="h-4 w-16 bg-slate-200 rounded" />
              </div>
              <div className="h-5 w-3/4 bg-slate-200 rounded" />
              <div className="space-y-2">
                <div className="h-3 w-1/2 bg-slate-100 rounded" />
                <div className="h-3 w-2/3 bg-slate-100 rounded" />
              </div>
            </div>
          ))}
        </div>
      ) : internships.length === 0 ? (
        /* Empty State */
        <div className="p-12 text-center rounded-md border border-slate-200 bg-white space-y-3">
          <div className="h-10 w-10 rounded bg-slate-100 flex items-center justify-center mx-auto text-slate-400">
            <Search className="h-5 w-5" />
          </div>
          <h3 className="font-semibold text-slate-800 text-sm">No matching internships found</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Try adjusting your search query, location, or clearing specific filters.
          </p>
          <Button variant="outline" size="sm" onClick={handleClearAllFilters} className="h-8 text-xs">
            Clear Filters
          </Button>
        </div>
      ) : (
        /* Listings Grid */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {internships.map((internship) => (
            <InternshipCard
              key={internship.id}
              internship={internship}
              isSaved={savedIds.has(internship.id)}
              onViewDetails={onViewDetails}
              onSavedChange={onSavedChange}
            />
          ))}
        </div>
      )}

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-6 border-t border-slate-200">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="text-xs"
          >
            <ChevronLeft className="h-4 w-4 mr-1" /> Previous
          </Button>

          <span className="text-xs text-slate-600 px-3 font-medium">
            Page {page} of {totalPages}
          </span>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="text-xs"
          >
            Next <ChevronRight className="h-4 w-4 ml-1" />
          </Button>
        </div>
      )}
    </div>
  );
};
