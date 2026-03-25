export default function ImpactCard({ title, items = [] }) {
  return (
    <div className="mb-4">
      <h3 className="text-sm font-medium text-gray-700 mb-2">
        {title}
      </h3>

      <div className="flex flex-wrap gap-2">
        {items.length > 0 ? (
          items.map((item, idx) => (
            <span
              key={idx}
              className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm"
            >
              {item}
            </span>
          ))
        ) : (
          <span className="text-gray-400">No impact</span>
        )}
      </div>
    </div>
  );
}