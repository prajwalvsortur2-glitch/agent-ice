import { AlertOctagon, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { Spinner } from "@/components/common/Spinner";
import { IncidentCard } from "@/components/incidents/IncidentCard";
import { listIncidents } from "@/api/audit";
import type { Incident } from "@/types";

export default function Incidents() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const rows = await listIncidents(100, 0);
      setIncidents(rows);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="space-y-4">
      <Card
        title="Security Incidents"
        subtitle={`${incidents.length} recorded · blocked, reviewed, or restricted actions`}
        actions={
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => void load()}
          >
            {loading ? <Spinner /> : <RefreshCw className="h-3.5 w-3.5" />}
            Refresh
          </button>
        }
        bodyClassName="p-0"
      >
        {error && (
          <div className="border-b border-line px-4 py-3 text-xs text-decision-block">
            {error}
          </div>
        )}
        {incidents.length === 0 && !loading ? (
          <EmptyState
            icon={AlertOctagon}
            title="No incidents"
            description="Blocked, reviewed, or restricted actions will appear here."
          />
        ) : (
          <div className="space-y-3 p-3">
            {incidents.map((i) => (
              <IncidentCard key={i.incident_id} incident={i} />
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}