export default function ImpactCard({ impact }) {
  return (
    <div className="p-4 rounded-xl shadow bg-white">
      <h3 className="text-lg font-semibold mb-2">Impact Analysis</h3>

      <div>
        <p className="font-medium">Departments:</p>
        <ul className="list-disc ml-6">
          {impact?.departments?.map((d, i) => (
            <li key={i}>{d}</li>
          ))}
        </ul>
      </div>

      <div className="mt-3">
        <p className="font-medium">Systems:</p>
        <ul className="list-disc ml-6">
          {impact?.systems?.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}