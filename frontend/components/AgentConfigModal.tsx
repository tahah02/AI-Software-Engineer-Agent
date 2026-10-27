"use client";

import React from "react";
import { X, Bot, ShieldCheck, FlaskConical, Server, Cpu, Check, AlertCircle } from "lucide-react";

interface AgentConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  agentToggles: {
    agent2: boolean;
    agent4: boolean;
    agent5: boolean;
  };
  onSave: (newToggles: { agent2: boolean; agent4: boolean; agent5: boolean }) => void;
}

export function AgentConfigModal({
  isOpen,
  onClose,
  agentToggles,
  onSave,
}: AgentConfigModalProps) {
  const [toggles, setToggles] = React.useState(agentToggles);

  // Sync state if modal reopens or props change
  const [prevToggles, setPrevToggles] = React.useState(agentToggles);
  if (prevToggles !== agentToggles) {
    setPrevToggles(agentToggles);
    setToggles(agentToggles);
  }

  if (!isOpen) return null;

  const handleToggle = (key: "agent2" | "agent4" | "agent5") => {
    setToggles((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSave = () => {
    onSave(toggles);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="w-full max-w-lg bg-[#0e121d] border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        {/* Modal Header */}
        <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-cyan-400">
              <Cpu className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-slate-100 font-semibold text-[14px]">Multi-Agent Topology Configuration</h3>
              <p className="text-slate-400 text-[11px]">Configure which specialized agents participate in this project</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Modal Body / Agent List */}
        <div className="p-5 space-y-3.5 max-h-[65vh] overflow-y-auto">
          {/* Agent 1 (Mandatory) */}
          <div className="p-3 rounded-xl bg-[#090c14] border border-slate-800/80 flex items-center justify-between opacity-90">
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-lg bg-emerald-950 border border-emerald-500/40 flex items-center justify-center text-emerald-400 shrink-0">
                <Bot className="h-4 w-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[13px] font-medium text-slate-200">Agent 1: Documentation Reviewer</span>
                  <span className="text-[10px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded border border-slate-700">MANDATORY</span>
                </div>
                <p className="text-[11px] text-slate-500">Ingests requirements and creates technical specs & test specs (Google Gemini)</p>
              </div>
            </div>
            <span className="text-[11px] font-semibold text-emerald-400">Enforced</span>
          </div>

          {/* Agent 2 (Configurable) */}
          <div className="p-3 rounded-xl bg-[#090c14] border border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-lg bg-cyan-950 border border-cyan-500/40 flex items-center justify-center text-cyan-400 shrink-0">
                <Server className="h-4 w-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[13px] font-medium text-slate-200">Agent 2: Mock Vendor API Developer</span>
                  <span className="text-[10px] bg-blue-900/40 text-cyan-300 px-1.5 py-0.5 rounded border border-cyan-500/30">OPTIONAL</span>
                </div>
                <p className="text-[11px] text-slate-500">Simulates third-party vendor APIs with FastAPI (Groq gpt-oss-120b)</p>
              </div>
            </div>
            <button
              onClick={() => handleToggle("agent2")}
              className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                toggles.agent2 ? "bg-cyan-500" : "bg-slate-700"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                  toggles.agent2 ? "translate-x-4" : "translate-x-0"
                }`}
              />
            </button>
          </div>

          {/* Agent 3 (Mandatory) */}
          <div className="p-3 rounded-xl bg-[#090c14] border border-slate-800/80 flex items-center justify-between opacity-90">
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-lg bg-blue-950 border border-blue-500/40 flex items-center justify-center text-blue-400 shrink-0">
                <Bot className="h-4 w-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[13px] font-medium text-slate-200">Agent 3: Main Coding Agent</span>
                  <span className="text-[10px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded border border-slate-700">MANDATORY</span>
                </div>
                <p className="text-[11px] text-slate-500">Implements channel app business logic (Local Ollama qwen2.5-coder:7b)</p>
              </div>
            </div>
            <span className="text-[11px] font-semibold text-blue-400">Enforced</span>
          </div>

          {/* Agent 4 (Configurable) */}
          <div className="p-3 rounded-xl bg-[#090c14] border border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-lg bg-purple-950 border border-purple-500/40 flex items-center justify-center text-purple-400 shrink-0">
                <FlaskConical className="h-4 w-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[13px] font-medium text-slate-200">Agent 4: Independent QA Engineer</span>
                  <span className="text-[10px] bg-purple-900/40 text-purple-300 px-1.5 py-0.5 rounded border border-purple-500/30">OPTIONAL</span>
                </div>
                <p className="text-[11px] text-slate-500">Autonomous black-box contract testing; skips reported as SKIPPED (Groq qwen3.8-27b)</p>
              </div>
            </div>
            <button
              onClick={() => handleToggle("agent4")}
              className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                toggles.agent4 ? "bg-purple-500" : "bg-slate-700"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                  toggles.agent4 ? "translate-x-4" : "translate-x-0"
                }`}
              />
            </button>
          </div>

          {/* Agent 5 (Configurable) */}
          <div className="p-3 rounded-xl bg-[#090c14] border border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-lg bg-amber-950 border border-amber-500/40 flex items-center justify-center text-amber-400 shrink-0">
                <ShieldCheck className="h-4 w-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[13px] font-medium text-slate-200">Agent 5: Security Reviewer</span>
                  <span className="text-[10px] bg-amber-900/40 text-amber-300 px-1.5 py-0.5 rounded border border-amber-500/30">OPTIONAL</span>
                </div>
                <p className="text-[11px] text-slate-500">Static SAST audit; skips reported as NOT_SCANNED (Gemini flash-lite)</p>
              </div>
            </div>
            <button
              onClick={() => handleToggle("agent5")}
              className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                toggles.agent5 ? "bg-amber-500" : "bg-slate-700"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                  toggles.agent5 ? "translate-x-4" : "translate-x-0"
                }`}
              />
            </button>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-5 py-3 border-t border-slate-800 bg-[#0a0d15] flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
            <AlertCircle className="h-3.5 w-3.5" />
            <span>Agent 1 & 3 are architectural invariants</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-3 py-1.5 rounded-lg border border-slate-700 text-slate-300 hover:text-white hover:bg-slate-800 text-[12px] transition"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-[12px] flex items-center gap-1.5 shadow-md shadow-blue-600/30 transition"
            >
              <Check className="h-3.5 w-3.5" /> Save Changes
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
