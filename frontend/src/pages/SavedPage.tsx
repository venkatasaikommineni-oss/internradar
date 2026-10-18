import React, { useState, useEffect } from "react";
import { Bookmark, ExternalLink, Trash2, Edit3, Check, X, Building2, MapPin, DollarSign, Calendar } from "lucide-react";
import { SavedInternship, Internship } from "../types";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { formatINR, formatDate } from "../lib/utils";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";

interface SavedPageProps {
  onViewDetails: (internship: Internship) => void;
  onSavedChange: (internshipId: number, saved: boolean) => void;
  onExplore: () => void;
}

export const SavedPage: React.FC<SavedPageProps> = ({
  onViewDetails,
  onSavedChange,
  onExplore,
}) => {
  const { isAuthenticated } = useAuth();
  const { success, error, info } = useToast();
  const [savedItems, setSavedItems] = useState<SavedInternship[]>([]);
  const [loading, setLoading] = useState(true);

  // Note editing state
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editNoteText, setEditNoteText] = useState("");

  const fetchSaved = async () => {
    setLoading(true);
    try {
      const data = await api.saved.list();
      setSavedItems(data);
    } catch {
      setSavedItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      fetchSaved();
    } else {
      setLoading(false);
    }
  }, [isAuthenticated]);

  const handleUnsave = async (internshipId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.saved.unsave(internshipId);
      setSavedItems((prev) => prev.filter((item) => item.internship.id !== internshipId));
      onSavedChange(internshipId, false);
      success("Removed from saved internships");
    } catch {
      error("Failed to remove bookmark");
    }
  };

  const handleStartEditNote = (item: SavedInternship, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(item.internship.id);
    setEditNoteText(item.notes || "");
  };

  const handleSaveNote = async (internshipId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.saved.save(internshipId, editNoteText);
      setSavedItems((prev) =>
        prev.map((item) =>
          item.internship.id === internshipId ? { ...item, notes: editNoteText } : item
        )
      );
      setEditingId(null);
      success("Note updated");
    } catch {
      error("Failed to update note");
    }
  };

  const handleApply = async (internship: Internship, e: React.MouseEvent) => {
    e.stopPropagation();
    if (internship.status === "expired") {
      info("Listing Expired", "This internship deadline has passed.");
      return;
    }
    if (isAuthenticated) {
      try {
        await api.activity.trackApply(internship.id);
      } catch {}
    }
    if (internship.application_url) {
      window.open(internship.application_url, "_blank", "noopener,noreferrer");
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Page Header */}
      <div className="border-b border-slate-200 pb-5 flex items-center justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900">
            Saved Internships
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1 leading-relaxed">
            Your saved opportunities and personal application notes.
          </p>
        </div>
        <span className="text-xs text-slate-500 font-medium">
          {savedItems.length} {savedItems.length === 1 ? "role" : "roles"}
        </span>
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-28 rounded-md border border-slate-200 bg-white p-4 sm:p-5 animate-pulse" />
          ))}
        </div>
      ) : savedItems.length === 0 ? (
        <div className="p-12 text-center rounded-md border border-slate-200 bg-white space-y-3">
          <Bookmark className="h-8 w-8 text-slate-300 mx-auto" />
          <h3 className="font-semibold text-slate-800 text-sm">No saved internships</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Click the bookmark icon on any internship listing to add it here.
          </p>
          <Button size="sm" onClick={onExplore} className="h-8 text-xs">
            Browse Internships
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {savedItems.map(({ internship, notes, saved_at }) => {
            const isEditing = editingId === internship.id;

            return (
              <div
                key={internship.id}
                onClick={() => onViewDetails(internship)}
                className="rounded-md border border-slate-200 bg-white p-4 sm:p-5 shadow-sm hover:border-slate-300 transition-all cursor-pointer space-y-3"
              >
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      <span className="font-semibold text-slate-800">{internship.company}</span>
                      <span>·</span>
                      <span className="capitalize">{internship.work_type || "Onsite"}</span>
                      <span>·</span>
                      <span>Saved on {formatDate(saved_at)}</span>
                    </div>

                    <h3 className="font-semibold text-slate-900 text-base hover:text-blue-600 transition-colors">
                      {internship.title}
                    </h3>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600 pt-0.5">
                      <span className="flex items-center gap-1">
                        <MapPin className="h-3.5 w-3.5 text-slate-400" />
                        {internship.location || internship.city || "India"}
                      </span>
                      <span className="flex items-center gap-1">
                        <DollarSign className="h-3.5 w-3.5 text-slate-400" />
                        {internship.stipend_text || (internship.stipend_max ? `${formatINR(internship.stipend_max)}/mo` : "Not stated")}
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3.5 w-3.5 text-slate-400" />
                        {internship.deadline ? `Deadline: ${formatDate(internship.deadline)}` : "Rolling"}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-start">
                    <Button
                      size="sm"
                      onClick={(e) => handleApply(internship, e)}
                      disabled={internship.status === "expired"}
                      className="text-xs h-8 gap-1.5"
                    >
                      Apply <ExternalLink className="h-3 w-3" />
                    </Button>
                    <button
                      onClick={(e) => handleUnsave(internship.id, e)}
                      className="p-1.5 rounded border border-slate-200 text-slate-400 hover:text-rose-600 hover:border-rose-200 transition-colors"
                      title="Remove from saved"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>

                {/* Notes Section */}
                <div
                  onClick={(e) => e.stopPropagation()}
                  className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs"
                >
                  {isEditing ? (
                    <div className="flex-1 flex items-center gap-2">
                      <input
                        type="text"
                        value={editNoteText}
                        onChange={(e) => setEditNoteText(e.target.value)}
                        placeholder="Add your note..."
                        className="flex-1 h-7 rounded border border-slate-300 bg-white px-2 text-xs text-slate-800"
                        autoFocus
                      />
                      <Button
                        size="sm"
                        onClick={(e) => handleSaveNote(internship.id, e)}
                        className="h-7 px-2.5 text-xs"
                      >
                        <Check className="h-3.5 w-3.5" />
                      </Button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditingId(null);
                        }}
                        className="p-1 text-slate-400 hover:text-slate-600"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ) : (
                    <div className="flex-1 flex items-center justify-between text-slate-600">
                      <span className="italic text-slate-500">
                        {notes ? `Note: "${notes}"` : "No personal notes added"}
                      </span>
                      <button
                        onClick={(e) => handleStartEditNote({ internship, notes, saved_at }, e)}
                        className="text-slate-400 hover:text-slate-700 flex items-center gap-1 font-medium ml-2"
                      >
                        <Edit3 className="h-3 w-3" /> {notes ? "Edit Note" : "Add Note"}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
