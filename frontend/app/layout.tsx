import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EAI · Enterprise AI Work Platform",
  description: "面向企业内部的 AI 工作平台",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
