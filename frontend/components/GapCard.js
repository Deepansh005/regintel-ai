import { RiskIcon, Badge, SourceBadge } from "./Badge";
import { AlertTriangle } from "lucide-react";

export default function GapCard({ gap }) {
  // Infer risk from gap or default
  const risk = gap.risk_level || gap.risk || "Medium";
  const riskVariant = risk.toLowerCase() === 'high' ? 'high' : risk.toLowerCase() === 'low' ? 'low' : 'medium';

  return (
    <div className={`mb-4 p-5 rounded-2xl border bg-white/5 backdrop-blur-sm transition-all hover:bg-white/10 ${
      risk.toLowerCase() === 'high' ? 'border-rose-500/30 hover:border-rose-500/50' : 'border-white/10 hover:border-white/20'
    }`}>
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center gap-2">
          <RiskIcon level={risk} />
          <h3 className="font-bold text-white text-base leading-tight">
            {gap.issue || gap.title || gap.summary || "Compliance Gap"}
          </h3>
        </div>
        <Badge variant={riskVariant} className="uppercase tracking-widest text-[10px]">
          {risk} Risk
        </Badge>
      </div>

      <div className="mt-4 space-y-3">
        {gap.regulation_requirement && (
          <div className="text-sm bg-rose-500/5 border border-rose-500/10 p-3 rounded-xl rounded-tl-none">
            <div className="text-xs font-semibold text-rose-400 mb-1 tracking-wider uppercase">Regulation Requirement</div>
            <div className="text-slate-300 leading-relaxed">{gap.regulation_requirement}</div>
          </div>
        )}
        
        {gap.policy_status && (
          <div className="text-sm bg-indigo-500/5 border border-indigo-500/10 p-3 rounded-xl rounded-tr-none">
            <div className="text-xs font-semibold text-indigo-400 mb-1 tracking-wider uppercase">Current Policy</div>
            <div className="text-slate-300 leading-relaxed">{gap.policy_status}</div>
          </div>
        )}
      </div>

      {(gap.source || gap.references) && (
        <div className="mt-4 pt-4 border-t border-white/5">
          <SourceBadge source={gap.source || gap.references} />
        </div>
      )}
    </div>
  );
}
