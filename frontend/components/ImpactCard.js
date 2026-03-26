import { Badge } from "./Badge";

export default function ImpactCard({ title, items = [], type = "department" }) {
  const isDepartment = type === "department" || title.toLowerCase().includes("department");
  const badgeVariant = isDepartment ? "category" : "default";

  return (
    <div className="mb-6 p-5 rounded-2xl bg-white/5 border border-white/10 hover:border-white/20 transition-all">
      <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4 flex items-center justify-between">
        {title}
        <span className="bg-black/20 text-slate-500 px-2 py-0.5 rounded-full text-[10px]">
          {items.length} Affected
        </span>
      </h3>

      <div className="flex flex-wrap gap-2.5">
        {items.length > 0 ? (
          items.map((item, idx) => (
            <Badge key={idx} variant={badgeVariant} className="px-3 py-1.5 text-sm shadow-sm">
              {item}
            </Badge>
          ))
        ) : (
          <div className="w-full text-center py-4 bg-black/10 rounded-xl border border-dashed border-white/5">
            <span className="text-slate-500 text-sm italic">No direct impact found</span>
          </div>
        )}
      </div>
    </div>
  );
}