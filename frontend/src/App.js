import React, { useMemo, useState } from "react";
import useHealth from "./hooks/useHealth";

const navItems = [
  { id: "home", label: "HOME" },
  { id: "workflow", label: "WORKFLOW" },
  { id: "codex", label: "CODEX" },
  { id: "validation", label: "VALIDATION" },
  { id: "deploy", label: "DEPLOY" },
  { id: "freeze", label: "FREEZE" },
  { id: "settings", label: "SETTINGS" },
];

const commandState = {
  nextAction: "Complete vNext integration certification",
  activeTask: "FORJA Phase 2.10",
  activeSystem: "FORJA",
  priority: "HIGH",
};

const globalStatus = [
  {
    label: "Ecosystem Status",
    value: "DEGRADED",
    detail: "Centinela blocked; FORJA local only",
    tone: "warning",
  },
  {
    label: "Active Blockers",
    value: "3 ACTIVE",
    detail: "1 critical, 2 high",
    tone: "danger",
  },
  {
    label: "Active Audits",
    value: "1 ACTIVE",
    detail: "FORJA Phase 2.10",
    tone: "warning",
  },
  {
    label: "Active Deploys",
    value: "0",
    detail: "No active deploy",
    tone: "neutral",
  },
  {
    label: "Freeze State",
    value: "NOT_READY",
    detail: "Blocked by traceability",
    tone: "warning",
  },
];

const ecosystemSystems = [
  {
    name: "Centinela",
    state: "Blocked",
    tone: "danger",
    evidence: "D:/AIC-REPORTS/FINAL/CENTINELA_FINAL_ENTERPRISE_FOUNDATION_STATUS.md",
    detail: "Source ready, live sync blocked; freeze NOT_READY.",
  },
  {
    name: "Cerebro",
    state: "Operational",
    tone: "good",
    evidence: "D:/AIC-REPORTS/CEREBRO/FINAL/CEREBRO_FINAL_OPERATIONAL_CLOSURE.md",
    detail: "Enterprise Automation Foundation closed with source-to-live verified.",
  },
  {
    name: "Forja",
    state: "Degraded",
    tone: "warning",
    evidence: "D:/AIC-REPORTS/FORJA/VALIDATIONS/FORJA_PHASE_2_3_VALIDATION.md",
    detail: "Command shell passes locally; source traceability and dev auth remain open.",
  },
];

const executiveBlockers = [
  {
    id: "CENTINELA_LIVE_SYNC_BLOCKED",
    severity: "CRITICAL",
    system: "Centinela",
    action: "Resolve Vercel deploy for validated frontend source before freeze.",
    impact: "Centinela cannot be honestly frozen while live is stale.",
  },
  {
    id: "FORJA_SOURCE_TRACEABILITY_MISSING",
    severity: "HIGH",
    system: "Forja",
    action: "Recover or initialize git source traceability before deploy/freeze trust.",
    impact: "Branch, remote, commit and staged-secret checks are unavailable.",
  },
  {
    id: "FORJA_DEV_AUTH_HARDCODED_BLOCKER",
    severity: "HIGH",
    system: "Forja",
    action: "Gate or replace development auth before production trust claims.",
    impact: "Auth cannot support governance or deploy confidence yet.",
  },
];

const auditStatus = {
  active: [{ name: "FORJA Phase 2.10", state: "IN_PROGRESS" }],
  pending: [{ name: "Post-vNext source/live hardening", state: "PENDING" }],
  completed: [
    { name: "Phase 2.1 implementation audit", state: "COMPLETED" },
    { name: "Phase 2.2 source stabilization", state: "COMPLETED" },
    { name: "Phase 2.3 command shell", state: "COMPLETED" },
    { name: "Phase 2.4 executive cabin", state: "COMPLETED" },
    { name: "Phase 2.5 workflow cabin", state: "COMPLETED" },
    { name: "Phase 2.6 codex cabin", state: "COMPLETED" },
    { name: "Phase 2.7 validation cabin", state: "COMPLETED" },
    { name: "Phase 2.8 deploy cabin", state: "COMPLETED" },
    { name: "Phase 2.9 freeze cabin", state: "COMPLETED" },
  ],
};

const deployStatus = {
  lastDeploy: "NOT_VERIFIED",
  pending: "0",
  blocked: "1",
  validated: "0",
  reason: "FORJA has no git/source-to-live traceability.",
};

const freezeStatus = {
  active: "0",
  blocked: "2",
  pending: "1",
  approved: "0",
  reason: "Centinela live sync and FORJA traceability block honest freeze.",
};

const executivePriorities = [
  {
    level: "CRITICAL",
    text: "Centinela live sync remains blocked; freeze cannot be approved.",
  },
  {
    level: "HIGH",
    text: "FORJA source traceability must be recovered before deploy trust.",
  },
  {
    level: "NORMAL",
    text: "Continue FORJA vNext implementation with shell-only honest states.",
  },
];

const executiveDecision =
  "Certify the integrated vNext operator experience; keep deploy and freeze blocked until source/live, rollback and auth evidence exist.";

const workflowSteps = [
  {
    label: "Idea",
    state: "COMPLETED",
    detail: "vNext operator workflow accepted",
    owner: "OPERATOR",
  },
  {
    label: "Plan",
    state: "COMPLETED",
    detail: "Workflow Cabin scope defined",
    owner: "FORJA",
  },
  {
    label: "Forja",
    state: "COMPLETED",
    detail: "Workflow Cabin foundation validated",
    owner: "FORJA",
  },
  {
    label: "Codex",
    state: "COMPLETED",
    detail: "Codex Cabin foundation validated",
    owner: "CODEX",
  },
  {
    label: "Validation",
    state: "COMPLETED",
    detail: "Validation Cabin foundation validated",
    owner: "VALIDATION",
  },
  {
    label: "Deploy",
    state: "COMPLETED",
    detail: "Deploy Cabin foundation validated",
    owner: "DEPLOY",
  },
  {
    label: "Freeze",
    state: "COMPLETED",
    detail: "Freeze Cabin foundation validated; approval remains NO",
    owner: "GOVERNANCE",
  },
];

const workflowOperation = {
  task: "FORJA Phase 2.10 vNext Integration Certification",
  system: "FORJA",
  phase: "vNext integration and operator certification",
  priority: "HIGH",
  status: "IN_PROGRESS",
  previousStep: "Freeze Cabin",
  currentStep: "Integrated platform",
  nextStep: "Source/live and auth hardening",
  evidence: "Integrated local build, browser smoke and final reports required before closure",
};

const workflowNextAction =
  "Validate the complete vNext operator flow across all cabins; keep deploy and freeze approval locked.";

const workflowTasks = [
  {
    title: "Validate vNext cabin integration",
    state: "In Progress",
    owner: "FORJA",
    priority: "HIGH",
  },
  {
    title: "Run Phase 2.10 build and browser smoke",
    state: "Validation",
    owner: "VALIDATION",
    priority: "HIGH",
  },
  {
    title: "Generate Phase 2.10 final reports",
    state: "Pending",
    owner: "FORJA",
    priority: "NORMAL",
  },
  {
    title: "Command Shell foundation",
    state: "Completed",
    owner: "FORJA",
    priority: "NORMAL",
  },
  {
    title: "Executive Cabin foundation",
    state: "Completed",
    owner: "FORJA",
    priority: "NORMAL",
  },
  {
    title: "Workflow Cabin foundation",
    state: "Completed",
    owner: "FORJA",
    priority: "NORMAL",
  },
  {
    title: "Codex Cabin foundation",
    state: "Completed",
    owner: "CODEX",
    priority: "NORMAL",
  },
  {
    title: "Validation Cabin foundation",
    state: "Completed",
    owner: "VALIDATION",
    priority: "NORMAL",
  },
  {
    title: "Deploy Cabin foundation",
    state: "Completed",
    owner: "DEPLOY",
    priority: "NORMAL",
  },
  {
    title: "Freeze Cabin foundation",
    state: "Completed",
    owner: "GOVERNANCE",
    priority: "NORMAL",
  },
  {
    title: "Recover FORJA source traceability",
    state: "Blocked",
    owner: "OPERATOR",
    priority: "HIGH",
  },
  {
    title: "Replace or gate development auth",
    state: "Blocked",
    owner: "GOVERNANCE",
    priority: "HIGH",
  },
];

const workflowBlockers = [
  {
    blocker: "FORJA_SOURCE_TRACEABILITY_MISSING",
    origin: "Phase 2.2 source stabilization",
    impact: "Deploy and freeze trust cannot be validated from git evidence.",
    action: "Recover or initialize FORJA repository before deploy/freeze gates.",
  },
  {
    blocker: "FORJA_DEV_AUTH_HARDCODED_BLOCKER",
    origin: "Phase 2.2 dev auth review",
    impact: "Auth cannot support production governance claims.",
    action: "Gate development auth or replace it with configured auth before production.",
  },
  {
    blocker: "CENTINELA_LIVE_SYNC_BLOCKED",
    origin: "Centinela final freeze decision",
    impact: "Ecosystem freeze remains blocked while Centinela live is stale.",
    action: "Resolve Centinela Vercel deploy before ecosystem freeze.",
  },
];

const codexSession = {
  id: "FORJA-CODEX-2.10",
  system: "FORJA",
  phase: "FORJA Phase 2.10",
  state: "IN_PROGRESS",
  lastResult: "All primary cabins exist locally; vNext integration and operator certification are under validation.",
};

const promptPipeline = [
  {
    state: "Draft",
    prompt: "Phase 2.7 Validation Cabin scope",
    owner: "OPERATOR",
    detail: "Not ready to send until Codex Cabin is validated.",
  },
  {
    state: "Ready",
    prompt: "Phase 2.6 validation request",
    owner: "FORJA",
    detail: "Ready after implementation: build, browser smoke and report generation.",
  },
  {
    state: "Sent",
    prompt: "Phase 2.6 implementation directive",
    owner: "OPERATOR",
    detail: "Accepted as the active operational instruction.",
  },
  {
    state: "Processing",
    prompt: "Build Codex Cabin foundation",
    owner: "CODEX",
    detail: "Session center, prompt pipeline, result center, memory panel and operator actions.",
  },
  {
    state: "Completed",
    prompt: "Phase 2.5 Workflow Cabin completion",
    owner: "CODEX",
    detail: "Validated with build and desktop/mobile smoke.",
  },
  {
    state: "Failed",
    prompt: "No failed prompt recorded",
    owner: "SYSTEM",
    detail: "Failure lane remains visible; no failure is fabricated.",
  },
];

