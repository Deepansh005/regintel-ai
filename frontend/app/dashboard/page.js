"use client";

import { useEffect, useState } from "react";
import ChangeCard from "../../components/ChangeCard";
import ImpactCard from "../../components/ImpactCard";
import ActionCard from "../../components/ActionCard";

export default function Dashboard() {
  const [data, setData] = useState(null);

  useEffect(() => {
    const stored = localStorage.getItem("result");
    if (stored) {
      const parsed = JSON.parse(stored);
      console.log("FULL DATA:", parsed);
      console.log("ACTIONS:", parsed.actions);
      setData(parsed);
    }
  }, []);

  if (!data) return <p className="p-6">No data found</p>;

  return (
    <div className="p-6 space-y-6 bg-gray-50 min-h-screen">
      <h1 className="text-2xl font-bold">RegIntel Dashboard</h1>

      {/* Changes */}
      <div className="grid md:grid-cols-3 gap-4">
        <ChangeCard type="added" items={data.changes?.added} />
        <ChangeCard type="removed" items={data.changes?.removed} />
        <ChangeCard type="modified" items={data.changes?.modified} />
      </div>

      {/* Impact */}
      <ImpactCard impact={data.impact} />

      {/* Actions */}
      <div>
        <h2 className="text-xl font-semibold mb-2">Recommended Actions</h2>

        <div className="grid md:grid-cols-2 gap-4">
          {data.actions?.actions?.length > 0 ? (
            data.actions.actions.map((action, i) => (
              <ActionCard key={i} action={action} />
            ))
          ) : (
            <p>No actions available</p>
          )}
        </div>
      </div>
    </div>
  );
}