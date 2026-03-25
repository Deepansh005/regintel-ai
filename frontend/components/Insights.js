"use client";

export default function Insights({ changes, total }) {
  return (
    <div className="bg-white p-6 rounded-xl shadow mt-6">
      <h3 className="font-semibold mb-4">AI Insights</h3>

      <ul className="space-y-2 text-gray-700">
        <li>📊 Total changes detected: <b>{total}</b></li>
        <li>🟢 Added rules dominate ({changes.added.length})</li>
        <li>🔴 Removed items: {changes.removed.length}</li>
        <li>🟡 Modified entries: {changes.modified.length}</li>

        {changes.added.length > changes.removed.length && (
          <li className="text-green-600">
            🚀 Regulatory expansion trend detected
          </li>
        )}

        {changes.removed.length > 0 && (
          <li className="text-red-600">
            ⚠️ Some compliance rules removed — review required
          </li>
        )}
      </ul>
    </div>
  );
}