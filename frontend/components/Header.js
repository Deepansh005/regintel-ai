"use client";

import { useEffect, useState } from "react";
import { User, Bell, Search } from "lucide-react";

export default function Header() {
  const [user, setUser] = useState(null);

  useEffect(() => {
    const storedUser = localStorage.getItem("regintel_user");
    if (storedUser) setUser(JSON.parse(storedUser));
  }, []);

  return (
    <div className="flex justify-between items-center mb-10 relative z-10">
      <div>
        <h1 className="text-3xl font-bold text-white tracking-tight">Dashboard</h1>
        <p className="text-slate-500 text-sm mt-1 font-medium">Monitoring circulars for {user?.name || "User"}</p>
      </div>

      <div className="flex items-center gap-6">
        <div className="relative group hidden md:block">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search results..."
            className="bg-white/5 border border-white/5 rounded-full py-2.5 pl-11 pr-5 text-sm text-white focus:outline-none focus:ring-1 focus:ring-violet-500/50 w-64 transition-all"
          />
        </div>

        <button className="relative p-2.5 bg-white/5 border border-white/5 rounded-xl text-slate-400 hover:text-white transition-colors">
          <Bell className="w-5 h-5" />
          <span className="absolute top-2.5 right-2.5 w-2 h-2 bg-violet-500 rounded-full border-2 border-[#020617]" />
        </button>

        <div className="flex items-center gap-3 pl-4 border-l border-white/10">
          <div className="text-right hidden sm:block">
            <p className="text-sm font-bold text-white leading-none">{user?.name || "Deepanshu"}</p>
            <p className="text-[10px] font-bold text-violet-500 uppercase tracking-widest mt-1">Compliance Head</p>
          </div>
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center border-2 border-[#020617] shadow-lg">
            <User className="w-5 h-5 text-white" />
          </div>
        </div>
      </div>
    </div>
  );
}