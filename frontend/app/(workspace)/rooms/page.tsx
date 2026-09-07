"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, getApiBase, getToken } from "@/lib/api";
import { useAuth } from "@/features/auth/AuthProvider";
import { RoomIcon } from "@/components/icons";
import {
  ROOM_STATUS_LABEL,
  WORK_EVENT_TYPE_LABEL,
  type ChatSource,
  type Employee,
  type KnowledgeDocument,
  type KnowledgeSpace,
  type Room,
  type RoomDocument,
  type RoomMember,
  type RoomStatus,
  type WorkEvent,
  type WorkEventType,
} from "@/lib/types";

const STATUS_STYLE: Record<RoomStatus, string> = {
  PLANNING: "bg-amber-50 text-amber-600",
  ACTIVE: "bg-green-50 text-green-600",
  PAUSED: "bg-gray-100 text-gray-500",
  COMPLETED: "bg-blue-50 text-blue-600",
};

const EVENT_STYLE: Record<WorkEventType, string> = {
  meeting: "bg-blue-50 text-blue-600",
  work_log: "bg-gray-100 text-gray-600",
  customer_feedback: "bg-amber-50 text-amber-600",
  decision: "bg-purple-50 text-purple-600",
  task_update: "bg-green-50 text-green-600",
  document_update: "bg-cyan-50 text-cyan-600",
};

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  status?: string;
  sources?: ChatSource[];
  error?: boolean;
}

