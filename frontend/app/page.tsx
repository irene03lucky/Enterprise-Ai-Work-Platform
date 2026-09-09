"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function HomeRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/workbench");
  }, [router]);
  return (
    <div className="flex h-full items-center justify-center text-sm text-gray-400">
      正在进入 Work Center…
    </div>
  );
}
