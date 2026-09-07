"use client";

import PlaceholderPage from "@/components/PlaceholderPage";
import { HomeIcon } from "@/components/icons";

export default function WorkCenterPage() {
  return (
    <PlaceholderPage
      icon={<HomeIcon width={26} height={26} />}
      title="Work Center"
      description="你的个人工作中心。未来这里将汇聚你的任务、日程、待办与工作动态，让每一天的工作有序推进。"
      capabilities={["个人任务管理", "Work Event 工作事件流", "智能日程建议", "工作摘要与回顾"]}
    />
  );
}
