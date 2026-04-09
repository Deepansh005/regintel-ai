"use client";

import Link from "next/link";
import { Shield, FileText, CheckCircle2, Building2, ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function SelectModePage() {
    const router = useRouter();
    const [user, setUser] = useState(null);

    useEffect(() => {
        const storedUser = localStorage.getItem("regintel_user");
        if (!storedUser) {
            router.push("/login");
        } else {
            setUser(JSON.parse(storedUser));
        }
    }, [router]);

    if (!user) return null;

    return (
        <div className="min-h-screen bg-[#F8FAFC] text-slate-900 selection:bg-violet-200 font-sans relative overflow-hidden flex flex-col items-center justify-center p-6">
            {/* Anti-Gravity Glows */}
            <style>{`
                @keyframes slowSpin {
                    0% { transform: rotate(0deg); opacity: 0.1; }
                    50% { transform: rotate(180deg); opacity: 0.3; }
                    100% { transform: rotate(360deg); opacity: 0.1; }
                }
            `}</style>
            <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden flex items-center justify-center">
                <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] bg-violet-400/20 rounded-full blur-[140px]" style={{ animation: 'slowSpin 25s linear infinite' }}></div>
                <div className="absolute bottom-[-10%] right-[-10%] w-[70%] h-[70%] bg-indigo-400/20 rounded-full blur-[140px]" style={{ animation: 'slowSpin 30s linear infinite reverse' }}></div>
            </div>

            <div className="relative z-10 w-full max-w-4xl">
                <div className="text-center mb-16">
                    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-violet-100 border border-violet-200 text-violet-800 text-[10px] font-extrabold uppercase tracking-widest mb-8 shadow-sm">
                        Step 1: Configuration
                    </div>
                    <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight mb-4 text-slate-900">
                        Choose Your <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-600 to-indigo-500">Analysis Path</span>
                    </h1>
                    <p className="text-slate-500 font-medium text-lg">
                        Select the regulatory context to initiate the automated upload and mapping engine.
                    </p>
                </div>

                <div className="grid md:grid-cols-3 gap-6">
                    {/* Old Regulation Selection */}
                    <button 
                        onClick={() => router.push('/upload?mode=old')}
                        className="group text-left bg-white/70 backdrop-blur-xl border border-slate-200 rounded-[2.5rem] p-8 hover:shadow-[0_40px_80px_-20px_rgba(124,58,237,0.15)] hover:-translate-y-2 hover:border-violet-300 transition-all duration-500 relative overflow-hidden"
                    >
                        <div className="absolute inset-0 bg-gradient-to-br from-violet-500/5 to-indigo-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
                        <div className="w-14 h-14 bg-slate-50 rounded-2xl border border-slate-100 flex items-center justify-center mb-6 group-hover:bg-violet-500 group-hover:border-violet-500 transition-colors shadow-sm relative z-10">
                            <FileText className="w-7 h-7 text-slate-400 group-hover:text-white transition-colors" />
                        </div>
                        <h2 className="text-2xl font-extrabold tracking-tight text-slate-900 mb-4 relative z-10">Old Regulation Analysis</h2>
                        <p className="text-slate-500 font-medium leading-relaxed mb-8 relative z-10 text-sm">
                            Compare a legacy regulatory document against your <strong>Internal Company Policy</strong> to identify historical compliance gaps.
                        </p>
                        <div className="flex items-center gap-2 text-sm font-bold text-violet-600 uppercase tracking-widest group-hover:gap-4 transition-all relative z-10 mt-auto">
                            Initialize Engine <ArrowRight className="w-4 h-4" />
                        </div>
                    </button>

                    {/* New Regulation Selection */}
                    <button 
                        onClick={() => router.push('/upload?mode=new')}
                        className="group text-left bg-white/70 backdrop-blur-xl border border-slate-200 rounded-[2.5rem] p-8 hover:shadow-[0_40px_80px_-20px_rgba(14,165,233,0.15)] hover:-translate-y-2 hover:border-blue-300 transition-all duration-500 relative overflow-hidden"
                    >
                        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-cyan-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
                        <div className="w-14 h-14 bg-slate-50 rounded-2xl border border-slate-100 flex items-center justify-center mb-6 group-hover:bg-blue-500 group-hover:border-blue-500 transition-colors shadow-sm relative z-10">
                            <CheckCircle2 className="w-7 h-7 text-slate-400 group-hover:text-white transition-colors" />
                        </div>
                        <h2 className="text-2xl font-extrabold tracking-tight text-slate-900 mb-4 relative z-10">New Regulation Update</h2>
                        <p className="text-slate-500 font-medium leading-relaxed mb-8 relative z-10 text-sm">
                            Analyze an updated circular against your <strong>Internal Company Policy</strong> to ensure your infrastructure remains compliant.
                        </p>
                        <div className="flex items-center gap-2 text-sm font-bold text-blue-600 uppercase tracking-widest group-hover:gap-4 transition-all relative z-10 mt-auto">
                            Initialize Engine <ArrowRight className="w-4 h-4" />
                        </div>
                    </button>

                    {/* All Regulation Selection */}
                    <button 
                        onClick={() => router.push('/upload?mode=all')}
                        className="group text-left bg-white/70 backdrop-blur-xl border border-slate-200 rounded-[2.5rem] p-8 hover:shadow-[0_40px_80px_-20px_rgba(16,185,129,0.15)] hover:-translate-y-2 hover:border-emerald-300 transition-all duration-500 relative overflow-hidden"
                    >
                        <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-teal-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
                        <div className="w-14 h-14 bg-slate-50 rounded-2xl border border-slate-100 flex items-center justify-center mb-6 group-hover:bg-emerald-500 group-hover:border-emerald-500 transition-colors shadow-sm relative z-10">
                            <Building2 className="w-7 h-7 text-slate-400 group-hover:text-white transition-colors" />
                        </div>
                        <h2 className="text-2xl font-extrabold tracking-tight text-slate-900 mb-4 relative z-10">Comprehensive Analysis</h2>
                        <p className="text-slate-500 font-medium leading-relaxed mb-8 relative z-10 text-sm">
                            Upload your <strong>Old Regulation</strong>, <strong>New Regulation</strong>, and <strong>Internal Policy</strong> to execute a full 3-way semantic map.
                        </p>
                        <div className="flex items-center gap-2 text-sm font-bold text-emerald-600 uppercase tracking-widest group-hover:gap-4 transition-all relative z-10 mt-auto">
                            Initialize Engine <ArrowRight className="w-4 h-4" />
                        </div>
                    </button>
                </div>
            </div>
            
            <button onClick={() => { localStorage.removeItem("regintel_user"); router.push("/"); }} className="mt-16 text-xs font-bold text-slate-400 uppercase tracking-widest hover:text-slate-900 transition-colors z-10 relative">
                Sign Out
            </button>
        </div>
    );
}
