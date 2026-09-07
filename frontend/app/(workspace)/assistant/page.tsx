"use client";

import { useEffect, useRef, useState } from "react";
import { api, apiUpload, getApiBase, getToken } from "@/lib/api";
import { useAuth } from "@/features/auth/AuthProvider";
import { BuildingIcon, SparklesIcon } from "@/components/icons";
import type { ChatSource, KnowledgeSpace } from "@/lib/types";

/** 按本地时间生成时段问候。 */
function greeting(): string {
  const hour = new Date().getHours();
  if (hour >= 5 && hour < 11) return "早上好";
  if (hour < 13) return "中午好";
  if (hour < 18) return "下午好";
  if (hour < 23) return "晚上好";
  return "夜深了";
}

/** 快捷操作：点击后直接发起对应任务。 */
const QUICK_ACTIONS = [
  { label: "查询企业知识", prompt: "公司差旅的住宿标准是多少？" },
  { label: "跟进项目进展", prompt: "帮我跟进一下当前项目的进展情况" },
  { label: "总结工作内容", prompt: "帮我总结一下本周的工作重点" },
  { label: "分析业务资料", prompt: "帮我分析一下产品业务资料，EAI 产品有哪些核心模块？" },
];

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  status?: string; // 检索中提示（仅本地展示）
  sources?: ChatSource[];
  error?: boolean;
}

