"use client";

export type WorkbenchView =
  | "overview"
  | "simulation"
  | "review-lab"
  | "data-packs"
  | "snapshots"
  | "policy-lab";

export const WORKBENCH_ITEMS: Array<{
  id: WorkbenchView;
  label: string;
  shortLabel: string;
}> = [
  { id: "overview", label: "Overview", shortLabel: "OV" },
  { id: "simulation", label: "Simulation", shortLabel: "SIM" },
  { id: "data-packs", label: "Data Management", shortLabel: "DM" },
  { id: "snapshots", label: "Snapshots", shortLabel: "SS" },
  { id: "policy-lab", label: "Policy Lab", shortLabel: "PL" },
];
