import React, { useState, useEffect } from "react";
import { Sparkles, CheckCircle2, AlertCircle, ArrowRight, UserCheck, Briefcase, SlidersHorizontal, Info } from "lucide-react";
import { Recommendation, Internship } from "../types";
import { api } from "../lib/api";
import { InternshipCard } from "../components/InternshipCard";
import { Button } from "../components/ui/button";
import { useAuth } from "../context/AuthContext";

interface RecommendationsPageProps {
  onViewDetails: (internship: Internship) => void;
  savedIds: Set<number>;
  onSavedChange: (internshipId: number, saved: boolean) => void;
  onNavigateToProfile: () => void;
  onOpenAuth: (mode: "login" | "register") => void;
}

export const RecommendationsPage: React.FC<RecommendationsPageProps> = ({
  onViewDetails,
  savedIds,
  onSavedChange,
  onNavigateToProfile,
  onOpenAuth,
}) => {
  const { user, isAuthenticated, loading: authLoading } = useAuth();
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [notes, setNotes] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [minScore, setMinScore] = useState(30);
  const [includeIneligible, setIncludeIneligible] = useState(false);

  const fetchRecommendations = async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    try {
      const res = await api.recommendations.get({
        min_score: minScore,
        include_ineligible: includeIneligible,
        limit: 30,
      });
      setRecommendations(res.items);
      setNotes(res.notes || []);
    } catch {
      setRecommendations([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      fetchRecommendations();
    } else {
      setLoading(false);
    }
  }, [isAuthenticated, minScore, includeIneligible]);

  if (authLoading) {
    return <div className="max-w-7xl mx-auto px-4 py-12 text-center text-sm text-slate-500">Loading recommendations...</div>;
  }

  if (!isAuthenticated) {
    return (
      <div className="max-w-md mx-auto px-4 py-20 text-center space-y-4">
        <div className="h-10 w-10 rounded-md bg-slate-100 border border-slate-200 text-slate-600 flex items-center justify-center mx-auto">
          <UserCheck className="h-5 w-5" />
        </div>
        <h2 className="text-lg font-semibold text-slate-900 tracking-tight">Sign in to view recommendations</h2>
        <p className="text-xs text-slate-500 leading-relaxed">
          Matches are ranked based on the skills, desired roles, and location saved in your profile.
        </p>
        <div className="pt-2 flex justify-center gap-2">
          <Button size="sm" onClick={() => onOpenAuth("login")} className="h-8 text-xs">
            Sign In
          </Button>
          <Button size="sm" variant="outline" onClick={() => onOpenAuth("register")} className="h-8 text-xs">
            Create Account
          </Button>
        </div>
      </div>
    );
  }

  const hasSkillsOrRoles = (user?.skills?.length ?? 0) > 0 || (user?.desired_roles?.length ?? 0) > 0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Page Header */}
      <div className="border-b border-slate-200 pb-5 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900">
            Recommendations
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-2xl leading-relaxed">
            Internships scored and ranked by skill and role alignment with your profile.
          </p>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <div className="flex items-center gap-2">
            <label className="text-slate-600 font-medium">Minimum match:</label>
            <select
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="h-8 rounded border border-slate-300 bg-white px-2 text-slate-800 text-xs"
            >
              <option value={0}>All (0%+)</option>
              <option value={30}>30%+</option>
              <option value={50}>50%+</option>
              <option value={70}>70%+</option>
            </select>
          </div>

          <label className="flex items-center gap-1.5 text-slate-600 cursor-pointer">
            <input
              type="checkbox"
              checked={includeIneligible}
              onChange={(e) => setIncludeIneligible(e.target.checked)}
              className="rounded border-slate-300 text-blue-600"
            />
            Include all graduation years
          </label>
        </div>
      </div>

      {/* Profile Completeness Advice */}
      {!hasSkillsOrRoles && (
        <div className="p-3.5 rounded-md border border-slate-200 bg-slate-50 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="space-y-0.5 text-slate-700">
            <p className="font-semibold text-slate-900">Complete your profile for better match accuracy</p>
            <p className="text-slate-500">
              Add your technical skills and desired roles to help rank opportunities.
            </p>
          </div>
          <Button size="sm" variant="outline" onClick={onNavigateToProfile} className="shrink-0 text-xs h-7">
            Edit profile
          </Button>
        </div>
      )}

      {/* Backend notes/alerts */}
      {notes.length > 0 && (
        <div className="space-y-1">
          {notes.map((n, idx) => (
            <p key={idx} className="text-xs text-slate-500 flex items-center gap-1.5">
              <Info className="h-3.5 w-3.5 text-slate-400 shrink-0" />
              {n}
            </p>
          ))}
        </div>
      )}

      {/* Recommendations Listing */}
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-28 rounded-md border border-slate-200 bg-white p-5 animate-pulse" />
          ))}
        </div>
      ) : recommendations.length === 0 ? (
        <div className="p-12 text-center rounded-md border border-slate-200 bg-white space-y-3">
          <Briefcase className="h-8 w-8 text-slate-400 mx-auto" />
          <h3 className="font-semibold text-slate-800 text-sm">No matching internships at this score</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Try lowering the minimum match filter or adding additional skills to your profile.
          </p>
          <Button variant="outline" size="sm" onClick={() => setMinScore(0)} className="h-8 text-xs">
            Show all matches
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {recommendations.map((rec) => {
            const fitScore = Math.round(rec.score * 100);
            return (
              <div
                key={rec.internship.id}
                className="rounded-md border border-slate-200 bg-white p-4 sm:p-5 shadow-sm hover:border-slate-300 transition-all flex flex-col md:flex-row gap-4 justify-between"
              >
                {/* Left: Role Details */}
                <div className="space-y-1.5 flex-1">
                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    <span className="font-semibold text-slate-800">
                      {rec.internship.company}
                    </span>
                    <span>·</span>
                    <span className="capitalize">
                      {rec.internship.work_type || "Onsite"}
                    </span>
                    <span>·</span>
                    <span>{rec.internship.location || "India"}</span>
                  </div>

                  <h3
                    onClick={() => onViewDetails(rec.internship)}
                    className="font-semibold text-slate-900 text-base hover:text-blue-600 transition-colors cursor-pointer"
                  >
                    {rec.internship.title}
                  </h3>

                  {/* Match Explanations */}
                  <div className="pt-1 flex flex-wrap gap-1.5 text-xs">
                    {rec.reasons.map((r, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 rounded bg-blue-50 text-blue-800 border border-blue-200 text-[11px] font-medium"
                      >
                        {r}
                      </span>
                    ))}

                    {!rec.eligible && (
                      <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-300 text-[11px]">
                        Outside graduation criteria
                      </span>
                    )}
                  </div>

                  {/* Skills breakdown */}
                  <div className="pt-1 flex flex-wrap items-center gap-1 text-xs">
                    <span className="text-slate-400 text-[11px] mr-1">Matched skills:</span>
                    {rec.matched_skills.map((s) => (
                      <span key={s} className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 text-[11px] font-medium">
                        {s}
                      </span>
                    ))}
                    {rec.missing_skills.slice(0, 3).map((s) => (
                      <span key={s} className="px-1.5 py-0.5 rounded bg-slate-50 text-slate-600 border border-slate-200 text-[11px]">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Right: Score and Action */}
                <div className="flex md:flex-col items-center md:items-end justify-between md:justify-center gap-2.5 shrink-0 pt-3 md:pt-0 border-t md:border-t-0 border-slate-100">
                  <div className="text-left md:text-right">
                    <span className="text-xl font-bold text-blue-700">{fitScore}%</span>
                    <span className="text-[11px] text-slate-400 block">Match</span>
                  </div>

                  <Button size="sm" onClick={() => onViewDetails(rec.internship)} className="h-8 text-xs">
                    View details
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
