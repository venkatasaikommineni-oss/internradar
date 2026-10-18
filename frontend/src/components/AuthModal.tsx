import React, { useState, useEffect } from "react";
import { Lock, Mail, User, CheckCircle2, XCircle, ArrowRight } from "lucide-react";
import { Dialog, DialogHeader, DialogBody } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

interface AuthModalProps {
  open: boolean;
  initialMode?: "login" | "register";
  onClose: () => void;
  onSuccess?: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({
  open,
  initialMode = "login",
  onClose,
  onSuccess,
}) => {
  const { login, register } = useAuth();
  const { success } = useToast();

  const [mode, setMode] = useState<"login" | "register">(initialMode);
  const [loading, setLoading] = useState(false);

  // Form states
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    setMode(initialMode);
    setErrorMessage("");
  }, [initialMode, open]);

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return;
    setErrorMessage("");
    setLoading(true);
    try {
      await login(email, password);
      success("Welcome back", "Signed in successfully.");
      onClose();
      onSuccess?.();
    } catch (err: any) {
      setErrorMessage(err.message || "Invalid credentials. Please verify your email and password.");
    } finally {
      setLoading(false);
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return;
    setErrorMessage("");
    if (password.length < 8) {
      setErrorMessage("Password must be at least 8 characters long.");
      return;
    }
    if (password !== confirmPassword) {
      setErrorMessage("Passwords do not match. Please re-enter.");
      return;
    }
    setLoading(true);
    try {
      await register(email, password, fullName, confirmPassword);
      success("Account Created", "Your account has been created successfully.");
      onClose();
      onSuccess?.();
    } catch (err: any) {
      setErrorMessage(err.message || "Registration failed. Please check your email and try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose} maxWidth="max-w-sm">
      <DialogHeader
        title={mode === "login" ? "Sign in" : "Create account"}
        onClose={onClose}
      />

      <DialogBody>
        {errorMessage && (
          <div className="mb-4 p-2.5 rounded-md bg-rose-50 border border-rose-200 text-rose-800 text-xs leading-relaxed">
            {errorMessage}
          </div>
        )}

        {/* ── Login Form ──────────────────────────────────────────────────────── */}
        {mode === "login" && (
          <form onSubmit={handleLoginSubmit} className="space-y-3.5">
            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">
                Email
              </label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                required
                autoFocus
                disabled={loading}
              />
            </div>

            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-xs font-medium text-slate-700 block">Password</label>
              </div>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                disabled={loading}
              />
            </div>

            <Button type="submit" loading={loading} disabled={loading} className="w-full h-9">
              Sign In
            </Button>

            <div className="text-center pt-1 text-xs text-slate-500">
              Don't have an account?{" "}
              <button
                type="button"
                onClick={() => {
                  setErrorMessage("");
                  setMode("register");
                }}
                disabled={loading}
                className="font-medium text-blue-600 hover:underline"
              >
                Create one
              </button>
            </div>
          </form>
        )}

        {/* ── Register Form ───────────────────────────────────────────────────── */}
        {mode === "register" && (
          <form onSubmit={handleRegisterSubmit} className="space-y-3.5">
            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">
                Full Name
              </label>
              <Input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Full name"
                required
                autoFocus
                disabled={loading}
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">
                Email
              </label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                required
                disabled={loading}
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">
                Password
              </label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
                required
                minLength={8}
                disabled={loading}
              />
            </div>

            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">
                Confirm Password
              </label>
              <div className="relative">
                <Input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter password"
                  required
                  minLength={8}
                  disabled={loading}
                  className={
                    confirmPassword && confirmPassword !== password
                      ? "border-rose-400 focus:ring-rose-500"
                      : ""
                  }
                />
              </div>
              {confirmPassword && confirmPassword !== password && (
                <p className="text-[11px] text-rose-600 mt-1">Passwords do not match</p>
              )}
            </div>

            <Button type="submit" loading={loading} disabled={loading} className="w-full h-9">
              {loading ? "Creating account..." : "Create Account"}
            </Button>

            <div className="text-center pt-1 text-xs text-slate-500">
              Already have an account?{" "}
              <button
                type="button"
                onClick={() => {
                  setErrorMessage("");
                  setMode("login");
                }}
                disabled={loading}
                className="font-medium text-blue-600 hover:underline"
              >
                Sign in
              </button>
            </div>
          </form>
        )}
      </DialogBody>
    </Dialog>
  );
};
