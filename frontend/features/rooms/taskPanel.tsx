"use client";

/** Project Room 任务面板：待办事项 / 我的任务 / 已完成 + 任务表单 + AI 提案确认卡片。 */

import { useMemo, useState } from "react";
import {
  TASK_SOURCE_LABEL,
  TASK_STATUS_LABEL,
  type RoomMember,
  type Task,
  type TaskProposal,
  type TaskStatus,
} from "@/lib/types";

type TabKey = "open" | "mine" | "done";

export interface TaskFormData {
  title: string;
  description: string | null;
  assignee_employee_id: string | null;
  due_date: string | null;
  status: TaskStatus;
}

const STATUS_DOT: Record<TaskStatus, string> = {
  TODO: "border-gray-300",
  IN_PROGRESS: "border-blue-500",
  DONE: "border-green-500 bg-green-500",
};

const STATUS_BADGE: Record<TaskStatus, string> = {
  TODO: "bg-gray-100 text-gray-500",
  IN_PROGRESS: "bg-blue-50 text-blue-600",
  DONE: "bg-green-50 text-green-600",
};

const NEXT_STATUS: Record<TaskStatus, TaskStatus> = {
  TODO: "IN_PROGRESS",
  IN_PROGRESS: "DONE",
  DONE: "TODO",
};

function isOverdue(task: Task): boolean {
  if (!task.due_date || task.status === "DONE") return false;
  return new Date(`${task.due_date}T23:59:59`).getTime() < Date.now();
}

function dueLabel(task: Task): string {
  const d = new Date(`${task.due_date}T00:00:00`);
  return `${d.getMonth() + 1}月${d.getDate()}日`;
}

