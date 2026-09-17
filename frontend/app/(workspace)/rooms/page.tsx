"use client";

import { useCallback, useEffect, useRef, useState } from "react";
export const dynamic = "force-dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/features/auth/AuthProvider";
import {
  ROOM_STAGE_LABEL,
  ROOM_STAGE_ORDER,
  ROOM_STATUS_LABEL,
  TASK_STATUS_LABEL,
  WORK_EVENT_TYPE_LABEL,
  type Employee,
  type KnowledgeDocument,
  type KnowledgeSpace,
  type Room,
  type RoomChatMessage,
  type RoomDocument,
  type RoomMember,
  type RoomStatus,
  type Task,
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

/* 成员真人状态标签（项目群公开协作信息） */
const MEMBER_STATUS_LABEL: Record<string, string> = {
  ONLINE: "在线",
  IN_MEETING: "会议中",
  CUSTOMER_VISIT: "客户拜访",
  BUSINESS_TRIP: "出差",
  LEAVE: "请假",
  OFFLINE: "离线",
  ACTIVE: "在线",
};

/* 成员状态圆点：让「谁在忙什么」在项目群里一眼可见 */
const MEMBER_STATUS_DOT: Record<string, string> = {
  ONLINE: "bg-green-500",
  ACTIVE: "bg-green-500",
  IN_MEETING: "bg-amber-500",
  CUSTOMER_VISIT: "bg-blue-500",
  BUSINESS_TRIP: "bg-purple-500",
  LEAVE: "bg-gray-400",
  OFFLINE: "bg-gray-300",
};

const TASK_STATUS_STYLE: Record<string, string> = {
  TODO: "bg-gray-100 text-gray-500",
  IN_PROGRESS: "bg-blue-50 text-blue-600",
  DONE: "bg-green-50 text-green-600",
};

export default function RoomsPage() {
  const { currentCompany } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeRoomId, setActiveRoomId] = useState<string | null>(null);

  const [members, setMembers] = useState<RoomMember[]>([]);
  const [roomDocs, setRoomDocs] = useState<RoomDocument[]>([]);
  const [events, setEvents] = useState<WorkEvent[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [eventFormOpen, setEventFormOpen] = useState(false);
  const [addMemberOpen, setAddMemberOpen] = useState(false);
  const [addDocOpen, setAddDocOpen] = useState(false);
  const [companyEmployees, setCompanyEmployees] = useState<Employee[]>([]);
  const [companyDocs, setCompanyDocs] = useState<KnowledgeDocument[]>([]);

  // 项目聊天 / 项目任务（T04.7）
  const [tab, setTab] = useState<"chat" | "timeline">("chat");
  const [chat, setChat] = useState<RoomChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatSending, setChatSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [roomTasks, setRoomTasks] = useState<Task[]>([]);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // 侧边栏「项目」点击 ?room= 进入；?new=1 打开新建
  useEffect(() => {
    const r = searchParams.get("room");
    if (r && rooms.some((x) => x.id === r)) setActiveRoomId(r);
  }, [searchParams, rooms]);

  useEffect(() => {
    if (searchParams.get("new") === "1") setCreateOpen(true);
  }, [searchParams]);

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
        const [m, d, e, c, t] = await Promise.all([
          api<RoomMember[]>(`/companies/${currentCompany.id}/rooms/${roomId}/members`),
          api<RoomDocument[]>(`/companies/${currentCompany.id}/rooms/${roomId}/documents`),
          api<WorkEvent[]>(`/companies/${currentCompany.id}/rooms/${roomId}/events`),
          api<RoomChatMessage[]>(`/companies/${currentCompany.id}/rooms/${roomId}/messages`),
          api<Task[]>(`/companies/${currentCompany.id}/rooms/${roomId}/tasks`),
        ]);
        setMembers(m);
        setRoomDocs(d);
        setEvents(e);
        setChat(c);
        setRoomTasks(t);
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载项目详情失败");
      }
    },
    [currentCompany]
  );

  useEffect(() => {
    if (activeRoomId) loadRoomDetail(activeRoomId);
    else {
      setMembers([]);
      setRoomDocs([]);
      setEvents([]);
      setChat([]);
      setRoomTasks([]);
    }
  }, [activeRoomId, loadRoomDetail]);

  // 聊天自动滚动到底部
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ block: "end" });
  }, [chat]);

  async function sendChatMessage() {
    if (!currentCompany || !activeRoom) return;
    const content = chatInput.trim();
    if (!content || chatSending) return;
    setChatSending(true);
    setChatError(null);
    setChatInput("");
    try {
      const created = await api<RoomChatMessage[]>(
        `/companies/${currentCompany.id}/rooms/${activeRoom.id}/messages`,
        { method: "POST", body: { content } }
      );
      setChat((prev) => [...prev, ...created]);
      // 接管可能生成任务 / 项目 Update，静默刷新
      void loadRoomDetail(activeRoom.id);
      void loadRooms();
    } catch (err) {
      /* 保留输入由用户重试，并把失败原因显示出来（此前是静默吞掉） */
      setChatInput(content);
      setChatError(err instanceof Error ? `发送失败：${err.message}` : "发送失败，请重试");
    } finally {
      setChatSending(false);
    }
  }

  async function openAddMember() {
    try {
      const data = await api<Employee[]>(`/companies/${currentCompany!.id}/employees`);
      setCompanyEmployees(data);
    } catch {
      /* ignore */
    }
    setAddMemberOpen(true);
  }

  async function openAddDoc() {
    try {
      const spaces = await api<KnowledgeSpace[]>(`/companies/${currentCompany!.id}/knowledge/spaces`);
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

  async function changeStage(room: Room, stage: string) {
    if (!currentCompany) return;
    await api(`/companies/${currentCompany.id}/rooms/${room.id}`, {
      method: "PATCH",
      body: { stage },
    });
    await Promise.all([loadRooms(), loadRoomDetail(room.id)]);
  }

  if (!currentCompany) return null;
  const activeRoom = rooms.find((r) => r.id === activeRoomId) ?? null;
  const isMember =
    !!activeRoom && members.some((m) => m.employee_id === currentCompany.employee_id);

  // 从当前 Room 进入 Work Center（携带项目上下文）
  function askAI() {
    if (!activeRoom) return;
    router.push(`/workbench?room=${activeRoom.id}`);
  }

  return (
    <div className="mx-auto flex h-full max-w-[1500px] flex-col p-6">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">项目工作空间</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            围绕项目的「事实与上下文空间」：阶段、成员、文档、工作事件与 Timeline。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-secondary" onClick={askAI} disabled={!activeRoom}>
            问 AI
          </button>
          <button className="btn-primary" onClick={() => setCreateOpen(true)}>
            新建项目
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 px-4 py-2.5 text-sm text-red-600">{error}</div>
      )}

      {!activeRoom ? (
        <div className="card flex flex-1 items-center justify-center text-sm text-gray-400">
          {loading ? "加载中…" : "在左侧选择或新建一个项目"}
        </div>
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-12 gap-4">
          {/* 左：项目基本信息 / 成员 / 文档 / 风险进展（按权限） */}
          <div className="col-span-7 min-h-0 space-y-4 overflow-y-auto pr-1">
            {/* 项目头卡：名称 / 简介 / 状态 / 阶段 */}
            <div className="card p-4">
              <div className="flex items-start justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h2 className="truncate text-base font-semibold tracking-tight">
                      {activeRoom.name}
                    </h2>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_STYLE[activeRoom.status]}`}
                    >
                      {ROOM_STATUS_LABEL[activeRoom.status]}
                    </span>
                  </div>
                  {activeRoom.description && (
                    <p className="mt-1 text-xs leading-relaxed text-gray-500">
                      {activeRoom.description}
                    </p>
                  )}
                </div>
                {isMember && (
                  <button
                    className="btn-danger shrink-0 px-2.5 py-1 text-xs"
                    onClick={async () => {
                      if (
                        !window.confirm(
                          `确定删除项目「${activeRoom.name}」？其成员、文档关联与事件将一并删除。`
                        )
                      )
                        return;
                      await api(`/companies/${currentCompany.id}/rooms/${activeRoom.id}`, {
                        method: "DELETE",
                      });
                      setActiveRoomId(null);
                      await loadRooms();
                    }}
                  >
                    删除项目
                  </button>
                )}
              </div>

              {/* 项目阶段流水线 */}
              <div className="mt-4">
                <div className="mb-2 text-xs font-medium text-gray-400">项目阶段</div>
                <div className="flex items-center">
                  {ROOM_STAGE_ORDER.map((stage, i) => {
                    const idx = ROOM_STAGE_ORDER.indexOf(activeRoom.stage);
                    const reached = i <= idx;
                    const isCurrent = stage === activeRoom.stage;
                    const canClick = isMember && stage !== activeRoom.stage;
                    return (
                      <div key={stage} className="flex flex-1 items-center last:flex-none">
                        <button
                          disabled={!canClick}
                          onClick={() => changeStage(activeRoom, stage)}
                          className={`flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-semibold transition ${
                            isCurrent
                              ? "bg-gray-900 text-white"
                              : reached
                              ? "bg-gray-700 text-white"
                              : "bg-gray-100 text-gray-400"
                          } ${canClick ? "cursor-pointer hover:ring-2 hover:ring-gray-300" : "cursor-default"}`}
                          title={ROOM_STAGE_LABEL[stage]}
                        >
                          {i + 1}
                        </button>
                        {i < ROOM_STAGE_ORDER.length - 1 && (
                          <span
                            className={`mx-1 h-0.5 flex-1 ${i < idx ? "bg-gray-700" : "bg-gray-100"}`}
                          />
                        )}
                      </div>
                    );
                  })}
                </div>
                <div className="mt-1.5 text-xs text-gray-500">
                  当前阶段：{ROOM_STAGE_LABEL[activeRoom.stage]}（
                  {activeRoom.access_level === "related"
                    ? "你为相关部门，可见大阶段与公开里程碑"
                    : "项目成员 / 管理层，可见详细进展"}
                  ）
                </div>
              </div>
            </div>

            {/* 成员与关联文档 */}
            <div className="card p-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-medium text-gray-400">
                      项目成员（{members.length}）
                    </span>
                    {isMember && (
                      <button
                        className="text-xs text-blue-600 hover:underline"
                        onClick={openAddMember}
                      >
                        + 添加
                      </button>
                    )}
                  </div>
                  <div className="space-y-1">
                    {members.map((m) => (
                      <div
                        key={m.id}
                        className="group flex items-center justify-between rounded-lg px-2 py-1.5 hover:bg-gray-50"
                      >
                        <div className="min-w-0 text-sm">
                          <span className="font-medium text-gray-900">{m.user_name}</span>
                          <span className="ml-1.5 text-xs text-gray-400">
                            {m.department_name ?? ""}
                            {m.role === "OWNER" ? " · 负责人" : ""}
                          </span>
                          <div className="mt-0.5 flex flex-wrap items-center gap-1">
                            {m.human_status && (
                              <span className="flex items-center gap-1 rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500">
                                <span
                                  className={`h-1.5 w-1.5 rounded-full ${
                                    MEMBER_STATUS_DOT[m.human_status] ?? "bg-gray-300"
                                  }`}
                                />
                                {MEMBER_STATUS_LABEL[m.human_status] ?? m.human_status}
                              </span>
                            )}
                            {m.ai_twin_status === "AGENT" && (
                              <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-medium text-indigo-600">
                                {m.ai_twin_display_name ?? "AI"} 已接管
                              </span>
                            )}
                          </div>
                        </div>
                        {isMember && m.role !== "OWNER" && (
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
                    {members.length === 0 && (
                      <div className="px-2 text-xs text-gray-300">暂无成员</div>
                    )}
                  </div>
                </div>

                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-medium text-gray-400">
                      关联文档（{roomDocs.length}）
                    </span>
                    {isMember && (
                      <button
                        className="text-xs text-blue-600 hover:underline"
                        onClick={openAddDoc}
                      >
                        + 关联
                      </button>
                    )}
                  </div>
                  <div className="space-y-1">
                    {roomDocs.map((d) => (
                      <div
                        key={d.id}
                        className="group flex items-center justify-between rounded-lg px-2 py-1.5 hover:bg-gray-50"
                      >
                        <div className="min-w-0 text-sm">
                          <span className="truncate font-medium text-gray-900">{d.document_name}</span>
                          <span className="ml-1.5 text-xs text-gray-400">
                            {d.chunk_count ?? 0} 知识块
                          </span>
                        </div>
                        {isMember && (
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
                        )}
                      </div>
                    ))}
                    {roomDocs.length === 0 && (
                      <div className="px-2 text-xs text-gray-300">暂无关联文档</div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* 风险 / 详细进展（按权限） */}
            <div className="card p-4">
              <div className="mb-2 text-xs font-medium text-gray-400">风险 / 详细进展（按权限）</div>
              {isMember ? (
                <div className="space-y-2 text-sm text-gray-700">
                  <div className="rounded-lg bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-700">
                    你为项目成员 / 管理层：可见详细进展、风险、Work Event 与内部跟进信息。
                  </div>
                  <div className="text-gray-500">
                    当前 {events.filter((e) => e.visibility === "INTERNAL").length} 条内部事件、
                    {events.filter((e) => e.type === "decision").length} 条决策记录。如需记录风险或进展，
                    可在右侧 Timeline 点击「+ 记录事件」。
                  </div>
                </div>
              ) : (
                <div className="rounded-lg bg-gray-50 px-3 py-2 text-xs leading-relaxed text-gray-500">
                  你为相关部门，仅可见项目大阶段与公开里程碑；详细进展与风险仅向项目成员 / 管理层开放。
                </div>
              )}
            </div>

            {/* 项目任务（状态公开；执行在 Work Center，完成后自动同步 Timeline） */}
            <div className="card p-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-xs font-medium text-gray-400">
                  项目任务（{roomTasks.length}）
                </span>
                <span className="text-[11px] text-gray-300">
                  在 Work Center 中执行，完成后自动同步 Timeline
                </span>
              </div>
              <div className="space-y-1">
                {roomTasks.length === 0 && (
                  <div className="px-2 text-xs text-gray-300">暂无任务</div>
                )}
                {roomTasks.map((t) => (
                  <div
                    key={t.id}
                    className="flex items-center justify-between rounded-lg px-2 py-1.5 hover:bg-gray-50"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm text-gray-800">{t.title}</div>
                      <div className="text-[11px] text-gray-400">
                        {t.assignee_name ?? "未分配"}
                        {t.source === "AI_TWIN" ? " · 来自 AI 分身" : ""}
                      </div>
                    </div>
                    <span
                      className={`shrink-0 rounded px-1.5 py-0.5 text-[11px] font-medium ${
                        TASK_STATUS_STYLE[t.status] ?? "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {TASK_STATUS_LABEL[t.status]}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* 右：项目聊天 / Work Event · Timeline */}
          <div className="card col-span-5 flex min-h-0 flex-col p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex gap-1">
              <button
                className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                  tab === "chat" ? "bg-gray-900 text-white" : "text-gray-500 hover:bg-gray-100"
                }`}
                onClick={() => setTab("chat")}
              >
                项目聊天
              </button>
              <button
                className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
                  tab === "timeline"
                    ? "bg-gray-900 text-white"
                    : "text-gray-500 hover:bg-gray-100"
                }`}
                onClick={() => setTab("timeline")}
              >
                Work Event · Timeline（{events.length}）
              </button>
            </div>
            {tab === "timeline" && isMember && (
              <button
                className="btn-secondary px-2.5 py-1 text-xs"
                onClick={() => setEventFormOpen(true)}
              >
                + 记录事件
              </button>
            )}
          </div>
          {tab === "chat" ? (
            <>
              {/* 项目群成员状态条：有谁、什么状态、谁开了 AI 代理，一眼可见 */}
              <div className="mb-2 flex flex-wrap items-center gap-1.5 border-b border-gray-100 pb-2">
                {members.length === 0 ? (
                  <span className="text-[11px] text-gray-300">暂无成员</span>
                ) : (
                  members.map((m) => (
                    <span
                      key={m.id}
                      className="flex items-center gap-1 rounded-full bg-gray-50 px-2 py-0.5 text-[11px]"
                    >
                      <span
                        className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                          MEMBER_STATUS_DOT[m.human_status ?? ""] ?? "bg-gray-300"
                        }`}
                      />
                      <span className="font-medium text-gray-700">{m.user_name ?? "成员"}</span>
                      <span className="text-gray-400">
                        {MEMBER_STATUS_LABEL[m.human_status ?? ""] ?? "状态未知"}
                      </span>
                      {m.ai_twin_status === "AGENT" && (
                        <span className="rounded bg-indigo-50 px-1 text-[10px] font-medium text-indigo-600">
                          AI 代理
                        </span>
                      )}
                    </span>
                  ))
                )}
              </div>
              <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto pr-1">
                {chat.length === 0 && (
                  <div className="flex h-full items-center justify-center text-xs text-gray-300">
                    暂无消息，发起第一条项目沟通
                  </div>
                )}
                {chat.map((m) =>
                  m.sender_kind === "SYSTEM" ? (
                    <div
                      key={m.id}
                      className="py-0.5 text-center text-[11px] text-gray-400"
                    >
                      {m.content}
                    </div>
                  ) : (
                    <div
                      key={m.id}
                      className={`rounded-lg border p-2.5 ${
                        m.sender_kind === "AI"
                          ? "border-indigo-100 bg-indigo-50/50"
                          : "border-gray-100 bg-white"
                      }`}
                    >
                      <div className="mb-1 flex items-center gap-1.5 text-[11px]">
                        <span className="font-medium text-gray-700">
                          {m.sender_name ?? "成员"}
                        </span>
                        {m.sender_kind === "AI" && (
                          <span className="rounded bg-indigo-100 px-1 py-0.5 text-[10px] font-medium text-indigo-600">
                            AI 分身
                          </span>
                        )}
                        <span className="text-gray-300">
                          {new Date(m.created_at).toLocaleTimeString("zh-CN", {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>
                      <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
                        {m.content}
                      </p>
                    </div>
                  )
                )}
                <div ref={chatEndRef} />
              </div>
              {(chatError || chatSending) && (
                <div
                  className={`mt-2 rounded-lg px-2.5 py-1.5 text-xs ${
                    chatError ? "bg-red-50 text-red-600" : "bg-indigo-50 text-indigo-600"
                  }`}
                >
                  {chatError ?? "已发送，AI 分身正在生成回复…"}
                </div>
              )}
              {isMember && (
                <div className="mt-2 flex gap-2">
                  <input
                    className="input flex-1"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.nativeEvent.isComposing) {
                        e.preventDefault();
                        void sendChatMessage();
                      }
                    }}
                    placeholder="讨论项目进展；被点名的成员若开启分身代理，其 AI 会接管回复"
                    disabled={chatSending}
                    maxLength={4000}
                  />
                  <button
                    className="btn-primary shrink-0 px-3"
                    disabled={chatSending || !chatInput.trim()}
                    onClick={() => void sendChatMessage()}
                  >
                    {chatSending ? "…" : "发送"}
                  </button>
                </div>
              )}
            </>
          ) : (
          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
              {events.length === 0 && (
                <div className="flex h-full items-center justify-center text-xs text-gray-300">
                  {activeRoom.access_level === "related"
                    ? "作为相关部门，仅可见公开里程碑"
                    : "暂无事件，点击右上角记录第一条工作事件"}
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
                      {e.visibility === "PUBLIC" && (
                        <span className="rounded bg-amber-50 px-1.5 py-0.5 font-medium text-amber-600">
                          公开里程碑
                        </span>
                      )}
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
            )}
          </div>
        </div>
      )}

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
              label: `${e.user_name ?? "?"}`,
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
              sub:
                d.status === "READY"
                  ? `可检索 · ${d.chunk_count} 知识块`
                  : "解析中 · 暂不可检索",
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
  onSubmit: (data: {
    name: string;
    description: string | null;
    status: RoomStatus;
    stage: string;
  }) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState<RoomStatus>("ACTIVE");
  const [stage, setStage] = useState<string>("CONTACT");
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
              await onSubmit({ name, description: description || null, status, stage });
            } catch (err) {
              setError(err instanceof Error ? err.message : "创建失败");
            } finally {
              setSubmitting(false);
            }
          }}
        >
          <div>
            <label className="label">项目名称</label>
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={200}
              autoFocus
            />
          </div>
          <div>
            <label className="label">项目简介</label>
            <textarea
              className="input min-h-16 resize-y"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">状态</label>
              <select
                className="input"
                value={status}
                onChange={(e) => setStatus(e.target.value as RoomStatus)}
              >
                {(Object.keys(ROOM_STATUS_LABEL) as RoomStatus[]).map((s) => (
                  <option key={s} value={s}>
                    {ROOM_STATUS_LABEL[s]}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">当前阶段</label>
              <select className="input" value={stage} onChange={(e) => setStage(e.target.value)}>
                {ROOM_STAGE_ORDER.map((s) => (
                  <option key={s} value={s}>
                    {ROOM_STAGE_LABEL[s]}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {error && (
            <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>
          )}
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
  onSubmit: (data: {
    type: WorkEventType;
    content: string;
    visibility: "PUBLIC" | "INTERNAL";
  }) => Promise<void>;
}) {
  const [type, setType] = useState<WorkEventType>("work_log");
  const [content, setContent] = useState("");
  const [visibility, setVisibility] = useState<"PUBLIC" | "INTERNAL">("INTERNAL");
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
              await onSubmit({ type, content, visibility });
            } catch (err) {
              setError(err instanceof Error ? err.message : "保存失败");
            } finally {
              setSubmitting(false);
            }
          }}
        >
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">事件类型</label>
              <select
                className="input"
                value={type}
                onChange={(e) => setType(e.target.value as WorkEventType)}
              >
                {(Object.keys(WORK_EVENT_TYPE_LABEL) as WorkEventType[]).map((t) => (
                  <option key={t} value={t}>
                    {WORK_EVENT_TYPE_LABEL[t]}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">可见范围</label>
              <select
                className="input"
                value={visibility}
                onChange={(e) => setVisibility(e.target.value as "PUBLIC" | "INTERNAL")}
              >
                <option value="INTERNAL">内部事件（仅项目成员/管理层）</option>
                <option value="PUBLIC">公开里程碑（相关部门可见）</option>
              </select>
            </div>
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
          {error && (
            <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>
          )}
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
          {items.length === 0 ? (
            <div className="py-8 text-center text-sm text-gray-400">{emptyText}</div>
          ) : (
            items.map((item) => (
              <button
                key={item.id}
                className="flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left transition hover:bg-gray-50"
                onClick={() => onPick(item.id)}
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-gray-900">{item.label}</span>
                  {item.sub && (
                    <span className="block truncate text-xs text-gray-400">{item.sub}</span>
                  )}
                </span>
                <span className="shrink-0 text-xs text-blue-600">选择</span>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
