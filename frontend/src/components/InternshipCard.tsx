import React, { useState } from "react";
import { Building2, MapPin, Calendar, Clock, DollarSign, Bookmark, ExternalLink, ShieldCheck, AlertCircle } from "lucide-react";
import { Internship } from "../types";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { formatINR, formatDate, getDaysRemaining } from "../lib/utils";
import { api } from "../lib/api";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";

interface InternshipCardProps {
  internship: Internship;
  isSaved?: boolean;
  onViewDetails: (internship: Internship) => void;
  onSavedChange?: (internshipId: number, saved: boolean) => void;
  showMatchScore?: number;
  matchedSkills?: string[];
}

export const InternshipCard: React.FC<InternshipCardProps> = ({
  internship,
  isSaved: initialIsSaved = false,
  onViewDetails,
  onSavedChange,
  showMatchScore,
  matchedSkills = [],
}) => {
  const { isAuthenticated } = useAuth();
  const { success, error, info } = useToast();
  const [saved, setSaved] = useState(initialIsSaved);
  const [saving, setSaving] = useState(false);

  const daysLeft = getDaysRemaining(internship.deadline);

  const handleToggleSave = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!isAuthenticated) {
      info("Authentication Required", "Please sign in to save internships to your account.");
      return;
    }
    setSaving(true);
    try {
      if (saved) {
        await api.saved.unsave(internship.id);
        setSaved(false);
        onSavedChange?.(internship.id, false);
        success("Removed from saved internships");
      } else {
        await api.saved.save(internship.id);
        setSaved(true);
        onSavedChange?.(internship.id, true);
        success("Saved internship", internship.title);
      }
    } catch {
      error("Failed to update bookmark", "Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const handleApplyClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (internship.status === "expired") {
      info("Application Expired", "This listing has passed its application deadline.");
      return;
    }
    // Track application click in backend if user is authenticated
    if (isAuthenticated) {
      try {
        await api.activity.trackApply(internship.id);
      } catch {
        // Continue even if tracking fails
      }
    }
    // Open verified application URL directly in a new tab
    if (internship.application_url) {
      window.open(internship.application_url, "_blank", "noopener,noreferrer");
    } else {
      error("Application URL Unavailable", "No valid application URL is associated with this listing.");
    }
  };

  const workTypeVariant =
    internship.work_type === "remote"
      ? "work_remote"
      : internship.work_type === "hybrid"
      ? "work_hybrid"
      : "work_onsite";

  return (
    <div
      onClick={() => onViewDetails(internship)}
      className="group rounded-md border border-slate-200 bg-white p-4 sm:p-5 shadow-sm hover:shadow-md hover:border-slate-300 transition-all cursor-pointer flex flex-col justify-between"
    >
      <div>
        {/* Header: Company & Badges */}
        <div className="flex items-start justify-between gap-3 mb-2.5">
          <div className="flex items-center gap-2 min-w-0">
            <div className="h-7 w-7 rounded bg-slate-100 border border-slate-200 text-slate-700 flex items-center justify-center font-semibold text-xs shrink-0 uppercase">
              {internship.company.charAt(0)}
            </div>
            <div className="min-w-0">
              <span className="font-medium text-xs text-slate-900 truncate block">
                {internship.company}
              </span>
              <span className="text-[11px] text-slate-500 truncate block capitalize">
                {internship.location || internship.city || "India"}
                {internship.work_type ? ` · ${internship.work_type}` : ""}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            {showMatchScore != null && (
              <span className="text-[11px] font-semibold text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded">
                {Math.round(showMatchScore)}% match
              </span>
            )}

            {internship.status === "closing_soon" && (
              <Badge variant="warning">Closing soon</Badge>
            )}

            {internship.status === "expired" && (
              <Badge variant="secondary">Closed</Badge>
            )}

            <button
              onClick={handleToggleSave}
              disabled={saving}
              className={`p-1.5 rounded border transition-colors ${
                saved
                  ? "bg-blue-50 border-blue-300 text-blue-700"
                  : "border-slate-200 text-slate-400 hover:text-slate-700 hover:bg-slate-50"
              }`}
              title={saved ? "Remove from saved" : "Save internship"}
              aria-label={saved ? "Saved" : "Save"}
            >
              <Bookmark className={`h-3.5 w-3.5 ${saved ? "fill-current" : ""}`} />
            </button>
          </div>
        </div>

        {/* Title */}
        <h3 className="font-semibold text-slate-900 text-sm sm:text-base leading-snug group-hover:text-blue-600 transition-colors line-clamp-2 mb-3">
          {internship.title}
        </h3>

        {/* Key Attributes */}
        <div className="grid grid-cols-2 gap-y-1.5 gap-x-2 text-xs text-slate-600 mb-3.5">
          <div className="flex items-center gap-1.5 truncate">
            <DollarSign className="h-3.5 w-3.5 text-slate-400 shrink-0" />
            <span className="truncate font-medium text-slate-800">
              {internship.stipend_text || (internship.stipend_max ? `${formatINR(internship.stipend_max)}/mo` : "Unpaid / Not stated")}
            </span>
          </div>

          <div className="flex items-center gap-1.5 truncate">
            <Clock className="h-3.5 w-3.5 text-slate-400 shrink-0" />
            <span className="truncate">
              {internship.duration_text || (internship.duration_months ? `${internship.duration_months} mo` : "Flexible")}
            </span>
          </div>

          <div className="flex items-center gap-1.5 truncate col-span-2">
            <Calendar className="h-3.5 w-3.5 text-slate-400 shrink-0" />
            <span className="truncate text-slate-500">
              {internship.deadline ? `Deadline: ${formatDate(internship.deadline)}` : "Rolling applications"}
              {daysLeft != null && daysLeft > 0 && daysLeft <= 7 && (
                <span className="ml-1.5 text-amber-600 font-medium">({daysLeft}d left)</span>
              )}
            </span>
          </div>
        </div>

        {/* Skills Tags */}
        {internship.skills.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3.5">
            {internship.skills.slice(0, 4).map((skill) => {
              const isMatched = matchedSkills.includes(skill);
              return (
                <span
                  key={skill}
                  className={`text-[11px] px-2 py-0.5 rounded border ${
                    isMatched
                      ? "bg-blue-50 text-blue-800 border-blue-200 font-medium"
                      : "bg-slate-50 text-slate-600 border-slate-200"
                  }`}
                >
                  {skill}
                </span>
              );
            })}
            {internship.skills.length > 4 && (
              <span className="text-[11px] px-1 py-0.5 text-slate-400">
                +{internship.skills.length - 4}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Footer / Buttons */}
      <div className="pt-3 border-t border-slate-100 flex items-center justify-between gap-2 mt-auto">
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation();
            onViewDetails(internship);
          }}
          className="text-xs h-7 px-2.5 text-slate-600 hover:text-slate-900"
        >
          Details
        </Button>

        <Button
          size="sm"
          onClick={handleApplyClick}
          disabled={internship.status === "expired"}
          className="text-xs h-7 px-3 gap-1"
        >
          Apply <ExternalLink className="h-3 w-3" />
        </Button>
      </div>
    </div>
  );
};