export function TaskPanel({
  tasks,
  members,
  currentEmployeeId,
  onChangeStatus,
  onDelete,
  onSubmitForm,
}: {
  tasks: Task[];
  members: RoomMember[];
  currentEmployeeId: string | null;
  onChangeStatus: (task: Task, status: TaskStatus) => Promise<void>;
  onDelete: (task: Task) => Promise<void>;
  onSubmitForm: (data: TaskFormData, task: Task | null) => Promise<void>;
}) {
  const [tab, setTab] = useState<TabKey>("open");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);

  const isMine = (t: Task) =>
    !!currentEmployeeId && t.assignee_employee_id === currentEmployeeId;

  const counts = useMemo(
    () => ({
      open: tasks.filter((t) => t.status !== "DONE").length,
      mine: tasks.filter((t) => t.status !== "DONE" && isMine(t)).length,
      done: tasks.filter((t) => t.status === "DONE").length,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [tasks, currentEmployeeId]
  );

  const visible = useMemo(() => {
    if (tab === "mine") return tasks.filter((t) => t.status !== "DONE" && isMine(t));
    if (tab === "done") return tasks.filter((t) => t.status === "DONE");
    return tasks.filter((t) => t.status !== "DONE");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tasks, tab, currentEmployeeId]);

  const tabs: { key: TabKey; label: string; count: number }[] = [
    { key: "open", label: "待办事项", count: counts.open },
    { key: "mine", label: "我的任务", count: counts.mine },
    { key: "done", label: "已完成", count: counts.done },
  ];

  return (
    <div className="card flex min-h-0 flex-col p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-1">
          {tabs.map((t) => (
            <button
              key={t.key}
              className={`rounded-lg px-2.5 py-1 text-xs transition ${
                tab === t.key ? "bg-gray-900 text-white" : "text-gray-500 hover:bg-gray-100"
              }`}
              onClick={() => setTab(t.key)}
            >
              {t.label}（{t.count}）
            </button>
          ))}
        </div>
        <button
          className="btn-secondary px-2.5 py-1 text-xs"
          onClick={() => {
            setEditing(null);
            setFormOpen(true);
          }}
        >
          + 新建任务
        </button>
      </div>

      <div className="min-h-0 flex-1 space-y-1 overflow-y-auto pr-1">
        {visible.length === 0 && (
          <div className="flex h-full items-center justify-center text-xs text-gray-300">
            暂无{tabs.find((t) => t.key === tab)?.label}
          </div>
        )}
        {visible.map((task) => (
          <div
            key={task.id}
            className="group flex items-start gap-2.5 rounded-lg px-2 py-2 transition hover:bg-gray-50"
          >
            <button
              className={`mt-0.5 h-4 w-4 shrink-0 rounded-full border-2 transition ${STATUS_DOT[task.status]}`}
              title={`当前状态：${TASK_STATUS_LABEL[task.status]}，点击切换`}
              onClick={() => void onChangeStatus(task, NEXT_STATUS[task.status])}
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-start justify-between gap-2">
                <span
                  className={`text-sm leading-snug ${
                    task.status === "DONE" ? "text-gray-400 line-through" : "text-gray-900"
                  }`}
                >
                  {task.title}
                </span>
                <div className="hidden shrink-0 items-center gap-2 group-hover:flex">
                  <button
                    className="text-xs text-gray-400 hover:text-blue-600"
                    onClick={() => {
                      setEditing(task);
                      setFormOpen(true);
                    }}
                  >
                    编辑
                  </button>
                  <button
                    className="text-xs text-gray-400 hover:text-red-500"
                    onClick={() => {
                      if (!window.confirm(`确定删除任务「${task.title}」？`)) return;
                      void onDelete(task);
                    }}
                  >
                    删除
                  </button>
                </div>
              </div>
              {task.description && (
                <p className="mt-0.5 text-xs leading-relaxed text-gray-500">{task.description}</p>
              )}
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px]">
                <span className={`rounded px-1.5 py-0.5 font-medium ${STATUS_BADGE[task.status]}`}>
                  {TASK_STATUS_LABEL[task.status]}
                </span>
                <span className="text-gray-400">
                  {task.assignee_name ? `负责人 ${task.assignee_name}` : "未指派"}
                </span>
                {task.due_date && (
                  <span className={isOverdue(task) ? "text-red-500" : "text-gray-400"}>
                    截止 {dueLabel(task)}
                    {isOverdue(task) ? "（已逾期）" : ""}
                  </span>
                )}
                <span className="rounded bg-gray-50 px-1.5 py-0.5 text-gray-400">
                  {TASK_SOURCE_LABEL[task.source]}
                </span>
                {task.source_quote && (
                  <span className="max-w-[16rem] truncate text-gray-300" title={`来源：${task.source_quote}`}>
                    来源：{task.source_quote}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {formOpen && (
        <TaskFormModal
          task={editing}
          members={members}
          onClose={() => setFormOpen(false)}
          onSubmit={async (data) => {
            await onSubmitForm(data, editing);
            setFormOpen(false);
          }}
        />
      )}
    </div>
  );
}

export function TaskFormModal({
  task,
  members,
  onClose,
  onSubmit,
}: {
  task: Task | null;
  members: RoomMember[];
  onClose: () => void;
  onSubmit: (data: TaskFormData) => Promise<void>;
}) {
  const [title, setTitle] = useState(task?.title ?? "");
  const [description, setDescription] = useState(task?.description ?? "");
  const [assignee, setAssignee] = useState(task?.assignee_employee_id ?? "");
  const [dueDate, setDueDate] = useState(task?.due_date ?? "");
  const [status, setStatus] = useState<TaskStatus>(task?.status ?? "TODO");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative w-[480px] max-w-[92vw] rounded-xl bg-white p-6 shadow-xl">
        <h3 className="mb-5 text-base font-semibold tracking-tight">
          {task ? "编辑任务" : "新建任务"}
        </h3>
        <form
          className="space-y-4"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!title.trim()) return;
            setSubmitting(true);
            setError(null);
            try {
              await onSubmit({
                title: title.trim(),
                description: description.trim() || null,
                assignee_employee_id: assignee || null,
                due_date: dueDate || null,
                status,
              });
            } catch (err) {
              setError(err instanceof Error ? err.message : "保存失败");
            } finally {
              setSubmitting(false);
            }
          }}
        >
          <div>
            <label className="label">任务标题</label>
            <input
              className="input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="例如：完成首页高保真设计稿"
              autoFocus
              required
            />
          </div>
          <div>
            <label className="label">任务描述</label>
            <textarea
              className="input min-h-20 resize-y"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">负责人</label>
              <select className="input" value={assignee} onChange={(e) => setAssignee(e.target.value)}>
                <option value="">未指派</option>
                {members.map((m) => (
                  <option key={m.id} value={m.employee_id}>
                    {m.user_name ?? m.user_email ?? "未知成员"}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">截止日期</label>
              <input
                className="input"
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
              />
            </div>
          </div>
          <div>
            <label className="label">状态</label>
            <select
              className="input"
              value={status}
              onChange={(e) => setStatus(e.target.value as TaskStatus)}
            >
              {(Object.keys(TASK_STATUS_LABEL) as TaskStatus[]).map((s) => (
                <option key={s} value={s}>
                  {TASK_STATUS_LABEL[s]}
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
              {submitting ? "保存中…" : task ? "保存" : "创建"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function TaskProposalCard({
  proposals,
  state,
  onConfirm,
  onDismiss,
}: {
  proposals: TaskProposal[];
  state: "pending" | "created" | "dismissed";
  onConfirm: (proposals: TaskProposal[]) => Promise<void>;
  onDismiss: () => void;
}) {
  const [submitting, setSubmitting] = useState(false);

  if (state === "dismissed") return null;

  return (
    <div className="mt-3 rounded-xl border border-blue-100 bg-blue-50/60 p-3">
      <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-blue-700">
        <span className="h-1.5 w-1.5 rounded-full bg-blue-500" />
        {state === "created" ? "已创建为任务" : "识别到行动事项，确认后创建"}
      </div>
      <div className="space-y-2">
        {proposals.map((p, i) => (
          <div key={i} className="rounded-lg bg-white px-3 py-2">
            <div className="text-sm text-gray-900">{p.title}</div>
            {p.description && <div className="mt-0.5 text-xs text-gray-500">{p.description}</div>}
            <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-gray-400">
              <span>{p.assignee_name ? `负责人 ${p.assignee_name}` : "未指定负责人"}</span>
              {p.due_date && <span>截止 {p.due_date}</span>}
              <span className="rounded bg-gray-50 px-1.5 py-0.5">
                {p.source === "FOLLOW_UP" ? "后续跟进" : "AI 对话"}
              </span>
            </div>
          </div>
        ))}
      </div>
      {state === "pending" && (
        <div className="mt-2.5 flex gap-2">
          <button
            className="btn-primary px-3 py-1 text-xs"
            disabled={submitting}
            onClick={async () => {
              setSubmitting(true);
              try {
                await onConfirm(proposals);
              } finally {
                setSubmitting(false);
              }
            }}
          >
            {submitting ? "创建中…" : "确认创建"}
          </button>
          <button className="btn-secondary px-3 py-1 text-xs" onClick={onDismiss}>
            忽略
          </button>
        </div>
      )}
    </div>
  );
}
