"use client";

import type { SocialActionRecord } from "@/lib/api";

export type SocialFieldActionType =
  | "FIELD_CONTACT"
  | "FIELD_ALIGN"
  | "FIELD_CONTEST"
  | "FIELD_NEGOTIATE"
  | "FIELD_PRESSURE_SHIFT"
  | "FIELD_DRIFT"
  | "DEEP_COMMIT";

export type SocialFieldTone = "positive" | "negative" | "hostile" | "dialogue";

const ACTION_META: Record<SocialFieldActionType, { ko: string; en: string; tone: SocialFieldTone; color: number; className: string }> = {
  FIELD_CONTACT: {
    ko: "사회장 접촉",
    en: "Field Contact",
    tone: "dialogue",
    color: 0x64748b,
    className: "bg-slate-100 text-slate-700",
  },
  FIELD_ALIGN: {
    ko: "정렬/협력",
    en: "Field Align",
    tone: "positive",
    color: 0x16a34a,
    className: "bg-emerald-50 text-emerald-700",
  },
  FIELD_CONTEST: {
    ko: "대립/압력 충돌",
    en: "Field Contest",
    tone: "hostile",
    color: 0xdc2626,
    className: "bg-rose-50 text-rose-700",
  },
  FIELD_NEGOTIATE: {
    ko: "협상/이견 조정",
    en: "Field Negotiate",
    tone: "negative",
    color: 0xf59e0b,
    className: "bg-amber-50 text-amber-700",
  },
  FIELD_PRESSURE_SHIFT: {
    ko: "압력장 변화",
    en: "Pressure Shift",
    tone: "negative",
    color: 0x0f766e,
    className: "bg-teal-50 text-teal-700",
  },
  FIELD_DRIFT: {
    ko: "장 내부 이동",
    en: "Field Drift",
    tone: "dialogue",
    color: 0x2563eb,
    className: "bg-blue-50 text-blue-700",
  },
  DEEP_COMMIT: {
    ko: "t 경계 심층 커밋",
    en: "Deep Commit",
    tone: "dialogue",
    color: 0x334155,
    className: "bg-slate-100 text-slate-800",
  },
};

export function normalizeSocialFieldActionType(value: unknown): SocialFieldActionType {
  const raw = String(value ?? "").trim().toUpperCase();
  if (raw in ACTION_META) return raw as SocialFieldActionType;
  if (raw === "CONSULT_ALIGN") return "FIELD_ALIGN";
  if (raw === "CONSULT_CONFLICT") return "FIELD_CONTEST";
  if (raw === "CONSULT_NEGOTIATE") return "FIELD_NEGOTIATE";
  if (raw === "CONSULT") return "FIELD_CONTACT";
  if (raw === "PRESSURE_SHIFT") return "FIELD_PRESSURE_SHIFT";
  if (raw === "COMMIT_SIGNAL") return "DEEP_COMMIT";
  return "FIELD_CONTACT";
}

export function socialFieldActionMeta(value: unknown) {
  return ACTION_META[normalizeSocialFieldActionType(value)];
}

export function socialFieldActionLabel(record: SocialActionRecord | null | undefined, locale: "ko" | "en" = "ko"): string {
  const explicit = String(record?.action_label ?? "").trim();
  if (explicit) return explicit;
  const meta = socialFieldActionMeta(record?.action_type);
  return locale === "ko" ? meta.ko : meta.en;
}

export function socialFieldToneFromRecord(record: SocialActionRecord | null | undefined, fallback?: unknown): SocialFieldTone {
  if (record?.action_type) return socialFieldActionMeta(record.action_type).tone;
  const raw = String(fallback ?? "dialogue").trim();
  if (raw === "positive" || raw === "negative" || raw === "hostile" || raw === "dialogue") return raw;
  if (raw === "alignment") return "positive";
  if (raw === "conflict") return "hostile";
  return "dialogue";
}

export function socialFieldColorFromRecord(record: SocialActionRecord | null | undefined, fallback?: unknown): number {
  if (record?.action_type) return socialFieldActionMeta(record.action_type).color;
  const tone = socialFieldToneFromRecord(record, fallback);
  if (tone === "positive") return ACTION_META.FIELD_ALIGN.color;
  if (tone === "negative") return ACTION_META.FIELD_NEGOTIATE.color;
  if (tone === "hostile") return ACTION_META.FIELD_CONTEST.color;
  return ACTION_META.FIELD_CONTACT.color;
}

export function socialFieldToneLabel(tone: SocialFieldTone | string | undefined, locale: "ko" | "en" = "ko"): string {
  if (tone === "positive") return locale === "ko" ? "협력" : "positive";
  if (tone === "negative") return locale === "ko" ? "갈등" : "negative";
  if (tone === "hostile") return locale === "ko" ? "적대" : "hostile";
  if (tone === "dialogue") return locale === "ko" ? "대화" : "dialogue";
  return locale === "ko" ? "압력" : "pressure";
}
