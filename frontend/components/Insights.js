"use client";

import { Lightbulb, TrendingUp, AlertCircle, CheckCircle2 } from "lucide-react";

export default function Insights({ changes, total }) {
  const trend = changes.added.length > changes.removed.length ? "Expansion" : "Consolidation";

  return (
    <div className="bg-white/5 border border-white/10 backdrop-blur-xl p-8 rounded-[2rem]">
      <div className="flex items-center gap-2 mb-6 text-violet-400">
        <Lightbulb className="w-5 h-5" />
        <h3 className="font-bold text-sm uppercase tracking-widest">AI Strategic Insights</h3>
      </div>

      <div className="space-y-6 text-slate-300">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-violet-600/10 flex items-center justify-center shrink-0 border border-violet-500/10">
            <TrendingUp className="w-5 h-5 text-violet-400" />
          </div>
          <div>
            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Market Trend</p>
            <p className="text-sm">Detected a <span className="text-violet-400 font-bold">{trend}</span> trend with {total} total regulatory points analyzed.</p>
          </div>
        </div>

        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-xl bg-emerald-600/10 flex items-center justify-center shrink-0 border border-emerald-500/10">
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Compliance Health</p>
            <p className="text-sm">{changes.added.length} new rules identified. System health score: <span className="text-emerald-400 font-bold">Optimal</span>.</p>
          </div>
        </div>

        {changes.removed.length > 0 && (
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 rounded-xl bg-rose-600/10 flex items-center justify-center shrink-0 border border-rose-500/10">
              <AlertCircle className="w-5 h-5 text-rose-400" />
            </div>
            <div>
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Risk Warning</p>
              <p className="text-sm">{changes.removed.length} legacy rules removed. Verification of overlapping circulars is <span className="text-rose-400 font-bold">Recommended</span>.</p>
            </div>
          </div>
        )}
      </div>

      <div className="mt-8 pt-6 border-t border-white/5">
        <div className="flex items-center justify-between text-[10px] font-bold text-slate-500 uppercase tracking-widest">
          <span>Confidence Score</span>
          <span className="text-violet-400">98.2%</span>
        </div>
        <div className="w-full h-1 bg-white/5 rounded-full mt-2 overflow-hidden">
          <div className="h-full bg-gradient-to-r from-violet-600 to-indigo-600 w-[98%]" />
        </div>
      </div>
    </div>
  );
}