export default function AssistantPage() {
  const { user, currentCompany } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 自动滚动到底部
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  function removePendingFile(index: number) {
    setPendingFiles((prev) => prev.filter((_, i) => i !== index));
  }

  /** 上传待发文件到默认知识空间，返回上传结果提示。 */
  async function uploadPendingFiles(): Promise<string | null> {
    if (pendingFiles.length === 0) return null;
    const spaces = await api<KnowledgeSpace[]>(
      `/companies/${currentCompany!.id}/knowledge/spaces`
    );
    if (spaces.length === 0) {
      throw new Error("企业还没有知识空间，请先到 Knowledge 模块创建");
    }
    const space = spaces[0];
    const uploadedNames: string[] = [];
    for (const file of pendingFiles) {
      await apiUpload(
        `/companies/${currentCompany!.id}/knowledge/spaces/${space.id}/documents`,
        file
      );
      uploadedNames.push(file.name);
    }
    setPendingFiles([]);
    return `已上传 ${uploadedNames.length} 个文件到知识空间「${space.name}」（${uploadedNames.join("、")}），系统正在自动解析并向量化，处理完成后即可基于它们提问。`;
  }

  async function send(text?: string) {
    const question = (text ?? input).trim();
    if ((!question && pendingFiles.length === 0) || streaming || !currentCompany) return;

    // 1. 有文件：先上传到企业知识库
    let uploadNote: string | null = null;
    if (pendingFiles.length > 0) {
      try {
        uploadNote = await uploadPendingFiles();
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          {
            role: "user",
            content: `（上传 ${pendingFiles.length} 个文件）${question}`.trim(),
          },
          {
            role: "assistant",
            content: err instanceof Error ? err.message : "文件上传失败，请重试",
            error: true,
          },
        ]);
        return;
      }
    }

    if (!question) {
      // 仅上传文件，无提问：展示上传确认
      setMessages((prev) => [
        ...prev,
        { role: "user", content: "（上传文件）" },
        { role: "assistant", content: uploadNote ?? "" },
      ]);
      return;
    }

    setInput("");
    const history = messages
      .filter((m) => !m.error && m.content)
      .slice(-10)
      .map((m) => ({ role: m.role, content: m.content }));

    setMessages((prev) => [
      ...prev,
      { role: "user", content: question },
      {
        role: "assistant",
        content: uploadNote ? `${uploadNote}\n\n` : "",
        status: "思考中…",
      },
    ]);
    setStreaming(true);

    try {
      const resp = await fetch(
        `${getApiBase()}/companies/${currentCompany.id}/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${getToken() ?? ""}`,
          },
          body: JSON.stringify({ message: question, history }),
        }
      );
      if (!resp.ok || !resp.body) {
        const detail = await resp.text().catch(() => "");
        throw new Error(detail || `请求失败（${resp.status}）`);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          let event: {
            type: string;
            content?: string;
            message?: string;
            sources?: ChatSource[];
          };
          try {
            event = JSON.parse(line.slice(6));
          } catch {
            continue;
          }

          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (!last || last.role !== "assistant") return prev;

            if (event.type === "status" && event.content) {
              last.status = event.content;
            } else if (event.type === "token" && event.content) {
              last.status = undefined;
              last.content += event.content;
            } else if (event.type === "sources" && event.sources) {
              last.sources = event.sources;
            } else if (event.type === "error" && event.message) {
              last.error = true;
              if (!last.content) last.content = event.message;
            }
            return next;
          });
        }
      }
    } catch (err) {
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last && last.role === "assistant") {
          last.error = true;
          last.status = undefined;
          if (!last.content) {
            last.content = err instanceof Error ? err.message : "请求失败，请重试";
          }
        }
        return next;
      });
    } finally {
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last && last.role === "assistant") last.status = undefined;
        return next;
      });
      setStreaming(false);
    }
  }

  const hasMessages = messages.length > 0;

  return (
    <div className="flex h-full flex-col bg-gray-50">
      {/* 消息流 */}
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-8 py-8">
          {!hasMessages && (
            <div className="flex flex-col items-center pt-16">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gray-900 text-white">
                <SparklesIcon width={26} height={26} />
              </div>
              <h1 className="mt-5 text-2xl font-semibold tracking-tight">
                {greeting()}，{user?.name ?? "同事"}
              </h1>
              <p className="mt-2 text-sm text-gray-500">我是你的企业 AI 助手，请问有什么可以帮你？</p>

              <div className="card mt-8 flex items-center gap-3 px-4 py-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-100 text-gray-600">
                  <BuildingIcon width={15} height={15} />
                </div>
                <div className="min-w-0 text-sm">
                  <span className="font-medium text-gray-900">
                    {currentCompany?.name ?? "未选择企业"}
                  </span>
                  <span className="text-gray-400"> · </span>
                  <span className="text-gray-500">
                    {currentCompany?.department_name ?? "暂未分配部门"}
                    {currentCompany?.position ? ` · ${currentCompany.position}` : ""}
                  </span>
                </div>
              </div>

              <div className="mt-6 flex flex-wrap justify-center gap-2">
                {QUICK_ACTIONS.map((action) => (
                  <button
                    key={action.label}
                    className="rounded-full border border-gray-200 bg-white px-3.5 py-1.5 text-xs text-gray-600 transition hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900"
                    onClick={() => send(action.prompt)}
                    disabled={streaming}
                  >
                    {action.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {hasMessages && (
            <div className="space-y-6">
              {messages.map((message, index) =>
                message.role === "user" ? (
                  <div key={index} className="flex justify-end">
                    <div className="max-w-[80%] rounded-2xl rounded-br-md bg-gray-900 px-4 py-2.5 text-sm leading-relaxed text-white">
                      {message.content}
                    </div>
                  </div>
                ) : (
                  <div key={index} className="flex gap-3">
                    <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gray-900 text-white">
                      <SparklesIcon width={14} height={14} />
                    </div>
                    <div className="min-w-0 flex-1">
                      {message.status ? (
                        <div className="flex items-center gap-2 text-sm text-gray-400">
                          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" />
                          {message.status}
                        </div>
                      ) : (
                        <div
                          className={`whitespace-pre-wrap text-sm leading-relaxed ${
                            message.error ? "text-red-600" : "text-gray-800"
                          }`}
                        >
                          {message.content || "…"}
                        </div>
                      )}

                      {/* 引用来源 */}
                      {message.sources && message.sources.length > 0 && (
                        <div className="mt-3 border-t border-dashed border-gray-200 pt-2.5">
                          <div className="mb-1.5 text-[11px] font-medium text-gray-400">
                            参考来源
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            {message.sources.map((source, i) => (
                              <span
                                key={`${source.document_id}-${i}`}
                                className="inline-flex items-center gap-1 rounded-md bg-blue-50 px-2 py-1 text-[11px] text-blue-700"
                                title={`相关度 ${Math.round((source.score ?? 0) * 100)}%`}
                              >
                                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                                  <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                                  <path d="M14 2v6h6" />
                                </svg>
                                {source.name}
                                <span className="text-blue-400">
                                  {Math.round((source.score ?? 0) * 100)}%
                                </span>
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )
              )}
            </div>
          )}
        </div>
      </div>

      {/* 输入区 */}
      <div className="shrink-0 bg-gradient-to-t from-gray-50 via-gray-50 to-transparent pb-6 pt-2">
        <div className="mx-auto w-full max-w-3xl px-8">
          <div className="card p-2 shadow-sm transition focus-within:border-gray-300 focus-within:shadow-md">
            {/* 待上传文件 */}
            {pendingFiles.length > 0 && (
              <div className="flex flex-wrap gap-2 px-2 pt-2">
                {pendingFiles.map((file, i) => (
                  <span
                    key={`${file.name}-${i}`}
                    className="inline-flex max-w-xs items-center gap-1.5 rounded-lg bg-gray-100 px-2.5 py-1 text-xs text-gray-600"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
                      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                      <path d="M14 2v6h6" />
                    </svg>
                    <span className="truncate">{file.name}</span>
                    <span className="shrink-0 text-gray-400">
                      {(file.size / 1024).toFixed(0)}KB
                    </span>
                    <button
                      className="shrink-0 rounded p-0.5 text-gray-400 hover:bg-gray-200 hover:text-gray-600"
                      onClick={() => removePendingFile(i)}
                      title="移除文件"
                    >
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                        <path d="M18 6L6 18M6 6l12 12" />
                      </svg>
                    </button>
                  </span>
                ))}
              </div>
            )}

            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  send();
                }
              }}
              placeholder="描述你的工作需求，或上传文件让 AI 理解企业资料"
              rows={2}
              className="w-full resize-none bg-transparent px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none"
              disabled={streaming}
            />

            {/* 底部工具行 */}
            <div className="flex items-center justify-between px-2 pb-1">
              <div className="flex items-center gap-1">
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  hidden
                  accept=".pdf,.docx,.pptx,.txt,.md"
                  onChange={(e) => {
                    const selected = Array.from(e.target.files ?? []);
                    if (selected.length > 0) {
                      setPendingFiles((prev) => [...prev, ...selected]);
                    }
                    e.target.value = "";
                  }}
                />
                <button
                  className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-gray-500 transition hover:bg-gray-100 hover:text-gray-700 disabled:opacity-40"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={streaming}
                  title="上传文件到企业知识库（支持 PDF / DOCX / PPTX / TXT / MD），自动解析向量化"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
                  </svg>
                  上传文件
                </button>
                <span className="hidden text-[11px] text-gray-300 sm:inline">
                  PDF / Word / PPT / TXT / MD
                </span>
              </div>
              <button
                className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-900 text-white transition hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-30"
                onClick={() => send()}
                disabled={streaming || (!input.trim() && pendingFiles.length === 0)}
                title="发送（Enter）"
              >
                {streaming ? (
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                ) : (
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M22 2L11 13" />
                    <path d="M22 2l-7 20-4-9-9-4 20-7z" />
                  </svg>
                )}
              </button>
            </div>
          </div>
          <div className="mt-2 text-center text-[11px] text-gray-400">
            回答基于企业知识库检索 · 上传文件自动归档为知识资产 · Enter 发送 · Shift+Enter 换行
          </div>
        </div>
      </div>
    </div>
  );
}
