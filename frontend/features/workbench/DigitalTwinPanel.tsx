"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/features/auth/AuthProvider";
import {
  AI_TWIN_STATUS_LABEL,
  DELEGATION_PERMISSION_LABEL,
  DELEGATION_PERMISSION_ORDER,
  HUMAN_STATUS_LABEL,
  HUMAN_STATUS_VALUES,
  type AITwinStatus,
  type DelegationPermissionKey,
  type HumanStatus,
  type WorkbenchProfile,
} from "@/lib/types";

const AI_TWIN_STATUSES: AITwinStatus[] = ["OFF", "ASSIST", "AGENT"];

export function DigitalTwinPanel({
  profile,
  onChange,
}: {
  profile: WorkbenchProfile;
  onChange: (p: WorkbenchProfile) => void;
}) {
  const { currentCompany } = useAuth();
  const [nameDraft, setNameDraft] = useState(profile.ai_twin_name ?? "");
  const [nameSaved, setNameSaved] = useState(true);
  const [busy, setBusy] = useState(false);

  if (!currentCompany) return null;

  async function patchTwin(body: Record<string, unknown>) {
    setBusy(true);
    try {
      const updated = await api<{ profile: WorkbenchProfile }>(
        `/companies/${currentCompany!.id}/workbench/ai-twin`,
        { method: "PATCH", body }
      );
      onChange(updated.profile);
    } finally {
      setBusy(false);
    }
  }

  async function patchHuman(status: HumanStatus) {
    setBusy(true);
    try {
      const updated = await api<{ profile: WorkbenchProfile }>(
        `/companies/${currentCompany!.id}/workbench/human-status`,
        { method: "PATCH", body: { status } }
      );
      onChange(updated.profile);
    } finally {
      setBusy(false);
    }
  }

  function togglePermission(key: DelegationPermissionKey, value: boolean) {
    const next = { ...profile.ai_permissions, [key]: value };
    void patchTwin({ ai_permissions: next });
  }

  function saveName() {
    setNameSaved(true);
    void patchTwin({ ai_twin_name: nameDraft.trim() || null });
  }

  return (
    <section className="card p-5">
      {/* UserIdentity */}
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-full bg-gray-900 text-base font-semibold text-white">
          {profile.user_name.slice(0, 1)}
        </div>
        <div className="min-w-0">
          <div className="truncate text-base font-semibold text-gray-900">{profile.user_name}</div>
          <div className="truncate text-xs text-gray-400">
            {profile.department_name ?? "未分配部门"}
            {profile.position ? ` · ${profile.position}` : ""}
          </div>
        </div>
      </div>

      {/* 真人状态 */}
      <div className="mt-5">
        <div className="mb-2 text-xs font-medium text-gray-400">真人状态</div>
        <div className="flex flex-wrap gap-2">
          {HUMAN_STATUS_VALUES.map((s) => {
            const active = profile.human_status === s;
            return (
              <button
                key={s}
                disabled={busy}
                onClick={() => patchHuman(s)}
                className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  active
                    ? "bg-gray-900 text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {HUMAN_STATUS_LABEL[s]}
              </button>
            );
          })}
        </div>
      </div>

      {/* AI 数字分身 */}
      <div className="mt-5 border-t border-gray-100 pt-4">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-medium text-gray-400">AI 数字分身</span>
          <span className="text-[11px] text-gray-400">对同事显示为「{profile.ai_twin_display_name}」</span>
        </div>
        <div className="mb-3 flex flex-wrap gap-2">
          {AI_TWIN_STATUSES.map((s) => {
            const active = profile.ai_twin_status === s;
            return (
              <button
                key={s}
                disabled={busy}
                onClick={() => void patchTwin({ ai_twin_status: s })}
                className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${
                  active
                    ? s === "AGENT"
                      ? "bg-indigo-600 text-white"
                      : s === "ASSIST"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-900 text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {AI_TWIN_STATUS_LABEL[s]}
              </button>
            );
          })}
        </div>

        <input
          className="input mb-3 text-sm"
          placeholder="自定义 AI 分身名称（留空则使用默认名）"
          value={nameDraft}
          onChange={(e) => {
            setNameDraft(e.target.value);
            setNameSaved(false);
          }}
          onBlur={saveName}
          maxLength={50}
        />
        {!nameSaved && (
          <button className="mb-3 text-xs text-blue-600 hover:underline" onClick={saveName}>
            保存名称
          </button>
        )}

        <div className="mb-2 text-[11px] font-medium text-gray-400">代理权限（AI 仅在授权范围内代理）</div>
        <div className="space-y-1.5">
          {DELEGATION_PERMISSION_ORDER.map((key) => (
            <label key={key} className="flex cursor-pointer items-center gap-2.5 text-sm text-gray-700">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-gray-300"
                checked={!!profile.ai_permissions[key]}
                disabled={busy}
                onChange={(e) => togglePermission(key, e.target.checked)}
              />
              {DELEGATION_PERMISSION_LABEL[key]}
            </label>
          ))}
        </div>
      </div>
    </section>
  );
}
