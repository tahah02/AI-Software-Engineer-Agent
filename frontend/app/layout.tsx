import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AAISE Platform — Autonomous AI Software Engineer",
  description: "Enterprise multi-agent software engineering platform with LangGraph orchestration",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased selection:bg-cyan-500/30 selection:text-cyan-200">
        {children}
      </body>
    </html>
  );
}
