import React from "react";
import "./globals.css";
export const metadata = {
  title: "Caliburn・職務說明書",
  description: "本機職務分析工作畫面",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-Hant">
      <body>{children}</body>
    </html>
  );
}
