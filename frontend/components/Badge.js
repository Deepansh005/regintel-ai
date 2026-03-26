import React from 'react';
import { AlertOctagon, AlertTriangle, ShieldCheck, FileText } from 'lucide-react';

export function Badge({ children, variant = 'default', className = '' }) {
  const variants = {
    default: 'bg-white/10 text-white border-white/20',
    high: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    medium: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    low: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    source: 'bg-violet-500/10 text-violet-300 border-violet-500/30 hover:bg-violet-500/20 cursor-pointer',
    category: 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20',
  };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border transition-colors ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
}

export function SourceBadge({ source }) {
  if (!source) return null;
  return (
    <Badge variant="source" className="group flex items-center gap-1.5 mt-2 max-w-fit">
      <FileText className="w-3 h-3 text-violet-400 group-hover:text-violet-300 transition-colors" />
      <span className="truncate max-w-[200px]">{source}</span>
    </Badge>
  );
}

export function RiskIcon({ level, className = "w-5 h-5" }) {
  switch (level?.toLowerCase()) {
    case 'high':
    case 'critical':
      return <AlertOctagon className={`text-rose-400 ${className}`} />;
    case 'medium':
      return <AlertTriangle className={`text-amber-400 ${className}`} />;
    case 'low':
      return <ShieldCheck className={`text-emerald-400 ${className}`} />;
    default:
      return <AlertTriangle className={`text-slate-400 ${className}`} />;
  }
}
