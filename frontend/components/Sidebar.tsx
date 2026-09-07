"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookIcon,
  HomeIcon,
  PeopleIcon,
  RoomIcon,
  SparklesIcon,
} from "@/components/icons";

const NAV_ITEMS = [
  { href: "/assistant", label: "AI Assistant", icon: SparklesIcon },
  { href: "/work-center", label: "Work Center", icon: HomeIcon },
  { href: "/rooms", label: "Rooms", icon: RoomIcon },
  { href: "/knowledge", label: "Knowledge", icon: BookIcon },
  { href: "/organization", label: "Organization", icon: PeopleIcon },
];

export default function Sidebar() {
  const pathname = usePathname();

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
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || pathname?.startsWith(`${item.href}/`);
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
        })}
      </nav>

      <div className="border-t border-gray-100 p-3">
        <div className="rounded-lg px-3 py-2 text-[11px] leading-relaxed text-gray-400">
          更多能力（Knowledge / Room / Agent / Connector）将在此陆续开放。
        </div>
      </div>
    </aside>
  );
}
