import { useState } from "react";
import { Clock, User } from "lucide-react";
import { Badge } from "./Badge";

export default function ActionCard({ action }) {
  const [completed, setCompleted] = useState(false);

  const priorityLevel = action.priority ? action.priority.toLowerCase() : "medium";
  const priorityVariant = priorityLevel === "high" || priorityLevel === "critical" ? "high" : priorityLevel === "low" ? "low" : "medium";

  return (
    <div className={`relative bg-white/5 border p-5 rounded-3xl transition-all duration-300 group ${
      completed 
        ? 'border-emerald-500/30 opacity-70 bg-emerald-500/5' 
        : 'border-white/10 hover:border-violet-500/50 hover:shadow-xl hover:shadow-violet-500/10 hover:-translate-y-1'
    }`}>
      {/* Checkbox UI overlay */}
      <button 
        onClick={() => setCompleted(!completed)}
        className={`absolute top-5 right-5 w-6 h-6 rounded-md border-2 flex items-center justify-center transition-all ${
          completed ? 'bg-emerald-500 border-emerald-500' : 'border-slate-500 hover:border-violet-400 bg-black/20'
        }`}
      >
        {completed && (
          <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
             <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
          </svg>
        )}
      </button>

      <div className="pr-10">
        <div className="flex justify-between items-start mb-3">
          <h3 className={`font-bold text-base transition-colors ${completed ? 'text-emerald-400 line-through' : 'text-white group-hover:text-violet-400'}`}>
            {action.step || action.action || action.title}
          </h3>
        </div>

        <p className={`text-sm leading-relaxed mb-5 ${completed ? 'text-slate-500' : 'text-slate-300'}`}>
          {action.description || action.summary}
        </p>

        <div className="flex flex-wrap items-center gap-3 mt-auto pt-4 border-t border-white/5">
          <Badge variant={priorityVariant} className="px-2 py-0.5 text-[10px] uppercase tracking-wider">
            {action.priority || "Medium"} Priority
          </Badge>
          
          <div className="flex items-center gap-1.5 text-xs font-medium text-slate-400 bg-black/20 px-2.5 py-1 rounded-md">
            <Clock className="w-3.5 h-3.5 text-slate-500" />
            {action.timeline || action.due_date || "Immediate"}
          </div>
          
          <div className="flex items-center gap-1.5 text-xs font-medium text-slate-400 bg-black/20 px-2.5 py-1 rounded-md">
            <User className="w-3.5 h-3.5 text-slate-500" />
            {action.owner || action.assignee || "Compliance Team"}
          </div>
        </div>
      </div>
    </div>
  );
}