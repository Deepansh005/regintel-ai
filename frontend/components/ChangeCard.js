export default function ChangeCard({ title, items, color }) {
  const colorMap = {
    green: "text-emerald-400",
    red: "text-rose-400",
    yellow: "text-amber-400",
  };

  const borderMap = {
    green: "border-emerald-500/20 bg-emerald-500/5",
    red: "border-rose-500/20 bg-rose-500/5",
    yellow: "border-amber-500/20 bg-amber-500/5",
  }

  return (
    <div className={`mb-4 p-4 rounded-2xl border ${borderMap[color]}`}>
      <h3 className={`font-bold text-sm uppercase tracking-widest ${colorMap[color]}`}>
        {title}
      </h3>

      <ul className="mt-3 space-y-2 text-sm text-slate-300">
        {items?.length > 0 ? (
          items.map((item, i) => (
            <li key={i} className="flex gap-2">
              <span className="opacity-50 mt-1">•</span>
              <span>{item.summary || item}</span>
            </li>
          ))
        ) : (
          <li className="text-slate-500 italic">No changes detected</li>
        )}
      </ul>
    </div>
  );
}