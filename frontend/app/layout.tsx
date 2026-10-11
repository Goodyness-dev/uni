import type { Metadata } from "next";
import { TopBar } from "../components/TopBar";
import "./globals.css";

export const metadata: Metadata = {
  title: "ScholarPilot — Autonomous Scholarship Agent",
  description:
    "Agentic scholarship discovery, evidence selection, and truthful application packaging.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#0d0e11] text-[#ECEDF0] min-h-screen antialiased selection:bg-[#5b8cff]/30 selection:text-white">
        <TopBar />
        <main className="w-full pt-14 bg-[#0d0e11]">
          {children}
        </main>
      </body>
    </html>
  );
}
