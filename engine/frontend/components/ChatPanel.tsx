"use client";

import { useEffect, useMemo, useState } from "react";
import {
  postWorldChat,
  type CellSnapshot,
  type WorldChatResponse,
  type WorldChatTargetType,
} from "@/lib/api";
import type { SelectedZone } from "@/components/SimulationInspectorPanel";
import type { UiLocale } from "@/lib/ui-language";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  response?: WorldChatResponse;
};

type ChatPanelProps = {
  locale: UiLocale;
  worldId: string | null;
  currentT: number;
  cells: CellSnapshot[];
  selectedAgent: CellSnapshot | null;
  selectedZone: SelectedZone | null;
};

export function ChatPanel({
  locale,
  worldId,
  currentT,
  cells,
  selectedAgent,
  selectedZone,
}: ChatPanelProps) {
  const isKo = locale === "ko";
  const [question, setQuestion] = useState("");
  const [targetType, setTargetType] = useState<WorldChatTargetType>("world");
  const [roleKey, setRoleKey] = useState("");
  const [zoneId, setZoneId] = useState("");
  const [cellId, setCellId] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const roleOptions = useMemo(() => uniqueOptions(cells, "role"), [cells]);
  const zoneOptions = useMemo(() => uniqueOptions(cells, "zone"), [cells]);
  const agentOptions = useMemo(
    () =>
      cells.slice(0, 80).map((cell) => ({
        value: cell.cell_id,
        label: formatAgentLabel(cell),
      })),
    [cells]
  );
  const targetLabel = useMemo(
    () => describeTarget(locale, targetType, { roleKey, zoneId, cellId, cells }),
    [cellId, cells, locale, roleKey, targetType, zoneId]
  );
  const promptSuggestions = useMemo(
    () => buildPromptSuggestions(locale, targetType, targetLabel),
    [locale, targetLabel, targetType]
  );

  useEffect(() => {
    if (selectedAgent) {
      setCellId(selectedAgent.cell_id);
      setRoleKey(selectedAgent.role_key || selectedAgent.role_label || "");
      setZoneId(selectedAgent.zone_id || selectedAgent.zone_label || "");
      return;
    }
    if (selectedZone) {
      setZoneId(selectedZone.zoneId);
    }
  }, [selectedAgent, selectedZone]);

  const submit = async (textOverride?: string) => {
    const text = (textOverride ?? question).trim();
    if (!worldId || !text || loading) return;
    setLoading(true);
    setError(null);
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
    };
    setMessages((current) => [...current, userMessage]);
    if (!textOverride) setQuestion("");
    try {
      const response = await postWorldChat(worldId, {
        question: text,
        session_id: sessionId,
        context: {
          t: currentT,
          target_type: targetType,
          cell_id: targetType === "agent" ? cellId || null : null,
          role_key: targetType === "role" ? roleKey || null : null,
          zone_id: targetType === "zone" ? zoneId || null : null,
        },
      });
      setSessionId(response.session_id);
      setMessages((current) => [
        ...current,
        {
          id: response.message_id,
          role: "assistant",
          content: response.answer,
          response,
        },
      ]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "chat failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-0 flex-col gap-3">
      <div className="rounded-[22px] border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-slate-900">{isKo ? "월드 챗" : "World Chat"}</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              {isKo
                ? "세계, 역할, 구역, 특정 페르소나에게 현재 t 기준으로 질문합니다."
                : "Ask the world, a role, a zone, or one persona at the current t."}
            </p>
          </div>
          <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">
            t={currentT.toFixed(1)}
          </span>
        </div>
        <div className="mt-3 rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600">
          <span className="font-semibold text-slate-800">{isKo ? "현재 질문 맥락" : "Current context"}</span>
          <span className="mx-1 text-slate-300">·</span>
          {targetLabel}
          <span className="mx-1 text-slate-300">·</span>
          {cells.length} {isKo ? "개 관측 셀" : "observed cells"}
        </div>
        <div className="mt-3 grid gap-2">
          <label className="flex flex-col gap-1 text-[11px] text-slate-500">
            {isKo ? "대화 대상" : "Target"}
            <select className="app-input" value={targetType} onChange={(event) => setTargetType(event.target.value as WorldChatTargetType)}>
              <option value="world">{isKo ? "세계 전체" : "Whole world"}</option>
              <option value="role">{isKo ? "역할 집단" : "Role group"}</option>
              <option value="zone">{isKo ? "구역" : "Zone"}</option>
              <option value="agent">{isKo ? "페르소나 에이전트" : "Persona agent"}</option>
            </select>
          </label>
          {targetType === "role" ? (
            <ContextSelect label={isKo ? "역할" : "Role"} value={roleKey} options={roleOptions} onChange={setRoleKey} />
          ) : null}
          {targetType === "zone" ? (
            <ContextSelect label={isKo ? "구역" : "Zone"} value={zoneId} options={zoneOptions} onChange={setZoneId} />
          ) : null}
          {targetType === "agent" ? (
            <ContextSelect label={isKo ? "에이전트" : "Agent"} value={cellId} options={agentOptions} onChange={setCellId} />
          ) : null}
        </div>
      </div>

      <div className="min-h-[220px] flex-1 space-y-3 overflow-y-auto rounded-[22px] border border-slate-200 bg-slate-50 p-3">
        {messages.length ? (
          messages.map((message) => (
            <article
              key={message.id}
              className={`rounded-2xl px-3 py-3 text-sm shadow-sm ${
                message.role === "user" ? "ml-6 bg-slate-900 text-white" : "mr-6 border border-slate-200 bg-white text-slate-800"
              }`}
            >
              <p className="whitespace-pre-wrap leading-6">{message.content}</p>
              {message.response ? <ChatEvidence locale={locale} response={message.response} /> : null}
              {message.response?.follow_up.length ? (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {message.response.follow_up.map((item) => (
                    <button
                      key={`${message.id}-${item}`}
                      type="button"
                      className="rounded-full border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium text-slate-600 hover:border-slate-400 hover:text-slate-900"
                      onClick={() => void submit(item)}
                    >
                      {item}
                    </button>
                  ))}
                </div>
              ) : null}
            </article>
          ))
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-3 py-4 text-xs leading-5 text-slate-500">
            {isKo
              ? "예: 지금 저소득층 시민들은 정책을 어떻게 해석하고 있어? / 이 구역의 긴장은 왜 높아졌어?"
              : "Try: How are low-income citizens interpreting the policy? Why did this zone become tense?"}
          </div>
        )}
      </div>

      {error ? <p className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</p> : null}

      <div className="flex flex-wrap gap-1.5">
        {promptSuggestions.map((item) => (
          <button
            key={item}
            type="button"
            className="rounded-full border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-slate-600 shadow-sm hover:border-slate-400 hover:text-slate-900"
            onClick={() => setQuestion(item)}
          >
            {item}
          </button>
        ))}
      </div>

      <div className="rounded-[22px] border border-slate-200 bg-white p-2 shadow-sm">
        <textarea
          className="min-h-20 w-full resize-none rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-800 outline-none focus:border-slate-400"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder={isKo ? "세계에 질문하기..." : "Ask this world..."}
          onKeyDown={(event) => {
            if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
              void submit();
            }
          }}
        />
        <div className="mt-2 flex items-center justify-between gap-2">
          <p className="text-[11px] text-slate-500">{isKo ? "⌘/Ctrl + Enter 전송" : "⌘/Ctrl + Enter to send"}</p>
          <button type="button" className="app-button app-button--primary" onClick={() => void submit()} disabled={!worldId || loading || !question.trim()}>
            {loading ? (isKo ? "해석 중…" : "Thinking…") : isKo ? "질문" : "Ask"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ChatEvidence({ locale, response }: { locale: UiLocale; response: WorldChatResponse }) {
  const isKo = locale === "ko";
  const snapshot = asRecord(response.metadata.snapshot);
  const target = asRecord(response.metadata.target);
  const comparison = asRecord(response.metadata.comparison);
  const targetSummary = asRecord(target.summary);
  const stats = [
    `${isKo ? "셀" : "cells"} ${Number(snapshot.target_cell_count ?? 0)}/${Number(snapshot.cell_count ?? 0)}`,
    `${isKo ? "압력" : "pressure"} ${formatMetric(targetSummary.avg_collective_pressure ?? snapshot.avg_collective_pressure)}`,
    `${isKo ? "결정Δ" : "decision Δ"} ${formatMetric(targetSummary.avg_decision_pressure_delta ?? snapshot.avg_decision_pressure_delta)}`,
    `${isKo ? "장면" : "scenes"} ${Number(targetSummary.relevant_scene_event_count ?? 0)}`,
    ...(comparison.compare_t != null
      ? [`${isKo ? "전 t 대비" : "vs prev"} ${formatSignedMetric(comparison.pressure_delta)}`]
      : []),
  ];
  return (
    <details className="mt-3 rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2 text-xs text-slate-600">
      <summary className="cursor-pointer list-none font-semibold text-slate-700">
        {isKo ? "근거 보기" : "Show grounding"} · {response.mode}
      </summary>
      <div className="mt-2 flex flex-wrap gap-1">
        {stats.map((item) => (
          <span key={item} className="rounded-full bg-white px-2 py-1 text-[10px] font-semibold text-slate-600">
            {item}
          </span>
        ))}
      </div>
      {response.evidence.length ? (
        <div className="mt-2 space-y-1">
          {response.evidence.map((item, index) => (
            <p key={`${response.message_id}-evidence-${index}`}>- {item}</p>
          ))}
        </div>
      ) : null}
      {response.citations.length ? (
        <div className="mt-2 flex flex-wrap gap-1">
          {response.citations.map((item) => (
            <span key={item.anchor_id} className="rounded-full bg-white px-2 py-1 text-[10px] font-semibold text-slate-600">
              {item.kind}:{item.label}
            </span>
          ))}
        </div>
      ) : null}
    </details>
  );
}

function ContextSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1 text-[11px] text-slate-500">
      {label}
      <select className="app-input" value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">auto</option>
        {options.map((item) => (
          <option key={item.value} value={item.value}>
            {item.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function uniqueOptions(cells: CellSnapshot[], kind: "role" | "zone"): Array<{ value: string; label: string }> {
  const rows = new Map<string, string>();
  for (const cell of cells) {
    const value = kind === "role" ? cell.role_key || cell.role_label : cell.zone_id || cell.zone_label;
    const label = kind === "role" ? cell.role_label || cell.role_key : cell.zone_label || cell.zone_id;
    if (value && !rows.has(value)) rows.set(value, label || value);
  }
  return Array.from(rows.entries()).map(([value, label]) => ({ value, label }));
}

function formatAgentLabel(cell: CellSnapshot): string {
  const attrs = cell.persona_attrs ?? {};
  const name = firstText(attrs.agent_name, attrs.display_name, attrs.name, cell.persona_id);
  const role = firstText(cell.role_label, cell.role_key, "agent");
  return name && name !== role ? `${name}(${role})` : role;
}

function firstText(...values: unknown[]): string {
  for (const value of values) {
    const text = String(value ?? "").trim();
    if (text && text !== "undefined" && text !== "null") return text;
  }
  return "";
}

function describeTarget(
  locale: UiLocale,
  targetType: WorldChatTargetType,
  {
    roleKey,
    zoneId,
    cellId,
    cells,
  }: {
    roleKey: string;
    zoneId: string;
    cellId: string;
    cells: CellSnapshot[];
  }
): string {
  const isKo = locale === "ko";
  if (targetType === "agent") {
    const cell = cells.find((item) => item.cell_id === cellId);
    return cell ? formatAgentLabel(cell) : isKo ? "선택된 에이전트 자동" : "Auto selected agent";
  }
  if (targetType === "role") return roleKey || (isKo ? "역할 자동" : "Auto role");
  if (targetType === "zone") return zoneId || (isKo ? "구역 자동" : "Auto zone");
  return isKo ? "세계 전체" : "Whole world";
}

function buildPromptSuggestions(locale: UiLocale, targetType: WorldChatTargetType, targetLabel: string): string[] {
  const isKo = locale === "ko";
  if (!isKo) {
    if (targetType === "agent") {
      return ["Who influenced this agent most?", "What will this agent likely do next?", "What pressure is shaping them?"];
    }
    return ["Which group is under the highest pressure?", "What changed after the latest scene?", "Where is fracture risk rising?"];
  }
  if (targetType === "agent") {
    return [
      `${targetLabel}은 누구의 말에 흔들렸어?`,
      `${targetLabel}의 다음 행동 가능성은 뭐야?`,
      "이 에이전트의 생각이 시나리오와 어떻게 연결돼?",
    ];
  }
  if (targetType === "role") {
    return [`${targetLabel} 내부에서 의견이 갈리는 지점은?`, "이 역할 집단의 압력은 왜 올라갔어?", "정책을 어떻게 해석하고 있어?"];
  }
  if (targetType === "zone") {
    return [`${targetLabel}에서 긴장이 생긴 이유는?`, "이 구역의 최근 상호작용을 요약해줘.", "다른 구역과 무엇이 달라?"];
  }
  return ["가장 압력이 높은 집단은 누구야?", "최근 장면에서 중요한 변화는 뭐야?", "정책 주입 전후 반응을 비교해줘."];
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function formatMetric(value: unknown): string {
  const num = Number(value ?? 0);
  return Number.isFinite(num) ? num.toFixed(3) : "0.000";
}

function formatSignedMetric(value: unknown): string {
  const num = Number(value ?? 0);
  if (!Number.isFinite(num)) return "+0.000";
  return `${num >= 0 ? "+" : ""}${num.toFixed(3)}`;
}
