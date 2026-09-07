"use client";

import type { ReactNode } from "react";

interface PlaceholderPageProps {
  icon: ReactNode;
  title: string;
  description: string;
  capabilities?: string[];
}

/** 页面框架占位：AI 能力尚未上线时的一致版式。 */
export default function PlaceholderPage({
  icon,
  title,
  description,
  capabilities = [],
}: PlaceholderPageProps) {
  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center bg-gray-50 p-8">
      <div className="card w-full max-w-lg p-10 text-center">
        <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-gray-900 text-white">
          {icon}
        </div>
        <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
        <p className="mt-2 text-sm leading-relaxed text-gray-500">{description}</p>
        <span className="mt-4 inline-block rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-500">
          即将上线 · V1 框架占位
        </span>
        {capabilities.length > 0 && (
          <div className="mt-6 border-t border-dashed border-gray-200 pt-5">
            <div className="mb-2.5 text-xs font-medium text-gray-400">规划中的能力</div>
            <div className="flex flex-wrap justify-center gap-2">
              {capabilities.map((c) => (
                <span
                  key={c}
                  className="rounded-full border border-gray-200 bg-white px-2.5 py-1 text-xs text-gray-600"
                >
                  {c}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