const codexResultCenter = {
  result: "RESULT_PENDING_FOR_PHASE_2_6",
  received:
    "Last confirmed result: Phase 2.5 completed PASS. Current Phase 2.6 result requires validation.",
  validations: ["npm run build", "browser smoke", "UX context visibility", "report generation"],
  blockers: [
    "FORJA_SOURCE_TRACEABILITY_MISSING",
    "FORJA_DEV_AUTH_HARDCODED_BLOCKER",
    "CENTINELA_LIVE_SYNC_BLOCKED",
  ],
  risks: [
    "Do not use Codex Cabin as generic chat.",
    "Do not present prompt history as infinite operational memory.",
    "Do not unlock deploy or freeze from a Codex result alone.",
  ],
  classification: "OPERATIONAL_CONTEXT_IN_PROGRESS",
};

const codexPhaseTracking = {
  phase: "FORJA 2.10",
  subphase: "VNEXT INTEGRATION",
  progress: "IN_PROGRESS",
  pending: [
    "Frontend build",
    "Desktop/mobile browser smoke",
    "Operator flow validation",
    "Final certification reports",
  ],
};

const codexMemory = [
  {
    label: "Active context",
    value: "FORJA vNext Human Cabin reconstruction",
    detail: "Phase 2 implementation sequence is preserved.",
  },
  {
    label: "Active system",
    value: "FORJA",
    detail: "Centinela and Cerebro remain ecosystem context, not active edit targets.",
  },
  {
    label: "Active audit",
    value: "FORJA Phase 2.10",
    detail: "vNext integration and operator certification under local validation.",
  },
  {
    label: "Freeze",
    value: "NOT_READY",
    detail: "Traceability, auth and ecosystem blockers remain visible.",
  },
];

const codexOperatorActions = [
  {
    question: "Que enviar?",
    answer: "Only scoped Phase 2.6 validation or remediation prompts tied to the active FORJA task.",
  },
  {
    question: "Que validar?",
    answer: "Build, browser smoke, session visibility, context visibility and next action visibility.",
  },
  {
    question: "Que corregir?",
    answer: "Only failures found in Codex Cabin UX or operational state clarity.",
  },
  {
    question: "Que desplegar?",
    answer: "Nothing. Deploy remains locked until source traceability and governance blockers are resolved.",
  },
];

const validationLanes = [
  {
    state: "Pending",
    items: [
      {
        name: "Generate Phase 2.10 final integration reports",
        system: "FORJA",
        evidence: "Pending report files",
      },
      {
        name: "Post-vNext deploy/freeze hardening",
        system: "FORJA",
        evidence: "Blocked until source/live and auth evidence exists",
      },
    ],
  },
  {
    state: "Active",
    items: [
      {
        name: "FORJA Phase 2.10 build and browser smoke",
        system: "FORJA",
        evidence: "Required before phase closure",
      },
    ],
  },
  {
    state: "Completed",
    items: [
      {
        name: "FORJA Phase 2.9 Freeze Cabin validation",
        system: "FORJA",
        evidence: "D:/AIC-REPORTS/FORJA/FREEZE/FORJA_PHASE_2_9_VALIDATION.md",
      },
      {
        name: "FORJA Phase 2.6 Codex Cabin validation",
        system: "FORJA",
        evidence: "D:/AIC-REPORTS/FORJA/CODEX/FORJA_PHASE_2_6_VALIDATION.md",
      },
      {
        name: "FORJA Phase 2.5 Workflow Cabin validation",
        system: "FORJA",
        evidence: "D:/AIC-REPORTS/FORJA/WORKFLOW/FORJA_PHASE_2_5_VALIDATION.md",
      },
    ],
  },
  {
    state: "Failed",
    items: [
      {
        name: "No failed validation recorded",
        system: "SYSTEM",
        evidence: "Failure lane visible; no failure fabricated",
      },
    ],
  },
];

const systemValidations = [
  {
    system: "Centinela",
    status: "WARNING",
    summary: "Operational foundation exists, but live sync/freeze blocker remains active.",
    evidence: "D:/AIC-REPORTS/FINAL/CENTINELA_FINAL_ENTERPRISE_FOUNDATION_STATUS.md",
    date: "2026-05-29",
    origin: "Centinela final closure",
    audit: "Final operational re-audit",
  },
  {
    system: "Cerebro",
    status: "PASS",
    summary: "Enterprise Automation Foundation closed with source-to-live verified.",
    evidence: "D:/AIC-REPORTS/CEREBRO/FINAL/CEREBRO_FINAL_OPERATIONAL_CLOSURE.md",
    date: "2026-05-29",
    origin: "Cerebro final auth closure",
    audit: "Final automation re-audit",
  },
  {
    system: "Forja",
    status: "WARNING",
    summary: "Local vNext cabins are integrated; source traceability and dev auth remain blockers.",
    evidence: "D:/AIC-REPORTS/FORJA/FINAL/FORJA_PHASE_2_10_VNEXT_INTEGRATION.md",
    date: "2026-05-29",
    origin: "FORJA Phase 2.10",
    audit: "vNext integration validation",
  },
];

const validationEvidence = [
  {
    name: "FORJA Phase 2.10 frontend build",
    status: "PASS",
    evidence: "npm run build compiled successfully after integrated vNext state update",
    date: "2026-05-29",
    origin: "local frontend",
    audit: "FORJA Phase 2.10",
  },
  {
    name: "FORJA Phase 2.10 browser smoke",
    status: "PASS",
    evidence: "D:/AIC-REPORTS/FORJA/VALIDATIONS/FORJA_PHASE_2_10_BROWSER_SMOKE.json",
    date: "2026-05-29",
    origin: "controlled browser smoke",
    audit: "FORJA Phase 2.10",
  },
  {
    name: "FORJA Phase 2.6 frontend build",
    status: "PASS",
    evidence: "npm run build compiled successfully",
    date: "2026-05-29",
    origin: "local frontend",
    audit: "FORJA Phase 2.6",
  },
  {
    name: "FORJA Phase 2.6 browser smoke",
    status: "PASS",
    evidence: "D:/AIC-REPORTS/FORJA/VALIDATIONS/FORJA_PHASE_2_6_BROWSER_SMOKE.json",
    date: "2026-05-29",
    origin: "controlled Edge smoke",
    audit: "FORJA Phase 2.6",
  },
  {
    name: "FORJA Phase 2.5 browser smoke",
    status: "PASS",
    evidence: "D:/AIC-REPORTS/FORJA/VALIDATIONS/FORJA_PHASE_2_5_BROWSER_SMOKE.json",
    date: "2026-05-29",
    origin: "controlled Edge smoke",
    audit: "FORJA Phase 2.5",
  },
  {
    name: "FORJA in-app browser surface",
    status: "WARNING",
    evidence: "No active Codex browser pane available during smoke attempt",
    date: "2026-05-29",
    origin: "browser integration attempt",
    audit: "FORJA Phase 2.6",
  },
];

const regressionTracking = [
  {
    name: "Integrated build validation",
    status: "PASS",
    detail: "Phase 2.10 build validates the integrated Executive, Workflow, Codex, Validation, Deploy and Freeze cabins.",
  },
  {
    name: "Integrated browser smoke",
    status: "PASS",
    detail: "Desktop and mobile smoke traverse the complete cabin navigation without losing global context.",
  },
  {
    name: "Degraded validation surface",
    status: "WARNING",
    detail: "In-app browser pane unavailable; controlled Edge smoke used as fallback evidence.",
  },
  {
    name: "Pending release evidence",
    status: "PENDING",
    detail: "Live deploy, source-to-live and freeze evidence remain pending after local vNext certification.",
  },
];

const riskValidations = [
  {
    risk: "CENTINELA_LIVE_SYNC_BLOCKED",
    impact: "Ecosystem freeze cannot be approved while live remains stale or blocked.",
    severity: "CRITICAL",
    state: "BLOCKED",
  },
  {
    risk: "FORJA_SOURCE_TRACEABILITY_MISSING",
    impact: "Deploy and rollback trust cannot be validated from repo evidence.",
    severity: "HIGH",
    state: "BLOCKED",
  },
  {
    risk: "FORJA_DEV_AUTH_HARDCODED_BLOCKER",
    impact: "Auth cannot support production governance trust.",
    severity: "HIGH",
    state: "BLOCKED",
  },
  {
    risk: "IN_APP_BROWSER_UNAVAILABLE",
    impact: "Browser validation requires controlled fallback evidence.",
    severity: "MODERATE",
    state: "WARNING",
  },
];

const validationDecision = {
  state: "BLOCKED",
  answer:
    "Not ready for deploy or freeze. Local cabin validation may continue, but ecosystem release remains blocked by traceability, auth and Centinela live sync evidence.",
};

const deployLanes = [
  {
    state: "Pending",
    items: [
      {
        name: "FORJA source traceability recovery",
        system: "FORJA",
        detail: "Repo, branch, remote and commit evidence must exist before deploy.",
      },
      {
        name: "Deploy Cabin validation evidence",
        system: "FORJA",
        detail: "Phase 2.8 build, browser smoke and reports are required.",
      },
    ],
  },
  {
    state: "Running",
    items: [
      {
        name: "No deploy executing",
        system: "SYSTEM",
        detail: "No active deploy process is claimed or simulated.",
      },
    ],
  },
  {
    state: "Validated",
    items: [
      {
        name: "No FORJA deploy validated",
        system: "FORJA",
        detail: "Local vNext cabin validations are not live deploy validations.",
      },
    ],
  },
  {
    state: "Blocked",
    items: [
      {
        name: "FORJA_SOURCE_TRACEABILITY_MISSING",
        system: "FORJA",
        detail: "Deploy cannot be trusted without git/source-to-live evidence.",
      },
      {
        name: "FORJA_DEV_AUTH_HARDCODED_BLOCKER",
        system: "FORJA",
        detail: "Production trust cannot be claimed until dev auth is gated or replaced.",
      },
    ],
  },
];

const sourceToLive = [
  {
    label: "Current commit",
    value: "UNKNOWN",
    detail: "SOURCE_TRACEABILITY_MISSING",
    tone: "warning",
  },
  {
    label: "Live commit",
    value: "UNKNOWN",
    detail: "No FORJA live linkage verified",
    tone: "warning",
  },
  {
    label: "Divergence",
    value: "UNVERIFIED",
    detail: "Cannot compare local and live without repo/live evidence",
    tone: "danger",
  },
  {
    label: "Synchronization",
    value: "BLOCKED",
    detail: "Recover traceability before deploy",
    tone: "danger",
  },
];

const deployReadiness = [
  {
    gate: "Audits",
    status: "PASS",
    evidence: "FORJA Phase 2.10 validates all cabin foundations together.",
  },
  {
    gate: "Validations",
    status: "PASS",
    evidence: "Phase 2.10 local build/browser evidence exists.",
  },
  {
    gate: "Blockers",
    status: "FAIL",
    evidence: "Source traceability and dev auth blockers remain active.",
  },
  {
    gate: "Freeze",
    status: "BLOCKED",
    evidence: "Freeze remains NOT_READY until deploy/rollback evidence exists.",
  },
];

