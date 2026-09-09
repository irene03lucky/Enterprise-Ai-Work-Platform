"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/features/auth/AuthProvider";
import {
  BookIcon,
  CalendarIcon,
  ChevronRightIcon,
  HomeIcon,
  PeopleIcon,
  PlusIcon,
  RoomIcon,
  SparklesIcon,
} from "@/components/icons";
import type { Conversation, Room } from "@/lib/types";

/* 一级导航：Rooms 不在这里（唯一 Rooms 入口是下方的项目分支） */
const NAV_TOP = [
  { href: "/workbench", label: "Work Center", icon: HomeIcon },
  { href: "/calendar", label: "Calendar", icon: CalendarIcon },
];

const NAV_BOTTOM = [
  { href: "/knowledge", label: "Knowledge", icon: BookIcon },
  { href: "/organization", label: "Organization", icon: PeopleIcon },
];

type NavItem = { href: string; label: string; icon: (p: { width: number; height: number; className?: string }) => React.ReactNode };

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { currentCompany } = useAuth();

  const [rooms, setRooms] = useState<Room[]>([]);
  const [roomsOpen, setRoomsOpen] = useState(true);
  const [conversations, setConversations] = useState<Conversation[]>([]);

  useEffect(() => {
    if (!currentCompany) return;
    api<Room[]>(`/companies/${currentCompany.id}/rooms`)
      .then(setRooms)
      .catch(() => setRooms([]));
    api<Conversation[]>(`/companies/${currentCompany.id}/conversations?limit=6`)
      .then(setConversations)
      .catch(() => setConversations([]));
  }, [currentCompany]);

  // Work Center 新建/更新对话后，自动刷新「历史对话」
  useEffect(() => {
    const handler = () => {
      if (!currentCompany) return;
      api<Conversation[]>(`/companies/${currentCompany.id}/conversations?limit=6`)
        .then(setConversations)
        .catch(() => {});
    };
    window.addEventListener("eai:conversations-updated", handler);
    return () => window.removeEventListener("eai:conversations-updated", handler);
  }, [currentCompany]);

  function isActive(href: string) {
    return pathname === href || pathname?.startsWith(`${href}/`);
  }

  function renderNavItem(item: NavItem) {
    const active = isActive(item.href);
    const Icon = item.icon;
    return (
      <Link
        key={item.href}
        href={item.href}
        className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition ${
          active
            ? "bg-gray-100 font-medium text-gray-900"
            : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
        }`}
      >
        <Icon width={17} height={17} className={active ? "text-gray-900" : "text-gray-400"} />
        {item.label}
      </Link>
    );
  }

  function openConversation(conv: Conversation) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("conv", conv.id);
    router.push(`/workbench?${params.toString()}`);
  }

  async function deleteConversation(conv: Conversation) {
    if (!currentCompany) return;
    if (!window.confirm(`删除对话记录「${conv.title}」？仅删除个人对话历史，不影响知识与项目数据。`))
      return;
    try {
      await api(`/companies/${currentCompany.id}/conversations/${conv.id}`, {
        method: "DELETE",
      });
    } catch {
      return;
    }
    setConversations((prev) => prev.filter((c) => c.id !== conv.id));
    // 若当前正打开该会话，清出 conv 参数
    if (searchParams.get("conv") === conv.id) {
      const params = new URLSearchParams(searchParams.toString());
      params.delete("conv");
      const qs = params.toString();
      router.push(qs ? `/workbench?${qs}` : "/workbench");
    }
  }

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-gray-200 bg-white">
      <div className="flex items-center gap-2.5 px-5 pb-5 pt-6">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gray-900 text-white">
          <SparklesIcon width={18} height={18} />
        </div>
        <div>
          <div className="text-sm font-semibold leading-tight tracking-tight">EAI</div>
          <div className="text-[11px] leading-tight text-gray-400">
            Enterprise AI Work Platform
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3">
        {NAV_TOP.map(renderNavItem)}

        {/* Rooms 分支：全站唯一 Rooms 入口，项目名称直接展开在下方 */}
        <div className="pt-1">
          <button
            className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm text-gray-600 transition hover:bg-gray-50 hover:text-gray-900"
            onClick={() => setRoomsOpen((v) => !v)}
          >
            <span className="flex items-center gap-2.5">
              <RoomIcon width={17} height={17} className="text-gray-400" />
              Rooms
            </span>
            <ChevronRightIcon
              width={14}
              height={14}
              className={`text-gray-400 transition-transform ${roomsOpen ? "rotate-90" : ""}`}
            />
          </button>
          {roomsOpen && (
            <div className="ml-3.5 mt-0.5 space-y-0.5 border-l border-gray-100 pl-2.5">
              {rooms.map((room) => {
                const active = pathname === "/rooms" && searchParams.get("room") === room.id;
                return (
                  <Link
                    key={room.id}
                    href={`/rooms?room=${room.id}`}
                    className={`block truncate rounded-md px-2.5 py-1.5 text-left text-[13px] transition ${
                      active
                        ? "bg-gray-100 font-medium text-gray-900"
                        : "text-gray-600 hover:bg-gray-50"
                    }`}
                    title={room.name}
                  >
                    {room.name}
                  </Link>
                );
              })}
              <Link
                href="/rooms?new=1"
                className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[13px] text-blue-600 transition hover:bg-blue-50"
              >
                <PlusIcon width={13} height={13} />
                新建 Room
              </Link>
            </div>
          )}
        </div>

        {NAV_BOTTOM.map(renderNavItem)}
      </nav>

      {/* 历史对话：仅个人 AI 交互记录，悬停可删除 */}
      <div className="border-t border-gray-100 px-3 py-3">
        <div className="px-2 pb-1.5 text-[11px] font-medium uppercase tracking-wide text-gray-400">
          历史对话
        </div>
        <div className="max-h-44 space-y-0.5 overflow-y-auto">
          {conversations.length === 0 ? (
            <div className="px-2 py-1 text-xs text-gray-300">暂无对话</div>
          ) : (
            conversations.map((c) => (
              <div
                key={c.id}
                className="group flex items-center rounded-md transition hover:bg-gray-50"
              >
                <button
                  onClick={() => openConversation(c)}
                  className="block min-w-0 flex-1 truncate px-2 py-1.5 text-left text-[13px] text-gray-600"
                  title={c.title}
                >
                  <span className="mr-1.5 text-[10px] text-gray-400">
                    {c.room_name ? "项目" : "对话"}
                  </span>
                  {c.title}
                </button>
                <button
                  className="mr-1 hidden shrink-0 rounded px-1.5 py-0.5 text-[11px] text-gray-400 transition hover:text-red-500 group-hover:block"
                  title="删除该对话记录（不影响知识与项目数据）"
                  onClick={() => void deleteConversation(c)}
                >
                  删除
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </aside>
  );
}
