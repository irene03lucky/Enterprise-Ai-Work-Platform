"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, getApiBase, getToken } from "@/lib/api";
import type { ChatSource, ConversationDetail, ModelInfo } from "@/lib/types";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  status?: string;
  sources?: ChatSource[];
  error?: boolean;
  attachment?: string | null;
}

const QUICK_ACTIONS = [
  { label: "查询企业知识", prompt: "帮我查询企业知识库中关于品牌官网的关键信息。" },
  { label: "分析上传文件", prompt: "请分析我上传的文件并给出要点。" },
  { label: "总结当前工作", prompt: "帮我总结本周的工作进展与待办。" },
  { label: "跟进项目动态", prompt: "我参与的项目最近有哪些新进展？" },
];

export function WorkbenchChat({
  companyId,
  conversationId,
  roomId,
  roomName,
  onActivity,
}: {
  companyId: string;
  conversationId?: string | null;
  roomId?: string | null;
  roomName?: string | null;
  onActivity: () => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const loadedConv = useRef<string | null>(null);

  const chatScrollRef = scrollRef;

  // 加载可用模型列表（Model Registry），并恢复用户最近选择（T04.8）
  useEffect(() => {
    fetch(`${getApiBase()}/models`, {
      headers: { Authorization: `Bearer ${getToken() ?? ""}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d?.models?.length) return;
        setModels(d.models);
        const saved = window.localStorage.getItem("eai_selected_model");
        const valid = d.models.find(
          (m: ModelInfo) => m.model_id === saved && m.enabled
        );
        const fallback =
          d.models.find((m: ModelInfo) => m.current) ?? d.models[0];
        setSelectedModel((valid ?? fallback).model_id);
      })
      .catch(() => {});
  }, []);

  // 从侧边栏「历史对话」进入时，加载该会话消息
  useEffect(() => {
    if (!conversationId || loadedConv.current === conversationId) return;
    loadedConv.current = conversationId;
    api<ConversationDetail>(`/companies/${companyId}/conversations/${conversationId}`)
      .then((c) => {
        setMessages(
          c.messages.map((m) => ({ role: m.role, content: m.content }))
        );
      })
      .catch(() => setMessages([]));
  }, [conversationId, companyId]);

  useEffect(() => {
    chatScrollRef.current?.scrollTo({ top: chatScrollRef.current.scrollHeight });
  }, [messages]);

  const sendChat = useCallback(async () => {
    const question = input.trim();
    if ((!question && !file) || streaming) return;
    const attachmentName = file?.name ?? null;
    setInput("");
    setFile(null);
    const history = messages
      .filter((m) => !m.error && m.content)
      .slice(-8)
      .map((m) => ({ role: m.role, content: m.content }));
    const userContent = attachmentName
      ? `[附件：${attachmentName}]\n${question}`
      : question;
    setMessages((prev) => [
      ...prev,
      { role: "user", content: userContent, attachment: attachmentName },
      { role: "assistant", content: "", status: "思考中…" },
    ]);
    setStreaming(true);
    try {
      const resp = await fetch(`${getApiBase()}/companies/${companyId}/workbench/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${getToken() ?? ""}`,
        },
        body: JSON.stringify({
          message: question || (attachmentName ? `请分析附件：${attachmentName}` : ""),
          history,
          conversation_id: conversationId ?? null,
          room_id: roomId ?? null,
          model_id: selectedModel || null,
        }),
      });
      if (!resp.ok || !resp.body) throw new Error(`请求失败（${resp.status}）`);
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let hasActivity = false;
      let createdConvId: string | null = null;
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
            conversation_id?: string;
          };
          try {
            event = JSON.parse(line.slice(6));
          } catch {
            continue;
          }
          if (event.type === "ai_items" || event.type === "task_created") hasActivity = true;
          else if (event.type === "conversation" && event.conversation_id)
            createdConvId = event.conversation_id;
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (!last || last.role !== "assistant") return prev;
            if (event.type === "status" && event.content) last.status = event.content;
            else if (event.type === "token" && event.content) {
              last.status = undefined;
              last.content += event.content;
            } else if (event.type === "sources" && event.sources) last.sources = event.sources;
            else if (event.type === "error" && event.message) {
              last.error = true;
              if (!last.content) last.content = event.message;
            }
            return next;
          });
        }
      }
      if (hasActivity) onActivity();
      // 通知侧边栏「历史对话」刷新（自动新增记录）
      if (createdConvId) window.dispatchEvent(new Event("eai:conversations-updated"));
    } catch (err) {
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last && last.role === "assistant") {
          last.error = true;
          last.status = undefined;
          if (!last.content) last.content = err instanceof Error ? err.message : "请求失败";
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
  }, [input, file, streaming, messages, companyId, conversationId, roomId, selectedModel, onActivity]);

  return (
    <section className="card flex min-h-0 flex-col">
      <div className="border-b border-gray-100 px-5 py-3">
        <div className="flex items-center justify-between gap-2">
          <div className="text-sm font-semibold text-gray-900">AI 助手</div>
          {models.length > 0 && (
            <label className="flex shrink-0 items-center gap-1.5 text-[11px] text-gray-400">
              当前模型
              <select
                className="rounded-lg border border-gray-200 bg-white px-1.5 py-1 text-[11px] text-gray-700 outline-none transition focus:border-gray-300"
                value={selectedModel}
                disabled={streaming}
                onChange={(e) => {
                  setSelectedModel(e.target.value);
                  window.localStorage.setItem("eai_selected_model", e.target.value);
                }}
              >
                {models.map((m) => (
                  <option key={m.model_id} value={m.model_id}>
                    {m.display_name}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        <div className="mt-0.5 text-xs text-gray-400">
          {roomName
            ? `已携带「${roomName}」项目上下文；以下回答均为 AI 助手生成，不属于 AI 分身行为。`
            : "企业知识查询 · 文件上传分析 · 内容生成 · 项目动态查询"}
        </div>
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
            <div className="text-sm text-gray-500">向我提问，或试试：</div>
            <div className="grid w-full grid-cols-2 gap-2">
              {QUICK_ACTIONS.map((q) => (
                <button
                  key={q.label}
                  disabled={streaming}
                  onClick={() => setInput(q.prompt)}
                  className="rounded-lg border border-gray-100 px-3 py-2 text-xs text-gray-600 transition hover:border-gray-200 hover:bg-gray-50"
                >
                  {q.label}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="flex justify-end">
                <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-gray-900 px-3.5 py-2 text-sm text-white">
                  {m.attachment && (
                    <span className="mb-1 flex items-center gap-1.5 rounded-md bg-white/10 px-2 py-1 text-[11px]">
                      <PaperclipIcon /> {m.attachment}
                    </span>
                  )}
                  {m.content}
                </div>
              </div>
            ) : (
              <div key={i} className="text-sm leading-relaxed">
                {m.status ? (
                  <span className="flex items-center gap-2 text-gray-400">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" />
                    {m.status}
                  </span>
                ) : (
                  <div className={`whitespace-pre-wrap ${m.error ? "text-red-600" : "text-gray-800"}`}>
                    {m.content || "…"}
                  </div>
                )}
                {m.sources && m.sources.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {m.sources.map((s, j) => (
                      <span key={j} className="rounded bg-blue-50 px-1.5 py-0.5 text-[11px] text-blue-700">
                        {s.name} {Math.round((s.score ?? 0) * 100)}%
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )
          )
        )}
      </div>

      {file && (
        <div className="flex items-center gap-2 px-3 pt-2">
          <span className="flex items-center gap-1.5 rounded-lg bg-gray-100 px-2.5 py-1.5 text-xs text-gray-700">
            <PaperclipIcon /> {file.name}
            <button
              className="ml-1 text-gray-400 hover:text-red-500"
              onClick={() => setFile(null)}
              aria-label="移除附件"
            >
              ×
            </button>
          </span>
        </div>
      )}

      <div className="border-t border-gray-100 p-3">
        <div className="flex gap-2">
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <button
            type="button"
            className="btn-secondary shrink-0 px-3"
            onClick={() => fileInputRef.current?.click()}
            title="上传文件（AI 可据此分析）"
          >
            <PaperclipIcon />
          </button>
          <input
            className="input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.nativeEvent.isComposing) {
                e.preventDefault();
                void sendChat();
              }
            }}
            placeholder={file ? "补充说明，让 AI 助手分析该文件…" : "询问企业知识、上传文件分析，或查询项目动态…"}
            disabled={streaming}
          />
          <button
            type="button"
            className="btn-primary shrink-0 px-3"
            onClick={() => void sendChat()}
            disabled={streaming || (!input.trim() && !file)}
          >
            {streaming ? "…" : "发送"}
          </button>
        </div>
        <div className="mt-2 flex items-center gap-3 text-[11px] text-gray-400">
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-blue-400" /> 文件上传 / 文件分析
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-gray-300" /> 语音输入（即将开放）
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-gray-300" /> 来源引用
          </span>
        </div>
      </div>
    </section>
  );
}

function PaperclipIcon() {
  return (
    <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21.44 11.05l-9.19 9.19a5 5 0 0 1-7.07-7.07l9.19-9.19a3 3 0 0 1 4.24 4.24l-9.2 9.19a1 1 0 0 1-1.41-1.41l8.49-8.49" />
    </svg>
  );
}