const postDeployTracking = [
  {
    item: "Post-deploy validation",
    status: "NOT_STARTED",
    detail: "No controlled FORJA deploy has been executed.",
  },
  {
    item: "Post-deploy audit",
    status: "NOT_STARTED",
    detail: "Requires source-to-live and live runtime evidence.",
  },
  {
    item: "Regression check",
    status: "NOT_STARTED",
    detail: "Post-deploy regression cannot run before deploy.",
  },
  {
    item: "Rollback readiness",
    status: "UNVERIFIED",
    detail: "Rollback maturity cannot be trusted without repo/deploy path.",
  },
];

const deployHistory = [
  {
    deploy: "FORJA vNext Phase 2.10 local integration validation",
    status: "LOCAL_ONLY",
    result: "PASS",
    evidence: "D:/AIC-REPORTS/FORJA/FINAL/FORJA_PHASE_2_10_VNEXT_INTEGRATION.md",
  },
  {
    deploy: "FORJA vNext Phase 2.7 local validation",
    status: "LOCAL_ONLY",
    result: "PASS",
    evidence: "D:/AIC-REPORTS/FORJA/VALIDATION/FORJA_PHASE_2_7_VALIDATION.md",
  },
  {
    deploy: "FORJA vNext Phase 2.6 local validation",
    status: "LOCAL_ONLY",
    result: "PASS",
    evidence: "D:/AIC-REPORTS/FORJA/CODEX/FORJA_PHASE_2_6_VALIDATION.md",
  },
  {
    deploy: "FORJA production deploy",
    status: "NOT_VERIFIED",
    result: "UNKNOWN",
    evidence: "SOURCE_TRACEABILITY_MISSING",
  },
];

const deployDecision = {
  state: "NO",
  answer:
    "Do not deploy. Audits and local validations have evidence, but source-to-live, blockers, freeze and rollback readiness are not sufficient.",
};

const freezeLanes = [
  {
    state: "Pending",
    items: [
      {
        name: "Post-vNext release readiness hardening",
        system: "FORJA",
        detail: "Requires source/live, rollback and auth remediation before deploy/freeze decisions.",
      },
      {
        name: "Live source-to-runtime validation",
        system: "FORJA",
        detail: "Cannot run until deploy target and repo linkage are recovered.",
      },
    ],
  },
  {
    state: "Blocked",
    items: [
      {
        name: "FORJA_SOURCE_TRACEABILITY_MISSING",
        system: "FORJA",
        detail: "Freeze cannot be approved without repo, branch, commit and source-to-live evidence.",
      },
      {
        name: "FORJA_DEV_AUTH_HARDCODED_BLOCKER",
        system: "FORJA",
        detail: "Governance trust cannot be certified while dev auth remains unresolved.",
      },
      {
        name: "CENTINELA_LIVE_SYNC_BLOCKED",
        system: "ECOSYSTEM",
        detail: "Ecosystem freeze is blocked while Centinela live sync remains unresolved.",
      },
    ],
  },
  {
    state: "Approved",
    items: [
      {
        name: "No freeze approved",
        system: "SYSTEM",
        detail: "Approval lane remains visible; no approval is fabricated.",
      },
    ],
  },
  {
    state: "Expired",
    items: [
      {
        name: "No expired freeze recorded",
        system: "SYSTEM",
        detail: "Expiration lane remains visible; no stale freeze is fabricated.",
      },
    ],
  },
];

const freezeReadiness = {
  classification: "NOT_READY",
  basis:
    "vNext local operator foundation is integrated, but source-to-live, deploy trust, rollback trust and ecosystem blockers prevent freeze.",
  evidence: [
    "FORJA Phase 2.10 vNext Integration PASS",
    "FORJA Phase 2.5 Workflow Cabin PASS",
    "FORJA Phase 2.6 Codex Cabin PASS",
    "FORJA Phase 2.7 Validation Cabin PASS",
    "FORJA Phase 2.8 Deploy Cabin visibility PASS / deploy execution NO",
  ],
};

const blockerGovernance = [
  {
    blocker: "FORJA_SOURCE_TRACEABILITY_MISSING",
    type: "ACTIVE",
    impact: "Freeze cannot verify source, branch, commit, live linkage or rollback path.",
    resolution: "Recover or initialize git/source traceability before freeze approval.",
  },
  {
    blocker: "FORJA_DEV_AUTH_HARDCODED_BLOCKER",
    type: "ACTIVE",
    impact: "Operational governance trust cannot be certified for production.",
    resolution: "Gate development auth or replace it with configured auth.",
  },
  {
    blocker: "CENTINELA_LIVE_SYNC_BLOCKED",
    type: "ACTIVE",
    impact: "Ecosystem-level freeze remains unsafe while Centinela live sync is blocked.",
    resolution: "Resolve Centinela live sync before ecosystem freeze.",
  },
  {
    blocker: "BACKEND_COMPILE_BLOCKER_FIX_CONFIG",
    type: "HISTORICAL",
    impact: "Past backend compile blocker was neutralized through archive/no-runtime handling.",
    resolution: "Keep archived evidence and do not reintroduce residual runtime files.",
  },
];

const certificationPanel = [
  {
    certification: "FORJA Human Cabin vNext Foundation",
    status: "CURRENT",
    evidence: "Phase 2.10 integrates Executive, Workflow, Codex, Validation, Deploy and Freeze cabins locally.",
  },
  {
    certification: "FORJA Deploy Trust",
    status: "BLOCKED",
    evidence: "Source-to-live and rollback readiness are unverified.",
  },
  {
    certification: "FORJA Operational Freeze",
    status: "BLOCKED",
    evidence: "Deploy decision is NO and readiness classification is NOT_READY.",
  },
  {
    certification: "FORJA Local Cabin Foundations",
    status: "CURRENT",
    evidence: "Executive, Workflow, Codex, Validation and Deploy cabins have local smoke evidence.",
  },
];

const operationalTrust = [
  {
    trust: "Runtime trust",
    status: "CONDITIONAL",
    evidence: "Local frontend and backend health are available, but this is not live trust.",
  },
  {
    trust: "Deploy trust",
    status: "LOW",
    evidence: "Source-to-live is unverified and deploy decision remains NO.",
  },
  {
    trust: "Rollback trust",
    status: "UNVERIFIED",
    evidence: "Rollback path cannot be trusted without repo/deploy traceability.",
  },
  {
    trust: "Governance trust",
    status: "BLOCKED",
    evidence: "Traceability and auth blockers remain active.",
  },
];

const freezeDecision = {
  state: "NO",
  answer:
    "Freeze cannot be approved. vNext is locally integrated as an operator platform, but deploy trust, rollback trust, source-to-live and active blockers prevent operational freeze.",
};

const cabinIntegration = [
  {
    cabin: "Executive Cabin",
    status: "INTEGRATED",
    evidence: "Ecosystem overview, blockers, audits, deploy, freeze and one decision visible on HOME.",
  },
  {
    cabin: "Workflow Cabin",
    status: "INTEGRATED",
    evidence: "Idea to Freeze rail, current operation, next action, task pipeline and blockers.",
  },
  {
    cabin: "Codex Cabin",
    status: "INTEGRATED",
    evidence: "Session, prompt pipeline, result center, phase tracking, memory and operator actions.",
  },
  {
    cabin: "Validation Cabin",
    status: "INTEGRATED",
    evidence: "System validation, evidence tracking, regression tracking, risk validation and decision.",
  },
  {
    cabin: "Deploy Cabin",
    status: "INTEGRATED",
    evidence: "Deploy center, source-to-live, readiness, post-deploy tracking and decision NO.",
  },
  {
    cabin: "Freeze Cabin",
    status: "INTEGRATED",
    evidence: "Freeze center, readiness, blockers, certification, trust and decision NO.",
  },
];

const operatorFlowValidation = [
  {
    step: "Idea",
    state: "PRESERVED",
    context: "vNext operator need remains visible through the workflow rail.",
  },
  {
    step: "Plan",
    state: "PRESERVED",
    context: "Phase sequence remains explicit; no hidden planning lane.",
  },
  {
    step: "Forja",
    state: "PRESERVED",
    context: "Active system and task stay in the global command center.",
  },
  {
    step: "Codex",
    state: "PRESERVED",
    context: "Codex work is shown as operational session, not generic chat.",
  },
  {
    step: "Validation",
    state: "PRESERVED",
    context: "Evidence, risks and readiness are visible before deploy.",
  },
  {
    step: "Deploy",
    state: "PRESERVED",
    context: "Deploy decision remains NO because source/live is unverified.",
  },
  {
    step: "Freeze",
    state: "PRESERVED",
    context: "Freeze decision remains NO; certification is not fabricated.",
  },
];

const cognitiveLoadEvaluation = {
  original: "HIGH",
  vNext: "MODERATE",
  maxCriticalAccessClicks: "1",
  sequentialFlowClicks: "5",
  decisionTime: "<10 seconds for ecosystem state, blockers, audits, deploy and freeze",
  reason:
    "vNext replaces a health-splash posture with one global status bar, one command center and dedicated cabins; remaining blockers keep load above LOW.",
};

const executiveVisibilityValidation = [
  {
    signal: "Ecosystem state",
    status: "VISIBLE",
    evidence: "Global status bar and Executive Cabin overview.",
  },
  {
    signal: "Blockers",
    status: "VISIBLE",
    evidence: "Global blocker count and Active Blockers panel.",
  },
  {
    signal: "Audits",
    status: "VISIBLE",
    evidence: "Active Audits status and Audit Status panel.",
  },
  {
    signal: "Deploys",
    status: "VISIBLE",
    evidence: "Active Deploys status and Deploy Status panel.",
  },
  {
    signal: "Freeze",
    status: "VISIBLE",
    evidence: "Freeze State status and Freeze Status panel.",
  },
];

const theaterEliminationAudit = [
  {
    check: "Decorative dashboards",
    result: "CLEARED",
    evidence: "Panels answer operational questions or show blockers.",
  },
  {
    check: "Fake metrics",
    result: "CLEARED",
    evidence: "Deploy, freeze and source-to-live remain blocked where evidence is missing.",
  },
  {
    check: "States without evidence",
    result: "CLEARED",
    evidence: "PASS states cite local validation evidence; unknown source/live remains UNKNOWN/BLOCKED.",
  },
  {
    check: "False command-center claim",
    result: "CLEARED",
    evidence: "Final classification stops at OPERATIONAL because release blockers remain.",
  },
];

