import { Badge, SourceBadge } from "./Badge";
import { PlusCircle, MinusCircle, ArrowRightLeft } from "lucide-react";

export default function ChangeCard({ title, items, color }) {
  const colorMap = {
    green: "text-emerald-400 border-emerald-500/30 bg-emerald-500/5",
    red: "text-rose-400 border-rose-500/30 bg-rose-500/5",
    yellow: "text-amber-400 border-amber-500/30 bg-amber-500/5",
  };
  
  const iconMap = {
    green: <PlusCircle className="w-4 h-4 text-emerald-400" />,
    red: <MinusCircle className="w-4 h-4 text-rose-400" />,
    yellow: <ArrowRightLeft className="w-4 h-4 text-amber-400" />
  };

  return (
    <div className={`mb-6 p-6 rounded-2xl border backdrop-blur-md transition-all ${colorMap[color]}`}>
      <div className="flex items-center gap-3 mb-5">
        {iconMap[color]}
        <h3 className="font-bold text-sm uppercase tracking-widest text-white">
          {title}
        </h3>
        <Badge className="ml-auto bg-black/20" variant="default">
          {items?.length || 0} Items
        </Badge>
      </div>

      <div className="space-y-4">
        {items?.length > 0 ? (
          items.map((item, i) => (
            <div key={i} className="flex flex-col gap-2 p-4 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors">
              <div className="flex justify-between items-start gap-4">
                <span className="text-sm font-medium text-slate-200 leading-relaxed">
                  {item.summary || item.description || item}
                </span>
                {item.category && (
                  <Badge variant="category" className="shrink-0">
                    {item.category}
                  </Badge>
                )}
              </div>
              
              {(item.section || item.source) && (
                <div className="flex items-center gap-3 mt-2">
                  {item.section && (
                    <span className="text-xs font-mono text-slate-500 bg-black/20 px-2 py-1 rounded">
                      Sec: {item.section}
                    </span>
                  )}
                  {item.source && <SourceBadge source={item.source} />}
                </div>
              )}
            </div>
          ))
        ) : (
          <div className="text-slate-500 italic p-4 text-center border border-dashed border-white/10 rounded-xl">
            No changes detected
          </div>
        )}
      </div>
    </div>
  );
}