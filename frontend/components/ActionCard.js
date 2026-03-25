export default function ActionCard({ action }) {
  // Extract values safely from your backend structure
  const title = action?.step || "No title";
  const description = action?.description || "No description available";

  return (
    <div className="p-5 rounded-2xl shadow-md bg-white border border-gray-100 hover:shadow-lg transition-all">
      
      {/* Title */}
      <h3 className="text-lg font-semibold text-gray-800">
        {title}
      </h3>

      {/* Description */}
      <p className="text-sm text-gray-600 mt-2">
        {description}
      </p>

    </div>
  );
}