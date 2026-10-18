import React, { useState } from "react";
import { Lock } from "lucide-react";
import { Dialog, DialogHeader, DialogBody, DialogFooter } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { api } from "../lib/api";
import { useToast } from "../context/ToastContext";

interface ChangePasswordModalProps {
  open: boolean;
  onClose: () => void;
}

export const ChangePasswordModal: React.FC<ChangePasswordModalProps> = ({ open, onClose }) => {
  const { success, error } = useToast();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errMessage, setErrMessage] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrMessage("");

    if (newPassword.length < 8) {
      setErrMessage("New password must be at least 8 characters long.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setErrMessage("New password and confirmation do not match.");
      return;
    }

    setLoading(true);
    try {
      await api.auth.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      success("Password Changed", "Your password has been updated successfully.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      onClose();
    } catch (err: any) {
      setErrMessage(err.message || "Failed to update password. Verify your current password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose} maxWidth="max-w-md">
      <DialogHeader
        title="Change Password"
        description="Enter your current password and choose a new one."
        onClose={onClose}
      />
      <form onSubmit={handleSubmit}>
        <DialogBody className="space-y-4">
          {errMessage && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded text-xs text-rose-800">
              {errMessage}
            </div>
          )}

          <div>
            <label className="text-xs font-semibold text-slate-800 block mb-1">
              Current Password
            </label>
            <Input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              placeholder="••••••••"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-800 block mb-1">
              New Password (min 8 chars)
            </label>
            <Input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={8}
              placeholder="••••••••"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-800 block mb-1">
              Confirm New Password
            </label>
            <Input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              minLength={8}
              placeholder="••••••••"
            />
          </div>
        </DialogBody>

        <DialogFooter>
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" size="sm" loading={loading}>
            Update Password
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
};
