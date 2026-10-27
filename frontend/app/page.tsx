"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Boxes,
  FolderGit2,
  Users,
  Play,
  FileCode2,
  GitBranch,
  Settings as SettingsIcon,
  Search,
  Bell,
  Plus,
  CheckCircle2,
  Code2,
  ShieldCheck,
  FlaskConical,
  Paperclip,
  AtSign,
  Send,
  Check,
  Wrench,
  ChevronDown,
  RotateCcw,
  AlertTriangle,
  Loader2,
  Sparkles,
  Bot,
  X,
  FileText,
  Download,
} from "lucide-react";
import {
  fetchProjects,
  fetchProjectArtifacts,
  fetchProjectDiff,
  getProjectDownloadUrl,
  createProject,
  startWorkflow,
  resolveApproval,
  subscribeToWorkflowStream,
  ProjectItem,
  ArtifactItem,
} from "@/lib/api";
import { AgentConfigModal } from "@/components/AgentConfigModal";

interface ChatMessage {
  id: string;
  sender: "user" | "assistant" | "agent1" | "agent3";
  senderName: string;
  timestamp: string;
  text?: string;
  checklist?: string[];
  specsReady?: boolean;
  approvalRequired?: boolean;
  workingTasks?: string[];
}

export default function WorkspacePage() {
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [selectedProject, setSelectedProject] = useState<ProjectItem | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactItem[]>([]);
  const [codeDiff, setCodeDiff] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeTab, setActiveTab] = useState<"artifacts" | "diff" | "tests" | "security">("artifacts");
  const [inputMessage, setInputMessage] = useState("");
  const [specApproved, setSpecApproved] = useState<boolean | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [activeApprovalId, setActiveApprovalId] = useState<string | null>(null);
  const [streamStatus, setStreamStatus] = useState<string>("idle");
  const [feedbackInput, setFeedbackInput] = useState("");
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<{ id: string; name: string; color: string }>({
    id: "auto",
    name: "Auto (All Agents)",
    color: "text-cyan-400",
  });
  const [showAgentMenu, setShowAgentMenu] = useState(false);
  const [showProjectMenu, setShowProjectMenu] = useState(false);
  const [showBranchMenu, setShowBranchMenu] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [activeNavView, setActiveNavView] = useState<"projects" | "agents" | "runs" | "artifacts" | "git">("projects");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatInputRef = useRef<HTMLInputElement>(null);

  // Dynamic project agents toggle states
  const [agentToggles, setAgentToggles] = useState({
    agent2: true,
    agent4: true,
    agent5: true,
  });

  // Keep selectedAgent active only if enabled; otherwise compute safe active agent
  const isAgentDisabled =
    (selectedAgent.id === "agent2" && !agentToggles.agent2) ||
    (selectedAgent.id === "agent4" && !agentToggles.agent4) ||
    (selectedAgent.id === "agent5" && !agentToggles.agent5);

  const currentActiveAgent = isAgentDisabled
    ? { id: "auto", name: "Auto (All Agents)", color: "text-cyan-400" }
    : selectedAgent;

  // Load existing projects from DB on mount
  useEffect(() => {
    fetchProjects().then((data) => {
      setProjects(data);
      if (data.length > 0) {
        setSelectedProject(data[0]);
      }
    });
  }, []);

  // Fetch real artifacts & diff whenever selected project changes
  useEffect(() => {
    if (!selectedProject?.id) return;
    let isMounted = true;
    fetchProjectArtifacts(selectedProject.id).then((arts) => {
      if (isMounted) setArtifacts(arts);
    });
    fetchProjectDiff(selectedProject.id).then((diff) => {
      if (isMounted) setCodeDiff(diff);
    });
    return () => {
      isMounted = false;
    };
  }, [selectedProject?.id]);

  // SSE Stream Listener
  useEffect(() => {
    if (!currentRunId) return;

    const es = subscribeToWorkflowStream(
      currentRunId,
      (eventData) => {
        if (eventData.event === "approval_requested") {
          setActiveApprovalId(eventData.approval_id as string);
          setMessages((prev) => [
            ...prev,
            {
              id: `approval-${Date.now()}`,
              sender: "agent1",
              senderName: "Agent 1: Documentation Reviewer",
              timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
              approvalRequired: true,
            },
          ]);
          // Refresh real artifacts
          if (selectedProject?.id) {
            fetchProjectArtifacts(selectedProject.id).then((arts) => setArtifacts(arts));
          }
        } else if (eventData.event === "stream_end") {
          setStreamStatus("ready");
          if (selectedProject?.id) {
            fetchProjectArtifacts(selectedProject.id).then((arts) => setArtifacts(arts));
          }
        } else {
          setStreamStatus("streaming");
        }
      },
      (err) => {
        console.warn("SSE stream info:", err);
      }
    );

    return () => {
      es.close();
    };
  }, [currentRunId, selectedProject]);

  // Handle User Message / Workflow Trigger
  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputMessage.trim() || isSubmitting) return;

    const userText = inputMessage.trim();
    setInputMessage("");
    setIsSubmitting(true);

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      senderName: "You",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      text: userText,
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const resp = await startWorkflow({
        project_id: selectedProject?.id,
        project_name: selectedProject ? undefined : userText.slice(0, 24),
        user_requirement: userText,
      });

      // If response is a greeting / conversational reply:
      if (resp.is_greeting && resp.assistant_reply) {
        setMessages((prev) => [
          ...prev,
          {
            id: `assistant-${Date.now()}`,
            sender: "assistant",
            senderName: "AAISE Assistant",
            timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            text: resp.assistant_reply,
          },
        ]);
        return;
      }

      // If genuine requirement was submitted:
      if (resp.workflow_run_id) {
        setCurrentRunId(resp.workflow_run_id);
      }

      // Refresh project list if a new one was auto-created
      const updatedProjects = await fetchProjects();
      setProjects(updatedProjects);
      if (!selectedProject && updatedProjects.length > 0) {
        setSelectedProject(updatedProjects[0]);
      }

      // Add Agent 1 thinking message
      setMessages((prev) => [
        ...prev,
        {
          id: `agent1-${Date.now()}`,
          sender: "agent1",
          senderName: "Agent 1 (Requirements & Design)",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          text: "I am analyzing your software requirements and generating technical specifications...",
          checklist: [
            "Analyzed architecture boundaries & target framework",
            "Extracted functional requirements & API contracts",
            "Created XUnit / Pytest test specifications",
            "Generated Technical Design Document (TDD)",
          ],
          specsReady: true,
          approvalRequired: true,
        },
      ]);
    } catch (err) {
      console.error("Workflow error:", err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle Human Approval Gate (Approve)
  const handleApprove = async () => {
    setSpecApproved(true);
    if (activeApprovalId) {
      try {
        await resolveApproval({
          approval_id: activeApprovalId,
          approved: true,
        });
      } catch (err) {
        console.error("Approve failed:", err);
      }
    }

    setMessages((prev) => [
      ...prev,
      {
        id: `agent3-${Date.now()}`,
        sender: "agent3",
        senderName: "Agent 3 (Main Coding Agent)",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        text: "Specifications approved. Implementing core channel application logic...",
        workingTasks: [
          "Provisioning channel-app local Git repository",
          "Generating FastAPI application entrypoint",
          "Implementing endpoints & Pydantic domain models",
          "Creating automated contract test suites",
        ],
      },
    ]);
  };

  // Handle Human Approval Gate (Request Changes)
  const handleRequestChanges = async () => {
    setSpecApproved(false);
    if (activeApprovalId) {
      try {
        await resolveApproval({
          approval_id: activeApprovalId,
          approved: false,
          comments: feedbackInput || "Requesting specifications revision.",
        });
      } catch (err) {
        console.error("Request changes failed:", err);
      }
    }
    setShowFeedbackModal(false);
    setFeedbackInput("");
  };

  return (
    <div className="flex h-screen w-screen bg-[#07090e] text-slate-200 overflow-hidden text-[13px]">
      {/* 1. LEFT-MOST ICON NAVIGATION BAR */}
      <aside className="w-14 shrink-0 flex flex-col items-center py-3 border-r border-slate-800/80 bg-[#0a0d14] justify-between z-20">
        <div className="flex flex-col items-center gap-5 w-full">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-cyan-600 to-blue-500 flex items-center justify-center text-white shadow-lg shadow-cyan-500/20 cursor-pointer">
            <Boxes className="h-5 w-5" />
          </div>

          <nav className="flex flex-col items-center gap-2 w-full px-2">
            {/* 1. Home / Projects View */}
            <button
              onClick={() => setActiveNavView("projects")}
              title="Workspace & Projects"
              className={`h-10 w-10 rounded-lg flex items-center justify-center transition ${
                activeNavView === "projects"
                  ? "bg-blue-600/20 text-cyan-400 border border-cyan-500/30"
                  : "text-slate-400 hover:text-white hover:bg-slate-800/60"
              }`}
            >
              <FolderGit2 className="h-4 w-4" />
            </button>

            {/* 2. Agents / Topology Team View */}
            <button
              onClick={() => {
                setActiveNavView("agents");
                setShowConfigModal(true);
              }}
              title="Multi-Agent Topology"
              className={`h-10 w-10 rounded-lg flex items-center justify-center transition ${
                activeNavView === "agents"
                  ? "bg-blue-600/20 text-cyan-400 border border-cyan-500/30"
                  : "text-slate-400 hover:text-white hover:bg-slate-800/60"
              }`}
            >
              <Users className="h-4 w-4" />
            </button>

            {/* 3. Workflows / Runs */}
            <button
              onClick={() => {
                setActiveNavView("runs");
                if (currentRunId) {
                  alert(`Active Workflow Run: ${currentRunId}\nStatus: ${streamStatus}`);
                } else {
                  alert("No active workflow run. Type your software requirements in the chat to start one.");
                }
              }}
              title="Workflow Executions"
              className={`h-10 w-10 rounded-lg flex items-center justify-center transition ${
                activeNavView === "runs"
                  ? "bg-blue-600/20 text-cyan-400 border border-cyan-500/30"
                  : "text-slate-400 hover:text-white hover:bg-slate-800/60"
              }`}
            >
              <Play className="h-4 w-4" />
            </button>

            {/* 4. Artifacts / Documents */}
            <button
              onClick={() => {
                setActiveNavView("artifacts");
                setActiveTab("artifacts");
              }}
              title="Project Artifacts & Technical Specs"
              className={`h-10 w-10 rounded-lg flex items-center justify-center transition ${
                activeNavView === "artifacts" || activeTab === "artifacts"
                  ? "bg-blue-600/20 text-cyan-400 border border-cyan-500/30"
                  : "text-slate-400 hover:text-white hover:bg-slate-800/60"
              }`}
            >
              <FileCode2 className="h-4 w-4" />
            </button>

            {/* 5. Git Branches / Commits */}
            <button
              onClick={() => {
                setActiveNavView("git");
                setActiveTab("diff");
              }}
              title="Git Branches & Code Diff"
              className={`h-10 w-10 rounded-lg flex items-center justify-center transition ${
                activeNavView === "git" || activeTab === "diff"
                  ? "bg-blue-600/20 text-cyan-400 border border-cyan-500/30"
                  : "text-slate-400 hover:text-white hover:bg-slate-800/60"
              }`}
            >
              <GitBranch className="h-4 w-4" />
            </button>
          </nav>
        </div>

        <div className="flex flex-col items-center gap-3">
          <button
            onClick={() => setShowConfigModal(true)}
            className="h-10 w-10 rounded-lg flex items-center justify-center text-slate-400 hover:text-white hover:bg-slate-800/60 transition"
          >
            <SettingsIcon className="h-4 w-4" />
          </button>
          <div className="h-7 w-7 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center text-xs font-semibold text-slate-300">
            TH
          </div>
        </div>
      </aside>

      {/* MAIN CONTAINER */}
      <div className="flex-1 flex flex-col min-w-0 h-full">
        {/* TOP HEADER BAR */}
        <header className="h-14 shrink-0 border-b border-slate-800/80 bg-[#0a0d14] flex items-center justify-between px-4">
          <div className="flex items-center gap-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-slate-100 text-[14px] tracking-tight">AAISE Platform</span>
                <span className="text-[11px] text-slate-500 font-normal hidden sm:inline">Autonomous AI Software Engineer</span>
              </div>
            </div>

            <div className="h-4 w-[1px] bg-slate-800 mx-1" />

            {/* Project Selector Badge & Dropdown */}
            <div className="relative">
              <button
                type="button"
                onClick={() => {
                  setShowProjectMenu((p) => !p);
                  setShowBranchMenu(false);
                }}
                className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-[#131926] border border-slate-700/80 hover:border-slate-600 text-slate-200 transition text-[12px]"
              >
                <FolderGit2 className="h-3.5 w-3.5 text-cyan-400" />
                <span>Project / <span className="font-medium text-white">{selectedProject ? selectedProject.name : "No Project Selected"}</span></span>
                <ChevronDown className="h-3 w-3 text-slate-400 ml-0.5" />
              </button>

              {showProjectMenu && (
                <div className="absolute top-full left-0 mt-1.5 w-60 bg-[#0e121d] border border-slate-700 rounded-xl shadow-2xl p-1.5 z-50 animate-in fade-in duration-150">
                  <div className="px-2 py-1 text-[10px] uppercase font-semibold text-slate-500 border-b border-slate-800 mb-1">
                    Select Project
                  </div>
                  {projects.length === 0 ? (
                    <div className="p-2 text-center text-slate-500 text-[11px]">No projects yet</div>
                  ) : (
                    projects.map((p) => (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => {
                          setSelectedProject(p);
                          setShowProjectMenu(false);
                          setMessages([]);
                        }}
                        className={`w-full flex items-center justify-between p-2 rounded-lg text-left text-[12px] transition ${
                          selectedProject?.id === p.id
                            ? "bg-blue-600/20 text-cyan-400 border border-cyan-500/30"
                            : "hover:bg-slate-800/60 text-slate-300"
                        }`}
                      >
                        <span className="font-medium truncate">{p.name}</span>
                        {selectedProject?.id === p.id && <Check className="h-3 w-3 text-cyan-400" />}
                      </button>
                    ))
                  )}
                  <button
                    type="button"
                    onClick={async () => {
                      const name = prompt("Enter project name:", "New Project");
                      if (name) {
                        const p = await createProject(name);
                        setProjects((prev) => [p, ...prev]);
                        setSelectedProject(p);
                        setShowProjectMenu(false);
                        setMessages([]);
                      }
                    }}
                    className="w-full mt-1 flex items-center gap-1.5 p-1.5 rounded-lg text-[11.5px] text-cyan-400 hover:bg-cyan-950/40 border border-dashed border-cyan-500/30"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    <span>Create New Project</span>
                  </button>
                </div>
              )}
            </div>

            {/* Branch Selector Badge & Dropdown */}
            <div className="relative">
              <button
                type="button"
                onClick={() => {
                  setShowBranchMenu((p) => !p);
                  setShowProjectMenu(false);
                }}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#131926] border border-slate-700/80 hover:border-slate-600 text-slate-300 transition text-[12px]"
              >
                <GitBranch className="h-3.5 w-3.5 text-purple-400" />
                <span>{selectedProject?.current_branch || (selectedProject ? "develop" : "no branch")}</span>
                <ChevronDown className="h-3 w-3 text-slate-400" />
              </button>

              {showBranchMenu && (
                <div className="absolute top-full left-0 mt-1.5 w-48 bg-[#0e121d] border border-slate-700 rounded-xl shadow-2xl p-1.5 z-50 animate-in fade-in duration-150">
                  <div className="px-2 py-1 text-[10px] uppercase font-semibold text-slate-500 border-b border-slate-800 mb-1">
                    Git Branches
                  </div>
                  {["develop", "main", "feature/specs", "release/v1.0"].map((br) => (
                    <button
                      key={br}
                      type="button"
                      onClick={() => {
                        if (selectedProject) {
                          setSelectedProject({ ...selectedProject, current_branch: br });
                        }
                        setShowBranchMenu(false);
                      }}
                      className={`w-full flex items-center justify-between p-2 rounded-lg text-left text-[11.5px] transition ${
                        (selectedProject?.current_branch || "develop") === br
                          ? "bg-purple-900/30 text-purple-300 border border-purple-500/30"
                          : "hover:bg-slate-800/60 text-slate-300"
                      }`}
                    >
                      <span className="font-mono truncate">{br}</span>
                      {(selectedProject?.current_branch || "develop") === br && (
                        <Check className="h-3 w-3 text-purple-400" />
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Dynamic Agent Toggles in Header */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setAgentToggles((p) => ({ ...p, agent2: !p.agent2 }))}
                className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium border transition ${
                  agentToggles.agent2
                    ? "bg-emerald-950/60 border-emerald-500/40 text-emerald-300"
                    : "bg-slate-900 border-slate-700 text-slate-500 line-through"
                }`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${agentToggles.agent2 ? "bg-emerald-400" : "bg-slate-600"}`} />
                Agent 2 {agentToggles.agent2 ? "ON" : "OFF"}
              </button>

              <button
                onClick={() => setAgentToggles((p) => ({ ...p, agent4: !p.agent4 }))}
                className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium border transition ${
                  agentToggles.agent4
                    ? "bg-emerald-950/60 border-emerald-500/40 text-emerald-300"
                    : "bg-slate-900 border-slate-700 text-slate-500 line-through"
                }`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${agentToggles.agent4 ? "bg-emerald-400" : "bg-slate-600"}`} />
                Agent 4 {agentToggles.agent4 ? "ON" : "OFF"}
              </button>

              <button
                onClick={() => setAgentToggles((p) => ({ ...p, agent5: !p.agent5 }))}
                className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium border transition ${
                  agentToggles.agent5
                    ? "bg-emerald-950/60 border-emerald-500/40 text-emerald-300"
                    : "bg-slate-900 border-slate-700 text-slate-500 line-through"
                }`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${agentToggles.agent5 ? "bg-emerald-400" : "bg-slate-600"}`} />
                Agent 5 {agentToggles.agent5 ? "ON" : "OFF"}
              </button>

              <button
                onClick={() => setShowConfigModal(true)}
                className="flex items-center gap-1 px-2.5 py-0.5 rounded-lg bg-[#141b2a] border border-cyan-500/30 text-cyan-300 hover:bg-cyan-950/50 text-[11px] font-medium transition"
              >
                <SettingsIcon className="h-3 w-3" />
                Configure
              </button>
            </div>

            <div className="h-4 w-[1px] bg-slate-800 mx-1" />

            <div className="relative flex items-center">
              <Search className="h-3.5 w-3.5 text-slate-500 absolute left-2.5 pointer-events-none" />
              <input
                type="text"
                placeholder="Search..."
                className="bg-[#101522] border border-slate-800 rounded-lg pl-8 pr-3 py-1 text-[12px] text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-cyan-500/50 w-36 transition"
              />
            </div>

            <button className="relative p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/60 transition">
              <Bell className="h-4 w-4" />
              <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-rose-500 ring-2 ring-[#0a0d14]" />
            </button>

            <div className="h-7 w-7 rounded-full bg-gradient-to-tr from-cyan-600 to-indigo-600 text-white font-semibold text-[11px] flex items-center justify-center border border-cyan-400/30">
              TH
            </div>
          </div>
        </header>

        {/* 3-COLUMN WORKSPACE BODY */}
        <div className="flex-1 flex min-h-0 divide-x divide-slate-800/70">
          {/* COLUMN 1: LEFT SIDEBAR */}
          <div className="w-64 shrink-0 flex flex-col bg-[#0b0e17] overflow-y-auto">
            <div className="p-3 border-b border-slate-800/60">
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-slate-300 text-[12px]">Projects</span>
                <button
                  onClick={async () => {
                    const name = prompt("Enter project name:", "My AI Project");
                    if (name) {
                      const p = await createProject(name);
                      setProjects((prev) => [p, ...prev]);
                      setSelectedProject(p);
                      setMessages([]);
                    }
                  }}
                  className="flex items-center gap-1 text-[11px] px-2 py-0.5 rounded bg-blue-600/20 text-cyan-400 border border-cyan-500/30 hover:bg-blue-600/30 transition"
                >
                  <Plus className="h-3 w-3" />
                  New Project
                </button>
              </div>

              {projects.length === 0 ? (
                <div className="p-4 text-center text-slate-500 text-[11px] border border-dashed border-slate-800 rounded-lg">
                  No projects yet.<br />Start by describing your requirements below.
                </div>
              ) : (
                <div className="space-y-1">
                  {projects.map((p) => (
                    <div
                      key={p.id}
                      onClick={() => setSelectedProject(p)}
                      className={`p-2 rounded-lg cursor-pointer transition ${
                        selectedProject?.id === p.id
                          ? "bg-blue-950/40 border border-blue-500/40"
                          : "hover:bg-slate-800/40 border border-transparent"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <div className="h-6 w-6 rounded bg-blue-500/20 border border-blue-500/40 flex items-center justify-center text-blue-400 shrink-0">
                          <FolderGit2 className="h-3.5 w-3.5" />
                        </div>
                        <div className="min-w-0">
                          <div className="font-medium text-white text-[12px] truncate">{p.name}</div>
                          <div className="text-[10px] text-slate-400 truncate">{p.target_framework}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* AI Agents Status */}
            <div className="p-3 border-b border-slate-800/60">
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-slate-300 text-[12px]">AI Agents</span>
                <button
                  onClick={() => setShowConfigModal(true)}
                  className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-cyan-400 transition"
                >
                  <Wrench className="h-3 w-3" />
                  Configure
                </button>
              </div>

              <div className="space-y-1.5 text-[11.5px]">
                <div className="flex items-center justify-between p-1.5 rounded-md hover:bg-slate-800/30">
                  <div className="flex items-center gap-2">
                    <div className="h-6 w-6 rounded bg-emerald-950/80 border border-emerald-500 flex items-center justify-center text-emerald-400">
                      <FileCode2 className="h-3.5 w-3.5" />
                    </div>
                    <div>
                      <div className="font-medium text-white text-[11px]">Agent 1 <span className="text-slate-400 font-normal">Doc Reviewer</span></div>
                      <div className="text-[10px] text-emerald-400">Mandatory (Active)</div>
                    </div>
                  </div>
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                </div>

                <div className="flex items-center justify-between p-1.5 rounded-md hover:bg-slate-800/30">
                  <div className="flex items-center gap-2">
                    <div className="h-6 w-6 rounded bg-cyan-950/80 border border-cyan-500 flex items-center justify-center text-cyan-400">
                      <Boxes className="h-3.5 w-3.5" />
                    </div>
                    <div>
                      <div className="font-medium text-white text-[11px]">Agent 2 <span className="text-slate-400 font-normal">Mock Dev</span></div>
                      <div className="text-[10px] text-cyan-400">{agentToggles.agent2 ? "Enabled" : "Disabled (Standalone)"}</div>
                    </div>
                  </div>
                  <span className={`text-[10px] ${agentToggles.agent2 ? "text-cyan-400" : "text-slate-500"}`}>{agentToggles.agent2 ? "ON" : "OFF"}</span>
                </div>

                <div className="flex items-center justify-between p-1.5 rounded-md hover:bg-slate-800/30">
                  <div className="flex items-center gap-2">
                    <div className="h-6 w-6 rounded bg-blue-600/20 border border-blue-500 flex items-center justify-center text-blue-400">
                      <Code2 className="h-3.5 w-3.5" />
                    </div>
                    <div>
                      <div className="font-medium text-white text-[11px]">Agent 3 <span className="text-slate-400 font-normal">Main Coder</span></div>
                      <div className="text-[10px] text-blue-400">Mandatory (Active)</div>
                    </div>
                  </div>
                  <CheckCircle2 className="h-3.5 w-3.5 text-blue-400" />
                </div>

                <div className="flex items-center justify-between p-1.5 rounded-md hover:bg-slate-800/30">
                  <div className="flex items-center gap-2">
                    <div className="h-6 w-6 rounded bg-purple-950/60 border border-purple-600/40 flex items-center justify-center text-purple-400">
                      <FlaskConical className="h-3.5 w-3.5" />
                    </div>
                    <div>
                      <div className="font-medium text-slate-300 text-[11px]">Agent 4 <span className="text-slate-400 font-normal">QA Testing</span></div>
                      <div className="text-[10px] text-purple-400">{agentToggles.agent4 ? "Enabled" : "Skipped"}</div>
                    </div>
                  </div>
                  <span className={`text-[10px] ${agentToggles.agent4 ? "text-purple-400" : "text-slate-500"}`}>{agentToggles.agent4 ? "ON" : "OFF"}</span>
                </div>

                <div className="flex items-center justify-between p-1.5 rounded-md hover:bg-slate-800/30">
                  <div className="flex items-center gap-2">
                    <div className="h-6 w-6 rounded bg-amber-950/60 border border-amber-600/40 flex items-center justify-center text-amber-400">
                      <ShieldCheck className="h-3.5 w-3.5" />
                    </div>
                    <div>
                      <div className="font-medium text-slate-300 text-[11px]">Agent 5 <span className="text-slate-400 font-normal">Security SAST</span></div>
                      <div className="text-[10px] text-amber-400">{agentToggles.agent5 ? "Enabled" : "Not Scanned"}</div>
                    </div>
                  </div>
                  <span className={`text-[10px] ${agentToggles.agent5 ? "text-amber-400" : "text-slate-500"}`}>{agentToggles.agent5 ? "ON" : "OFF"}</span>
                </div>
              </div>
            </div>
          </div>

          {/* COLUMN 2: CENTER CHAT */}
          <div className="flex-1 flex flex-col min-w-0 bg-[#090b12]">
            <div className="h-10 shrink-0 border-b border-slate-800/60 px-4 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-slate-200 text-[13px]">Chat & Agent Activity</span>
                <span className="text-[11px] text-slate-500 hidden md:inline">Ask, plan, approve and build with autonomous AI agents</span>
                {streamStatus !== "idle" && (
                  <span className="ml-2 flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] bg-cyan-950/70 border border-cyan-500/30 text-cyan-400">
                    <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse" />
                    {streamStatus}
                  </span>
                )}
              </div>
              <button
                onClick={() => setMessages([])}
                className="text-[11px] text-slate-400 hover:text-white px-2 py-0.5 rounded hover:bg-slate-800/40"
              >
                Clear
              </button>
            </div>

            {/* Messages Scroll Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center p-8 max-w-lg mx-auto">
                  <div className="h-12 w-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 mb-4 shadow-lg shadow-cyan-500/10">
                    <Sparkles className="h-6 w-6" />
                  </div>
                  <h3 className="text-white font-semibold text-[16px] mb-1.5">Fresh Workspace Ready</h3>
                  <p className="text-slate-400 text-[12.5px] leading-relaxed mb-6">
                    Say &quot;Hi&quot; to converse, or describe any software project to build from scratch.
                  </p>
                  <div className="grid grid-cols-2 gap-2.5 w-full text-left">
                    <button
                      onClick={() => setInputMessage("Build a Student Management CRUD API with FastAPI and SQLite.")}
                      className="p-3 rounded-xl bg-[#0f1422] border border-slate-800 hover:border-cyan-500/40 text-[11.5px] text-slate-300 transition"
                    >
                      💡 <span className="font-medium text-white">Student Management API</span>
                      <p className="text-[10px] text-slate-500 mt-1">FastAPI CRUD with SQLite persistence</p>
                    </button>
                    <button
                      onClick={() => setInputMessage("Build JWT Authentication service with login, logout and refresh token.")}
                      className="p-3 rounded-xl bg-[#0f1422] border border-slate-800 hover:border-cyan-500/40 text-[11.5px] text-slate-300 transition"
                    >
                      💡 <span className="font-medium text-white">JWT Auth Service</span>
                      <p className="text-[10px] text-slate-500 mt-1">Role-based access control & refresh tokens</p>
                    </button>
                  </div>
                </div>
              ) : (
                messages.map((m) => (
                  <div key={m.id} className="flex items-start gap-3">
                    {m.sender === "user" ? (
                      <div className="h-7 w-7 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center text-xs font-semibold text-white shrink-0 mt-0.5">
                        TH
                      </div>
                    ) : m.sender === "assistant" ? (
                      <div className="h-7 w-7 rounded-full bg-cyan-950 border border-cyan-500 flex items-center justify-center text-cyan-400 shrink-0 mt-0.5">
                        <Bot className="h-3.5 w-3.5" />
                      </div>
                    ) : m.sender === "agent1" ? (
                      <div className="h-7 w-7 rounded-full bg-emerald-950 border border-emerald-500 flex items-center justify-center text-emerald-400 shrink-0 mt-0.5">
                        <FileCode2 className="h-3.5 w-3.5" />
                      </div>
                    ) : (
                      <div className="h-7 w-7 rounded-full bg-blue-950 border border-blue-500 flex items-center justify-center text-blue-400 shrink-0 mt-0.5">
                        <Code2 className="h-3.5 w-3.5" />
                      </div>
                    )}

                    <div className="flex-1 space-y-3 max-w-2xl">
                      <div className="bg-[#121624] border border-slate-800 rounded-xl p-3.5 shadow-sm">
                        <div className="flex items-center justify-between mb-1.5">
                          <span className={`font-semibold text-[12px] ${m.sender === "user" ? "text-white" : m.sender === "assistant" ? "text-cyan-400" : m.sender === "agent1" ? "text-emerald-400" : "text-blue-400"}`}>
                            {m.senderName}
                          </span>
                          <span className="text-[10px] text-slate-500">{m.timestamp}</span>
                        </div>
                        {m.text && <p className="text-slate-200 leading-relaxed text-[13px]">{m.text}</p>}

                        {m.checklist && (
                          <div className="mt-3 space-y-1 text-[11.5px] text-slate-300">
                            {m.checklist.map((item, idx) => (
                              <div key={idx} className="flex items-center gap-2 text-emerald-400">
                                <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                                <span>{item}</span>
                              </div>
                            ))}
                          </div>
                        )}

                        {m.workingTasks && (
                          <div className="mt-3 space-y-1.5 text-[11.5px] text-slate-300">
                            {m.workingTasks.map((t, idx) => (
                              <div key={idx} className="flex items-center gap-2 text-cyan-300">
                                <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse" />
                                <span>{t}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      {m.approvalRequired && (
                        <div className="bg-[#181308] border-2 border-amber-600/60 rounded-xl p-4 shadow-lg shadow-amber-950/20">
                          <div className="flex items-center gap-2.5 mb-1.5">
                            <div className="h-6 w-6 rounded-full bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 font-semibold text-xs">
                              !
                            </div>
                            <span className="font-semibold text-amber-300 text-[13px]">Human Approval Required</span>
                            <span className="text-[10px] text-amber-500/80 ml-auto">{m.timestamp}</span>
                          </div>

                          <p className="text-amber-100/90 text-[12.5px] mb-3 ml-8">
                            Please review the technical design and test specifications.
                            <br />
                            Shall I proceed with the implementation?
                          </p>

                          <div className="flex items-center gap-3 ml-8">
                            <button
                              onClick={handleApprove}
                              className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-[12px] flex items-center gap-1.5 shadow-md shadow-emerald-700/30 transition"
                            >
                              <Check className="h-3.5 w-3.5" /> Approve & Continue
                            </button>

                            <button
                              onClick={() => setShowFeedbackModal(true)}
                              className="px-3.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 font-medium text-[12px] flex items-center gap-1.5 transition"
                            >
                              <RotateCcw className="h-3.5 w-3.5 text-amber-400" /> Request Changes
                            </button>
                          </div>

                          {showFeedbackModal && (
                            <div className="mt-3 ml-8 p-3 rounded-lg bg-[#0e121e] border border-amber-600/40 space-y-2">
                              <span className="text-[11px] font-semibold text-amber-300">Specify required changes for Agent 1:</span>
                              <input
                                type="text"
                                value={feedbackInput}
                                onChange={(e) => setFeedbackInput(e.target.value)}
                                placeholder="e.g., Add Redis caching to token validation and rate limiting..."
                                className="w-full bg-[#080b12] border border-slate-700 rounded px-2.5 py-1.5 text-[12px] text-slate-200 focus:outline-none focus:border-amber-500"
                              />
                              <div className="flex items-center gap-2 justify-end">
                                <button
                                  onClick={() => setShowFeedbackModal(false)}
                                  className="px-2.5 py-1 text-[11px] text-slate-400 hover:text-slate-200"
                                >
                                  Cancel
                                </button>
                                <button
                                  onClick={handleRequestChanges}
                                  className="px-3 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded text-[11px] font-medium"
                                >
                                  Submit Revisions
                                </button>
                              </div>
                            </div>
                          )}

                          {specApproved === true && (
                            <div className="mt-3 ml-8 text-[11px] text-emerald-400 flex items-center gap-1.5">
                              <CheckCircle2 className="h-3 w-3" /> Specs approved! Main Coder (Agent 3) resumed.
                            </div>
                          )}
                          {specApproved === false && (
                            <div className="mt-3 ml-8 text-[11px] text-amber-400 flex items-center gap-1.5">
                              <AlertTriangle className="h-3 w-3" /> Revision requested. Looping back to Agent 1.
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Bottom Chat Input Box */}
            <div className="p-3 border-t border-slate-800/80 bg-[#0a0d14]">
              {/* Attached Files Preview Chips */}
              {attachedFiles.length > 0 && (
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  {attachedFiles.map((f, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#141b2b] border border-cyan-500/40 text-[11.5px] text-cyan-300 shadow-sm"
                    >
                      <FileText className="h-3.5 w-3.5" />
                      <span className="font-medium truncate max-w-[200px]">{f.name}</span>
                      <span className="text-[10px] text-slate-500">({(f.size / 1024).toFixed(1)} KB)</span>
                      <button
                        type="button"
                        onClick={() => setAttachedFiles((prev) => prev.filter((_, idx) => idx !== i))}
                        className="ml-1 text-slate-400 hover:text-white"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* Hidden File Input for PDF / DOCX / MD / TXT */}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.doc,.docx,.md,.txt,.json,.csv"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files) {
                    const newFiles = Array.from(e.target.files);
                    setAttachedFiles((prev) => [...prev, ...newFiles]);
                  }
                }}
              />

              <form
                onSubmit={handleSendMessage}
                className="border border-slate-800 focus-within:border-cyan-500/60 rounded-xl bg-[#101420] p-2 transition"
              >
                <input
                  ref={chatInputRef}
                  type="text"
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  placeholder={
                    attachedFiles.length > 0
                      ? "Add notes or prompt for the attached document..."
                      : "Describe your software project, or say 'Hi'..."
                  }
                  disabled={isSubmitting}
                  className="w-full bg-transparent text-[13px] text-slate-200 placeholder:text-slate-600 focus:outline-none px-2 py-1 disabled:opacity-50"
                />

                <div className="flex items-center justify-between pt-2 border-t border-slate-800/50 mt-1">
                  <div className="flex items-center gap-2 relative">
                    {/* Paperclip Button */}
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      title="Attach requirements document (Word, PDF, Markdown, Text)"
                      className="text-slate-500 hover:text-cyan-400 p-1.5 rounded-lg hover:bg-slate-800/70 transition"
                    >
                      <Paperclip className="h-4 w-4" />
                    </button>

                    {/* @ Mention Button */}
                    <button
                      type="button"
                      onClick={() => {
                        setInputMessage((prev) => (prev ? `${prev} @` : "@"));
                        chatInputRef.current?.focus();
                      }}
                      title="Mention an Agent"
                      className="text-slate-500 hover:text-cyan-400 p-1.5 rounded-lg hover:bg-slate-800/70 transition"
                    >
                      <AtSign className="h-4 w-4" />
                    </button>

                    {/* Agent Selector Dropdown Pill */}
                    <div className="relative">
                      <button
                        type="button"
                        onClick={() => setShowAgentMenu((prev) => !prev)}
                        className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700/80 text-[11px] text-slate-200 border border-slate-700 transition"
                      >
                        <Code2 className={`h-3.5 w-3.5 ${currentActiveAgent.color}`} />
                        <span>{currentActiveAgent.name}</span>
                        <ChevronDown className="h-3 w-3 text-slate-400 ml-0.5" />
                      </button>

                      {/* Dropdown Menu */}
                      {showAgentMenu && (
                        <div className="absolute bottom-full left-0 mb-2 w-64 bg-[#0e121d] border border-slate-700 rounded-xl shadow-2xl p-1.5 z-50 space-y-0.5 animate-in fade-in duration-150">
                          <div className="px-2 py-1 text-[10px] uppercase font-semibold tracking-wider text-slate-500">
                            Direct message to Agent
                          </div>
                          {[
                            { id: "auto", name: "Auto (All Agents)", role: "Standard multi-agent topology", color: "text-cyan-400", enabled: true },
                            { id: "agent1", name: "Agent 1: Doc Reviewer", role: "Requirements & Specifications", color: "text-emerald-400", enabled: true },
                            { id: "agent2", name: "Agent 2: Mock Vendor", role: "Mock third-party APIs", color: "text-cyan-400", enabled: agentToggles.agent2 },
                            { id: "agent3", name: "Agent 3: Main Coder", role: "Channel code implementation", color: "text-blue-400", enabled: true },
                            { id: "agent4", name: "Agent 4: QA Engineer", role: "Contract & black-box testing", color: "text-purple-400", enabled: agentToggles.agent4 },
                            { id: "agent5", name: "Agent 5: Security Reviewer", role: "SAST & vulnerability audit", color: "text-amber-400", enabled: agentToggles.agent5 },
                          ]
                            .filter((ag) => ag.enabled)
                            .map((ag) => (
                              <button
                                key={ag.id}
                                type="button"
                                onClick={() => {
                                  setSelectedAgent({ id: ag.id, name: ag.name, color: ag.color });
                                  setShowAgentMenu(false);
                                }}
                                className={`w-full flex items-start gap-2 p-2 rounded-lg text-left transition ${
                                  currentActiveAgent.id === ag.id
                                    ? "bg-blue-600/20 text-white border border-blue-500/30"
                                    : "hover:bg-slate-800/60 text-slate-300"
                                }`}
                              >
                                <Code2 className={`h-3.5 w-3.5 mt-0.5 shrink-0 ${ag.color}`} />
                                <div>
                                  <div className="text-[11.5px] font-medium leading-none mb-1">{ag.name}</div>
                                  <div className="text-[10px] text-slate-500">{ag.role}</div>
                                </div>
                              </button>
                            ))}
                        </div>
                      )}
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={isSubmitting || (!inputMessage.trim() && attachedFiles.length === 0)}
                    className="h-7 w-7 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:hover:bg-blue-600 text-white flex items-center justify-center transition shadow-md shadow-blue-600/30"
                  >
                    {isSubmitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                  </button>
                </div>
              </form>

              <div className="flex items-center justify-between text-[10px] text-slate-600 px-1 pt-1.5">
                <span>Enter to submit &nbsp;|&nbsp; Conversational greetings & full specs both supported</span>
                <span>AAISE v1.0 Enterprise</span>
              </div>
            </div>
          </div>

          {/* COLUMN 3: RIGHT PANEL */}
          <div className="w-96 shrink-0 flex flex-col bg-[#0a0d15] overflow-hidden">
            <div className="h-10 shrink-0 border-b border-slate-800/80 flex items-center justify-between px-2 text-[12px]">
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setActiveTab("artifacts")}
                  className={`px-3 py-1.5 rounded-md font-medium transition ${
                    activeTab === "artifacts"
                      ? "bg-[#141b2b] text-cyan-400 border border-cyan-500/30"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Artifacts ({artifacts.length})
                </button>
                <button
                  onClick={() => {
                    setActiveTab("diff");
                    if (selectedProject?.id) {
                      fetchProjectDiff(selectedProject.id).then((d) => setCodeDiff(d));
                    }
                  }}
                  className={`px-3 py-1.5 rounded-md font-medium transition ${
                    activeTab === "diff"
                      ? "bg-[#141b2b] text-cyan-400 border border-cyan-500/30"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Code Diff
                </button>
                <button
                  onClick={() => setActiveTab("tests")}
                  className={`px-3 py-1.5 rounded-md font-medium transition ${
                    activeTab === "tests"
                      ? "bg-[#141b2b] text-cyan-400 border border-cyan-500/30"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Test Results
                </button>
                <button
                  onClick={() => setActiveTab("security")}
                  className={`px-3 py-1.5 rounded-md font-medium transition ${
                    activeTab === "security"
                      ? "bg-[#141b2b] text-cyan-400 border border-cyan-500/30"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  Security
                </button>
              </div>

              {selectedProject && (
                <a
                  href={getProjectDownloadUrl(selectedProject.id)}
                  download
                  title="Download Project ZIP"
                  className="p-1.5 rounded-lg text-slate-400 hover:text-cyan-400 hover:bg-slate-800/60 transition"
                >
                  <Download className="h-4 w-4" />
                </a>
              )}
            </div>

            {/* Panel Content */}
            <div className="flex-1 overflow-y-auto p-3 space-y-3">
              {activeTab === "diff" ? (
                codeDiff ? (
                  <pre className="font-mono text-[11px] text-slate-300 p-2.5 rounded-lg bg-[#0c101b] border border-slate-800 overflow-x-auto whitespace-pre-wrap leading-relaxed">
                    {codeDiff}
                  </pre>
                ) : (
                  <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500 text-[11.5px]">
                    <GitBranch className="h-8 w-8 text-slate-600 mb-2" />
                    No code diff available yet.<br />When Agent 3 implements code, git diffs will appear here.
                  </div>
                )
              ) : activeTab === "artifacts" ? (
                artifacts.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500 text-[11.5px]">
                    <FileCode2 className="h-8 w-8 text-slate-600 mb-2" />
                    No project artifacts generated yet.<br />Artifacts will appear here when Agent 1 generates specifications or Agent 3 creates code.
                  </div>
                ) : (
                  <div className="space-y-2 text-[11.5px]">
                    {artifacts.map((art) => (
                      <div
                        key={art.id}
                        className="flex items-center justify-between p-2 rounded bg-[#101422] border border-cyan-500/30"
                      >
                        <div className="flex items-center gap-2">
                          {art.file_path.includes("TEST") ? (
                            <FlaskConical className="h-4 w-4 text-purple-400 shrink-0" />
                          ) : (
                            <FileCode2 className="h-4 w-4 text-cyan-400 shrink-0" />
                          )}
                          <span className="font-mono text-slate-200 truncate">{art.file_path}</span>
                        </div>
                        <span className="text-[10px] text-emerald-400 font-medium">Generated</span>
                      </div>
                    ))}
                  </div>
                )
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500 text-[11.5px]">
                  <ShieldCheck className="h-8 w-8 text-slate-600 mb-2" />
                  No test results or security scans yet.<br />They will be recorded after code execution.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <AgentConfigModal
        isOpen={showConfigModal}
        onClose={() => setShowConfigModal(false)}
        agentToggles={agentToggles}
        onSave={(newToggles) => setAgentToggles(newToggles)}
      />
    </div>
  );
}
