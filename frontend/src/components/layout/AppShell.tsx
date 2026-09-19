import type { ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-full min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="min-w-0 flex-1 overflow-y-auto p-4 md:p-6">
          <div className="mx-auto w-full max-w-[1400px]">{children}</div>
        </main>
        <footer className="border-t border-line bg-base-panel/40 px-4 py-2 text-[10px] text-ink-muted">
          Agent ICE · Agent proposes, ICE authorizes, receipt binds, executor
          enforces. This UI displays backend decisions — it does not make them.
        </footer>
      </div>
    </div>
  );
}