const finalOperatorCertification = {
  classification: "OPERATIONAL",
  basis:
    "All primary cabins are integrated and navigable with preserved context. FORJA is not certified for executive-ready or ecosystem command-center operation until source/live traceability, auth and freeze blockers are resolved.",
};

const viewCopy = {
  home: {
    title: "vNext Integrated Executive Home",
    eyebrow: "HOME",
    summary:
      "Vista ejecutiva integrada: ecosistema, blockers, auditoria, deploy, freeze, flujo operativo y certificacion local vNext.",
    primary: executiveDecision,
    points: [
      "All primary cabins are reachable from one navigation model.",
      "The global status bar and command center preserve context across cabins.",
      "No deploy, freeze or command-center claim is approved without evidence.",
    ],
  },
  workflow: {
    title: "Workflow Shell",
    eyebrow: "WORKFLOW",
    summary:
      "Rail operacional visible sin ejecutar workflow real todavia.",
    primary: "Current operational step: Command Shell validation.",
    points: [
      "Future steps are locked until evidence and models exist.",
      "No completed work is fabricated.",
      "The operator always sees why deploy and freeze are unavailable.",
    ],
  },
  codex: {
    title: "Codex Shell",
    eyebrow: "CODEX",
    summary:
      "Superficie reservada para handoff y resultados Codex; sin ejecucion simulada.",
    primary: "Codex cabin is not implemented in Phase 2.3.",
    points: [
      "No prompt, result, or validation is shown without evidence.",
      "Future handoff state must include source and timestamp.",
      "Errors and validation pending states will stay visible when implemented.",
    ],
  },
  validation: {
    title: "Validation Shell",
    eyebrow: "VALIDATION",
    summary:
      "Base visual para evidencia de build, browser smoke y regresion.",
    primary: "Validation is available as a shell; evidence lives in reports for this phase.",
    points: [
      "No PASS state is shown without command/browser evidence.",
      "Deploy remains locked until validation passes.",
      "Failure states must include reason, owner and recovery path.",
    ],
  },
  deploy: {
    title: "Deploy Shell",
    eyebrow: "DEPLOY",
    summary:
      "Deploy esta bloqueado porque source-to-live traceability no existe localmente.",
    primary: "Deploy state: NO_ACTIVE_DEPLOY / SOURCE_TRACEABILITY_MISSING.",
    points: [
      "No repo, branch, remote or commit can be trusted yet.",
      "Rollback and post-deploy validation are not evaluated.",
      "Deploy action must remain unavailable until traceability is restored.",
    ],
  },
  freeze: {
    title: "Freeze Shell",
    eyebrow: "FREEZE",
    summary:
      "Freeze se mantiene no evaluado hasta que existan validacion, deploy y rollback reales.",
    primary: "Freeze state: NOT_EVALUATED.",
    points: [
      "No SAFE_TO_FREEZE claim exists.",
      "Freeze depends on validation and source-to-live evidence.",
      "Current blockers must stay visible before closure.",
    ],
  },
  settings: {
    title: "Settings Shell",
    eyebrow: "SETTINGS",
    summary:
      "Estado minimo de configuracion y riesgos conocidos antes de implementar vNext.",
    primary: "Config posture: local only, env protected, dev auth blocker open.",
    points: [
      ".env remains local and ignored.",
      "backend/.env.example documents required variables without secrets.",
      "Dev auth hardcoding remains a production blocker.",
    ],
  },
};

function toneClasses(tone) {
  const tones = {
    danger: "border-red-400/40 bg-red-500/10 text-red-100",
    warning: "border-amber-300/40 bg-amber-400/10 text-amber-100",
    neutral: "border-slate-600 bg-slate-900/70 text-slate-100",
    good: "border-emerald-400/40 bg-emerald-500/10 text-emerald-100",
  };

  return tones[tone] || tones.neutral;
}

function operationalTone(status) {
  const normalized = String(status).toUpperCase();

  if (["PASS", "READY", "COMPLETED", "YES", "CURRENT", "FOUNDATION_READY", "OPERATIONALLY_READY", "INTEGRATED", "PRESERVED", "VISIBLE", "CLEARED", "OPERATIONAL"].includes(normalized)) return "good";
  if (["WARNING", "PENDING", "ACTIVE", "HISTORICAL", "CONDITIONALLY_READY", "CONDITIONAL", "IN_PROGRESS", "LOCAL_ONLY", "RUNNING", "NOT_STARTED", "UNVERIFIED", "UNKNOWN", "LOW"].includes(normalized)) {
    return "warning";
  }
  if (["FAIL", "FAILED", "BLOCKED", "NO", "NOT_READY"].includes(normalized)) return "danger";

  return "neutral";
}

function StatusPill({ label, value, detail, tone }) {
  return (
    <div className={`rounded-lg border px-3 py-3 ${toneClasses(tone)}`}>
      <div className="text-[11px] uppercase tracking-[0.14em] text-slate-400">
        {label}
      </div>
      <div className="mt-1 text-sm font-semibold">{value}</div>
      <div className="mt-1 text-xs text-slate-400">{detail}</div>
    </div>
  );
}

function StateBadge({ value, tone }) {
  return (
    <span className={`inline-flex rounded-md border px-2 py-1 text-xs font-semibold ${toneClasses(tone)}`}>
      {value}
    </span>
  );
}

function MiniMetric({ label, value, detail, tone = "neutral" }) {
  return (
    <div className={`rounded-lg border p-3 ${toneClasses(tone)}`}>
      <div className="text-[11px] uppercase tracking-[0.14em] text-slate-400">
        {label}
      </div>
      <div className="mt-2 text-lg font-semibold">{value}</div>
      {detail && <div className="mt-1 text-xs text-slate-400">{detail}</div>}
    </div>
  );
}

