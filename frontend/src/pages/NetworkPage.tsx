import React, { useState, useEffect } from "react";
import { Users, Search, UserPlus, Check, X, Building, MapPin, GraduationCap, Clock } from "lucide-react";
import { PublicUser, Connection } from "../types";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";

export const NetworkPage: React.FC = () => {
  const { user, isAuthenticated } = useAuth();
  const { success, error, info } = useToast();

  const [activeSubTab, setActiveSubTab] = useState<"directory" | "connections">("directory");
  const [students, setStudents] = useState<PublicUser[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);

  // Search
  const [searchQuery, setSearchQuery] = useState("");
  const [skillFilter, setSkillFilter] = useState("");

  const fetchDirectory = async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    try {
      const data = await api.network.searchStudents({
        q: searchQuery.trim() || undefined,
        skills: skillFilter.trim() || undefined,
        limit: 30,
      });
      setStudents(data);
    } catch {
      setStudents([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchConnections = async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    try {
      const data = await api.network.listConnections();
      setConnections(data);
    } catch {
      setConnections([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeSubTab === "directory") {
      fetchDirectory();
    } else {
      fetchConnections();
    }
  }, [activeSubTab, searchQuery, skillFilter, isAuthenticated]);

  const handleSendConnection = async (targetId: number) => {
    try {
      await api.network.sendRequest(targetId, "Interested in connecting regarding internships.");
      success("Connection Request Sent");
      fetchDirectory();
    } catch (err: any) {
      error("Unable to send request", err.message);
    }
  };

  const handleRespond = async (connectionId: number, action: "accept" | "reject") => {
    try {
      await api.network.respondRequest(connectionId, action);
      success(action === "accept" ? "Connection Accepted" : "Connection Request Declined");
      fetchConnections();
    } catch (err: any) {
      error("Action failed", err.message);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header */}
      <div className="border-b border-slate-200 pb-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Student Network
          </h1>
          <p className="text-xs text-slate-500 mt-1 max-w-2xl leading-relaxed">
            Connect with student peers, discover shared skills, and exchange internship updates.
          </p>
        </div>

        {/* Tab Toggle */}
        <div className="flex items-center gap-1 p-1 bg-slate-100 rounded border border-slate-200 text-xs">
          <button
            onClick={() => setActiveSubTab("directory")}
            className={`px-3 py-1.5 rounded transition-colors font-medium ${
              activeSubTab === "directory" ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Directory
          </button>
          <button
            onClick={() => setActiveSubTab("connections")}
            className={`px-3 py-1.5 rounded transition-colors font-medium ${
              activeSubTab === "connections" ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Connections ({connections.length})
          </button>
        </div>
      </div>

      {activeSubTab === "directory" ? (
        <div className="space-y-6">
          {/* Search Inputs */}
          <div className="bg-white p-3 rounded border border-slate-200 shadow-sm flex flex-col sm:flex-row gap-2.5">
            <div className="relative flex-1">
              <Search className="h-4 w-4 text-slate-400 absolute left-3 top-2.5" />
              <Input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search students by name or college..."
                className="pl-9 h-9 text-xs"
              />
            </div>
            <div className="w-full sm:w-64">
              <Input
                type="text"
                value={skillFilter}
                onChange={(e) => setSkillFilter(e.target.value)}
                placeholder="Filter by skill..."
                className="h-9 text-xs"
              />
            </div>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="h-40 rounded border border-slate-200 bg-white p-5 animate-pulse" />
              ))}
            </div>
          ) : students.length === 0 ? (
            <div className="p-12 text-center rounded border border-slate-200 bg-white space-y-2">
              <Users className="h-10 w-10 text-slate-300 mx-auto" />
              <h3 className="font-semibold text-slate-800 text-sm">No students match your query</h3>
              <p className="text-xs text-slate-500">Try modifying your search criteria or clear the skill filter.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {students.map((student) => (
                <div
                  key={student.id}
                  className="rounded border border-slate-200 bg-white p-5 shadow-sm space-y-3 flex flex-col justify-between"
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h4 className="font-bold text-slate-900 text-sm">
                          {student.full_name || "Engineering Student"}
                        </h4>
                        <p className="text-xs text-slate-500 flex items-center gap-1 mt-0.5">
                          <Building className="h-3 w-3 text-slate-400 shrink-0" />
                          <span className="truncate">{student.college || "University Student"}</span>
                        </p>
                      </div>

                      <div className="h-8 w-8 rounded bg-blue-100 text-blue-800 font-semibold text-xs flex items-center justify-center shrink-0 uppercase">
                        {(student.full_name || "S").charAt(0)}
                      </div>
                    </div>

                    <div className="text-xs text-slate-600 space-y-1 pt-1">
                      {student.degree && (
                        <p className="flex items-center gap-1.5 text-slate-500">
                          <GraduationCap className="h-3.5 w-3.5 text-slate-400" />
                          <span>{student.degree} {student.branch ? `in ${student.branch}` : ""} {student.graduation_year ? `(${student.graduation_year})` : ""}</span>
                        </p>
                      )}
                      {student.location && (
                        <p className="flex items-center gap-1.5 text-slate-500">
                          <MapPin className="h-3.5 w-3.5 text-slate-400" />
                          <span>{student.location}</span>
                        </p>
                      )}
                    </div>

                    {student.skills && student.skills.length > 0 && (
                      <div className="pt-2 flex flex-wrap gap-1">
                        {student.skills.slice(0, 4).map((s) => (
                          <span key={s} className="text-[11px] px-2 py-0.5 rounded bg-slate-50 border border-slate-200 text-slate-600">
                            {s}
                          </span>
                        ))}
                        {student.skills.length > 4 && (
                          <span className="text-[11px] text-slate-400">+{student.skills.length - 4}</span>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="pt-3 border-t border-slate-100 flex justify-end">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleSendConnection(student.id)}
                      className="text-xs gap-1.5"
                    >
                      <UserPlus className="h-3.5 w-3.5" /> Connect
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        /* My Connections Sub-Tab */
        <div className="space-y-4">
          {loading ? (
            <div className="h-32 rounded border border-slate-200 bg-white animate-pulse" />
          ) : connections.length === 0 ? (
            <div className="p-12 text-center rounded border border-slate-200 bg-white space-y-2">
              <Users className="h-10 w-10 text-slate-300 mx-auto" />
              <h3 className="font-semibold text-slate-800 text-sm">No active connections yet</h3>
              <p className="text-xs text-slate-500">
                Explore the Student Directory to connect with classmates and peers.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-200 rounded border border-slate-200 bg-white shadow-sm overflow-hidden">
              {connections.map((conn) => {
                const isIncomingPending = conn.status === "pending" && conn.addressee_id === user?.id;

                return (
                  <div key={conn.id} className="p-4 flex items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={
                            conn.status === "accepted"
                              ? "success"
                              : conn.status === "pending"
                              ? "warning"
                              : "secondary"
                          }
                          className="capitalize"
                        >
                          {conn.status}
                        </Badge>
                        <span className="text-xs text-slate-500 font-mono">
                          {conn.other_user?.full_name || "Student"}
                        </span>
                      </div>
                      <p className="text-xs text-slate-600">
                        {conn.other_user?.college} {conn.other_user?.location ? `· ${conn.other_user.location}` : ""}
                      </p>
                      {conn.message && (
                        <p className="text-xs text-slate-500 italic">"{conn.message}"</p>
                      )}
                    </div>

                    {isIncomingPending ? (
                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          onClick={() => handleRespond(conn.id, "accept")}
                          className="h-8 text-xs gap-1"
                        >
                          <Check className="h-3.5 w-3.5" /> Accept
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleRespond(conn.id, "reject")}
                          className="h-8 text-xs gap-1"
                        >
                          <X className="h-3.5 w-3.5" /> Decline
                        </Button>
                      </div>
                    ) : (
                      <span className="text-xs text-slate-400 capitalize">{conn.status}</span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
