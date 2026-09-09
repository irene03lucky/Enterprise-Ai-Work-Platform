"use client";

import { Suspense, type ReactNode } from "react";
import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";
import CreateCompanyPanel from "@/components/CreateCompanyPanel";
import { AuthProvider, useAuth } from "@/features/auth/AuthProvider";

function WorkspaceShell({ children }: { children: ReactNode }) {
  const { user, companies, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-gray-200 border-t-gray-900" />
          <span className="text-sm text-gray-400">正在加载工作区…</span>
        </div>
      </div>
    );
  }

  if (!user) return null; // 正在跳转登录页

  return (
    <div className="flex h-screen overflow-hidden">
      <Suspense fallback={<div className="w-60 shrink-0 border-r border-gray-200 bg-white" />}>
        <Sidebar />
      </Suspense>
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="flex-1 overflow-y-auto">
          {companies.length === 0 ? <CreateCompanyPanel /> : children}
        </main>
      </div>
    </div>
  );
}

export default function WorkspaceLayout({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <WorkspaceShell>{children}</WorkspaceShell>
    </AuthProvider>
  );
}
