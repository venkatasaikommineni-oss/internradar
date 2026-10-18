import React, { useState } from "react";
import { Compass, Bookmark, CheckSquare, Users, User, LogOut, Menu, X, Sparkles, ChevronDown, Lock } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { Button } from "./ui/button";

interface NavbarProps {
  activeTab: string;
  onNavigate: (tab: string) => void;
  onOpenAuth: (mode: "login" | "register") => void;
  onOpenChangePassword: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  onNavigate,
  onOpenAuth,
  onOpenChangePassword,
}) => {
  const { user, isAuthenticated, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);

  const navItems = [
    { id: "discover", label: "Internships", icon: Compass },
    { id: "matches", label: "Matches", icon: Sparkles },
    { id: "saved", label: "Saved", icon: Bookmark, authRequired: true },
    { id: "applied", label: "Applications", icon: CheckSquare, authRequired: true },
    { id: "network", label: "Network", icon: Users, authRequired: true },
  ];

  const handleNavClick = (tabId: string) => {
    onNavigate(tabId);
    setMobileMenuOpen(false);
  };

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex h-14 items-center justify-between">
          {/* Brand */}
          <div
            className="flex items-center gap-2 cursor-pointer select-none"
            onClick={() => handleNavClick("discover")}
          >
            <div className="h-7 w-7 rounded-md bg-blue-600 flex items-center justify-center text-white">
              <Compass className="h-4 w-4" />
            </div>
            <span className="font-semibold text-base text-slate-900 tracking-tight">InternRadar</span>
          </div>

          {/* Desktop Navigation Links */}
          <nav className="hidden md:flex items-center gap-0.5">
            {navItems.map((item) => {
              if (item.authRequired && !isAuthenticated) return null;
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleNavClick(item.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    isActive
                      ? "text-blue-600 bg-blue-50/80 font-semibold"
                      : "text-slate-600 hover:text-slate-900 hover:bg-slate-100/70"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {item.label}
                </button>
              );
            })}
          </nav>

          {/* Right Action / Auth Buttons */}
          <div className="hidden md:flex items-center gap-2">
            {isAuthenticated && user ? (
              <div className="relative">
                <button
                  onClick={() => setUserDropdownOpen(!userDropdownOpen)}
                  className="flex items-center gap-2 py-1 px-2 rounded-md hover:bg-slate-100 border border-transparent hover:border-slate-200 transition-colors"
                >
                  <div className="h-7 w-7 rounded-full bg-slate-100 text-slate-700 font-semibold text-xs flex items-center justify-center border border-slate-200 uppercase">
                    {user.full_name ? user.full_name.charAt(0) : user.email.charAt(0)}
                  </div>
                  <span className="text-xs font-medium text-slate-800 max-w-[120px] truncate">
                    {user.full_name || user.email.split("@")[0]}
                  </span>
                  <ChevronDown className="h-3 w-3 text-slate-400" />
                </button>

                {userDropdownOpen && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setUserDropdownOpen(false)} />
                    <div className="absolute right-0 mt-1.5 w-52 rounded-md border border-slate-200 bg-white py-1 shadow-md z-50 text-xs">
                      <div className="px-3 py-2 border-b border-slate-100">
                        <p className="text-[11px] text-slate-400">Signed in as</p>
                        <p className="font-medium text-slate-800 truncate">{user.email}</p>
                      </div>
                      <button
                        onClick={() => {
                          setUserDropdownOpen(false);
                          handleNavClick("profile");
                        }}
                        className="w-full flex items-center gap-2 px-3 py-1.5 text-slate-700 hover:bg-slate-50 text-left"
                      >
                        <User className="h-3.5 w-3.5 text-slate-400" />
                        Profile & Resume
                      </button>
                      <button
                        onClick={() => {
                          setUserDropdownOpen(false);
                          onOpenChangePassword();
                        }}
                        className="w-full flex items-center gap-2 px-3 py-1.5 text-slate-700 hover:bg-slate-50 text-left"
                      >
                        <Lock className="h-3.5 w-3.5 text-slate-400" />
                        Change Password
                      </button>
                      <div className="my-1 border-t border-slate-100" />
                      <button
                        onClick={() => {
                          setUserDropdownOpen(false);
                          logout();
                        }}
                        className="w-full flex items-center gap-2 px-3 py-1.5 text-rose-600 hover:bg-rose-50 text-left"
                      >
                        <LogOut className="h-3.5 w-3.5 text-rose-500" />
                        Sign Out
                      </button>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={() => onOpenAuth("login")} className="text-xs h-8">
                  Sign In
                </Button>
                <Button size="sm" onClick={() => onOpenAuth("register")} className="text-xs h-8">
                  Create Account
                </Button>
              </div>
            )}
          </div>

          {/* Mobile Hamburger Toggle */}
          <div className="flex md:hidden items-center gap-2">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded text-slate-600 hover:text-slate-900 hover:bg-slate-100"
              aria-label="Toggle mobile navigation"
            >
              {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-slate-200 bg-white px-4 pt-3 pb-6 space-y-2">
          {navItems.map((item) => {
            if (item.authRequired && !isAuthenticated) return null;
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => handleNavClick(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded ${
                  isActive ? "bg-blue-50 text-blue-700" : "text-slate-700 hover:bg-slate-100"
                }`}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </button>
            );
          })}

          <div className="pt-4 border-t border-slate-100">
            {isAuthenticated && user ? (
              <div className="space-y-2">
                <button
                  onClick={() => handleNavClick("profile")}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 text-left rounded"
                >
                  <User className="h-4 w-4" />
                  My Profile & Resume
                </button>
                <button
                  onClick={() => {
                    setMobileMenuOpen(false);
                    onOpenChangePassword();
                  }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 text-left rounded"
                >
                  <Lock className="h-4 w-4" />
                  Change Password
                </button>
                <button
                  onClick={() => {
                    setMobileMenuOpen(false);
                    logout();
                  }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-rose-600 hover:bg-rose-50 text-left rounded"
                >
                  <LogOut className="h-4 w-4" />
                  Sign Out ({user.email})
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-2 pt-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setMobileMenuOpen(false);
                    onOpenAuth("login");
                  }}
                >
                  Sign In
                </Button>
                <Button
                  onClick={() => {
                    setMobileMenuOpen(false);
                    onOpenAuth("register");
                  }}
                >
                  Create Account
                </Button>
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  );
};
