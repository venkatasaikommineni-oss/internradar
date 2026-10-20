import React, { createContext, useContext, useEffect, useState } from "react";
import { api, getAccessToken, clearTokens, setTokens } from "../lib/api";
import { User, AuthTokens } from "../types";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  login: (email: string, pass: string) => Promise<AuthTokens>;
  register: (email: string, pass: string, name?: string, confirmPass?: string) => Promise<AuthTokens>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const isAdmin = Boolean(user?.is_admin);

  const refreshProfile = async () => {
    const token = getAccessToken();
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const data = await api.profile.get();
      setUser(data);
    } catch (err: any) {
      // Only clear tokens if the server explicitly reports token unauthorized (401)
      if (err?.status === 401) {
        clearTokens();
        setUser(null);
      } else {
        console.error("Profile retrieval error (preserving session):", err);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshProfile();
  }, []);

  const login = async (email: string, pass: string) => {
    const tokens = await api.auth.login({ email, password: pass });
    setTokens(tokens);
    await refreshProfile();
    return tokens;
  };

  const register = async (email: string, pass: string, name?: string, confirmPass?: string) => {
    const tokens = await api.auth.register({ email, password: pass, full_name: name, confirm_password: confirmPass || pass });
    setTokens(tokens);
    await refreshProfile();
    return tokens;
  };

  const logout = async () => {
    await api.auth.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAuthenticated: !!user,
        isAdmin,
        login,
        register,
        logout,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
