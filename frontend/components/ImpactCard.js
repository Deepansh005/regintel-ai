export default function ImpactCard({ title, items = [] }) {
  return (
    <div className="mb-6">
      <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-3 ml-1">
        {title}
      </h3>

      <div className="flex flex-wrap gap-2">
        {items.length > 0 ? (
          items.map((item, idx) => (
            <span
              key={idx}
              className="px-4 py-1.5 bg-violet-600/10 border border-violet-500/20 text-violet-400 rounded-full text-xs font-semibold"
            >
              {item}
            </span>
          ))
        ) : (
          <span className="text-slate-600 text-sm italic ml-1">No direct impact found</span>
        )}
      </div>
    </div>
  );
}