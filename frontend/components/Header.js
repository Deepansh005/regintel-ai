"use client";

export default function Header() {
  return (
    <div className="flex justify-between items-center mb-6">

      <h1 className="text-2xl font-semibold text-gray-800">
        Dashboard
      </h1>

      <div className="flex items-center gap-4">
        <span className="text-gray-600">Deepanshu</span>
        <button className="bg-red-500 text-white px-3 py-1 rounded-lg">
          Logout
        </button>
      </div>

    </div>
  );
}