import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { ROUTES } from "@/lib/constants";
import Overview from "@/pages/Overview";
import LiveMonitor from "@/pages/LiveMonitor";
import Sessions from "@/pages/Sessions";
import Incidents from "@/pages/Incidents";
import Provenance from "@/pages/Provenance";
import Policies from "@/pages/Policies";
import Audit from "@/pages/Audit";
import Evaluation from "@/pages/Evaluation";
import SystemHealth from "@/pages/SystemHealth";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path={ROUTES.overview} element={<Overview />} />
        <Route path={ROUTES.liveMonitor} element={<LiveMonitor />} />
        <Route path={ROUTES.sessions} element={<Sessions />} />
        <Route path={ROUTES.incidents} element={<Incidents />} />
        <Route path={ROUTES.provenance} element={<Provenance />} />
        <Route path={ROUTES.policies} element={<Policies />} />
        <Route path={ROUTES.audit} element={<Audit />} />
        <Route path={ROUTES.evaluation} element={<Evaluation />} />
        <Route path={ROUTES.health} element={<SystemHealth />} />
        <Route path="*" element={<Navigate to={ROUTES.overview} replace />} />
      </Routes>
    </AppShell>
  );
}