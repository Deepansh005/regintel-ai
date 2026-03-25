"use client";

import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";

const COLORS = ["#22c55e", "#ef4444", "#f59e0b"];

export default function Charts({ changes, impact }) {
  // SAFETY FALLBACKS
  const safeChanges = changes || {
    added: [],
    removed: [],
    modified: [],
  };

  const safeImpact = impact || {
    departments: [],
    systems: [],
  };

  // PIE DATA
  const pieData = [
    { name: "Added", value: safeChanges.added?.length || 0 },
    { name: "Removed", value: safeChanges.removed?.length || 0 },
    { name: "Modified", value: safeChanges.modified?.length || 0 },
  ];

  //  BAR DATA 
  const barData = [
    {
      name: "Departments",
      value: safeImpact.departments?.length || 0,
    },
    {
      name: "Systems",
      value: safeImpact.systems?.length || 0,
    },
  ];

  return (
    <div className="grid md:grid-cols-2 gap-6">
      
      {/* PIE CHART */}
      <div className="bg-white p-4 rounded-xl shadow">
        <h3 className="font-semibold mb-4">Changes Distribution</h3>
        <ResponsiveContainer width="100%" height={250}>
          <PieChart>
            <Pie data={pieData} dataKey="value" outerRadius={80}>
              {pieData.map((entry, index) => (
                <Cell key={index} fill={COLORS[index]} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* BAR CHART */}
      <div className="bg-white p-4 rounded-xl shadow">
        <h3 className="font-semibold mb-4">Impact Overview</h3>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={barData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="value" fill="#3b82f6" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}