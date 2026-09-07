"use client";

import { useState, type FormEvent } from "react";
import {
  SPACE_VISIBILITY_LABEL,
  type KnowledgeSpace,
  type SpaceVisibility,
} from "@/lib/types";

/* ---------------- 新建/编辑知识空间 ---------------- */

export interface SpaceFormData {
  name: string;
  description: string | null;
  visibility: SpaceVisibility;
}

export function SpaceFormModal({
  mode,
  initial,
  onClose,
  onSubmit,
}: {
  mode: "create" | "edit";
  initial?: KnowledgeSpace;
  onClose: () => void;
  onSubmit: (data: SpaceFormData) => Promise<void>;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [visibility, setVisibility] = useState<SpaceVisibility>(
    initial?.visibility ?? "COMPANY"
  );
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({ name, description: description || null, visibility });
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative w-[460px] max-w-[92vw] rounded-xl bg-white p-6 shadow-xl">
        <h3 className="mb-5 text-base font-semibold tracking-tight">
          {mode === "create" ? "新建知识空间" : "编辑知识空间"}
        </h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">空间名称</label>
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：制度规范"
              required
              maxLength={200}
              autoFocus
            />
          </div>
          <div>
            <label className="label">空间描述</label>
            <textarea
              className="input min-h-16 resize-y"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="这个空间存放什么内容（可选）"
            />
          </div>
          <div>
            <label className="label">权限设置</label>
            <select
              className="input"
              value={visibility}
              onChange={(e) => setVisibility(e.target.value as SpaceVisibility)}
            >
              {(Object.keys(SPACE_VISIBILITY_LABEL) as SpaceVisibility[]).map((v) => (
                <option key={v} value={v}>
                  {SPACE_VISIBILITY_LABEL[v]}
                  {v === "DEPARTMENT" && "（预留）"}
                  {v === "PRIVATE" && "（预留）"}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-gray-400">
              本轮按企业内公开处理，部门/私有权限将在后续版本生效。
            </p>
          </div>
          {error && (
            <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" className="btn-secondary" onClick={onClose}>
              取消
            </button>
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? "保存中…" : mode === "create" ? "创建" : "保存"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
