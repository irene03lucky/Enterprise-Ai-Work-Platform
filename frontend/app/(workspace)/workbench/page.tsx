"use client";

import { useCallback, useEffect, useState } from "react";
export const dynamic = "force-dynamic";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/features/auth/AuthProvider";
import { DigitalTwinPanel } from "@/features/workbench/DigitalTwinPanel";
import { AIHandledItemsPanel, MyTasksPanel } from "@/features/workbench/ItemsPanels";
import { WorkbenchChat } from "@/features/workbench/WorkbenchChat";
import { ScheduleModal } from "@/components/ScheduleModal";
import type { Room, Schedule, Task, WorkbenchData } from "@/lib/types";

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

export default function WorkCenterPage() {
  const { currentCompany } = useAuth();
  const searchParams = useSearchParams();
  const convId = searchParams.get("conv");

  const [data, setData] = useState<WorkbenchData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [myTasks, setMyTasks] = useState<Task[]>([]);
  const [scheduleModal, setScheduleModal] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<Schedule | null>(null);

  const activeRoomId = searchParams.get("room");
  const activeRoomName = rooms.find((r) => r.id === activeRoomId)?.name ?? null;

  const load = useCallback(async () => {
    if (!currentCompany) return;
    setLoading(true);
    setError(null);
    try {
      const [wb, rs, ts] = await Promise.all([
        api<WorkbenchData>(`/companies/${currentCompany.id}/workbench`),
        api<Room[]>(`/companies/${currentCompany.id}/rooms`),
        api<Task[]>(`/companies/${currentCompany.id}/tasks?scope=my`),
      ]);
      setData(wb);
      setRooms(rs);
      setMyTasks(ts);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载 Work Center 失败");
    } finally {
      setLoading(false);
    }
  }, [currentCompany]);

  useEffect(() => {
    void load();
  }, [load]);

  async function resolveItem(id: string, resolved: boolean) {
    if (!currentCompany) return;
    await api(`/companies/${currentCompany.id}/ai-items/${id}`, {
      method: "PATCH",
      body: { resolved },
    });
    await load();
  }

  async function completeTask(id: string) {
    if (!currentCompany) return;
    await api(`/companies/${currentCompany.id}/tasks/${id}`, {
      method: "PATCH",
      body: { status: "DONE" },
    });
    await load();
  }

  if (!currentCompany) return null;

  if (loading) {
    return <div className="flex h-full items-center justify-center text-sm text-gray-400">加载中…</div>;
  }
  if (error || !data) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-red-600">
        {error ?? "暂无数据"}
      </div>
    );
  }

  return (
    <div className="mx-auto flex h-full max-w-[1700px] flex-col gap-4 p-6">
      {/* 顶部：今日工作日程（仅日程，不放身份/分身/对话入口） */}
      <section className="card shrink-0 p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">今日工作日程</h2>
            <p className="mt-0.5 text-xs text-gray-400">今天我要做什么；点击日程可编辑或删除。</p>
          </div>
          <button
            className="text-xs text-blue-600 hover:underline"
            onClick={() => {
              setEditingSchedule(null);
              setScheduleModal(true);
            }}
          >
            + 新建日程
          </button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {data.today_schedules.length === 0 && (
            <div className="text-xs text-gray-300">今天没有安排</div>
          )}
          {data.today_schedules.map((s) => (
            <button
              key={s.id}
              className="flex items-center gap-2 rounded-lg border border-gray-100 px-3 py-2 text-left transition hover:border-blue-200 hover:bg-blue-50/50"
              title="点击编辑或删除该日程"
              onClick={() => {
                setEditingSchedule(s);
                setScheduleModal(true);
              }}
            >
              <span className="text-xs font-semibold text-gray-900">{fmtTime(s.start_time)}</span>
              <span className="text-sm text-gray-700">{s.title}</span>
              {s.room_name && (
                <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-500">
                  {s.room_name}
                </span>
              )}
            </button>
          ))}
        </div>
      </section>

      {/* 主体三列：左 AI 助手对话 / 中 AI 分身代理行为 / 右 身份与 AI 分身 */}
      <div className="grid min-h-0 flex-1 grid-cols-12 gap-4">
        {/* 左：AI 助手对话窗口（用户主动调用的企业 AI，非 AI 分身） */}
        <div className="col-span-5 min-h-0">
          <WorkbenchChat
            companyId={currentCompany.id}
            conversationId={convId}
            roomId={activeRoomId}
            roomName={activeRoomName}
            onActivity={() => void load()}
          />
        </div>

        {/* 中：AI 分身代我回复 / 记录事项 + 我的任务 */}
        <div className="col-span-4 flex min-h-0 flex-col gap-4">
          <div className="min-h-0 flex-1">
            <AIHandledItemsPanel items={data.ai_items} onResolve={resolveItem} />
          </div>
          <MyTasksPanel tasks={myTasks} onComplete={completeTask} />
        </div>

        {/* 右：你的身份与 AI 分身 */}
        <div className="col-span-3 min-h-0 overflow-y-auto pr-1">
          <DigitalTwinPanel
            profile={data.profile}
            onChange={(p) => setData({ ...data, profile: p })}
          />
        </div>
      </div>

      {scheduleModal && (
        <ScheduleModal
          companyId={currentCompany.id}
          rooms={rooms}
          schedule={editingSchedule}
          onClose={() => {
            setScheduleModal(false);
            setEditingSchedule(null);
          }}
          onSuccess={async () => {
            setScheduleModal(false);
            setEditingSchedule(null);
            await load();
          }}
        />
      )}
    </div>
  );
}
