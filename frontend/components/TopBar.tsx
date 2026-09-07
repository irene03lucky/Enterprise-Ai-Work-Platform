"use client";

import { useState } from "react";
import { useAuth } from "@/features/auth/AuthProvider";
import { BuildingIcon } from "@/components/icons";

export default function TopBar() {
  const { companies, currentCompany, setCurrentCompanyId, user, logout } = useAuth();
  const [open, setOpen] = useState(false);

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-gray-200 bg-white px-6">
      <div className="relative">
        <button
          className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium text-gray-900 transition hover:bg-gray-50"
          onClick={() => setOpen((v) => !v)}
          disabled={companies.length === 0}
        >
          <BuildingIcon width={16} height={16} className="text-gray-400" />
          {currentCompany?.name ?? "暂无企业空间"}
          {companies.length > 1 && (
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-gray-400">
              <path d="M6 9l6 6 6-6" />
            </svg>
          )}
        </button>

        {open && companies.length > 0 && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
            <div className="absolute left-0 top-full z-20 mt-1 w-56 rounded-xl border border-gray-200 bg-white p-1 shadow-lg">
              <div className="px-3 py-1.5 text-[11px] font-medium text-gray-400">
                我的企业空间
              </div>
              {companies.map((c) => (
                <button
                  key={c.id}
                  className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition ${
                    c.id === currentCompany?.id
                      ? "bg-gray-100 font-medium text-gray-900"
                      : "text-gray-700 hover:bg-gray-50"
                  }`}
                  onClick={() => {
                    setCurrentCompanyId(c.id);
                    setOpen(false);
                  }}
                >
                  {c.name}
                  {c.industry && (
                    <span className="text-[11px] text-gray-400">{c.industry}</span>
                  )}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="flex items-center gap-3">
        {user && (
          <>
            <span className="text-sm text-gray-600">{user.name}</span>
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gray-900 text-xs font-semibold text-white">
              {user.name.slice(0, 1)}
            </div>
            <button
              onClick={logout}
              className="rounded-lg px-3 py-1.5 text-sm text-gray-500 transition hover:bg-gray-50 hover:text-gray-700"
            >
              退出
            </button>
          </>
        )}
      </div>
    </header>
  );
}
