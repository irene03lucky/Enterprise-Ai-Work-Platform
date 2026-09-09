"use client";

import {
  AI_ACTIVITY_TYPE_LABEL,
  TASK_STATUS_LABEL,
  type AIActivity,
  type AIActivityType,
  type Task,
} from "@/lib/types";

const TYPE_STYLE: Record<AIActivityType, string> = {
  ANSWERED: "bg-green-50 text-green-700",
  RECEIVED: "bg-blue-50 text-blue-700",
  TASK_CREATED: "bg-indigo-50 text-indigo-700",
  NEED_CONFIRM: "bg-amber-50 text-amber-700",
};

function fmtTime(s: string) {
  return new Date(s).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

/* ---------------- 我的任务（个人执行层，完成后同步回 Room） ---------------- */

export function MyTasksPanel({
  tasks,
  onComplete,
}: {
  tasks: Task[];
  onComplete: (id: string) => Promise<void>;
}) {
  return (
    <section className="card flex shrink-0 flex-col p-5">
      <div className="mb-1 text-sm font-semibold text-gray-900">我的任务</div>
      <div className="mb-3 text-[11px] text-gray-400">
        完成后状态自动同步回 Room Timeline，所有项目成员可见。
      </div>
      <div className="max-h-56 space-y-2 overflow-y-auto pr-1">
        {tasks.length === 0 && (
          <div className="text-xs text-gray-300">暂无待办任务</div>
        )}
        {tasks.map((t) => (
          <div key={t.id} className="rounded-lg border border-gray-100 p-3">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 text-sm font-medium text-gray-800">{t.title}</div>
              <button
                className="btn-primary shrink-0 px-2 py-0.5 text-[11px]"
                onClick={() => void onComplete(t.id)}
              >
                完成
              </button>
            </div>
            <div className="mt-1 text-[11px] text-gray-400">
              {t.room_name ? `来源：${t.room_name}` : "个人事项"} ·{" "}
              {TASK_STATUS_LABEL[t.status]}
              {t.source === "AI_TWIN" ? " · 来自 AI 分身" : ""}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ---------------- 中间区域：AI 分身代我回复 / 记录事项 ----------------
 * 只展示 AI 分身代理产生的行为（外部沟通代回复、接收事项、生成 Task、待确认），
 * 不是 AI 助手的聊天记录。 */

export function AIHandledItemsPanel({
  items,
  onResolve,
}: {
  items: AIActivity[];
  onResolve: (id: string, resolved: boolean) => void;
}) {
  const groups: { key: AIActivityType; label: string }[] = [
    { key: "ANSWERED", label: "AI 分身已回复" },
    { key: "RECEIVED", label: "AI 分身已接收" },
    { key: "TASK_CREATED", label: "AI 分身生成 Task" },
    { key: "NEED_CONFIRM", label: "待本人确认" },
  ];
  const byType = (t: AIActivityType) =>
    items
      .filter((i) => i.type === t)
      .sort((a, b) => b.created_at.localeCompare(a.created_at));

  return (
    <section className="card flex h-full min-h-0 flex-col p-5">
      <div className="mb-1 text-sm font-semibold text-gray-900">
        AI 分身代我回复 / 记录事项
      </div>
      <div className="mb-3 text-[11px] text-gray-400">
        仅展示 AI 分身代理产生的行为，不是 AI 助手聊天记录。
      </div>
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
        {items.length === 0 && (
          <div className="flex h-full items-center justify-center text-xs text-gray-300">
            暂无 AI 分身代理行为
          </div>
        )}
        {groups.map((g) => {
          const list = byType(g.key);
          return (
            <div key={g.key}>
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-xs font-medium text-gray-500">{g.label}</span>
                {list.length > 0 && (
                  <span className="rounded-full bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-500">
                    {list.length}
                  </span>
                )}
              </div>
              {list.length === 0 ? (
                <div className="text-[11px] text-gray-300">暂无</div>
              ) : (
                <div className="space-y-2">
                  {list.map((item) => {
                    const pending = item.type === "NEED_CONFIRM" && !item.resolved;
                    return (
                      <div
                        key={item.id}
                        className={`rounded-lg border p-3 ${
                          item.resolved
                            ? "border-gray-100 bg-gray-50/60 opacity-70"
                            : "border-gray-100 bg-white"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <span
                            className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${TYPE_STYLE[item.type]}`}
                          >
                            {AI_ACTIVITY_TYPE_LABEL[item.type]}
                          </span>
                          <span className="shrink-0 text-[11px] text-gray-300">
                            {fmtTime(item.created_at)}
                          </span>
                        </div>
                        <div className="mt-1.5 text-sm font-medium text-gray-800">{item.title}</div>
                        {item.content && (
                          <div className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-gray-500">
                            {item.content}
                          </div>
                        )}
                        {item.counterparty && (
                          <div className="mt-1 text-[11px] text-gray-400">来自：{item.counterparty}</div>
                        )}
                        {item.room_name && (
                          <div className="mt-0.5 text-[11px] text-gray-400">
                            来源：{item.room_name}
                          </div>
                        )}
                        {pending && (
                          <div className="mt-2 flex gap-2">
                            <button
                              className="btn-primary px-2.5 py-1 text-xs"
                              onClick={() => onResolve(item.id, true)}
                            >
                              已处理
                            </button>
                            <button
                              className="btn-secondary px-2.5 py-1 text-xs"
                              onClick={() => onResolve(item.id, false)}
                            >
                              暂不处理
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
