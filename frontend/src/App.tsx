import React, { useState, useEffect } from "react";
import { Navbar } from "./components/Navbar";
import { Footer } from "./components/Footer";
import { DiscoverPage } from "./pages/DiscoverPage";
import { RecommendationsPage } from "./pages/RecommendationsPage";
import { SavedPage } from "./pages/SavedPage";
import { AppliedPage } from "./pages/AppliedPage";
import { ProfilePage } from "./pages/ProfilePage";
import { NetworkPage } from "./pages/NetworkPage";
import { InternshipDetailModal } from "./components/InternshipDetailModal";
import { AuthModal } from "./components/AuthModal";
import { ChangePasswordModal } from "./components/ChangePasswordModal";
import { Internship } from "./types";
import { api } from "./lib/api";
import { useAuth } from "./context/AuthContext";

export const App: React.FC = () => {
  const { isAuthenticated } = useAuth();

  // Navigation tab: discover | matches | saved | applied | profile | network
  const [activeTab, setActiveTab] = useState<string>("discover");

  // Detail Modal
  const [selectedInternship, setSelectedInternship] = useState<Internship | null>(null);

  // Auth Modal
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState<"login" | "register">("login");

  // Change Password Modal
  const [changePasswordOpen, setChangePasswordOpen] = useState(false);

  // Saved IDs set for instant bookmark state across cards
  const [savedIds, setSavedIds] = useState<Set<number>>(new Set());

  // Listen to hash changes for direct deep linking
  useEffect(() => {
    const handleHash = () => {
      const hash = window.location.hash.replace(/^#\/?/, "");
      if (hash.startsWith("login")) {
        setAuthModalMode("login");
        setAuthModalOpen(true);
      } else if (hash.startsWith("register")) {
        setAuthModalMode("register");
        setAuthModalOpen(true);
      } else if (["discover", "matches", "saved", "applied", "profile", "network"].includes(hash)) {
        setActiveTab(hash);
      }
    };

    handleHash();
    window.addEventListener("hashchange", handleHash);
    return () => window.removeEventListener("hashchange", handleHash);
  }, []);

  // Fetch saved IDs when authenticated
  useEffect(() => {
    if (isAuthenticated) {
      api.saved
        .list()
        .then((items) => {
          setSavedIds(new Set(items.map((i) => i.internship.id)));
        })
        .catch(() => {});
    } else {
      setSavedIds(new Set());
    }
  }, [isAuthenticated]);

  const handleNavigate = (tab: string) => {
    setActiveTab(tab);
    window.location.hash = `#${tab}`;
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleOpenAuth = (mode: "login" | "register") => {
    setAuthModalMode(mode);
    setAuthModalOpen(true);
  };

  const handleSavedChange = (id: number, saved: boolean) => {
    setSavedIds((prev) => {
      const next = new Set(prev);
      if (saved) next.add(id);
      else next.delete(id);
      return next;
    });
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900 font-sans selection:bg-blue-100 selection:text-blue-900">
      {/* Navigation Bar */}
      <Navbar
        activeTab={activeTab}
        onNavigate={handleNavigate}
        onOpenAuth={handleOpenAuth}
        onOpenChangePassword={() => setChangePasswordOpen(true)}
      />

      {/* Main Content Area */}
      <main className="flex-1">
        {activeTab === "discover" && (
          <DiscoverPage
            onViewDetails={(item) => setSelectedInternship(item)}
            savedIds={savedIds}
            onSavedChange={handleSavedChange}
          />
        )}

        {activeTab === "matches" && (
          <RecommendationsPage
            onViewDetails={(item) => setSelectedInternship(item)}
            savedIds={savedIds}
            onSavedChange={handleSavedChange}
            onNavigateToProfile={() => handleNavigate("profile")}
            onOpenAuth={handleOpenAuth}
          />
        )}

        {activeTab === "saved" && (
          <SavedPage
            onViewDetails={(item) => setSelectedInternship(item)}
            onSavedChange={handleSavedChange}
            onExplore={() => handleNavigate("discover")}
          />
        )}

        {activeTab === "applied" && (
          <AppliedPage
            onViewDetails={(item) => setSelectedInternship(item)}
            onExplore={() => handleNavigate("discover")}
          />
        )}

        {activeTab === "profile" && (
          <ProfilePage onOpenChangePassword={() => setChangePasswordOpen(true)} />
        )}

        {activeTab === "network" && <NetworkPage />}
      </main>

      {/* Footer */}
      <Footer />

      {/* Internship Detail Modal */}
      <InternshipDetailModal
        internship={selectedInternship}
        open={!!selectedInternship}
        onClose={() => setSelectedInternship(null)}
        isSaved={selectedInternship ? savedIds.has(selectedInternship.id) : false}
        onSavedChange={handleSavedChange}
      />

      {/* Sign In / Register / OTP Modal */}
      <AuthModal
        open={authModalOpen}
        initialMode={authModalMode}
        onClose={() => setAuthModalOpen(false)}
      />

      {/* Change Password Modal */}
      <ChangePasswordModal
        open={changePasswordOpen}
        onClose={() => setChangePasswordOpen(false)}
      />
    </div>
  );
};
