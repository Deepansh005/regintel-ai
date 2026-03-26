"use client";

import { useEffect, useState } from "react";
import Sidebar from "../../components/sidebar";
import Header from "../../components/Header";
import StatsCard from "../../components/StatsCard";
import ChangeCard from "../../components/ChangeCard";
import ImpactCard from "../../components/ImpactCard";
import ActionCard from "../../components/ActionCard";
import GapCard from "../../components/GapCard";
import Charts from "../../components/Charts";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Upload, ArrowRight, AlertOctagon, RefreshCw } from "lucide-react";
import { RiskIcon, Badge } from "../../components/Badge";

export default function Dashboard() {
  const [data, setData] = useState(null);
  const router = useRouter();

  useEffect(() => {
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
      <div className="ml-64 w-full p-8 flex flex-col relative z-10 min-h-screen">
        <Header />
        <div className="flex-1 flex flex-col items-center justify-center mt-[-60px]">
          <div className="w-20 h-20 bg-white/5 rounded-3xl flex items-center justify-center mb-6 border border-white/10 shadow-[0_0_50px_-10px_rgba(139,92,246,0.3)]">
            <Upload className="w-10 h-10 text-violet-400" />
          </div>
          <h2 className="text-3xl font-bold mb-3 tracking-tight">Dashboard Empty</h2>
          <p className="text-slate-400 mb-8 max-w-md text-center leading-relaxed">Your compliance dashboard is waiting for data. Upload regulatory circulars to automatically generate AI insights, impact analysis, and compliance workflows.</p>
          <Link href="/upload" className="px-8 py-4 bg-white text-black rounded-full font-bold flex items-center gap-3 hover:bg-slate-200 transition-all active:scale-95 group shadow-xl">
            Compare Circulars
            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
          </Link>
        </div>
      </div>
    </div>
  );

  // Safely parse Strict Contract
  const changesRaw = data.changes?.changes || data.changes || [];
  const changesArray = Array.isArray(changesRaw) ? changesRaw : (
    [...(changesRaw.added||[]), ...(changesRaw.modified||[]), ...(changesRaw.removed||[])]
  );
  
  const formattedChanges = {
    added: changesArray.filter((c) => c.type === "added") || [],
    removed: changesArray.filter((c) => c.type === "removed") || [],
    modified: changesArray.filter((c) => c.type === "modified") || [],
  };

  const totalChanges = formattedChanges.added.length + formattedChanges.removed.length + formattedChanges.modified.length;
  
  const gapsRaw = data.compliance_gaps?.gaps || data.compliance_gaps || [];
  const gapsArray = Array.isArray(gapsRaw) ? gapsRaw : [];
  const criticalGapsCount = gapsArray.filter(g => g.risk_level?.toLowerCase() === 'high' || g.risk?.toLowerCase() === 'high').length;

  const impactData = data.impact?.impact || data.impact || { departments: [], systems: [], summary: "" };
  
  const actionsRaw = data.actions?.actions || data.actions || [];
  const actionsData = Array.isArray(actionsRaw) ? actionsRaw : [];

  // Determine overall risk
  const overallRisk = criticalGapsCount > 0 ? "High" : gapsArray.length > 0 ? "Medium" : "Low";

  return (
    <div className="min-h-screen bg-[#020617] text-white selection:bg-violet-500/30 font-sans">
      <Sidebar />

      <div className="ml-64 min-h-screen p-8 relative">
        <Header />

        {/* Global Glow */}
        <div className="fixed top-0 left-64 w-full h-full overflow-hidden pointer-events-none z-0">
          <div className="absolute top-[-20%] right-[-10%] w-[60%] h-[60%] bg-violet-600/5 rounded-full blur-[140px]" />
          <div className="absolute bottom-[-10%] left-[-10%] w-[50%] h-[50%] bg-indigo-600/5 rounded-full blur-[120px]" />
        </div>

        <div className="relative z-10 max-w-[100rem] mx-auto">
          {/* Header Row */}
          <div className="flex justify-between items-end mb-8">
            <div>
              <h1 className="text-3xl font-bold tracking-tight mb-2">Compliance Intelligence</h1>
              <p className="text-slate-400">Analysis complete. Found {totalChanges} reg changes and {gapsArray.length} policy gaps.</p>
            </div>
            <div className="flex gap-4">
              <Link href="/upload" className="flex items-center gap-2 bg-white/5 border border-white/10 hover:bg-white/10 px-4 py-2 rounded-xl text-sm font-semibold transition-colors">
                <RefreshCw className="w-4 h-4" />
                New Analysis
              </Link>
              <button className="flex items-center gap-2 bg-violet-600 hover:bg-violet-500 px-6 py-2 rounded-xl text-sm font-bold shadow-[0_0_20px_-5px_rgba(139,92,246,0.5)] transition-all">
                Export Report
              </button>
            </div>
          </div>

          {/* A. Executive Summary Panels */}
          <div className="grid md:grid-cols-4 gap-6 mb-8">
            <div className={`p-6 rounded-3xl border flex items-center justify-between col-span-1 bg-white/5 backdrop-blur-xl ${
              overallRisk === 'High' ? 'border-rose-500/30' : overallRisk === 'Medium' ? 'border-amber-500/30' : 'border-emerald-500/30'
            }`}>
              <div>
                <p className="text-slate-400 text-xs font-bold uppercase tracking-widest mb-1">Overall Risk Level</p>
                <p className={`text-2xl font-bold ${
                  overallRisk === 'High' ? 'text-rose-400' : overallRisk === 'Medium' ? 'text-amber-400' : 'text-emerald-400'
                }`}>{overallRisk} Risk</p>
              </div>
              <RiskIcon level={overallRisk} className="w-10 h-10 opacity-80" />
            </div>
            
            <StatsCard title="Total Reg Changes" value={totalChanges} />
            <StatsCard title="Compliance Gaps" value={gapsArray.length} />
            <StatsCard title="Critical Actions" value={actionsData.filter(a => a.priority?.toLowerCase() === 'high').length} />
          </div>

          <div className="grid lg:grid-cols-12 gap-8">
            {/* LEFT COLUMN: GAPS & CHANGES */}
            <div className="lg:col-span-7 space-y-8">
              
              {/* C. Compliance Gaps Panel (MOST IMPORTANT) */}
              <div className="bg-white/5 border border-white/10 backdrop-blur-xl rounded-[2rem] p-8 relative overflow-hidden">
                {criticalGapsCount > 0 && (
                  <div className="absolute top-0 right-0 w-32 h-32 bg-rose-500/10 blur-3xl rounded-full"></div>
                )}
                
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-xl font-bold flex items-center gap-3">
                    <AlertOctagon className="w-6 h-6 text-rose-400" />
                    Compliance Gaps
                  </h2>
                  <Badge variant="high">{criticalGapsCount} Critical Issues</Badge>
                </div>

                {gapsArray.length > 0 ? (
                  <div className="space-y-4 relative z-10">
                    {gapsArray.map((gap, i) => <GapCard key={i} gap={gap} />)}
                  </div>
                ) : (
                  <div className="p-8 text-center border border-dashed border-emerald-500/20 rounded-2xl bg-emerald-500/5">
                    <RiskIcon level="low" className="mx-auto mb-3" />
                    <p className="text-emerald-400 font-semibold">No compliance gaps detected!</p>
                  </div>
                )}
              </div>

              {/* B. Changes Panel */}
              <div className="bg-white/5 border border-white/10 backdrop-blur-xl rounded-[2rem] p-8">
                <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
                  Regulatory Changes
                </h2>
                <div className="space-y-4">
                  <ChangeCard title="Added Rules" items={formattedChanges.added} color="green" />
                  <ChangeCard title="Updated Rules" items={formattedChanges.modified} color="yellow" />
                  <ChangeCard title="Removed Rules" items={formattedChanges.removed} color="red" />
                </div>
              </div>
            </div>

            {/* RIGHT COLUMN: IMPACT & ACTIONS */}
            <div className="lg:col-span-5 space-y-8">
              
              {/* D. Impact Panel */}
              <div className="bg-white/5 border border-white/10 backdrop-blur-xl rounded-[2rem] p-8">
                <h2 className="text-xl font-bold mb-6">Impact Analysis</h2>
                
                {(impactData.summary || typeof impactData === "string") && (
                  <div className="mb-6 p-4 rounded-xl bg-violet-600/10 border border-violet-500/20">
                    <p className="text-sm text-violet-200 leading-relaxed font-medium">
                      {impactData.summary || impactData}
                    </p>
                  </div>
                )}

                <ImpactCard title="Affected Departments" items={impactData.departments} type="department" />
                <ImpactCard title="Impacted Systems" items={impactData.systems} type="system" />
              </div>

              <div className="bg-white/5 border border-white/10 backdrop-blur-xl rounded-[2rem] p-8 hidden xl:block">
                <Charts changes={formattedChanges} impact={impactData} />
              </div>
            </div>
          </div>

          {/* E. Actions Panel */}
          <div className="mt-8 bg-white/5 border border-white/10 backdrop-blur-xl rounded-[2rem] p-8">
            <div className="flex items-center justify-between mb-8">
              <h2 className="text-xl font-bold">Remediation Roadmap</h2>
              <Badge variant="default">{actionsData.length} Tasks Generated</Badge>
            </div>
            
            {actionsData.length > 0 ? (
              <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-6">
                {actionsData.map((a, i) => (
                  <ActionCard key={i} action={a} />
                ))}
              </div>
            ) : (
              <div className="py-20 text-center border border-dashed border-white/10 rounded-3xl bg-black/20">
                <p className="text-slate-500 italic">No remediation tasks required.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}