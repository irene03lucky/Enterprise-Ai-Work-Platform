"use client";

import { useState, type FormEvent } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/features/auth/AuthProvider";
import { BuildingIcon } from "@/components/icons";

/** 无企业空间时的引导面板：创建第一个企业。 */
export default function CreateCompanyPanel() {
  const { refresh } = useAuth();
  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api("/companies", {
        method: "POST",
        body: {
          name,
          industry: industry || null,
          description: description || null,
        },
      });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败，请重试");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center bg-gray-50 p-8">
      <div className="card w-full max-w-md p-8">
        <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-gray-900 text-white">
          <BuildingIcon width={22} height={22} />
        </div>
        <h1 className="text-lg font-semibold tracking-tight">创建你的企业空间</h1>
        <p className="mt-1.5 text-sm leading-relaxed text-gray-500">
          企业空间是组织、知识、协作与 AI 能力的容器。创建后，你将成为该企业的管理员。
        </p>

        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <div>
            <label className="label" htmlFor="company-name">
              企业名称
            </label>
            <input
              id="company-name"
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：示例科技有限公司"
              required
              maxLength={200}
            />
          </div>
          <div>
            <label className="label" htmlFor="company-industry">
              所在行业（可选）
            </label>
            <input
              id="company-industry"
              className="input"
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              placeholder="例如：互联网"
              maxLength={100}
            />
          </div>
          <div>
            <label className="label" htmlFor="company-description">
              企业简介（可选）
            </label>
            <textarea
              id="company-description"
              className="input min-h-20 resize-y"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="一句话介绍你的企业"
            />
          </div>
          {error && (
            <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
              {error}
            </div>
          )}
          <button type="submit" className="btn-primary w-full" disabled={submitting}>
            {submitting ? "创建中…" : "创建企业"}
          </button>
        </form>
      </div>
    </div>
  );
}
