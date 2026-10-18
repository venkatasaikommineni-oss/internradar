import React, { useState, useEffect } from "react";
import {
  Building2,
  MapPin,
  Calendar,
  Clock,
  DollarSign,
  ExternalLink,
  ShieldCheck,
  Bookmark,
  Share2,
  CheckCircle2,
  AlertTriangle,
  FileText,
  GraduationCap,
  Briefcase,
} from "lucide-react";
import { Internship } from "../types";
import { Dialog, DialogHeader, DialogBody, DialogFooter } from "./ui/dialog";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { formatINR, formatDate, getDaysRemaining } from "../lib/utils";
import { api } from "../lib/api";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";

interface InternshipDetailModalProps {
  internship: Internship | null;
  open: boolean;
  onClose: () => void;
  isSaved?: boolean;
  onSavedChange?: (internshipId: number, saved: boolean) => void;
  initialNote?: string;
}

export const InternshipDetailModal: React.FC<InternshipDetailModalProps> = ({
  internship,
  open,
  onClose,
  isSaved: initialIsSaved = false,
  onSavedChange,
  initialNote = "",
}) => {
  const { user, isAuthenticated } = useAuth();
  const { success, error, info } = useToast();

  const [saved, setSaved] = useState(initialIsSaved);
  const [note, setNote] = useState(initialNote);
  const [savingNote, setSavingNote] = useState(false);

  useEffect(() => {
    setSaved(initialIsSaved);
    setNote(initialNote || "");
  }, [initialIsSaved, initialNote, internship]);

  useEffect(() => {
    if (internship && open && isAuthenticated) {
      // Record view activity
      api.activity.trackView(internship.id).catch(() => {});
    }
  }, [internship, open, isAuthenticated]);

  if (!internship) return null;

  const daysLeft = getDaysRemaining(internship.deadline);

  const handleToggleSave = async () => {
    if (!isAuthenticated) {
      info("Authentication Required", "Please sign in to save internships.");
      return;
    }
    try {
      if (saved) {
        await api.saved.unsave(internship.id);
        setSaved(false);
        onSavedChange?.(internship.id, false);
        success("Removed from saved internships");
      } else {
        await api.saved.save(internship.id, note || undefined);
        setSaved(true);
        onSavedChange?.(internship.id, true);
        success("Saved internship");
      }
    } catch {
      error("Error saving internship");
    }
  };

  const handleSaveNote = async () => {
    if (!isAuthenticated || !saved) return;
    setSavingNote(true);
    try {
      await api.saved.save(internship.id, note);
      success("Notes updated");
    } catch {
      error("Failed to update notes");
    } finally {
      setSavingNote(false);
    }
  };

  const handleApply = async () => {
    if (internship.status === "expired") {
      info("Application Closed", "This listing has passed its application deadline.");
      return;
    }

    if (isAuthenticated) {
      try {
        await api.activity.trackApply(internship.id);
      } catch {
        // Continue
      }
    }

    if (internship.application_url) {
      window.open(internship.application_url, "_blank", "noopener,noreferrer");
    } else {
      error("Application URL Unavailable", "No direct application link is configured for this posting.");
    }
  };

  const handleCopyLink = () => {
    const url = `${window.location.origin}/#discover?id=${internship.id}`;
    navigator.clipboard.writeText(url);
    success("Link copied to clipboard");
  };

  const userSkills = user?.skills || [];

  return (
    <Dialog open={open} onOpenChange={onClose} maxWidth="max-w-3xl">
      <DialogHeader
        title={internship.title}
        description={`${internship.company} · ${internship.location || internship.city || "India"}`}
        onClose={onClose}
      />

      <DialogBody className="space-y-6">
        {/* Source & Status Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-slate-50 rounded-md border border-slate-200 text-xs">
          <div className="flex items-center gap-2 text-slate-600">
            <span>Source:</span>
            <span className="font-mono text-slate-800">{internship.source_name}</span>
          </div>

          <div className="flex items-center gap-2">
            {internship.status === "open" && (
              <Badge variant="success">Open</Badge>
            )}
            {internship.status === "closing_soon" && (
              <Badge variant="warning">
                Closing soon {daysLeft != null ? `(${daysLeft}d left)` : ""}
              </Badge>
            )}
            {internship.status === "expired" && (
              <Badge variant="secondary">Closed</Badge>
            )}
            {internship.status === "unverified" && (
              <Badge variant="outline">Unverified</Badge>
            )}
          </div>
        </div>

        {/* Key Metrics Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3.5 rounded-md border border-slate-200 bg-white">
          <div>
            <span className="text-[11px] font-medium text-slate-500 block mb-0.5">
              Stipend
            </span>
            <p className="font-semibold text-xs sm:text-sm text-slate-900">
              {internship.stipend_text || (internship.stipend_max ? `${formatINR(internship.stipend_max)}/mo` : "Not disclosed")}
            </p>
          </div>

          <div>
            <span className="text-[11px] font-medium text-slate-500 block mb-0.5">
              Work Mode
            </span>
            <p className="font-semibold text-xs sm:text-sm text-slate-900 capitalize">
              {internship.work_type || "Onsite"}
            </p>
          </div>

          <div>
            <span className="text-[11px] font-medium text-slate-500 block mb-0.5">
              Duration
            </span>
            <p className="font-semibold text-xs sm:text-sm text-slate-900">
              {internship.duration_text || (internship.duration_months ? `${internship.duration_months} months` : "Flexible")}
            </p>
          </div>

          <div>
            <span className="text-[11px] font-medium text-slate-500 block mb-0.5">
              Deadline
            </span>
            <p className="font-semibold text-xs sm:text-sm text-slate-900">
              {internship.deadline ? formatDate(internship.deadline) : "Rolling"}
            </p>
          </div>
        </div>

        {/* Required Skills & Student Match */}
        <div>
          <h4 className="text-xs font-semibold text-slate-800 mb-2">
            Required Skills ({internship.skills.length})
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {internship.skills.map((skill) => {
              const matchesUser = userSkills.includes(skill);
              return (
                <span
                  key={skill}
                  className={`text-xs px-2.5 py-0.5 rounded border inline-flex items-center gap-1 ${
                    matchesUser
                      ? "bg-blue-50 text-blue-800 border-blue-200 font-medium"
                      : "bg-slate-50 text-slate-700 border-slate-200"
                  }`}
                >
                  {matchesUser && <CheckCircle2 className="h-3 w-3 text-blue-600" />}
                  {skill}
                </span>
              );
            })}
          </div>
        </div>

        {/* Eligibility Requirements */}
        <div>
          <h4 className="text-xs font-semibold text-slate-800 mb-1.5">
            Eligibility
          </h4>
          <div className="p-3 bg-slate-50 rounded-md border border-slate-200 text-xs text-slate-700 space-y-1.5">
            {internship.eligibility ? (
              <p className="leading-relaxed">{internship.eligibility}</p>
            ) : (
              <p className="text-slate-500">Not specified</p>
            )}

            {internship.grad_years && internship.grad_years.length > 0 && (
              <div className="pt-2 border-t border-slate-200 flex items-center gap-2">
                <span className="font-medium text-slate-700">Target graduation:</span>
                <div className="flex gap-1">
                  {internship.grad_years.map((yr) => (
                    <span key={yr} className="px-1.5 py-0.5 rounded bg-white border border-slate-300 font-mono text-slate-800 text-[11px]">
                      {yr}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Full Job Description */}
        <div>
          <h4 className="text-xs font-semibold text-slate-800 mb-1.5">
            Description
          </h4>
          <div className="p-3.5 rounded-md border border-slate-200 bg-white text-xs text-slate-700 leading-relaxed whitespace-pre-line max-h-56 overflow-y-auto">
            {internship.description || "Refer to the employer application page for full responsibilities and qualifications."}
          </div>
        </div>

        {/* Personal Notes (if Saved) */}
        {saved && isAuthenticated && (
          <div className="p-3 rounded-md border border-slate-200 bg-slate-50">
            <label className="text-xs font-medium text-slate-700 block mb-1">
              Personal note
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="e.g. Applied on Oct 18, follow up next week"
                className="flex-1 h-8 rounded border border-slate-300 bg-white px-2.5 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-600"
              />
              <Button size="sm" variant="outline" onClick={handleSaveNote} loading={savingNote} className="h-8 text-xs">
                Save
              </Button>
            </div>
          </div>
        )}
      </DialogBody>

      <DialogFooter>
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleCopyLink} className="h-8 text-xs">
              <Share2 className="h-3.5 w-3.5 mr-1" /> Share
            </Button>
            <Button
              variant={saved ? "secondary" : "outline"}
              size="sm"
              onClick={handleToggleSave}
              className="h-8 text-xs"
            >
              <Bookmark className={`h-3.5 w-3.5 mr-1 ${saved ? "fill-current text-blue-600" : ""}`} />
              {saved ? "Saved" : "Save"}
            </Button>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={onClose} className="h-8 text-xs">
              Close
            </Button>
            <Button
              size="sm"
              onClick={handleApply}
              disabled={internship.status === "expired"}
              className="h-8 text-xs gap-1.5"
            >
              Apply <ExternalLink className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </DialogFooter>
    </Dialog>
  );
};
