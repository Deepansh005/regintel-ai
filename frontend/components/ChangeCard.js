export default function ChangeCard({ type, items }) {
  const colorMap = {
    added: "bg-green-100 text-green-700",
    removed: "bg-red-100 text-red-700",
    modified: "bg-yellow-100 text-yellow-700",
  };

  return (
    <div className="p-4 rounded-xl shadow bg-white">
      <h3 className={`inline-block px-3 py-1 rounded ${colorMap[type]}`}>
        {type.toUpperCase()}
      </h3>

      <ul className="mt-3 space-y-2">
        {items?.map((item, index) => (
          <li key={index} className="border p-2 rounded">
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}