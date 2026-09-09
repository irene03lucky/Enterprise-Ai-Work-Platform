"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api";
import { SparklesIcon } from "@/components/icons";

type Mode = "login" | "register";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "register") {
        await api("/auth/register", {
          method: "POST",
          body: { name, email, password },
        });
      }
      const resp = await api<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: { email, password },
      });
      setToken(resp.access_token);
      router.replace("/workbench");
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败，请重试");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen">
      {/* 品牌区 */}
      <div className="relative hidden w-1/2 flex-col justify-between bg-gray-900 p-12 text-white lg:flex">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/10">
            <SparklesIcon width={20} height={20} />
          </div>
          <span className="text-lg font-semibold tracking-tight">EAI</span>
        </div>
        <div>
          <h1 className="text-3xl font-bold leading-snug tracking-tight">
            Enterprise AI Work Platform
          </h1>
          <p className="mt-4 text-base leading-relaxed text-gray-400">
            在企业已有办公体系之上，建立一层 AI 工作层。
            <br />
            让 AI 理解你的组织、知识、项目与工作过程。
          </p>
          <div className="mt-8 flex gap-3">
            {["AI Assistant", "Knowledge", "Rooms", "Agents"].map((tag) => (
              <span
                key={tag}
                className="rounded-full border border-white/15 px-3 py-1 text-xs text-gray-300"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
        <p className="text-xs text-gray-500">© 2026 EAI · 面向企业内部的 AI 工作平台</p>
      </div>

      {/* 表单区 */}
      <div className="flex w-full items-center justify-center bg-white lg:w-1/2">
        <div className="w-full max-w-sm px-6">
          <div className="mb-8 lg:hidden">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-900 text-white">
                <SparklesIcon width={16} height={16} />
              </div>
              <span className="text-lg font-semibold tracking-tight">EAI</span>
            </div>
          </div>

          <h2 className="text-xl font-semibold tracking-tight">
            {mode === "login" ? "欢迎回来" : "创建账号"}
          </h2>
          <p className="mt-1.5 text-sm text-gray-500">
            {mode === "login"
              ? "登录你的企业 AI 工作平台"
              : "注册一个平台账号，随后可创建或加入企业"}
          </p>

          <form onSubmit={onSubmit} className="mt-8 space-y-4">
            {mode === "register" && (
              <div>
                <label className="label" htmlFor="name">
                  姓名
                </label>
                <input
                  id="name"
                  className="input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="你的姓名"
                  required
                  minLength={1}
                  maxLength={100}
                />
              </div>
            )}
            <div>
              <label className="label" htmlFor="email">
                邮箱
              </label>
              <input
                id="email"
                type="email"
                className="input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                required
              />
            </div>
            <div>
              <label className="label" htmlFor="password">
                密码
              </label>
              <input
                id="password"
                type="password"
                className="input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="至少 6 位"
                required
                minLength={6}
              />
            </div>

            {error && (
              <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
                {error}
              </div>
            )}

            <button type="submit" className="btn-primary w-full" disabled={submitting}>
              {submitting ? "请稍候…" : mode === "login" ? "登录" : "注册并登录"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-gray-500">
            {mode === "login" ? "还没有账号？" : "已有账号？"}
            <button
              type="button"
              className="ml-1 font-medium text-blue-600 hover:underline"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError(null);
              }}
            >
              {mode === "login" ? "注册一个" : "直接登录"}
            </button>
          </p>

          <div className="mt-10 rounded-lg border border-dashed border-gray-200 bg-gray-50 p-3 text-xs leading-relaxed text-gray-500">
            演示环境已内置账号：admin@eai.dev / admin123（管理员）；
            zhangsan@eai.dev 等 / demo1234（员工）。
          </div>
        </div>
      </div>
    </div>
  );
}
