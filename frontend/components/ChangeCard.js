export default function ChangeCard({ title, items, color }) {
  const colorMap = {
    green: "text-green-600",
    red: "text-red-600",
    yellow: "text-yellow-600",
  };

  return (
    <div className="mb-4">
      <h3 className={`font-semibold ${colorMap[color]}`}>
        {title}
      </h3>

      <ul className="mt-2 space-y-1 text-sm text-gray-600">
        {items?.length > 0 ? (
          items.map((item, i) => (
            <li key={i}>• {item.summary || item}</li>
          ))
        ) : (
          <li>No data</li>
        )}
      </ul>
    </div>
  );
}