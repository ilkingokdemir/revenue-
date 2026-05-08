import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { CheckCircle, AlertTriangle, XCircle, ArrowRight, Settings, Target, Zap, Shield, BookOpen, UserCheck } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STEP_ICONS = [Settings, Target, Zap, Shield, BookOpen, UserCheck];

export const RevenueSetupWizard = ({ propertyId }) => {
  const [wizard, setWizard] = useState(null);

  useEffect(() => {
    axios.get(`${API}/revenue/setup-wizard/${propertyId}`).then(r => setWizard(r.data)).catch(() => toast.error("Failed"));
  }, [propertyId]);

  if (!wizard) return <div className="text-center py-12 text-stone-400">Loading...</div>;

  const completedSteps = wizard.steps?.filter(s => s.completed).length || 0;
  const totalSteps = wizard.steps?.length || 6;

  return (
    <div className="space-y-6" data-testid="rev-setup-wizard">
      <div className="text-center py-4">
        <h2 className="text-2xl font-bold text-stone-800">Revenue Setup Wizard</h2>
        <p className="text-sm text-stone-500 mt-1">Configure your revenue optimization strategy</p>
      </div>

      {/* Progress */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <span className="text-sm font-medium text-stone-600">Progress</span>
          <span className="text-sm font-bold text-emerald-600">{completedSteps} / {totalSteps} steps</span>
        </div>
        <div className="w-full bg-stone-100 rounded-full h-2 mb-6">
          <div className="bg-emerald-500 h-2 rounded-full transition-all" style={{ width: `${(completedSteps / totalSteps) * 100}%` }} />
        </div>

        <div className="flex items-center justify-between">
          {wizard.steps?.map((step, i) => {
            const StepIcon = STEP_ICONS[i] || Settings;
            return (
              <div key={step.id} className="flex flex-col items-center text-center flex-1">
                <div className={`w-12 h-12 rounded-full flex items-center justify-center text-sm font-bold mb-2 border-2 transition-all ${
                  step.completed ? "bg-emerald-50 border-emerald-400 text-emerald-700" :
                  "bg-white border-stone-200 text-stone-400"
                }`}>
                  {step.completed ? <CheckCircle className="w-5 h-5" /> : step.id}
                </div>
                <span className={`text-xs font-medium ${step.completed ? "text-emerald-700" : "text-stone-400"}`}>{step.name}</span>
                {i < totalSteps - 1 && <div className="hidden" />}
              </div>
            );
          })}
        </div>
      </div>

      {/* Checklist */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6">
        <h3 className="text-lg font-bold text-stone-800 mb-4">Revenue Setup Checklist</h3>
        <div className="space-y-3">
          {wizard.checklist?.map(item => (
            <div key={item.key} className={`flex items-center justify-between p-4 rounded-xl border ${
              item.status === "passed" ? "bg-white border-stone-200" :
              item.status === "failed" ? "bg-red-50 border-red-100" :
              "bg-amber-50/50 border-amber-100"
            }`} data-testid={`rev-checklist-${item.key}`}>
              <div className="flex items-center gap-3">
                {item.status === "passed" ? <CheckCircle className="w-5 h-5 text-emerald-500" /> :
                 item.status === "failed" ? <XCircle className="w-5 h-5 text-red-500" /> :
                 <AlertTriangle className="w-5 h-5 text-amber-500" />}
                <div>
                  <p className="text-sm font-semibold text-stone-800">{item.label}</p>
                  <p className="text-xs text-stone-400 mt-0.5">{item.detail}</p>
                </div>
              </div>
              <Badge className={`text-[10px] ${
                item.status === "passed" ? "bg-emerald-100 text-emerald-700" :
                item.status === "failed" ? "bg-red-100 text-red-700" :
                "bg-amber-100 text-amber-700"
              }`}>{item.status}</Badge>
            </div>
          ))}
        </div>
      </div>

      {/* CTA */}
      {completedSteps < totalSteps && (
        <div className="bg-gradient-to-r from-emerald-500 to-teal-500 rounded-2xl p-8 text-center text-white">
          <p className="text-lg font-bold mb-2">You are {totalSteps - completedSteps} steps away from automated revenue optimization.</p>
          <button className="inline-flex items-center gap-2 bg-white text-emerald-700 px-6 py-3 rounded-xl font-semibold text-sm hover:bg-emerald-50 transition-all mt-2" data-testid="rev-start-setup">
            Start Setup <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* What you'll configure */}
      <div className="bg-blue-50 border border-blue-100 rounded-2xl p-6">
        <h4 className="font-bold text-stone-800 mb-3 flex items-center gap-2">
          <Target className="w-4 h-4 text-blue-500" /> What you'll configure
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { name: "Business Context", desc: "Define your optimization goals" },
            { name: "Segments & Rates", desc: "Set up base and derived rates" },
            { name: "Smart Pricing", desc: "Configure AI-powered pricing" },
            { name: "Guardrails", desc: "Set safety limits and restrictions" },
            { name: "Playbooks", desc: "Enable automated pricing rules" },
            { name: "Approval Flow", desc: "Choose manual or autopilot" },
          ].map(item => (
            <div key={item.name} className="flex items-center gap-2 text-sm">
              <CheckCircle className="w-4 h-4 text-blue-500 flex-shrink-0" />
              <span><strong className="text-blue-800">{item.name}</strong> <span className="text-blue-600">– {item.desc}</span></span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
