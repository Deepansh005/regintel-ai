"use client";

import Link from "next/link";
import { ArrowRight, Shield, Zap, BarChart3, Globe } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#F8FAFC] text-slate-900 selection:bg-violet-200 font-sans font-medium overflow-hidden">
      {/* Navbar */}
      <nav className="fixed top-0 w-full z-50 border-b border-slate-200/50 bg-white/70 backdrop-blur-xl shadow-sm">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-violet-500/20">
              <Shield className="w-6 h-6 text-white" />
            </div>
            <span className="text-xl font-extrabold tracking-tight text-slate-900">RegIntel AI</span>
          </div>

          <div className="hidden md:flex items-center gap-8 text-sm font-bold text-slate-500">
            <a href="#features" className="hover:text-violet-600 transition-colors">Features</a>
            <a href="#solutions" className="hover:text-violet-600 transition-colors">Solutions</a>
            <a href="#pricing" className="hover:text-violet-600 transition-colors">Pricing</a>
          </div>

          <div className="flex items-center gap-4">
            <Link
              href="/login"
              className="px-5 py-2 text-sm font-bold text-slate-600 hover:text-slate-900 transition-colors"
            >
              Sign In
            </Link>
            <Link
              href="/register"
              className="px-6 py-3 text-sm font-bold bg-slate-900 text-white rounded-full hover:bg-slate-800 transition-all shadow-[0_10px_20px_-10px_rgba(0,0,0,0.3)] active:scale-95"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-48 pb-20 overflow-hidden">
        {/* Anti-Gravity Holographic Background Glows */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-[600px] bg-gradient-to-b from-violet-300/30 to-transparent blur-[120px] pointer-events-none" />
        <div className="absolute top-20 right-0 w-[500px] h-[500px] bg-indigo-300/20 rounded-full blur-[140px] pointer-events-none" />
        <div className="absolute top-40 left-0 w-[400px] h-[400px] bg-blue-300/20 rounded-full blur-[120px] pointer-events-none" />

        <div className="max-w-7xl mx-auto px-6 relative z-10 flex flex-col items-center text-center">
          <div className="max-w-[54rem]">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-violet-100 border border-violet-200 text-violet-700 text-xs font-extrabold uppercase tracking-widest mb-8 shadow-sm">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-violet-500"></span>
              </span>
              v2.0 is now live
            </div>

            <h1 className="text-5xl sm:text-6xl md:text-[5rem] font-extrabold leading-[1.05] tracking-tight mb-8">
              Regulatory Intelligence, <br />
              <span className="bg-clip-text text-transparent bg-gradient-to-r from-violet-600 via-indigo-600 to-cyan-500">
                Redefined by AI.
              </span>
            </h1>

            <p className="text-lg md:text-xl text-slate-500 leading-relaxed mb-12 max-w-3xl mx-auto font-medium">
              Automate compliance tracking, analyze regulatory updates in seconds, and stay ahead of changes from RBI, SEBI, and global regulators without leaving your dashboard.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/register"
                className="w-full sm:w-auto px-8 py-4.5 bg-gradient-to-r from-violet-600 to-indigo-600 rounded-full font-bold text-white flex items-center justify-center gap-2 shadow-[0_20px_40px_-10px_rgba(124,58,237,0.4)] hover:shadow-[0_25px_50px_-10px_rgba(124,58,237,0.5)] hover:-translate-y-1 transition-all active:scale-[0.98] group"
              >
                Start Free Trial
                <ArrowRight className="w-5 h-5 group-hover:translate-x-1.5 transition-transform" />
              </Link>
              <button className="w-full sm:w-auto px-8 py-4.5 bg-white border border-slate-200 rounded-full font-bold hover:bg-slate-50 hover:shadow-sm hover:-translate-y-1 transition-all active:scale-[0.98] text-slate-700 shadow-sm">
                Watch Demo
              </button>
            </div>

            <div className="mt-20 flex items-center justify-center gap-10 opacity-70 grayscale">
              <span className="font-black text-2xl tracking-tighter text-slate-400">RBI</span>
              <span className="font-black text-2xl tracking-tighter text-slate-400">SEBI</span>
              <span className="font-black text-2xl tracking-tighter text-slate-400">BSE</span>
              <span className="font-black text-2xl tracking-tighter text-slate-400">NSE</span>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Grid */}
      <section id="features" className="py-32 bg-white relative z-20">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center max-w-2xl mx-auto mb-20 text-slate-900">
            <h2 className="text-4xl md:text-5xl font-extrabold mb-6 tracking-tight">Built for Precise Compliance</h2>
            <p className="text-slate-500 text-lg leading-relaxed font-medium">Advanced AI inference engines designed to silently handle the complexity of modern financial regulations.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <FeatureCard
              icon={<Zap className="w-6 h-6 text-violet-600" />}
              title="Instant Comparison"
              description="Identify exactly what changed between two versions of any regulatory circular in seconds."
            />
            <FeatureCard
              icon={<Shield className="w-6 h-6 text-indigo-600" />}
              title="Impact Analysis"
              description="Get automated mapping of changes to your departments, systems, and internal policies."
            />
            <FeatureCard
              icon={<BarChart3 className="w-6 h-6 text-cyan-500" />}
              title="Actionable Insights"
              description="Transform abstract rules into step-by-step compliance tasks assigned to your teams."
            />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 border-t border-slate-200 bg-white">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-lg flex items-center justify-center shadow-sm">
                <Shield className="w-4 h-4 text-white" />
            </div>
            <span className="font-extrabold text-slate-900 tracking-tight">RegIntel AI</span>
          </div>
          <p className="text-sm text-slate-500 font-medium">© 2026 RegIntel AI. All rights reserved.</p>
          <div className="flex items-center gap-6 text-sm font-bold text-slate-400">
            <a href="#" className="hover:text-slate-900 transition-colors">Privacy</a>
            <a href="#" className="hover:text-slate-900 transition-colors">Terms</a>
            <a href="#" className="hover:text-slate-900 transition-colors">Cookies</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({ icon, title, description }) {
  return (
    <div className="p-10 rounded-[2rem] bg-white border border-slate-100 shadow-[0_15px_40px_-15px_rgba(0,0,0,0.05)] hover:shadow-[0_40px_80px_-20px_rgba(124,58,237,0.15)] hover:border-violet-200 transition-all duration-300 group hover:-translate-y-2">
      <div className="w-14 h-14 rounded-2xl bg-slate-50 border border-slate-100 flex items-center justify-center mb-8 group-hover:bg-violet-50 group-hover:border-violet-100 group-hover:scale-110 transition-all duration-300 shadow-sm">
        {icon}
      </div>
      <h3 className="text-2xl font-extrabold mb-4 text-slate-900 tracking-tight">{title}</h3>
      <p className="text-slate-500 leading-relaxed font-medium">
        {description}
      </p>
    </div>
  );
}