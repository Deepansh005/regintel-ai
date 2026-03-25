export default function StatsCard({ title, value }) {
  return (
    <div className="bg-white rounded-xl shadow p-5 hover:shadow-lg transition">

      <p className="text-gray-500 text-sm">{title}</p>

      <h2 className="text-2xl font-bold mt-2 text-gray-800">
        {value}
      </h2>

    </div>
  );
}