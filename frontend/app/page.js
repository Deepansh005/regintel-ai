"use client";

import { useState } from "react";
import { uploadDocuments } from "../services/api";

export default function Home() {
  const [oldFile, setOldFile] = useState(null);
  const [newFile, setNewFile] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!oldFile || !newFile) {
      alert("Please upload both files");
      return;
    }

    setLoading(true);

    try {
      const data = await uploadDocuments(oldFile, newFile);

      localStorage.setItem("result", JSON.stringify(data));
      window.location.href = "/dashboard";
    } catch (err) {
      console.error(err);
      alert("Error uploading files");
    }

    setLoading(false);
  };

  return (
    <div className="flex flex-col items-center justify-center h-screen gap-6">
      <h1 className="text-3xl font-bold">RegIntel AI</h1>

      <input
        type="file"
        accept="application/pdf"
        onChange={(e) => setOldFile(e.target.files[0])}
      />

      <input
        type="file"
        accept="application/pdf"
        onChange={(e) => setNewFile(e.target.files[0])}
      />

      <button
        onClick={handleSubmit}
        className="bg-blue-500 text-white px-6 py-2 rounded"
      >
        {loading ? "Processing..." : "Upload & Analyze"}
      </button>
    </div>
  );
}