export default function RoomsPage() {
  const { currentCompany } = useAuth();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeRoomId, setActiveRoomId] = useState<string | null>(null);

  const [members, setMembers] = useState<RoomMember[]>([]);
  const [roomDocs, setRoomDocs] = useState<RoomDocument[]>([]);
  const [events, setEvents] = useState<WorkEvent[]>([]);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [eventFormOpen, setEventFormOpen] = useState(false);
  const [addMemberOpen, setAddMemberOpen] = useState(false);
  const [addDocOpen, setAddDocOpen] = useState(false);
  const [companyEmployees, setCompanyEmployees] = useState<Employee[]>([]);
  const [companyDocs, setCompanyDocs] = useState<KnowledgeDocument[]>([]);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  const loadRooms = useCallback(async () => {
    if (!currentCompany) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api<Room[]>(`/companies/${currentCompany.id}/rooms`);
      setRooms(data);
      setActiveRoomId((prev) =>
        prev && data.some((r) => r.id === prev) ? prev : (data[0]?.id ?? null)
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载项目列表失败");
    } finally {
      setLoading(false);
    }
  }, [currentCompany]);

  useEffect(() => {
    loadRooms();
  }, [loadRooms]);

  const loadRoomDetail = useCallback(
    async (roomId: string) => {
      if (!currentCompany) return;
      try {
        const [m, d, e] = await Promise.all([
          api<RoomMember[]>(`/companies/${currentCompany.id}/rooms/${roomId}/members`),
          api<RoomDocument[]>(`/companies/${currentCompany.id}/rooms/${roomId}/documents`),
          api<WorkEvent[]>(`/companies/${currentCompany.id}/rooms/${roomId}/events`),
        ]);
        setMembers(m);
        setRoomDocs(d);
        setEvents(e);
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载项目详情失败");
      }
    },
    [currentCompany]
  );

  useEffect(() => {
    setChatMessages([]);
    if (activeRoomId) loadRoomDetail(activeRoomId);
    else {
      setMembers([]);
      setRoomDocs([]);
      setEvents([]);
    }
  }, [activeRoomId, loadRoomDetail]);

  useEffect(() => {
    chatScrollRef.current?.scrollTo({ top: chatScrollRef.current.scrollHeight });
  }, [chatMessages]);

  // 打开弹窗前拉取可选项
  async function openAddMember() {
    try {
      const data = await api<Employee[]>(
        `/companies/${currentCompany!.id}/employees`
      );
      setCompanyEmployees(data);
    } catch {
      /* ignore */
    }
    setAddMemberOpen(true);
  }

  async function openAddDoc() {
    try {
      const spaces = await api<KnowledgeSpace[]>(
        `/companies/${currentCompany!.id}/knowledge/spaces`
      );
      const all: KnowledgeDocument[] = [];
      for (const s of spaces) {
        const docs = await api<KnowledgeDocument[]>(
          `/companies/${currentCompany!.id}/knowledge/spaces/${s.id}/documents`
        );
        all.push(...docs);
      }
      setCompanyDocs(all);
    } catch {
      /* ignore */
    }
    setAddDocOpen(true);
  }

  async function sendChat() {
    const question = chatInput.trim();
    if (!question || streaming || !activeRoomId || !currentCompany) return;
    setChatInput("");
    const history = chatMessages
      .filter((m) => !m.error && m.content)
      .slice(-8)
      .map((m) => ({ role: m.role, content: m.content }));
    setChatMessages((prev) => [
      ...prev,
      { role: "user", content: question },
      { role: "assistant", content: "", status: "思考中…" },
    ]);
    setStreaming(true);
    try {
      const resp = await fetch(
        `${getApiBase()}/companies/${currentCompany.id}/rooms/${activeRoomId}/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${getToken() ?? ""}`,
          },
          body: JSON.stringify({ message: question, history }),
        }
      );
      if (!resp.ok || !resp.body) throw new Error(`请求失败（${resp.status}）`);
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
          let event: { type: string; content?: string; message?: string; sources?: ChatSource[] };
          try {
            event = JSON.parse(line.slice(6));
          } catch {
            continue;
          }
          setChatMessages((prev) => {
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
    } catch (err) {
      setChatMessages((prev) => {
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
      setChatMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last && last.role === "assistant") last.status = undefined;
        return next;
      });
      setStreaming(false);
    }
  }

  if (!currentCompany) return null;
  const activeRoom = rooms.find((r) => r.id === activeRoomId) ?? null;

  return (
    <div className="mx-auto flex h-full max-w-7xl flex-col p-6">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">项目工作空间</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            围绕项目的协作空间：成员、知识、工作事件与 AI 助手。
          </p>
        </div>
        <button className="btn-primary" onClick={() => setCreateOpen(true)}>
          新建项目
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 px-4 py-2.5 text-sm text-red-600">{error}</div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-6 gap-4">
        {/* 左：项目列表 */}
        <div className="card col-span-1 overflow-y-auto p-3">
          {loading ? (
            <div className="py-10 text-center text-sm text-gray-400">加载中…</div>
          ) : rooms.length === 0 ? (
            <div className="px-2 py-8 text-center text-xs leading-relaxed text-gray-400">
              还没有项目
              <br />
              点击右上角创建
            </div>
          ) : (
            rooms.map((room) => (
              <button
                key={room.id}
                className={`mb-1 flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left transition ${
                  room.id === activeRoomId ? "bg-blue-50" : "hover:bg-gray-50"
                }`}
                onClick={() => setActiveRoomId(room.id)}
              >
                <span
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                    room.id === activeRoomId ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-500"
                  }`}
                >
                  <RoomIcon width={15} height={15} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-gray-900">{room.name}</span>
                  <span className="block text-xs text-gray-400">
                    {room.member_count} 成员 · {room.event_count} 事件
                  </span>
                </span>
              </button>
            ))
          )}
        </div>

        {/* 中：项目详情（成员/文档/事件/Timeline） */}
        <div className="col-span-3 grid min-h-0 grid-rows-[auto_1fr] gap-4">
          {!activeRoom ? (
            <div className="card flex items-center justify-center text-sm text-gray-400">
              选择左侧项目查看详情
            </div>
          ) : (
            <>
              <div className="card p-4">
                <div className="flex items-start justify-between">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h2 className="truncate text-base font-semibold tracking-tight">{activeRoom.name}</h2>
                      <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_STYLE[activeRoom.status]}`}>
                        {ROOM_STATUS_LABEL[activeRoom.status]}
                      </span>
                    </div>
                    {activeRoom.description && (
                      <p className="mt-1 text-xs leading-relaxed text-gray-500">{activeRoom.description}</p>
                    )}
                  </div>
                  <button
                    className="btn-danger shrink-0 px-2.5 py-1 text-xs"
                    onClick={async () => {
                      if (!window.confirm(`确定删除项目「${activeRoom.name}」？其成员、文档关联与事件将一并删除。`)) return;
                      await api(`/companies/${currentCompany.id}/rooms/${activeRoom.id}`, { method: "DELETE" });
                      setActiveRoomId(null);
                      await loadRooms();
                    }}
                  >
                    删除项目
                  </button>
                </div>

                {/* 成员与关联文档 */}
                <div className="mt-4 grid grid-cols-2 gap-4">
                  <div>
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-xs font-medium text-gray-400">项目成员（{members.length}）</span>
                      <button className="text-xs text-blue-600 hover:underline" onClick={openAddMember}>
                        + 添加
                      </button>
                    </div>
                    <div className="space-y-1">
                      {members.map((m) => (
                        <div key={m.id} className="group flex items-center justify-between rounded-lg px-2 py-1.5 hover:bg-gray-50">
                          <div className="min-w-0 text-sm">
                            <span className="font-medium text-gray-900">{m.user_name}</span>
                            <span className="ml-1.5 text-xs text-gray-400">
                              {m.department_name ?? ""}
                              {m.role === "OWNER" ? " · 负责人" : ""}
                            </span>
                          </div>
                          {m.role !== "OWNER" && (
                            <button
                              className="hidden text-xs text-gray-300 hover:text-red-500 group-hover:block"
                              onClick={async () => {
                                await api(
                                  `/companies/${currentCompany.id}/rooms/${activeRoom.id}/members/${m.employee_id}`,
                                  { method: "DELETE" }
                                );
                                await Promise.all([loadRoomDetail(activeRoom.id), loadRooms()]);
                              }}
                            >
                              移除
                            </button>
                          )}
                        </div>
                      ))}
                      {members.length === 0 && <div className="px-2 text-xs text-gray-300">暂无成员</div>}
                    </div>
                  </div>

                  <div>
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-xs font-medium text-gray-400">关联文档（{roomDocs.length}）</span>
                      <button className="text-xs text-blue-600 hover:underline" onClick={openAddDoc}>
                        + 关联
                      </button>
                    </div>
                    <div className="space-y-1">
                      {roomDocs.map((d) => (
                        <div key={d.id} className="group flex items-center justify-between rounded-lg px-2 py-1.5 hover:bg-gray-50">
                          <div className="min-w-0 text-sm">
                            <span className="truncate font-medium text-gray-900">{d.document_name}</span>
                            <span className="ml-1.5 text-xs text-gray-400">{d.chunk_count ?? 0} 知识块</span>
                          </div>
                          <button
                            className="hidden text-xs text-gray-300 hover:text-red-500 group-hover:block"
                            onClick={async () => {
                              await api(
                                `/companies/${currentCompany.id}/rooms/${activeRoom.id}/documents/${d.document_id}`,
                                { method: "DELETE" }
                              );
                              await loadRoomDetail(activeRoom.id);
                            }}
                          >
                            移除
                          </button>
                        </div>
                      ))}
                      {roomDocs.length === 0 && <div className="px-2 text-xs text-gray-300">暂无关联文档</div>}
                    </div>
                  </div>
                </div>
              </div>

              {/* Work Event / Timeline */}
              <div className="card flex min-h-0 flex-col p-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-xs font-medium text-gray-400">
                    Work Event · Timeline（{events.length}）
                  </span>
                  <button className="btn-secondary px-2.5 py-1 text-xs" onClick={() => setEventFormOpen(true)}>
                    + 记录事件
                  </button>
                </div>
                <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
                  {events.length === 0 && (
                    <div className="flex h-full items-center justify-center text-xs text-gray-300">
                      暂无事件，点击右上角记录第一条工作事件
                    </div>
                  )}
                  {events.map((e) => (
                    <div key={e.id} className="flex gap-2.5">
                      <div className="flex flex-col items-center pt-1.5">
                        <span className="h-2 w-2 rounded-full bg-blue-500" />
                        <span className="mt-1 w-px flex-1 bg-gray-100" />
                      </div>
                      <div className="min-w-0 flex-1 pb-1">
                        <div className="flex flex-wrap items-center gap-1.5 text-xs">
                          <span className={`rounded px-1.5 py-0.5 font-medium ${EVENT_STYLE[e.type]}`}>
                            {WORK_EVENT_TYPE_LABEL[e.type]}
                          </span>
                          <span className="text-gray-400">
                            {new Date(e.event_date).toLocaleString("zh-CN", {
                              month: "2-digit",
                              day: "2-digit",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                          <span className="text-gray-500">{e.author_name ?? "未知"}</span>
                        </div>
                        <p className="mt-1 text-sm leading-relaxed text-gray-700">{e.content}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        {/* 右：Room AI 对话 */}
        <div className="card col-span-2 flex min-h-0 flex-col">
          <div className="border-b border-gray-100 px-4 py-3">
            <div className="text-sm font-semibold text-gray-900">项目 AI 助手</div>
            <div className="mt-0.5 text-xs text-gray-400">
              {activeRoom ? `已携带「${activeRoom.name}」项目上下文` : "选择项目后开始对话"}
            </div>
          </div>
          <div ref={chatScrollRef} className="min-h-0 flex-1 overflow-y-auto p-4">
            {chatMessages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gray-900 text-white">
                  <RoomIcon width={18} height={18} />
                </div>
                <div className="space-y-1">
                  <div className="text-sm text-gray-500">试试问：</div>
                  {["当前项目情况如何？", "上次会议决定了什么？", "客户目前最关注什么？", "当前有哪些风险？"].map((q) => (
                    <button
                      key={q}
                      className="block w-full rounded-lg border border-gray-100 bg-white px-3 py-1.5 text-xs text-gray-600 transition hover:border-gray-200 hover:bg-gray-50"
                      disabled={!activeRoom || streaming}
                      onClick={() => {
                        setChatInput(q);
                      }}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {chatMessages.map((m, i) =>
                  m.role === "user" ? (
                    <div key={i} className="flex justify-end">
                      <div className="max-w-[85%] rounded-2xl rounded-br-md bg-gray-900 px-3.5 py-2 text-sm text-white">
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
                )}
              </div>
            )}
          </div>
          <div className="border-t border-gray-100 p-3">
            <div className="flex gap-2">
              <input
                className="input"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.nativeEvent.isComposing) {
                    e.preventDefault();
                    sendChat();
                  }
                }}
                placeholder={activeRoom ? "询问项目情况，无需重复项目名…" : "请先选择项目"}
                disabled={!activeRoom || streaming}
              />
              <button className="btn-primary shrink-0 px-3" onClick={sendChat} disabled={streaming || !chatInput.trim()}>
                {streaming ? "…" : "发送"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 新建项目弹窗 */}
      {createOpen && (
        <CreateRoomModal
          onClose={() => setCreateOpen(false)}
          onSubmit={async (data) => {
            await api(`/companies/${currentCompany.id}/rooms`, { method: "POST", body: data });
            setCreateOpen(false);
            await loadRooms();
          }}
        />
      )}

      {/* 记录事件弹窗 */}
      {eventFormOpen && activeRoom && (
        <EventFormModal
          onClose={() => setEventFormOpen(false)}
          onSubmit={async (data) => {
            await api(`/companies/${currentCompany.id}/rooms/${activeRoom.id}/events`, {
              method: "POST",
              body: data,
            });
            setEventFormOpen(false);
            await Promise.all([loadRoomDetail(activeRoom.id), loadRooms()]);
          }}
        />
      )}

      {/* 添加成员弹窗 */}
      {addMemberOpen && activeRoom && (
        <SimpleSelectModal
          title="添加项目成员"
          items={companyEmployees
            .filter((e) => !members.some((m) => m.employee_id === e.id))
            .map((e) => ({
              id: e.id,
              label: `${e.user_name ?? "?"}${e.department_id ? "" : ""}`,
              sub: `${e.position ?? "员工"}${e.user_email ? " · " + e.user_email : ""}`,
            }))}
          emptyText="没有可添加的成员"
          onClose={() => setAddMemberOpen(false)}
          onPick={async (employeeId) => {
            await api(`/companies/${currentCompany.id}/rooms/${activeRoom.id}/members`, {
              method: "POST",
              body: { employee_id: employeeId },
            });
            setAddMemberOpen(false);
            await Promise.all([loadRoomDetail(activeRoom.id), loadRooms()]);
          }}
        />
      )}

      {/* 关联文档弹窗 */}
      {addDocOpen && activeRoom && (
        <SimpleSelectModal
          title="关联知识文档"
          items={companyDocs
            .filter((d) => !roomDocs.some((rd) => rd.document_id === d.id))
            .map((d) => ({
              id: d.id,
              label: d.name,
              sub: `${d.status === "READY" ? "已就绪" : "处理中"} · ${d.chunk_count} 知识块`,
            }))}
          emptyText="企业知识库暂无可关联文档"
          onClose={() => setAddDocOpen(false)}
          onPick={async (documentId) => {
            await api(`/companies/${currentCompany.id}/rooms/${activeRoom.id}/documents`, {
              method: "POST",
              body: { document_id: documentId },
            });
            setAddDocOpen(false);
            await loadRoomDetail(activeRoom.id);
          }}
        />
      )}
    </div>
  );
}

/* ---------------- 弹窗组件 ---------------- */

function CreateRoomModal({
  onClose,
  onSubmit,
}: {
  onClose: () => void;
  onSubmit: (data: { name: string; description: string | null; status: RoomStatus }) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState<RoomStatus>("ACTIVE");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative w-[440px] max-w-[92vw] rounded-xl bg-white p-6 shadow-xl">
        <h3 className="mb-5 text-base font-semibold tracking-tight">新建项目</h3>
        <form
          className="space-y-4"
          onSubmit={async (e) => {
            e.preventDefault();
            setSubmitting(true);
            setError(null);
            try {
              await onSubmit({ name, description: description || null, status });
            } catch (err) {
              setError(err instanceof Error ? err.message : "创建失败");
            } finally {
              setSubmitting(false);
            }
          }}
        >
          <div>
            <label className="label">项目名称</label>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} autoFocus />
          </div>
          <div>
            <label className="label">项目简介</label>
            <textarea className="input min-h-16 resize-y" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div>
            <label className="label">状态</label>
            <select className="input" value={status} onChange={(e) => setStatus(e.target.value as RoomStatus)}>
              {(Object.keys(ROOM_STATUS_LABEL) as RoomStatus[]).map((s) => (
                <option key={s} value={s}>
                  {ROOM_STATUS_LABEL[s]}
                </option>
              ))}
            </select>
          </div>
          {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" className="btn-secondary" onClick={onClose}>
              取消
            </button>
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? "创建中…" : "创建"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function EventFormModal({
  onClose,
  onSubmit,
}: {
  onClose: () => void;
  onSubmit: (data: { type: WorkEventType; content: string }) => Promise<void>;
}) {
  const [type, setType] = useState<WorkEventType>("work_log");
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative w-[480px] max-w-[92vw] rounded-xl bg-white p-6 shadow-xl">
        <h3 className="mb-5 text-base font-semibold tracking-tight">记录工作事件</h3>
        <form
          className="space-y-4"
          onSubmit={async (e) => {
            e.preventDefault();
            setSubmitting(true);
            setError(null);
            try {
              await onSubmit({ type, content });
            } catch (err) {
              setError(err instanceof Error ? err.message : "保存失败");
            } finally {
              setSubmitting(false);
            }
          }}
        >
          <div>
            <label className="label">事件类型</label>
            <select className="input" value={type} onChange={(e) => setType(e.target.value as WorkEventType)}>
              {(Object.keys(WORK_EVENT_TYPE_LABEL) as WorkEventType[]).map((t) => (
                <option key={t} value={t}>
                  {WORK_EVENT_TYPE_LABEL[t]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">事件内容</label>
            <textarea
              className="input min-h-28 resize-y"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="例如：今天与客户沟通，对方希望增加数字人导览，预算控制在50万元以内。"
              required
              autoFocus
            />
          </div>
          {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" className="btn-secondary" onClick={onClose}>
              取消
            </button>
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? "保存中…" : "保存"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function SimpleSelectModal({
  title,
  items,
  emptyText,
  onClose,
  onPick,
}: {
  title: string;
  items: { id: string; label: string; sub?: string }[];
  emptyText: string;
  onClose: () => void;
  onPick: (id: string) => Promise<void>;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative w-[440px] max-w-[92vw] rounded-xl bg-white p-6 shadow-xl">
        <h3 className="mb-4 text-base font-semibold tracking-tight">{title}</h3>
        <div className="max-h-80 space-y-1 overflow-y-auto">
          {items.length === 0 && (
            <div className="py-8 text-center text-sm text-gray-400">{emptyText}</div>
          )}
          {items.map((item) => (
            <button
              key={item.id}
              className="flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left transition hover:bg-gray-50"
              onClick={() => onPick(item.id)}
            >
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-gray-900">{item.label}</span>
                {item.sub && <span className="block truncate text-xs text-gray-400">{item.sub}</span>}
              </span>
              <span className="shrink-0 text-xs text-blue-600">选择</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
