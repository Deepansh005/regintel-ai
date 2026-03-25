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

const COLORS = ["#10b981", "#f43f5e", "#f59e0b"]; // Emerald, Rose, Amber

export default function Charts({ changes, impact }) {
  const safeChanges = changes || { added: [], removed: [], modified: [] };
  const safeImpact = impact || { departments: [], systems: [] };

  const pieData = [
    { name: "Added", value: safeChanges.added?.length || 0 },
    { name: "Removed", value: safeChanges.removed?.length || 0 },
    { name: "Modified", value: safeChanges.modified?.length || 0 },
  ];

  const barData = [
    { name: "Depts", value: safeImpact.departments?.length || 0 },
    { name: "Systems", value: safeImpact.systems?.length || 0 },
  ];

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-[#0f172a] border border-white/10 p-3 rounded-xl shadow-2xl backdrop-blur-xl">
          <p className="text-xs font-bold text-slate-300 uppercase tracking-widest">{payload[0].name}</p>
          <p className="text-lg font-bold text-white mt-1">{payload[0].value}</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="grid md:grid-cols-2 gap-8">
      {/* PIE CHART */}
      <div className="flex flex-col">
        <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-6">Changes Distrubution</h3>
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie
              data={pieData}
              dataKey="value"
              outerRadius={80}
              innerRadius={60}
              paddingAngle={8}
              stroke="none"
            >
              {pieData.map((entry, index) => (
                <Cell key={index} fill={COLORS[index]} />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="flex justify-center gap-6 mt-4">
          {pieData.map((d, i) => (
            <div key={i} className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[i] }} />
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">{d.name}</span>
            </div>
          ))}
        </div>
      </div>

      {/* BAR CHART */}
      <div className="flex flex-col">
        <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-6">Impact Reach</h3>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={barData} margin={{ top: 0, right: 0, left: -25, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
            <XAxis
              dataKey="name"
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#64748b', fontSize: 10, fontWeight: 700 }}
              dy={10}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#64748b', fontSize: 10, fontWeight: 700 }}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: '#ffffff05' }} />
            <Bar dataKey="value" fill="url(#barGradient)" radius={[6, 6, 0, 0]} barSize={40}>
              <defs>
                <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#8b5cf6" />
                  <stop offset="100%" stopColor="#6366f1" />
                </linearGradient>
              </defs>
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}