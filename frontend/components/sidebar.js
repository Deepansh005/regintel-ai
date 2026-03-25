"use client";

import { LayoutDashboard, Upload, History, Settings, Shield, LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = () => {
    localStorage.removeItem("regintel_user");
    router.push("/");
  };

  const menuItems = [
    { name: "Dashboard", icon: <LayoutDashboard className="w-5 h-5" />, path: "/dashboard" },
    { name: "New Analysis", icon: <Upload className="w-5 h-5" />, path: "/upload" },
    { name: "History", icon: <History className="w-5 h-5" />, path: "#" },
    { name: "Settings", icon: <Settings className="w-5 h-5" />, path: "#" },
  ];

  return (
    <div className="fixed top-0 left-0 h-screen w-64 border-r border-white/5 bg-[#020617] flex flex-col z-50">
      <div className="p-8">
        <div className="flex items-center gap-3 mb-10">
          <div className="w-9 h-9 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-violet-500/20">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <span className="text-lg font-bold tracking-tight text-white">RegIntel AI</span>
        </div>

        <nav className="space-y-2">
          {menuItems.map((item) => (
            <Link
              key={item.name}
              href={item.path}
              className={`flex items-center gap-3 px-4 py-3 rounded-2xl text-sm font-medium transition-all group ${pathname === item.path
                  ? "bg-violet-600/10 text-violet-400 border border-violet-500/20"
                  : "text-slate-400 hover:text-white hover:bg-white/5"
                }`}
            >
              <span className={`${pathname === item.path ? "text-violet-400" : "text-slate-500 group-hover:text-slate-300"}`}>
                {item.icon}
              </span>
              {item.name}
            </Link>
          ))}
        </nav>
      </div>

      <div className="mt-auto p-8">
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-4 py-3 rounded-2xl text-sm font-medium text-slate-500 hover:text-rose-400 hover:bg-rose-500/5 transition-all group"
        >
          <LogOut className="w-5 h-5 group-hover:rotate-12 transition-transform" />
          Log Out
        </button>
      </div>
    </div>
  );
}