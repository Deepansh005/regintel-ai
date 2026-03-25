import { CheckCircle2, AlertTriangle, Clock } from "lucide-react";

export default function ActionCard({ action }) {
  const priorityColors = {
    High: "text-rose-400 bg-rose-500/10 border-rose-500/20",
    Medium: "text-amber-400 bg-amber-500/10 border-amber-500/20",
    Low: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  };

  return (
    <div className="bg-white/5 border border-white/10 p-5 rounded-3xl transition-all hover:border-violet-500/30 group">
      <div className="flex justify-between items-start mb-3">
        <h3 className="font-bold text-white group-hover:text-violet-400 transition-colors">
          {action.step}
        </h3>
        {action.priority && (
          <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border ${priorityColors[action.priority] || priorityColors.Medium}`}>
            {action.priority}
          </span>
        )}
      </div>

      <p className="text-sm text-slate-400 leading-relaxed mb-4">
        {action.description}
      </p>

      <div className="flex items-center gap-4 text-[11px] font-bold text-slate-500 uppercase tracking-widest">
        <div className="flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5" />
          {action.timeline || "Immediate"}
        </div>
        <div className="flex items-center gap-1.5">
          <CheckCircle2 className="w-3.5 h-3.5" />
          {action.owner || "Compliance"}
        </div>
      </div>
    </div>
  );
}