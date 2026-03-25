"use client";

import { LayoutDashboard, Upload, History, Settings } from "lucide-react";
import Link from "next/link";

export default function Sidebar() {
  return (
    <div className="fixed top-0 left-0 h-screen w-64 bg-gray-900 text-white p-6 flex flex-col">

      {/* LOGO */}
      <h2 className="text-2xl font-bold mb-10 text-blue-400">
        RegIntel AI
      </h2>

      {/* NAV */}
      <nav className="space-y-4">
        <Link href="/dashboard" className="flex items-center gap-2 hover:text-blue-400">
          <LayoutDashboard size={18} /> Dashboard
        </Link>

        <Link href="/" className="flex items-center gap-2 hover:text-blue-400">
          <Upload size={18} /> Upload
        </Link>

        <Link href="#" className="flex items-center gap-2 hover:text-blue-400">
          <History size={18} /> History
        </Link>

        <Link href="#" className="flex items-center gap-2 hover:text-blue-400">
          <Settings size={18} /> Settings
        </Link>
      </nav>

    </div>
  );
}