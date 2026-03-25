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
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Upload, ArrowRight } from "lucide-react";

export default function Dashboard() {
  const [data, setData] = useState(null);
  const router = useRouter();

  useEffect(() => {
    // Check auth
    const user = localStorage.getItem("regintel_user");
    if (!user) {
      router.push("/login");
      return;
    }

    const stored = localStorage.getItem("analysisData");
    if (stored) setData(JSON.parse(stored));
  }, [router]);

  if (!data) return (
    <div className="min-h-screen bg-[#020617] text-white flex">
      <Sidebar />
      <div className="ml-64 w-full p-8 flex flex-col relative z-10">
        <Header />

        {/* BACKGROUND GLOWS */}
        <div className="fixed top-0 left-64 w-full h-full overflow-hidden pointer-events-none -z-10">
          <div className="absolute top-[-10%] right-[-10%] w-[50%] h-[50%] bg-violet-600/5 rounded-full blur-[120px]" />
          <div className="absolute bottom-[-10%] left-[-10%] w-[50%] h-[50%] bg-indigo-600/5 rounded-full blur-[120px]" />
        </div>

        <div className="flex-1 flex flex-col items-center justify-center mt-[-60px]">
          <div className="w-20 h-20 bg-white/5 rounded-3xl flex items-center justify-center mb-6 border border-white/10 shadow-2xl">
            <Upload className="w-10 h-10 text-violet-400" />
          </div>
          <h2 className="text-3xl font-bold mb-3 tracking-tight">Dashboard Empty</h2>
          <p className="text-slate-400 mb-8 max-w-md text-center leading-relaxed">Your compliance dashboard is currently waiting for data. Upload regulatory circulars to automatically generate AI insights, impact analysis, and compliance workflows.</p>
          <Link href="/upload" className="px-8 py-4 bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-full font-bold flex items-center gap-3 hover:shadow-xl hover:shadow-violet-500/20 hover:-translate-y-0.5 transition-all active:scale-95 group">
            Compare Circulars Now
            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
          </Link>
        </div>
      </div>
    </div>
  );

  let formattedChanges = {
    added: [],
    removed: [],
    modified: [],
  };

  if (data.changes?.changes && Array.isArray(data.changes.changes)) {
    const raw = data.changes.changes;
    formattedChanges = {
      added: raw.filter((c) => c.type === "added"),
      removed: raw.filter((c) => c.type === "removed"),
      modified: raw.filter((c) => c.type === "modified"),
    };
  } else if (data.changes && !Array.isArray(data.changes)) {
    formattedChanges = {
      added: data.changes.added || [],
      removed: data.changes.removed || [],
      modified: data.changes.modified || [],
    };
  } else if (Array.isArray(data.changes)) {
    formattedChanges = {
      added: data.changes.filter((c) => c.type === "added"),
      removed: data.changes.filter((c) => c.type === "removed"),
      modified: data.changes.filter((c) => c.type === "modified"),
    };
  }

  const totalChanges =
    formattedChanges.added.length +
    formattedChanges.removed.length +
    formattedChanges.modified.length;

  let impactData = { departments: [], systems: [] };
  if (data.impact?.impact) {
    impactData = data.impact.impact;
  } else if (data.impact) {
    impactData = data.impact;
  }

  let actionsData = [];
  if (data.actions?.actions) {
    actionsData = data.actions.actions;
  } else if (Array.isArray(data.actions)) {
    actionsData = data.actions;
  }

  return (
    <div className="min-h-screen bg-[#020617] text-white selection:bg-violet-500/30">
      <Sidebar />

      <div className="ml-64 min-h-screen p-8">
        <Header />

        {/* BACKGROUND GLOWS */}
        <div className="fixed top-0 left-64 w-full h-full overflow-hidden pointer-events-none">
          <div className="absolute top-[-10%] right-[-10%] w-[50%] h-[50%] bg-violet-600/5 rounded-full blur-[120px]" />
          <div className="absolute bottom-[-10%] left-[-10%] w-[50%] h-[50%] bg-indigo-600/5 rounded-full blur-[120px]" />
        </div>

        <div className="relative z-10">
          {/* STATS */}
          <div className="grid md:grid-cols-3 gap-6 mb-8">
            <StatsCard title="Total Changes" value={totalChanges} />
            <StatsCard title="Added Items" value={formattedChanges.added.length} />
            <StatsCard title="Impacted Areas" value={impactData.departments?.length || 0} />
          </div>

          <div className="grid lg:grid-cols-12 gap-8">
            {/* LEFT COLUMN: CHANGES & CHARTS */}
            <div className="lg:col-span-7 space-y-8">
              <div className="bg-white/5 border border-white/10 backdrop-blur-xl rounded-[2rem] p-8">
                <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
                  Detailed Changes
                </h2>
                <div className="space-y-4">
                  <ChangeCard title="Added Rules" items={formattedChanges.added} color="green" />
                  <ChangeCard title="Removed Rules" items={formattedChanges.removed} color="red" />
                  <ChangeCard title="Updated Rules" items={formattedChanges.modified} color="yellow" />
                </div>
              </div>

              <div className="bg-white/5 border border-white/10 backdrop-blur-xl rounded-[2rem] p-8">
                <Charts changes={formattedChanges} impact={impactData} />
              </div>
            </div>

            {/* RIGHT COLUMN: IMPACT & INSIGHTS */}
            <div className="lg:col-span-5 space-y-8">
              <div className="bg-white/5 border border-white/10 backdrop-blur-xl rounded-[2rem] p-8">
                <h2 className="text-xl font-bold mb-6">Impact Analysis</h2>
                <ImpactCard title="Affected Departments" items={impactData.departments} />
                <ImpactCard title="Impacted Systems" items={impactData.systems} />
                <div className="mt-6 p-4 rounded-2xl bg-white/5 border border-white/10">
                  <h4 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">Executive Summary</h4>
                  <p className="text-sm text-slate-300 leading-relaxed">
                    {impactData.summary || "No executive summary provided. Please review the detailed changes and actions."}
                  </p>
                </div>
              </div>

              <Insights changes={formattedChanges} total={totalChanges} />
            </div>
          </div>

          {/* ACTIONS ROW */}
          <div className="mt-8 bg-white/5 border border-white/10 backdrop-blur-xl rounded-[2rem] p-8">
            <h2 className="text-xl font-bold mb-6">Remediation Roadmap</h2>
            {actionsData.length > 0 ? (
              <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-6">
                {actionsData.map((a, i) => (
                  <ActionCard key={i} action={a} />
                ))}
              </div>
            ) : (
              <div className="py-20 text-center border-2 border-dashed border-white/5 rounded-3xl">
                <p className="text-slate-500 italic">No recommended actions generated for this analysis.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}