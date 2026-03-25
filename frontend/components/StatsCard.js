export default function StatsCard({ title, value }) {
  return (
    <div className="bg-white/5 border border-white/10 backdrop-blur-xl p-6 rounded-3xl">
      <p className="text-slate-400 text-sm font-medium uppercase tracking-wider mb-1">{title}</p>
      <p className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
        {value}
      </p>
    </div>
  );
}