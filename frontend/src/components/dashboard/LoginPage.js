import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { SignIn, Key, Eye, UserCircle, Buildings, ArrowsClockwise } from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { API, formatApiErrorDetail } from "./config";

const LoginPage = ({ onLogin }) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");
    try {
      const { data } = await axios.post(`${API}/auth/login`, { email, password });
      onLogin(data);
    } catch (e) {
      setError(formatApiErrorDetail(e.response?.data?.detail) || e.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-stone-50 flex items-center justify-center p-4" data-testid="login-page">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md"
      >
        <div className="bg-white rounded-2xl shadow-card border border-stone-200/80 overflow-hidden">
          <div className="bg-[#3E5245] p-8 text-center">
            <div className="w-14 h-14 bg-white/15 rounded-xl flex items-center justify-center mx-auto mb-3">
              <Buildings size={28} className="text-white" weight="fill" />
            </div>
            <h1 className="text-xl font-semibold text-white">Review Hub</h1>
            <p className="text-sm text-white/60 mt-1">Hotel Review Management</p>
          </div>
          
          <form onSubmit={handleSubmit} className="p-8 space-y-5">
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2.5 text-sm text-red-700" data-testid="login-error">
                {error}
              </div>
            )}
            
            <div>
              <label className="text-sm font-medium text-stone-700 mb-1.5 block">Email</label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@hotelbox.com"
                className="border-stone-200 h-11"
                data-testid="login-email"
                required
              />
            </div>
            
            <div>
              <label className="text-sm font-medium text-stone-700 mb-1.5 block">Password</label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                className="border-stone-200 h-11"
                data-testid="login-password"
                required
              />
            </div>
            
            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-[#3E5245] text-white py-2.5 rounded-lg hover:bg-[#2A3B30] transition-all active:scale-[0.98] disabled:opacity-50 flex items-center justify-center gap-2 font-medium"
              data-testid="login-submit-btn"
            >
              {isLoading ? (
                <ArrowsClockwise size={16} className="animate-spin" />
              ) : (
                <SignIn size={16} />
              )}
              {isLoading ? "Signing in..." : "Sign In"}
            </button>
          </form>
          
          <div className="px-8 pb-6 text-center">
            <p className="text-xs text-stone-400">Hotel staff accounts are created by administrators</p>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export { LoginPage };
