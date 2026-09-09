"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/features/auth/AuthProvider";
import { ScheduleModal } from "@/components/ScheduleModal";
import type { Room, Schedule } from "@/lib/types";

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];

function toDateKey(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

export default function CalendarPage() {
  const { currentCompany } = useAuth();
  const today = new Date();
  const [view, setView] = useState({ year: today.getFullYear(), month: today.getMonth() });
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createDay, setCreateDay] = useState<string>(toDateKey(today));
  // 点击已有日程 → 编辑 / 删除
  const [editing, setEditing] = useState<Schedule | null>(null);

  const load = useCallback(async () => {
    if (!currentCompany) return;
    setLoading(true);
    setError(null);
    try {
      const first = new Date(view.year, view.month, 1);
      const startDow = (first.getDay() + 6) % 7;
      const gridStart = new Date(view.year, view.month, 1 - startDow);
      const gridEnd = new Date(gridStart);
      gridEnd.setDate(gridStart.getDate() + 41);
      gridEnd.setHours(23, 59, 59, 999);

      const [s, r] = await Promise.all([
        api<Schedule[]>(
          `/companies/${currentCompany.id}/schedules?start=${gridStart.toISOString()}&end=${gridEnd.toISOString()}`
        ),
        api<Room[]>(`/companies/${currentCompany.id}/rooms`),
      ]);
      setSchedules(s);
      setRooms(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载日程失败");
    } finally {
      setLoading(false);
    }
  }, [currentCompany, view]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!currentCompany) return null;

  // 构建 6×7 网格
  const first = new Date(view.year, view.month, 1);
  const startDow = (first.getDay() + 6) % 7;
  const gridStart = new Date(view.year, view.month, 1 - startDow);
  const cells: Date[] = [];
  for (let i = 0; i < 42; i++) {
    const d = new Date(gridStart);
    d.setDate(gridStart.getDate() + i);
    cells.push(d);
  }

  const byDay = new Map<string, Schedule[]>();
  for (const s of schedules) {
    const key = toDateKey(new Date(s.start_time));
    if (!byDay.has(key)) byDay.set(key, []);
    byDay.get(key)!.push(s);
  }
  byDay.forEach((list) => {
    list.sort((a, b) => a.start_time.localeCompare(b.start_time));
  });

  const todayKey = toDateKey(today);

  function openCreate(d: Date) {
    setCreateDay(toDateKey(d));
    setCreateOpen(true);
  }

  function closeModal() {
    setCreateOpen(false);
    setEditing(null);
  }

  return (
    <div className="mx-auto flex h-full max-w-5xl flex-col p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">
            {view.year}年{view.month + 1}月
          </h1>
          <p className="mt-0.5 text-sm text-gray-500">
            记录你的日程，帮助 AI 理解你的未来安排与真人状态。点击日程可编辑或删除。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="btn-secondary px-2.5"
            onClick={() => setView({ year: today.getFullYear(), month: today.getMonth() })}
          >
            今天
          </button>
          <div className="flex items-center overflow-hidden rounded-lg border border-gray-200">
            <button
              className="px-2.5 py-1.5 text-gray-600 transition hover:bg-gray-50"
              onClick={() =>
                setView((v) =>
                  v.month === 0
                    ? { year: v.year - 1, month: 11 }
                    : { year: v.year, month: v.month - 1 }
                )
              }
              aria-label="上一月"
            >
              ‹
            </button>
            <button
              className="border-l border-gray-200 px-2.5 py-1.5 text-gray-600 transition hover:bg-gray-50"
              onClick={() =>
                setView((v) =>
                  v.month === 11
                    ? { year: v.year + 1, month: 0 }
                    : { year: v.year, month: v.month + 1 }
                )
              }
              aria-label="下一月"
            >
              ›
            </button>
          </div>
          <button className="btn-primary" onClick={() => openCreate(today)}>
            + 新建日程
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 px-4 py-2.5 text-sm text-red-600">{error}</div>
      )}

      <div className="card flex min-h-0 flex-1 flex-col overflow-hidden p-0">
        {/* 星期表头 */}
        <div className="grid grid-cols-7 border-b border-gray-100">
          {WEEKDAYS.map((w, i) => (
            <div
              key={w}
              className={`px-2 py-2 text-center text-xs font-medium ${
                i >= 5 ? "text-gray-400" : "text-gray-500"
              }`}
            >
              {w}
            </div>
          ))}
        </div>

        {/* 日期格子 */}
        <div className="grid min-h-0 flex-1 grid-cols-7 grid-rows-6">
          {cells.map((d, idx) => {
            const key = toDateKey(d);
            const inMonth = d.getMonth() === view.month;
            const isToday = key === todayKey;
            const daySchedules = byDay.get(key) ?? [];
            return (
              <div
                key={idx}
                className={`group flex min-h-0 flex-col border-b border-r border-gray-100 p-1.5 ${
                  inMonth ? "bg-white" : "bg-gray-50/60"
                } ${idx % 7 === 6 ? "border-r-0" : ""} ${Math.floor(idx / 7) === 5 ? "border-b-0" : ""}`}
              >
                <div className="flex items-center justify-between">
                  <button
                    className={`flex h-6 w-6 items-center justify-center rounded-full text-xs transition ${
                      isToday
                        ? "bg-gray-900 font-semibold text-white"
                        : inMonth
                        ? "text-gray-700 hover:bg-gray-100"
                        : "text-gray-300 hover:bg-gray-100"
                    }`}
                    onClick={() => openCreate(d)}
                    title="新建当日日程"
                  >
                    {d.getDate()}
                  </button>
                  <button
                    className="hidden text-gray-300 transition hover:text-blue-600 group-hover:block"
                    onClick={() => openCreate(d)}
                    title="新建日程"
                  >
                    +
                  </button>
                </div>
                <div className="mt-0.5 min-h-0 flex-1 space-y-0.5 overflow-hidden">
                  {daySchedules.slice(0, 3).map((s) => (
                    <button
                      key={s.id}
                      className="block w-full truncate rounded px-1 py-0.5 text-left text-[11px] leading-tight transition hover:bg-blue-50"
                      title={`${s.title}${s.room_name ? " · " + s.room_name : ""}（点击编辑/删除）`}
                      onClick={() => setEditing(s)}
                    >
                      <span className="text-gray-400">{fmtTime(s.start_time)}</span>{" "}
                      <span className="text-gray-700">{s.title}</span>
                    </button>
                  ))}
                  {daySchedules.length > 3 && (
                    <div className="px-1 text-[11px] text-gray-400">
                      +{daySchedules.length - 3} 更多
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {(createOpen || editing) && (
        <ScheduleModal
          companyId={currentCompany.id}
          rooms={rooms}
          schedule={editing}
          onClose={closeModal}
          onSuccess={async () => {
            closeModal();
            await load();
          }}
        />
      )}
    </div>
  );
}
