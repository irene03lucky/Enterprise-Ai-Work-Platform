"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Room, Schedule } from "@/lib/types";

/** ISO 时间 → datetime-local 输入值（本地时区） */
function toLocalInput(iso: string): string {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

/** 日程新建 / 编辑 / 删除弹窗（Work Center 与 Calendar 共用）。 */
export function ScheduleModal({
  companyId,
  rooms,
  schedule = null,
  onClose,
  onSuccess,
}: {
  companyId: string;
  rooms: Room[];
  /** 传入则为编辑模式，否则为新建 */
  schedule?: Schedule | null;
  onClose: () => void;
  onSuccess: () => Promise<void> | void;
}) {
  const editing = !!schedule;
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
  const defaultDay = toLocalInput(schedule?.start_time ?? now.toISOString()).slice(0, 10);

  const [title, setTitle] = useState(schedule?.title ?? "");
  const [start, setStart] = useState(
    schedule ? toLocalInput(schedule.start_time) : `${defaultDay}T09:00`
  );
  const [end, setEnd] = useState(schedule?.end_time ? toLocalInput(schedule.end_time) : "");
  const [roomId, setRoomId] = useState(schedule?.room_id ?? "");
  const [note, setNote] = useState(schedule?.note ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleDelete() {
    if (!schedule) return;
    if (!window.confirm(`删除日程「${schedule.title}」？`)) return;
    setSubmitting(true);
    setErr(null);
    try {
      await api(`/companies/${companyId}/schedules/${schedule.id}`, { method: "DELETE" });
      await onSuccess();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "删除失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative w-[440px] max-w-[92vw] rounded-xl bg-white p-6 shadow-xl">
        <h3 className="mb-5 text-base font-semibold tracking-tight">
          {editing ? "编辑日程" : "新建日程"}
        </h3>
        <form
          className="space-y-4"
          onSubmit={async (e) => {
            e.preventDefault();
            setSubmitting(true);
            setErr(null);
            const body = {
              title,
              start_time: new Date(start).toISOString(),
              end_time: end ? new Date(end).toISOString() : null,
              room_id: roomId || null,
              note: note || null,
            };
            try {
              if (editing && schedule) {
                await api(`/companies/${companyId}/schedules/${schedule.id}`, {
                  method: "PATCH",
                  body,
                });
              } else {
                await api(`/companies/${companyId}/schedules`, { method: "POST", body });
              }
              await onSuccess();
            } catch (e2) {
              setErr(e2 instanceof Error ? e2.message : "保存失败");
            } finally {
              setSubmitting(false);
            }
          }}
        >
          <div>
            <label className="label">标题</label>
            <input
              className="input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              maxLength={200}
              autoFocus
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">开始时间</label>
              <input
                type="datetime-local"
                className="input"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="label">结束时间</label>
              <input
                type="datetime-local"
                className="input"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </div>
          </div>
          <div>
            <label className="label">关联项目（可选）</label>
            <select className="input" value={roomId} onChange={(e) => setRoomId(e.target.value)}>
              <option value="">不关联</option>
              {rooms.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">备注</label>
            <textarea
              className="input min-h-16 resize-y"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
          {err && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{err}</div>}
          <div className="flex items-center justify-between gap-2 pt-1">
            {editing ? (
              <button
                type="button"
                className="btn-danger"
                onClick={() => void handleDelete()}
                disabled={submitting}
              >
                删除
              </button>
            ) : (
              <span />
            )}
            <div className="flex gap-2">
              <button type="button" className="btn-secondary" onClick={onClose}>
                取消
              </button>
              <button type="submit" className="btn-primary" disabled={submitting}>
                {submitting ? "保存中…" : "保存"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
