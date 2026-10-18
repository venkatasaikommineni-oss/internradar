import React, { useState, useEffect } from "react";
import { CheckSquare, Eye, Bookmark, ExternalLink, Calendar, Building2, MapPin } from "lucide-react";
import { Activity, Internship } from "../types";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { formatDate } from "../lib/utils";
import { useAuth } from "../context/AuthContext";

interface AppliedPageProps {
  onViewDetails: (internship: Internship) => void;
  onExplore: () => void;
}

export const AppliedPage: React.FC<AppliedPageProps> = ({
  onViewDetails,
  onExplore,
}) => {
  const { isAuthenticated } = useAuth();
  const [activities, setActivities] = useState<Activity[]>([]);
  const [filterAction, setFilterAction] = useState<string>("apply_clicked");
  const [loading, setLoading] = useState(true);

  const fetchActivities = async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    try {
      const data = await api.activity.list({
        action: filterAction === "all" ? undefined : filterAction,
        limit: 50,
      });
      setActivities(data.items);
    } catch {
      setActivities([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      fetchActivities();
    } else {
      setLoading(false);
    }
  }, [isAuthenticated, filterAction]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Page Header */}
      <div className="border-b border-slate-200 pb-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900">
            Applications
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1 leading-relaxed">
            History of internships you have applied to or viewed.
          </p>
        </div>

        {/* Action Type Filter */}
        <div className="flex items-center gap-1 p-0.5 bg-slate-100 rounded-md border border-slate-200 text-xs self-start sm:self-auto">
          {[
            { id: "apply_clicked", label: "Applied" },
            { id: "viewed", label: "Viewed" },
            { id: "all", label: "All" },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setFilterAction(item.id)}
              className={`px-3 py-1 rounded transition-colors text-xs font-medium ${
                filterAction === item.id
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-16 rounded-md border border-slate-200 bg-white p-4 animate-pulse" />
          ))}
        </div>
      ) : activities.length === 0 ? (
        <div className="p-12 text-center rounded-md border border-slate-200 bg-white space-y-3">
          <CheckSquare className="h-8 w-8 text-slate-300 mx-auto" />
          <h3 className="font-semibold text-slate-800 text-sm">No activity recorded</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Internships you open or apply to will be tracked here.
          </p>
          <Button size="sm" onClick={onExplore} className="h-8 text-xs">
            Browse Internships
          </Button>
        </div>
      ) : (
        <div className="divide-y divide-slate-200 rounded-md border border-slate-200 bg-white shadow-sm overflow-hidden">
          {activities.map((act) => {
            const hasInternship = !!act.internship;
            const actionLabel =
              act.action === "apply_clicked"
                ? "Applied"
                : act.action === "viewed"
                ? "Viewed"
                : "Saved";

            const actionBadgeVariant =
              act.action === "apply_clicked"
                ? "success"
                : act.action === "viewed"
                ? "secondary"
                : "default";

            return (
              <div
                key={act.id}
                onClick={() => act.internship && onViewDetails(act.internship)}
                className={`p-3.5 flex items-center justify-between gap-4 transition-colors ${
                  hasInternship ? "hover:bg-slate-50 cursor-pointer" : ""
                }`}
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge variant={actionBadgeVariant}>{actionLabel}</Badge>
                    <span className="text-xs text-slate-400 font-mono">
                      {formatDate(act.timestamp)}
                    </span>
                  </div>

                  {act.internship ? (
                    <div>
                      <h4 className="font-semibold text-sm text-slate-900 hover:text-blue-600 transition-colors">
                        {act.internship.title}
                      </h4>
                      <p className="text-xs text-slate-500 flex items-center gap-2 mt-0.5">
                        <span className="font-medium text-slate-700">{act.internship.company}</span>
                        <span>·</span>
                        <span>{act.internship.location || "India"}</span>
                      </p>
                    </div>
                  ) : (
                    <p className="text-xs text-slate-400 italic">
                      Listing #{act.internship_id} (inactive)
                    </p>
                  )}
                </div>

                {act.internship?.application_url && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      window.open(act.internship!.application_url, "_blank", "noopener,noreferrer");
                    }}
                    className="text-xs h-7 gap-1 shrink-0 text-slate-600 hover:text-slate-900"
                  >
                    View posting <ExternalLink className="h-3 w-3" />
                  </Button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
