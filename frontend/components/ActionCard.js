export default function ActionCard({ action }) {
  return (
    <div className="bg-blue-50 border border-blue-200 p-4 rounded-lg">

      <h3 className="font-semibold text-blue-700">
        {action.step}
      </h3>

      <p className="text-sm text-gray-600 mt-1">
        {action.description}
      </p>

    </div>
  );
}