function ExecutiveSection({ title, children }) {
  return (
    <section className="rounded-xl border border-slate-700 bg-slate-950/75 p-4">
      <h2 className="text-sm font-semibold text-slate-100">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function CommandCenter() {
  return (
    <section
      className="rounded-xl border border-slate-700 bg-slate-950/75 p-4 shadow-2xl shadow-black/20"
      aria-label="Global command center"
    >
      <div className="grid gap-3 lg:grid-cols-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
            Next action
          </div>
          <div className="mt-1 text-base font-semibold text-white">
            {commandState.nextAction}
          </div>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
            Active task
          </div>
          <div className="mt-1 text-base font-semibold text-slate-200">
            {commandState.activeTask}
          </div>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
            Active system
          </div>
          <div className="mt-1 text-base font-semibold text-slate-200">
            {commandState.activeSystem}
          </div>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
            Priority
          </div>
          <div className="mt-1 inline-flex rounded-md border border-amber-300/40 bg-amber-400/10 px-2 py-1 text-sm font-semibold text-amber-100">
            {commandState.priority}
          </div>
        </div>
      </div>
    </section>
  );
}

function WorkflowRail() {
  return (
    <section
      className="rounded-xl border border-slate-700 bg-slate-950/70 p-4"
      aria-label="Workflow rail"
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-slate-100">Operational Flow</h2>
        <span className="text-xs text-slate-500">Phase 2.10</span>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-7">
        {workflowSteps.map((step, index) => {
          const active = step.state === "IN_PROGRESS";
          return (
            <div
              key={step.label}
              className={`min-h-[76px] rounded-lg border p-3 ${
                active
                  ? "border-sky-300/50 bg-sky-400/10"
                  : "border-slate-700 bg-slate-900/70"
              }`}
            >
              <div className="text-sm font-semibold text-slate-100">{step.label}</div>
              <div
                className={`mt-2 text-xs font-medium ${
                  active ? "text-sky-100" : "text-slate-400"
                }`}
              >
                {step.state}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function WorkflowStepCard({ step, index }) {
  const isCurrent = step.state === "IN_PROGRESS";
  const isBlocked = step.state === "LOCKED";
  const isValidation = step.state === "NEEDS_VALIDATION";
  const tone = isCurrent
    ? "border-sky-300/50 bg-sky-400/10"
    : isBlocked
      ? "border-red-400/30 bg-red-500/10"
      : isValidation
        ? "border-amber-300/40 bg-amber-400/10"
        : "border-slate-700 bg-slate-900/70";

  return (
    <article className={`relative min-w-0 rounded-lg border p-4 ${tone}`}>
      {index < workflowSteps.length - 1 && (
        <div
          aria-hidden="true"
          className="absolute bottom-[-17px] left-7 hidden h-4 border-l border-slate-700 lg:block"
        />
      )}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
            Step {index + 1}
          </div>
          <h3 className="mt-1 text-base font-semibold text-white">{step.label}</h3>
        </div>
        <span
          className={`shrink-0 rounded-md border px-2 py-1 text-xs font-semibold ${
            isCurrent
              ? "border-sky-300/50 bg-sky-400/10 text-sky-100"
              : isBlocked
                ? "border-red-400/40 bg-red-500/10 text-red-100"
                : isValidation
                  ? "border-amber-300/40 bg-amber-400/10 text-amber-100"
                  : "border-slate-700 bg-slate-950/70 text-slate-300"
          }`}
        >
          {step.state}
        </span>
      </div>
      <p className="mt-3 text-sm leading-5 text-slate-300">{step.detail}</p>
      <div className="mt-3 text-xs text-slate-500">Owner: {step.owner}</div>
    </article>
  );
}

function WorkflowCabin() {
  const taskBuckets = ["Pending", "In Progress", "Validation", "Completed", "Blocked"];
  const completedSteps = workflowSteps.filter((step) => step.state === "COMPLETED");
  const currentStep = workflowSteps.find((step) => step.state === "IN_PROGRESS");
  const nextStep = workflowSteps.find((step) => step.state === "NEEDS_VALIDATION");
  const blockedSteps = workflowSteps.filter((step) => step.state === "LOCKED");

  return (
    <section className="space-y-4" aria-label="Workflow Cabin">
      <section className="rounded-xl border border-slate-700 bg-slate-950/75 p-5">
        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
          WORKFLOW CABIN
        </div>
        <div className="mt-2 grid gap-4 xl:grid-cols-[1.2fr_0.8fr] xl:items-start">
          <div>
            <h1 className="text-2xl font-semibold text-white">
              Operator Workflow Cabin
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
              Vista unica del flujo Idea, Plan, Forja, Codex, Validation, Deploy y Freeze. La operacion actual, la siguiente accion y los bloqueos quedan visibles sin navegar a otra pantalla.
            </p>
          </div>
          <div className="rounded-lg border border-sky-300/40 bg-sky-400/10 p-4">
            <div className="text-[11px] uppercase tracking-[0.14em] text-sky-200">
              Que debo hacer despues?
            </div>
            <div className="mt-2 text-base font-semibold leading-6 text-white">
              {workflowNextAction}
            </div>
          </div>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
        <section
          className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
          aria-label="Workflow rail detailed"
        >
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-100">Workflow Rail</h2>
              <p className="mt-1 text-xs text-slate-500">
                Previous: {completedSteps.at(-1)?.label || "None"} | Current: {currentStep?.label || "Unknown"} | Next: {nextStep?.label || "Unknown"}
              </p>
            </div>
            <StateBadge value={`${blockedSteps.length} BLOCKED`} tone="warning" />
          </div>
          <div className="mt-4 space-y-3">
            {workflowSteps.map((step, index) => (
              <WorkflowStepCard key={step.label} step={step} index={index} />
            ))}
          </div>
        </section>

        <div className="space-y-4">
          <section
            className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
            aria-label="Current operation"
          >
            <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
              Que estoy haciendo ahora?
            </div>
            <h2 className="mt-2 text-xl font-semibold text-white">
              {workflowOperation.task}
            </h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <MiniMetric label="Affected system" value={workflowOperation.system} />
              <MiniMetric label="Current phase" value={workflowOperation.phase} />
              <MiniMetric label="Priority" value={workflowOperation.priority} tone="warning" />
              <MiniMetric label="State" value={workflowOperation.status} tone="warning" />
            </div>
            <div className="mt-4 rounded-lg border border-slate-800 bg-slate-900/70 p-3 text-sm leading-5 text-slate-300">
              Previous: {workflowOperation.previousStep}. Current: {workflowOperation.currentStep}. Next: {workflowOperation.nextStep}. Evidence: {workflowOperation.evidence}.
            </div>
          </section>

          <section
            className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
            aria-label="Next action"
          >
            <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
              Single Next Action
            </div>
            <div className="mt-2 rounded-lg border border-emerald-400/40 bg-emerald-500/10 p-4 text-base font-semibold leading-6 text-white">
              {workflowNextAction}
            </div>
            <p className="mt-3 text-sm text-slate-400">
              No hay acciones paralelas en esta vista; deploy y freeze permanecen bloqueados hasta evidencia real.
            </p>
          </section>

          <section
            className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
            aria-label="Blocker visibility"
          >
            <h2 className="text-sm font-semibold text-slate-100">Blocker Visibility</h2>
            <div className="mt-4 space-y-3">
              {workflowBlockers.map((item) => (
                <article
                  key={item.blocker}
                  className="rounded-lg border border-slate-800 bg-slate-900/70 p-4"
                >
                  <div className="break-all text-sm font-semibold text-white">
                    {item.blocker}
                  </div>
                  <div className="mt-2 text-xs uppercase tracking-[0.14em] text-slate-500">
                    Origin
                  </div>
                  <p className="mt-1 text-sm text-slate-300">{item.origin}</p>
                  <div className="mt-3 text-xs uppercase tracking-[0.14em] text-slate-500">
                    Impact
                  </div>
                  <p className="mt-1 text-sm text-slate-300">{item.impact}</p>
                  <div className="mt-3 rounded-md border border-slate-700 bg-slate-950/70 p-3 text-sm text-slate-200">
                    Required action: {item.action}
                  </div>
                </article>
              ))}
            </div>
          </section>
        </div>
      </div>

      <section
        className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
        aria-label="Task pipeline"
      >
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Task Pipeline</h2>
            <p className="mt-1 text-xs text-slate-500">
              Cada tarea pertenece a un unico estado operacional.
            </p>
          </div>
          <StateBadge value="NO HIDDEN STEPS" tone="good" />
        </div>
        <div className="mt-4 grid gap-3 lg:grid-cols-5">
          {taskBuckets.map((bucket) => (
            <div key={bucket} className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
              <h3 className="text-sm font-semibold text-white">{bucket}</h3>
              <div className="mt-3 space-y-2">
                {workflowTasks
                  .filter((task) => task.state === bucket)
                  .map((task) => (
                    <article
                      key={task.title}
                      className="rounded-md border border-slate-700 bg-slate-950/70 p-3"
                    >
                      <div className="text-sm font-semibold leading-5 text-slate-100">
                        {task.title}
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
                        <span>Owner: {task.owner}</span>
                        <span>Priority: {task.priority}</span>
                      </div>
                    </article>
                  ))}
              </div>
            </div>
          ))}
        </div>
      </section>
    </section>
  );
}

function CodexCabin() {
  const promptStates = ["Draft", "Ready", "Sent", "Processing", "Completed", "Failed"];

  return (
    <section className="space-y-4" aria-label="Codex Cabin">
      <section className="rounded-xl border border-slate-700 bg-slate-950/75 p-5">
        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
          CODEX CABIN
        </div>
        <div className="mt-2 grid gap-4 xl:grid-cols-[1.15fr_0.85fr] xl:items-start">
          <div>
            <h1 className="text-2xl font-semibold text-white">
              Codex Operation Center
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
              Cabina operacional para trabajar con Codex sin perder contexto: sesion activa, prompt pipeline, resultado, fase, memoria y acciones del operador en una sola superficie.
            </p>
          </div>
          <div className="rounded-lg border border-sky-300/40 bg-sky-400/10 p-4">
            <div className="text-[11px] uppercase tracking-[0.14em] text-sky-200">
              Current Codex Session
            </div>
            <div className="mt-2 break-all text-base font-semibold text-white">
              {codexSession.id}
            </div>
            <div className="mt-2 text-sm leading-5 text-slate-300">
              {codexSession.lastResult}
            </div>
          </div>
        </div>
      </section>

      <section
        className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
        aria-label="Codex session center"
      >
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Codex Session Center</h2>
            <p className="mt-1 text-xs text-slate-500">
              One active session; no generic chat timeline.
            </p>
          </div>
          <StateBadge value={codexSession.state} tone="warning" />
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <MiniMetric label="Active system" value={codexSession.system} />
          <MiniMetric label="Active phase" value={codexSession.phase} />
          <MiniMetric label="Current state" value={codexSession.state} tone="warning" />
          <MiniMetric label="Last result" value="PHASE_2_5_PASS" tone="good" />
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[1fr_0.9fr]">
        <section
          className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
          aria-label="Prompt pipeline"
        >
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-100">Prompt Pipeline</h2>
              <p className="mt-1 text-xs text-slate-500">
                Every prompt belongs to one operational state.
              </p>
            </div>
            <StateBadge value="NO INFINITE HISTORY" tone="good" />
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {promptStates.map((state) => {
              const item = promptPipeline.find((prompt) => prompt.state === state);
              const tone =
                state === "Failed"
                  ? "border-slate-700 bg-slate-900/70"
                  : state === "Processing"
                    ? "border-sky-300/50 bg-sky-400/10"
                    : state === "Completed"
                      ? "border-emerald-400/40 bg-emerald-500/10"
                      : "border-slate-800 bg-slate-900/70";

              return (
                <article key={state} className={`rounded-lg border p-4 ${tone}`}>
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="text-sm font-semibold text-white">{state}</h3>
                    <span className="text-xs text-slate-500">{item.owner}</span>
                  </div>
                  <div className="mt-3 text-sm font-semibold leading-5 text-slate-100">
                    {item.prompt}
                  </div>
                  <p className="mt-2 text-sm leading-5 text-slate-400">{item.detail}</p>
                </article>
              );
            })}
          </div>
        </section>

        <section
          className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
          aria-label="Result center"
        >
          <h2 className="text-sm font-semibold text-slate-100">Result Center</h2>
          <div className="mt-4 rounded-lg border border-amber-300/40 bg-amber-400/10 p-4">
            <div className="text-[11px] uppercase tracking-[0.14em] text-amber-100">
              Result received
            </div>
            <div className="mt-2 text-base font-semibold text-white">
              {codexResultCenter.result}
            </div>
            <p className="mt-2 text-sm leading-5 text-slate-300">
              {codexResultCenter.received}
            </p>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
              <h3 className="text-sm font-semibold text-white">Validations</h3>
              <ul className="mt-3 space-y-2 text-sm text-slate-300">
                {codexResultCenter.validations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
              <h3 className="text-sm font-semibold text-white">Risks</h3>
              <ul className="mt-3 space-y-2 text-sm text-slate-300">
                {codexResultCenter.risks.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
          <div className="mt-4 rounded-lg border border-slate-800 bg-slate-900/70 p-3">
            <div className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
              Operational classification
            </div>
            <div className="mt-2 text-sm font-semibold text-white">
              {codexResultCenter.classification}
            </div>
          </div>
        </section>
      </div>

      <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <section
          className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
          aria-label="Phase tracking"
        >
          <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
            Phase Tracking
          </div>
          <div className="mt-2 grid gap-3 sm:grid-cols-3">
            <MiniMetric label="Phase" value={codexPhaseTracking.phase} />
            <MiniMetric label="Subphase" value={codexPhaseTracking.subphase} />
            <MiniMetric label="Progress" value={codexPhaseTracking.progress} tone="warning" />
          </div>
          <div className="mt-4 rounded-lg border border-slate-800 bg-slate-900/70 p-3">
            <h3 className="text-sm font-semibold text-white">Real pending work</h3>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {codexPhaseTracking.pending.map((item) => (
                <div
                  key={item}
                  className="rounded-md border border-slate-700 bg-slate-950/70 p-3 text-sm text-slate-300"
                >
                  {item}
                </div>
              ))}
            </div>
          </div>
        </section>

        <section
          className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
          aria-label="Codex memory panel"
        >
          <h2 className="text-sm font-semibold text-slate-100">Codex Memory Panel</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {codexMemory.map((item) => (
              <article
                key={item.label}
                className="rounded-lg border border-slate-800 bg-slate-900/70 p-4"
              >
                <div className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
                  {item.label}
                </div>
                <div className="mt-2 text-base font-semibold text-white">{item.value}</div>
                <p className="mt-2 text-sm leading-5 text-slate-400">{item.detail}</p>
              </article>
            ))}
          </div>
        </section>
      </div>

      <section
        className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
        aria-label="Operator actions"
      >
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Operator Actions</h2>
            <p className="mt-1 text-xs text-slate-500">
              Four questions, one operational answer each.
            </p>
          </div>
          <StateBadge value="DEPLOY LOCKED" tone="warning" />
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {codexOperatorActions.map((item) => (
            <article
              key={item.question}
              className="rounded-lg border border-slate-800 bg-slate-900/70 p-4"
            >
              <h3 className="text-sm font-semibold text-white">{item.question}</h3>
              <p className="mt-3 text-sm leading-5 text-slate-300">{item.answer}</p>
            </article>
          ))}
        </div>
      </section>

      <section
        className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
        aria-label="Codex blockers"
      >
        <h2 className="text-sm font-semibold text-slate-100">Codex Blockers</h2>
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          {codexResultCenter.blockers.map((blocker) => (
            <div
              key={blocker}
              className="break-all rounded-lg border border-red-400/30 bg-red-500/10 p-3 text-sm font-semibold text-red-100"
            >
              {blocker}
            </div>
          ))}
        </div>
      </section>
    </section>
  );
}

function ValidationCabin() {
  const pendingCount = validationLanes.find((lane) => lane.state === "Pending")?.items.length || 0;
  const activeCount = validationLanes.find((lane) => lane.state === "Active")?.items.length || 0;
  const completedCount = validationLanes.find((lane) => lane.state === "Completed")?.items.length || 0;
  const failedCount =
    validationLanes.find((lane) => lane.state === "Failed")?.items.filter((item) => !item.name.startsWith("No failed")).length || 0;

  return (
    <section className="space-y-4" aria-label="Validation Cabin">
      <section className="rounded-xl border border-slate-700 bg-slate-950/75 p-5">
        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
          VALIDATION CABIN
        </div>
        <div className="mt-2 grid gap-4 xl:grid-cols-[1.15fr_0.85fr] xl:items-start">
          <div>
            <h1 className="text-2xl font-semibold text-white">
              Validation Operation Center
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
              Centro unico para validar Centinela, Cerebro y Forja con evidencia visible, regresiones, riesgos y decision operativa. No hay PASS sin origen, fecha y auditoria asociada.
            </p>
          </div>
          <div className={`rounded-lg border p-4 ${toneClasses(operationalTone(validationDecision.state))}`}>
            <div className="text-[11px] uppercase tracking-[0.14em] text-slate-300">
              Esta listo?
            </div>
            <div className="mt-2 text-xl font-semibold text-white">
              {validationDecision.state}
            </div>
            <p className="mt-2 text-sm leading-5 text-slate-300">
              {validationDecision.answer}
            </p>
          </div>
        </div>
      </section>

      <section
        className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
        aria-label="Validation center"
      >
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Validation Center</h2>
            <p className="mt-1 text-xs text-slate-500">
              Pending, active, completed and failed validations in one operator surface.
            </p>
          </div>
          <StateBadge value="NO PASS WITHOUT EVIDENCE" tone="good" />
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MiniMetric label="Pending" value={pendingCount} tone="warning" />
          <MiniMetric label="Active" value={activeCount} tone="warning" />
          <MiniMetric label="Completed" value={completedCount} tone="good" />
          <MiniMetric label="Failed" value={failedCount} />
        </div>
        <div className="mt-4 grid gap-3 xl:grid-cols-4">
          {validationLanes.map((lane) => (
            <div key={lane.state} className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-white">{lane.state}</h3>
                <StateBadge
                  value={lane.state === "Failed" ? failedCount : lane.items.length}
                  tone={operationalTone(lane.state)}
                />
              </div>
              <div className="mt-3 space-y-2">
                {lane.items.map((item) => (
                  <article
                    key={`${lane.state}-${item.name}`}
                    className="rounded-md border border-slate-700 bg-slate-950/70 p-3"
                  >
                    <div className="text-sm font-semibold leading-5 text-slate-100">
                      {item.name}
                    </div>
                    <div className="mt-2 text-xs text-slate-500">System: {item.system}</div>
                    <div className="mt-2 break-all text-xs text-slate-400">
                      Evidence: {item.evidence}
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section
        className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
        aria-label="System validation"
      >
        <h2 className="text-sm font-semibold text-slate-100">System Validation</h2>
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          {systemValidations.map((item) => (
            <article
              key={item.system}
              className="rounded-lg border border-slate-800 bg-slate-900/70 p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-lg font-semibold text-white">{item.system}</h3>
                  <p className="mt-2 text-sm leading-5 text-slate-400">{item.summary}</p>
                </div>
                <StateBadge value={item.status} tone={operationalTone(item.status)} />
              </div>
              <div className="mt-4 grid gap-2 text-xs text-slate-500">
                <div>Date: {item.date}</div>
                <div>Origin: {item.origin}</div>
                <div>Audit: {item.audit}</div>
                <div className="break-all">Evidence: {item.evidence}</div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <section
          className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
          aria-label="Validation evidence"
        >
          <h2 className="text-sm font-semibold text-slate-100">Validation Evidence</h2>
          <div className="mt-4 space-y-3">
            {validationEvidence.map((item) => (
              <article
                key={item.name}
                className="rounded-lg border border-slate-800 bg-slate-900/70 p-4"
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-white">{item.name}</h3>
                    <div className="mt-2 text-xs text-slate-500">
                      {item.date} | {item.origin} | {item.audit}
                    </div>
                  </div>
                  <StateBadge value={item.status} tone={operationalTone(item.status)} />
                </div>
                <div className="mt-3 break-all rounded-md border border-slate-700 bg-slate-950/70 p-3 text-sm text-slate-300">
                  Evidence: {item.evidence}
                </div>
              </article>
            ))}
          </div>
        </section>

        <section
          className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
          aria-label="Regression tracking"
        >
          <h2 className="text-sm font-semibold text-slate-100">Regression Tracking</h2>
          <div className="mt-4 space-y-3">
            {regressionTracking.map((item) => (
              <article
                key={item.name}
                className="rounded-lg border border-slate-800 bg-slate-900/70 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-semibold text-white">{item.name}</h3>
                  <StateBadge value={item.status} tone={operationalTone(item.status)} />
                </div>
                <p className="mt-3 text-sm leading-5 text-slate-300">{item.detail}</p>
              </article>
            ))}
          </div>
        </section>
      </div>

      <section
        className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
        aria-label="Risk validation"
      >
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Risk Validation</h2>
            <p className="mt-1 text-xs text-slate-500">
              Risk, impact, severity and current state stay visible before deploy/freeze.
            </p>
          </div>
          <StateBadge value="RELEASE BLOCKED" tone="danger" />
        </div>
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {riskValidations.map((item) => (
            <article
              key={item.risk}
              className="rounded-lg border border-slate-800 bg-slate-900/70 p-4"
            >
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <h3 className="break-all text-sm font-semibold text-white">{item.risk}</h3>
                <div className="flex flex-wrap gap-2">
                  <StateBadge value={item.severity} tone={operationalTone(item.state)} />
                  <StateBadge value={item.state} tone={operationalTone(item.state)} />
                </div>
              </div>
              <p className="mt-3 text-sm leading-5 text-slate-300">{item.impact}</p>
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}

function DeployCabin() {
  const pendingCount = deployLanes.find((lane) => lane.state === "Pending")?.items.length || 0;
  const runningCount =
    deployLanes.find((lane) => lane.state === "Running")?.items.filter((item) => !item.name.startsWith("No deploy")).length || 0;
  const validatedCount =
    deployLanes.find((lane) => lane.state === "Validated")?.items.filter((item) => !item.name.startsWith("No FORJA")).length || 0;
  const blockedCount = deployLanes.find((lane) => lane.state === "Blocked")?.items.length || 0;

  return (
    <section className="space-y-4" aria-label="Deploy Cabin">
      <section className="rounded-xl border border-slate-700 bg-slate-950/75 p-5">
        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
          DEPLOY CABIN
        </div>
        <div className="mt-2 grid gap-4 xl:grid-cols-[1.15fr_0.85fr] xl:items-start">
          <div>
            <h1 className="text-2xl font-semibold text-white">
              Deploy Control Center
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
              Centro unico para controlar deploys sin reconstruir mentalmente el estado: pending, running, validated, blocked, source-to-live, readiness, post-deploy y decision del operador.
            </p>
          </div>
          <div className={`rounded-lg border p-4 ${toneClasses(operationalTone(deployDecision.state))}`}>
            <div className="text-[11px] uppercase tracking-[0.14em] text-slate-300">
              Puedo desplegar?
            </div>
            <div className="mt-2 text-xl font-semibold text-white">{deployDecision.state}</div>
            <p className="mt-2 text-sm leading-5 text-slate-300">{deployDecision.answer}</p>
          </div>
        </div>
      </section>

      <section
        className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
        aria-label="Deploy center"
      >
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Deploy Center</h2>
            <p className="mt-1 text-xs text-slate-500">
              Pending, running, validated and blocked deploy states in one surface.
            </p>
          </div>
          <StateBadge value="NO ACTIVE DEPLOY" tone="warning" />
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MiniMetric label="Pending" value={pendingCount} tone="warning" />
          <MiniMetric label="Running" value={runningCount} />
          <MiniMetric label="Validated" value={validatedCount} />
          <MiniMetric label="Blocked" value={blockedCount} tone="danger" />
        </div>
        <div className="mt-4 grid gap-3 xl:grid-cols-4">
          {deployLanes.map((lane) => {
            const visibleCount =
              lane.state === "Running"
                ? runningCount
                : lane.state === "Validated"
                  ? validatedCount
                  : lane.items.length;

            return (
              <div key={lane.state} className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-white">{lane.state}</h3>
                  <StateBadge value={visibleCount} tone={operationalTone(lane.state)} />
                </div>
                <div className="mt-3 space-y-2">
                  {lane.items.map((item) => (
                    <article
                      key={`${lane.state}-${item.name}`}
                      className="rounded-md border border-slate-700 bg-slate-950/70 p-3"
                    >
                      <div className="break-all text-sm font-semibold leading-5 text-slate-100">
                        {item.name}
                      </div>
                      <div className="mt-2 text-xs text-slate-500">System: {item.system}</div>
                      <div className="mt-2 text-sm leading-5 text-slate-400">{item.detail}</div>
                    </article>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section
        className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
        aria-label="Source to live panel"
      >
        <h2 className="text-sm font-semibold text-slate-100">Source-to-Live Panel</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {sourceToLive.map((item) => (
            <StatusPill
              key={item.label}
              label={item.label}
              value={item.value}
              detail={item.detail}
              tone={item.tone}
            />
          ))}
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
        <section
          className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
          aria-label="Deploy readiness"
        >
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-100">Deploy Readiness</h2>
              <p className="mt-1 text-xs text-slate-500">
                Audits, validations, blockers and freeze must be checked before deploy.
              </p>
            </div>
            <StateBadge value="READINESS FAIL" tone="danger" />
          </div>
          <div className="mt-4 space-y-3">
            {deployReadiness.map((item) => (
              <article
                key={item.gate}
                className="rounded-lg border border-slate-800 bg-slate-900/70 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-semibold text-white">{item.gate}</h3>
                  <StateBadge value={item.status} tone={operationalTone(item.status)} />
                </div>
                <div className="mt-3 break-all rounded-md border border-slate-700 bg-slate-950/70 p-3 text-sm text-slate-300">
                  Evidence: {item.evidence}
                </div>
              </article>
            ))}
          </div>
        </section>

        <section
          className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
          aria-label="Post deploy tracking"
        >
          <h2 className="text-sm font-semibold text-slate-100">Post-Deploy Tracking</h2>
          <div className="mt-4 space-y-3">
            {postDeployTracking.map((item) => (
              <article
                key={item.item}
                className="rounded-lg border border-slate-800 bg-slate-900/70 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-semibold text-white">{item.item}</h3>
                  <StateBadge value={item.status} tone={operationalTone(item.status)} />
                </div>
                <p className="mt-3 text-sm leading-5 text-slate-300">{item.detail}</p>
              </article>
            ))}
          </div>
        </section>
      </div>

      <section
        className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
        aria-label="Deploy history"
      >
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Deploy History</h2>
            <p className="mt-1 text-xs text-slate-500">
              Only relevant deploy or deploy-adjacent validation events are shown.
            </p>
          </div>
          <StateBadge value="LIVE DEPLOY UNKNOWN" tone="warning" />
        </div>
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          {deployHistory.map((item) => (
            <article
              key={item.deploy}
              className="rounded-lg border border-slate-800 bg-slate-900/70 p-4"
            >
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <h3 className="text-sm font-semibold text-white">{item.deploy}</h3>
                <StateBadge value={item.result} tone={operationalTone(item.result)} />
              </div>
              <div className="mt-3 text-xs uppercase tracking-[0.14em] text-slate-500">
                {item.status}
              </div>
              <div className="mt-3 break-all rounded-md border border-slate-700 bg-slate-950/70 p-3 text-sm text-slate-300">
                Evidence: {item.evidence}
              </div>
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}

function FreezeCabin() {
  const pendingCount = freezeLanes.find((lane) => lane.state === "Pending")?.items.length || 0;
  const blockedCount = freezeLanes.find((lane) => lane.state === "Blocked")?.items.length || 0;
  const approvedCount =
    freezeLanes.find((lane) => lane.state === "Approved")?.items.filter((item) => !item.name.startsWith("No freeze")).length || 0;
  const expiredCount =
    freezeLanes.find((lane) => lane.state === "Expired")?.items.filter((item) => !item.name.startsWith("No expired")).length || 0;

  return (
    <section className="space-y-4" aria-label="Freeze Cabin">
      <section className="rounded-xl border border-slate-700 bg-slate-950/75 p-5">
        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
          FREEZE CABIN
        </div>
        <div className="mt-2 grid gap-4 xl:grid-cols-[1.15fr_0.85fr] xl:items-start">
          <div>
            <h1 className="text-2xl font-semibold text-white">
              Freeze Governance Center
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
              Centro unico para freeze y certificacion operacional: estado de freeze, readiness, blockers, certificaciones, confianza operacional y decision del operador.
            </p>
          </div>
          <div className={`rounded-lg border p-4 ${toneClasses(operationalTone(freezeDecision.state))}`}>
            <div className="text-[11px] uppercase tracking-[0.14em] text-slate-300">
              Puede congelarse?
            </div>
            <div className="mt-2 text-xl font-semibold text-white">{freezeDecision.state}</div>
            <p className="mt-2 text-sm leading-5 text-slate-300">{freezeDecision.answer}</p>
          </div>
        </div>
      </section>

      <section
        className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
        aria-label="Freeze center"
      >
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Freeze Center</h2>
            <p className="mt-1 text-xs text-slate-500">
              Pending, blocked, approved and expired freeze states in one governance surface.
            </p>
          </div>
          <StateBadge value="FREEZE NOT APPROVED" tone="danger" />
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MiniMetric label="Pending" value={pendingCount} tone="warning" />
          <MiniMetric label="Blocked" value={blockedCount} tone="danger" />
          <MiniMetric label="Approved" value={approvedCount} />
          <MiniMetric label="Expired" value={expiredCount} />
        </div>
        <div className="mt-4 grid gap-3 xl:grid-cols-4">
          {freezeLanes.map((lane) => {
            const visibleCount =
              lane.state === "Approved"
                ? approvedCount
                : lane.state === "Expired"
                  ? expiredCount
                  : lane.items.length;

            return (
              <div key={lane.state} className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-white">{lane.state}</h3>
                  <StateBadge value={visibleCount} tone={operationalTone(lane.state)} />
                </div>
                <div className="mt-3 space-y-2">
                  {lane.items.map((item) => (
                    <article
                      key={`${lane.state}-${item.name}`}
                      className="rounded-md border border-slate-700 bg-slate-950/70 p-3"
                    >
                      <div className="break-all text-sm font-semibold leading-5 text-slate-100">
                        {item.name}
                      </div>
                      <div className="mt-2 text-xs text-slate-500">System: {item.system}</div>
                      <div className="mt-2 text-sm leading-5 text-slate-400">{item.detail}</div>
                    </article>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section
        className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
        aria-label="Readiness classification"
      >
        <div className="grid gap-4 xl:grid-cols-[0.8fr_1.2fr]">
          <div className={`rounded-lg border p-4 ${toneClasses(operationalTone(freezeReadiness.classification))}`}>
            <div className="text-[11px] uppercase tracking-[0.14em] text-slate-300">
              Readiness Classification
            </div>
            <div className="mt-2 text-2xl font-semibold text-white">
              {freezeReadiness.classification}
            </div>
            <p className="mt-3 text-sm leading-5 text-slate-300">{freezeReadiness.basis}</p>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-4">
            <h2 className="text-sm font-semibold text-slate-100">Evidence Basis</h2>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {freezeReadiness.evidence.map((item) => (
                <div
                  key={item}
                  className="rounded-md border border-slate-700 bg-slate-950/70 p-3 text-sm text-slate-300"
                >
                  {item}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section
        className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
        aria-label="Blocker governance"
      >
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Blocker Governance</h2>
            <p className="mt-1 text-xs text-slate-500">
              Active and historical blockers stay visible with impact and required resolution.
            </p>
          </div>
          <StateBadge value={`${blockedCount} ACTIVE BLOCKERS`} tone="danger" />
        </div>
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {blockerGovernance.map((item) => (
            <article
              key={item.blocker}
              className="rounded-lg border border-slate-800 bg-slate-900/70 p-4"
            >
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <h3 className="break-all text-sm font-semibold text-white">{item.blocker}</h3>
                <StateBadge value={item.type} tone={operationalTone(item.type)} />
              </div>
              <div className="mt-3 text-xs uppercase tracking-[0.14em] text-slate-500">
                Impact
              </div>
              <p className="mt-1 text-sm leading-5 text-slate-300">{item.impact}</p>
              <div className="mt-3 rounded-md border border-slate-700 bg-slate-950/70 p-3 text-sm text-slate-200">
                Required resolution: {item.resolution}
              </div>
            </article>
          ))}
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <section
          className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
          aria-label="Certification panel"
        >
          <h2 className="text-sm font-semibold text-slate-100">Certification Panel</h2>
          <div className="mt-4 space-y-3">
            {certificationPanel.map((item) => (
              <article
                key={item.certification}
                className="rounded-lg border border-slate-800 bg-slate-900/70 p-4"
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <h3 className="text-sm font-semibold text-white">{item.certification}</h3>
                  <StateBadge value={item.status} tone={operationalTone(item.status)} />
                </div>
                <div className="mt-3 break-all rounded-md border border-slate-700 bg-slate-950/70 p-3 text-sm text-slate-300">
                  Evidence: {item.evidence}
                </div>
              </article>
            ))}
          </div>
        </section>

        <section
          className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
          aria-label="Operational trust panel"
        >
          <h2 className="text-sm font-semibold text-slate-100">Operational Trust Panel</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {operationalTrust.map((item) => (
              <article
                key={item.trust}
                className="rounded-lg border border-slate-800 bg-slate-900/70 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-semibold text-white">{item.trust}</h3>
                  <StateBadge value={item.status} tone={operationalTone(item.status)} />
                </div>
                <p className="mt-3 text-sm leading-5 text-slate-300">{item.evidence}</p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}

function ViewPanel({ view }) {
  const copy = viewCopy[view];

  return (
    <section className="rounded-xl border border-slate-700 bg-slate-950/75 p-5">
      <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
        {copy.eyebrow}
      </div>
      <h1 className="mt-2 text-2xl font-semibold text-white">{copy.title}</h1>
      <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
        {copy.summary}
      </p>
      <div className="mt-5 rounded-lg border border-slate-700 bg-slate-900/80 p-4">
        <div className="text-[11px] uppercase tracking-[0.14em] text-slate-500">
          Current state
        </div>
        <div className="mt-2 text-base font-semibold text-slate-100">
          {copy.primary}
        </div>
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-3">
        {copy.points.map((point) => (
          <div
            key={point}
            className="rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-sm leading-5 text-slate-300"
          >
            {point}
          </div>
        ))}
      </div>
    </section>
  );
}

function IntegrationCertificationPanel() {
  return (
    <section
      className="rounded-xl border border-slate-700 bg-slate-950/75 p-4"
      aria-label="vNext Integration Certification"
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
            FORJA PHASE 2.10
          </div>
          <h2 className="mt-2 text-xl font-semibold text-white">
            vNext Integration Certification
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
            {finalOperatorCertification.basis}
          </p>
        </div>
        <div className={`min-w-[220px] rounded-lg border p-4 ${toneClasses(operationalTone(finalOperatorCertification.classification))}`}>
          <div className="text-[11px] uppercase tracking-[0.14em] text-slate-300">
            Final Classification
          </div>
          <div className="mt-2 text-2xl font-semibold text-white">
            {finalOperatorCertification.classification}
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <MiniMetric
          label="Cabin Integration"
          value={`${cabinIntegration.length}/6`}
          detail="Primary cabins integrated"
          tone="good"
        />
        <MiniMetric
          label="Operator Flow"
          value="PRESERVED"
          detail="Idea to Freeze context retained"
          tone="good"
        />
        <MiniMetric
          label="Cognitive Load"
          value={cognitiveLoadEvaluation.vNext}
          detail={`Original: ${cognitiveLoadEvaluation.original}`}
          tone="warning"
        />
        <MiniMetric
          label="Executive Visibility"
          value="PASS"
          detail={cognitiveLoadEvaluation.decisionTime}
          tone="good"
        />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_1fr]">
        <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <h3 className="text-sm font-semibold text-white">Cabin Integration</h3>
            <StateBadge value="6 INTEGRATED" tone="good" />
          </div>
          <div className="mt-3 grid gap-2 md:grid-cols-2">
            {cabinIntegration.map((item) => (
              <article
                key={item.cabin}
                className="rounded-md border border-slate-700 bg-slate-950/70 p-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="text-sm font-semibold text-slate-100">{item.cabin}</div>
                  <StateBadge value={item.status} tone={operationalTone(item.status)} />
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-400">{item.evidence}</p>
              </article>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <h3 className="text-sm font-semibold text-white">Operator Flow Validation</h3>
            <StateBadge value={`${cognitiveLoadEvaluation.sequentialFlowClicks} CLICKS`} tone="good" />
          </div>
          <div className="mt-3 grid gap-2 md:grid-cols-2">
            {operatorFlowValidation.map((item) => (
              <article
                key={item.step}
                className="rounded-md border border-slate-700 bg-slate-950/70 p-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="text-sm font-semibold text-slate-100">{item.step}</div>
                  <StateBadge value={item.state} tone={operationalTone(item.state)} />
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-400">{item.context}</p>
              </article>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_1fr]">
        <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-4">
          <h3 className="text-sm font-semibold text-white">Executive Visibility</h3>
          <div className="mt-3 grid gap-2 md:grid-cols-2">
            {executiveVisibilityValidation.map((item) => (
              <article
                key={item.signal}
                className="rounded-md border border-slate-700 bg-slate-950/70 p-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="text-sm font-semibold text-slate-100">{item.signal}</div>
                  <StateBadge value={item.status} tone={operationalTone(item.status)} />
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-400">{item.evidence}</p>
              </article>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-4">
          <h3 className="text-sm font-semibold text-white">Theater Elimination</h3>
          <div className="mt-3 grid gap-2 md:grid-cols-2">
            {theaterEliminationAudit.map((item) => (
              <article
                key={item.check}
                className="rounded-md border border-slate-700 bg-slate-950/70 p-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="text-sm font-semibold text-slate-100">{item.check}</div>
                  <StateBadge value={item.result} tone={operationalTone(item.result)} />
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-400">{item.evidence}</p>
              </article>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-amber-300/40 bg-amber-400/10 p-4">
        <div className="text-[11px] uppercase tracking-[0.14em] text-amber-100">
          Certification Boundary
        </div>
        <p className="mt-2 text-sm leading-6 text-slate-200">
          vNext is certified as OPERATIONAL for local operator experience. It is not certified for executive-ready or ecosystem command-center operation because deploy trust, source-to-live traceability, rollback trust and development auth remain unresolved.
        </p>
      </div>
    </section>
  );
}

function ExecutiveCabin() {
  return (
    <section className="space-y-4" aria-label="Executive Cabin">
      <section className="rounded-xl border border-slate-700 bg-slate-950/75 p-5">
        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
          EXECUTIVE CABIN
        </div>
        <div className="mt-2 grid gap-4 lg:grid-cols-[1.4fr_1fr] lg:items-start">
          <div>
            <h1 className="text-2xl font-semibold text-white">
              Ecosystem Operational View
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
              Vista ejecutiva inicial: tres sistemas, blockers activos, auditoria, deploy, freeze y una decision inmediata. Estados basados en reportes locales verificados; no hay estados seguros fabricados.
            </p>
          </div>
          <div className="space-y-3">
            <div className="rounded-lg border border-sky-300/40 bg-sky-400/10 p-4">
              <div className="text-[11px] uppercase tracking-[0.14em] text-sky-200">
                Decision Center
              </div>
              <div className="mt-2 text-base font-semibold text-white">
                {executiveDecision}
              </div>
            </div>
            <div className="rounded-lg border border-red-400/40 bg-red-500/10 p-4">
              <div className="text-[11px] uppercase tracking-[0.14em] text-red-100">
                Top Blocker
              </div>
              <div className="mt-2 break-all text-base font-semibold text-white">
                {executiveBlockers[0].id}
              </div>
              <div className="mt-1 text-sm text-slate-300">
                {executiveBlockers[0].action}
              </div>
            </div>
          </div>
        </div>
      </section>

      <IntegrationCertificationPanel />

      <ExecutiveSection title="Ecosystem Overview">
        <div className="grid gap-3 lg:grid-cols-3">
          {ecosystemSystems.map((system) => (
            <article
              key={system.name}
              className="min-w-0 rounded-lg border border-slate-800 bg-slate-900/70 p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-lg font-semibold text-white">{system.name}</div>
                  <p className="mt-2 text-sm leading-5 text-slate-400">{system.detail}</p>
                </div>
                <StateBadge value={system.state} tone={system.tone} />
              </div>
              <div className="mt-4 break-all text-xs text-slate-500">
                Evidence: {system.evidence}
              </div>
            </article>
          ))}
        </div>
      </ExecutiveSection>

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <ExecutiveSection title="Active Blockers">
          <div className="space-y-3">
            {executiveBlockers.map((blocker) => (
              <article
                key={blocker.id}
                className="rounded-lg border border-slate-800 bg-slate-900/70 p-4"
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div className="break-all font-semibold text-white">{blocker.id}</div>
                  <StateBadge
                    value={blocker.severity}
                    tone={blocker.severity === "CRITICAL" ? "danger" : "warning"}
                  />
                </div>
                <div className="mt-2 text-sm text-slate-400">
                  System: <span className="text-slate-200">{blocker.system}</span>
                </div>
                <div className="mt-2 text-sm leading-5 text-slate-300">{blocker.impact}</div>
                <div className="mt-3 rounded-md border border-slate-700 bg-slate-950/70 p-3 text-sm text-slate-200">
                  Required action: {blocker.action}
                </div>
              </article>
            ))}
          </div>
        </ExecutiveSection>

        <div className="space-y-4">
          <ExecutiveSection title="Audit Status">
            <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
              <MiniMetric
                label="Active"
                value={auditStatus.active.length}
                detail={auditStatus.active[0]?.name}
                tone="warning"
              />
              <MiniMetric
                label="Pending"
                value={auditStatus.pending.length}
                detail={auditStatus.pending[0]?.name}
              />
              <MiniMetric
                label="Completed"
                value={auditStatus.completed.length}
                detail="Phase 2.1 - 2.3"
                tone="good"
              />
            </div>
          </ExecutiveSection>

          <ExecutiveSection title="Executive Priorities">
            <div className="space-y-2">
              {executivePriorities.map((priority) => (
                <div
                  key={priority.level}
                  className="rounded-lg border border-slate-800 bg-slate-900/70 p-3"
                >
                  <StateBadge
                    value={priority.level}
                    tone={priority.level === "CRITICAL" ? "danger" : priority.level === "HIGH" ? "warning" : "neutral"}
                  />
                  <div className="mt-2 text-sm leading-5 text-slate-300">{priority.text}</div>
                </div>
              ))}
            </div>
          </ExecutiveSection>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <ExecutiveSection title="Deploy Status">
          <div className="grid gap-3 sm:grid-cols-2">
            <MiniMetric label="Last deploy" value={deployStatus.lastDeploy} />
            <MiniMetric label="Pending" value={deployStatus.pending} />
            <MiniMetric label="Blocked" value={deployStatus.blocked} tone="warning" />
            <MiniMetric label="Validated" value={deployStatus.validated} />
          </div>
          <div className="mt-3 rounded-lg border border-slate-800 bg-slate-900/70 p-3 text-sm text-slate-300">
            {deployStatus.reason}
          </div>
        </ExecutiveSection>

        <ExecutiveSection title="Freeze Status">
          <div className="grid gap-3 sm:grid-cols-2">
            <MiniMetric label="Active" value={freezeStatus.active} />
            <MiniMetric label="Blocked" value={freezeStatus.blocked} tone="warning" />
            <MiniMetric label="Pending" value={freezeStatus.pending} />
            <MiniMetric label="Approved" value={freezeStatus.approved} />
          </div>
          <div className="mt-3 rounded-lg border border-slate-800 bg-slate-900/70 p-3 text-sm text-slate-300">
            {freezeStatus.reason}
          </div>
        </ExecutiveSection>
      </div>
    </section>
  );
}

function RuntimeEvidence({ health }) {
  const tone = health.loading ? "warning" : health.status === "ok" ? "good" : "danger";
  const value = health.loading ? "CHECKING" : health.status.toUpperCase();
  const detail =
    health.loading
      ? "Health request in progress"
      : health.error
        ? "Backend health unavailable"
        : `Source: /api/v1/health${health.timestamp ? ` | ${health.timestamp}` : ""}`;

  return (
    <StatusPill
      label="Runtime Evidence"
      value={value}
      detail={detail}
      tone={tone}
    />
  );
}

function App() {
  const [activeView, setActiveView] = useState("home");
  const health = useHealth();
  const activeLabel = useMemo(
    () => navItems.find((item) => item.id === activeView)?.label || "HOME",
    [activeView]
  );

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 py-4 sm:px-6 lg:px-8">
        <header className="rounded-xl border border-slate-700 bg-slate-950/80 p-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">
                FORJA COMMAND SHELL
              </div>
              <div className="mt-2 text-3xl font-semibold text-white">
                vNext Operational Shell
              </div>
              <div className="mt-2 text-sm text-slate-400">
                Active view: {activeLabel}. Shell phase only; no fake deploy, freeze, or cabin completion claims.
              </div>
            </div>
            <div className="rounded-lg border border-slate-700 bg-slate-900/70 px-3 py-2 text-sm text-slate-300">
              Evidence posture: LOCAL / PARTIAL
            </div>
          </div>
        </header>

        <nav
          className="mt-4 flex gap-2 overflow-x-auto rounded-xl border border-slate-700 bg-slate-950/80 p-2"
          aria-label="FORJA vNext navigation"
        >
          {navItems.map((item) => {
            const active = item.id === activeView;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setActiveView(item.id)}
                className={`min-h-[40px] flex-none rounded-lg px-3 text-sm font-semibold transition ${
                  active
                    ? "bg-sky-400 text-slate-950"
                    : "bg-slate-900 text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
                aria-current={active ? "page" : undefined}
              >
                {item.label}
              </button>
            );
          })}
        </nav>

        <main className="flex flex-1 flex-col gap-4 py-4">
          <section
            className="grid gap-3 md:grid-cols-2 xl:grid-cols-6"
            aria-label="Global status bar"
          >
            {globalStatus.map((item) => (
              <StatusPill key={item.label} {...item} />
            ))}
            <RuntimeEvidence health={health} />
          </section>

          <CommandCenter />
          {activeView === "home" ? (
            <>
              <ExecutiveCabin />
              <WorkflowRail />
            </>
          ) : activeView === "workflow" ? (
            <WorkflowCabin />
          ) : activeView === "codex" ? (
            <CodexCabin />
          ) : activeView === "validation" ? (
            <ValidationCabin />
          ) : activeView === "deploy" ? (
            <DeployCabin />
          ) : activeView === "freeze" ? (
            <FreezeCabin />
          ) : (
            <>
              <WorkflowRail />
              <ViewPanel view={activeView} />
            </>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
