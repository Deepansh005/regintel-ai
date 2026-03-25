"use client";

import { useEffect, useState } from "react";
import Sidebar from "../../components/sidebar";
import Header from "../../components/Header";
import StatsCard from "../../components/StatsCard";
import ChangeCard from "../../components/ChangeCard";
import ImpactCard from "../../components/ImpactCard";
import ActionCard from "../../components/ActionCard";
import Charts from "../../components/Charts";
import Insights from "../../components/Insights";

export default function Dashboard() {
  const [data, setData] = useState(null);
  

  useEffect(() => {
    const stored = localStorage.getItem("analysisData");
    if (stored) setData(JSON.parse(stored));
  }, []);

  if (!data) return <div className="p-6">Loading...</div>;

  let formattedChanges = {
  added: [],
  removed: [],
  modified: [],
};

//nested structure
if (data.changes?.changes && Array.isArray(data.changes.changes)) {
  const raw = data.changes.changes;

  formattedChanges = {
    added: raw.filter((c) => c.type === "added"),
    removed: raw.filter((c) => c.type === "removed"),
    modified: raw.filter((c) => c.type === "modified"),
  };
}

// grouped object
else if (data.changes && !Array.isArray(data.changes)) {
  formattedChanges = {
    added: data.changes.added || [],
    removed: data.changes.removed || [],
    modified: data.changes.modified || [],
  };
}

// plain array
else if (Array.isArray(data.changes)) {
  formattedChanges = {
    added: data.changes.filter((c) => c.type === "added"),
    removed: data.changes.filter((c) => c.type === "removed"),
    modified: data.changes.filter((c) => c.type === "modified"),
  };
}

//  total
const totalChanges =
  formattedChanges.added.length +
  formattedChanges.removed.length +
  formattedChanges.modified.length;

// IMPACT 
let impactData = { departments: [], systems: [] };

if (data.impact?.impact) {
  impactData = data.impact.impact;
} else if (data.impact) {
  impactData = data.impact;
}

// ACTION
let actionsData = [];

if (data.actions?.actions) {
  actionsData = data.actions.actions;
} else if (Array.isArray(data.actions)) {
  actionsData = data.actions;
}

  return (
    <div>

      <Sidebar />

      <div className="ml-64 min-h-screen bg-gray-100 p-6">

        <Header />

        {/* STATS */}
        <div className="grid md:grid-cols-3 gap-4 mb-6">
          <StatsCard title="Total Changes" value={totalChanges} />
          <StatsCard title="Added" value={formattedChanges.added.length} />
          <StatsCard title="Removed" value={formattedChanges.removed.length} />
        </div>

        {/* MAIN GRID */}
        <div className="grid md:grid-cols-2 gap-6">

          {/* CHANGES */}
          <div className="bg-white rounded-xl shadow p-6">
            <h2 className="font-semibold mb-4">Changes</h2>

            <ChangeCard title="Added" items={formattedChanges.added} color="green" />
            <ChangeCard title="Removed" items={formattedChanges.removed} color="red" />
            <ChangeCard title="Modified" items={formattedChanges.modified} color="yellow" />
          </div>
          {/* CHARTS */}
          <Charts changes={formattedChanges} impact={impactData} />
          {/* INSIGHTS */}
          <Insights changes={formattedChanges} total={totalChanges} />

          {/* IMPACT */}
          <div className="bg-white rounded-xl shadow p-6">
            <h2 className="font-semibold mb-4">Impact Analysis</h2>

            <ImpactCard title="Departments" items={impactData.departments} />
            <ImpactCard title="Systems" items={impactData.systems} />
          </div>

        </div>

        {/* ACTIONS */}
        <div className="mt-6 bg-white rounded-xl shadow p-6">
          <h2 className="font-semibold mb-4">Recommended Actions</h2>

          {actionsData.length > 0 ? (
            <div className="grid md:grid-cols-2 gap-4">
              {actionsData.map((a, i) => (
                <ActionCard key={i} action={a} />
              ))}
            </div>
          ) : (
            <p className="text-gray-400">No actions available</p>
          )}
        </div>

      </div>
    </div>
  );
}