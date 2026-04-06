"use client";

import { useState, useEffect } from "react";
import { uploadDocuments } from "../../services/api";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Shield, Upload, FileText, CheckCircle2, AlertCircle, Loader2, LogOut, ArrowRight, FileCheck, Building2, User, Search, Bell, Clock } from "lucide-react";

export default function UploadPage() {
    const router = useRouter();
    const [oldFile, setOldFile] = useState(null);
    const [newFile, setNewFile] = useState(null);
    const [policyFile, setPolicyFile] = useState(null);
    const [loading, setLoading] = useState(false);
    const [user, setUser] = useState(null);
    const [progress, setProgress] = useState(0);
    const mode = typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get("mode") || "old" : "old";

    useEffect(() => {
        const storedUser = localStorage.getItem("regintel_user");
        if (!storedUser) {
            router.push("/login");
            return;
        } 
        setUser(JSON.parse(storedUser));

        const params = new URLSearchParams(window.location.search);
        if (!params.get("mode")) {
            router.push("/select-mode");
        }
    }, [router]);

    const handleLogout = () => {
        localStorage.removeItem("regintel_user");
        router.push("/login");
    };

    const handleSubmit = async () => {
        if (mode === "old" && (!oldFile || !policyFile)) {
            alert("Please upload Old Policy and Internal Policy.");
            return;
        }
        if (mode === "new" && (!newFile || !policyFile)) {
            alert("Please upload New Policy and Internal Policy.");
            return;
        }

        setLoading(true);
        setProgress(10);

        try {
            const formData = new FormData();
            formData.append("mode", mode);
            if (oldFile) formData.append("old_file", oldFile);
            if (newFile) formData.append("new_file", newFile);
            if (policyFile) formData.append("policy_file", policyFile);

            const res = await fetch("http://127.0.0.1:8000/upload-documents", {
                method: "POST",
                body: formData,
            });

            const data = await res.json();
            pollStatus(data.task_id);

        } catch (err) {
            console.error("Upload failed:", err);
            alert("Error uploading files: " + err.message);
            setLoading(false);
            setProgress(0);
        }
    };

    async function pollStatus(taskId) {
        const interval = setInterval(async () => {
            const res = await fetch(`http://127.0.0.1:8000/status/${taskId}`);
            const data = await res.json();

            setProgress((prev) => {
                if (data.status === "processing") {
                    if (prev < 30) return prev + 5;        // extracting
                    if (prev < 60) return prev + 3;        // analyzing
                    if (prev < 85) return prev + 2;        // generating
                    return prev;
                }
                return prev;
            });

            if (data.status === "completed") {
                clearInterval(interval);
                setProgress(100);
                setTimeout(() => {
                    router.push("/dashboard");
                }, 800);
            }

            if (data.status === "failed") {
                clearInterval(interval);
                alert("Processing failed");
                setLoading(false);
                setProgress(0);
            }
        }, 2000);
    }

    if (!user) return null;

    if (loading) {
        return (
            <div className="min-h-screen bg-[#F8FAFC] text-slate-900 flex flex-col items-center justify-center p-6 relative overflow-hidden font-sans">
                {/* Anti-gravity styles */}
                <style>{`
                    @keyframes floatPulse {
                        0% { transform: translateY(0px) scale(1); box-shadow: 0 20px 40px -10px rgba(124,58,237,0.1); }
                        50% { transform: translateY(-10px) scale(1.02); box-shadow: 0 30px 60px -10px rgba(124,58,237,0.25); }
                        100% { transform: translateY(0px) scale(1); box-shadow: 0 20px 40px -10px rgba(124,58,237,0.1); }
                    }
                    @keyframes ray {
                        0% { opacity: 0.3; transform: rotate(0deg) scale(1); }
                        50% { opacity: 0.6; transform: rotate(180deg) scale(1.1); }
                        100% { opacity: 0.3; transform: rotate(360deg) scale(1); }
                    }
                `}</style>

                {/* Holographic Glowing Rays */}
                <div className="absolute inset-0 pointer-events-none z-0 flex items-center justify-center">
                    <div className="w-[800px] h-[800px] bg-gradient-to-r from-violet-300/30 to-indigo-300/30 rounded-full blur-[140px]" style={{ animation: 'ray 20s linear infinite' }}></div>
                </div>

                <div className="w-full max-w-lg bg-white/80 border border-white p-10 rounded-[2.5rem] backdrop-blur-2xl text-center relative z-10 shadow-[0_30px_60px_-15px_rgba(0,0,0,0.05)]" style={{ animation: 'floatPulse 4s ease-in-out infinite' }}>

                    <div className="relative mb-10 w-32 h-32 mx-auto">
                        {/* Loading rings */}
                        <div className="absolute inset-0 border-[6px] border-slate-100 rounded-full"></div>
                        <div className="absolute inset-0 border-[6px] border-violet-500 border-t-transparent border-l-transparent rounded-full animate-spin shadow-[0_0_15px_rgba(139,92,246,0.5)]"></div>
                        <div className="absolute inset-0 border-[6px] border-indigo-400 border-b-transparent border-r-transparent rounded-full animate-[spin_2s_linear_infinite_reverse] opacity-60"></div>

                        <div className="absolute inset-0 flex items-center justify-center">
                            <div className="w-16 h-16 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-2xl flex items-center justify-center shadow-lg shadow-violet-500/40 animate-pulse">
                                <Shield className="w-8 h-8 text-white" />
                            </div>
                        </div>
                    </div>

                    <h2 className="text-3xl font-extrabold tracking-tight mb-3 text-slate-900 font-sans">Synthesizing Data...</h2>
                    <p className="text-slate-500 text-sm mb-10 leading-relaxed font-medium">
                        Cross-referencing your documents against the RegIntel AI semantic core to extrapolate risk gaps and execution plans.
                    </p>

                    <div className="space-y-4 text-left">
                        <div className={`flex items-center gap-4 p-3.5 rounded-2xl transition-all ${progress > 10 ? 'bg-violet-50 border border-violet-100' : 'bg-slate-50 border border-slate-100'}`}>
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${progress > 10 ? 'bg-violet-500 text-white' : 'bg-white shadow-sm'}`}>
                                {progress > 10 ? <CheckCircle2 className="w-5 h-5" /> : <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />}
                            </div>
                            <span className={`text-sm font-bold tracking-tight ${progress > 10 ? "text-violet-700" : "text-slate-500"}`}>Extracting definitions</span>
                        </div>
                        <div className={`flex items-center gap-4 p-3.5 rounded-2xl transition-all ${progress > 40 ? 'bg-indigo-50 border border-indigo-100' : 'bg-slate-50 border border-slate-100'}`}>
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${progress > 40 ? 'bg-indigo-500 text-white' : 'bg-white shadow-sm'}`}>
                                {progress > 40 ? <CheckCircle2 className="w-5 h-5" /> : <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />}
                            </div>
                            <span className={`text-sm font-bold tracking-tight ${progress > 40 ? "text-indigo-700" : "text-slate-500"}`}>Vectorizing compliance deltas</span>
                        </div>
                        <div className={`flex items-center gap-4 p-3.5 rounded-2xl transition-all ${progress > 70 ? 'bg-cyan-50 border border-cyan-100' : 'bg-slate-50 border border-slate-100'}`}>
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${progress > 70 ? 'bg-cyan-500 text-white' : 'bg-white shadow-sm'}`}>
                                {progress > 70 ? <CheckCircle2 className="w-5 h-5" /> : <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />}
                            </div>
                            <span className={`text-sm font-bold tracking-tight ${progress > 70 ? "text-cyan-700" : "text-slate-500"}`}>Generating remediation roadmap</span>
                        </div>
                    </div>

                    <div className="mt-8 relative h-2.5 w-full bg-slate-100 rounded-full overflow-hidden border border-black/5">
                        <div className="h-full bg-gradient-to-r from-violet-500 via-indigo-500 to-cyan-400 transition-all duration-700 shadow-[0_0_10px_rgba(139,92,246,0.8)]" style={{ width: `${progress}%` }} />
                    </div>
                </div>
            </div>
        );
    }

    const FileUploadCard = ({ file, setFile, title, icon: Icon, delay, gradientFrom, gradientTo }) => (
        <div className="flex-1 flex flex-col relative z-10 group" style={{ animation: `floatItems 6s ease-in-out ${delay}s infinite` }}>
            <label className="text-[11px] font-extrabold text-slate-400 uppercase tracking-widest pl-2 mb-3 drop-shadow-sm">{title}</label>
            <div className={`relative overflow-hidden bg-white/70 backdrop-blur-2xl border border-white/80 rounded-[2rem] p-8 flex flex-col items-center justify-center transition-all duration-500 min-h-[260px] 
            hover:shadow-[0_40px_80px_-20px_rgba(124,58,237,0.3)] hover:-translate-y-4 hover:bg-white cursor-pointer shadow-[0_20px_40px_-15px_rgba(0,0,0,0.05)]`}>

                {/* Glow ring on hover */}
                <div className={`absolute inset-0 bg-gradient-to-br ${gradientFrom} ${gradientTo} opacity-0 group-hover:opacity-5 transition-opacity duration-500`}></div>

                <input
                    type="file"
                    accept="application/pdf"
                    className="absolute inset-0 opacity-0 cursor-pointer z-50"
                    onChange={(e) => setFile(e.target.files[0])}
                />

                <div className={`w-20 h-20 rounded-2xl flex items-center justify-center mb-6 transition-all duration-500 shadow-xl relative z-10 
                    ${file ? `bg-gradient-to-br ${gradientFrom} ${gradientTo} scale-110 shadow-[0_0_30px_rgba(124,58,237,0.3)]` : 'bg-slate-50 border border-slate-100 group-hover:bg-white group-hover:scale-110 group-hover:shadow-[0_0_30px_rgba(124,58,237,0.15)]'}`}>
                    {file ? <CheckCircle2 className="w-10 h-10 text-white" /> : <Icon className={`w-10 h-10 transition-colors ${file ? 'text-white' : 'text-slate-400 group-hover:text-violet-500'}`} />}
                </div>

                <p className={`font-extrabold text-center px-4 relative z-10 tracking-tight text-lg transition-colors ${file ? 'text-slate-900 bg-clip-text text-transparent bg-gradient-to-br ' + gradientFrom + ' ' + gradientTo : 'text-slate-600 group-hover:text-slate-900'}`}>
                    {file ? file.name : `Select ${title}`}
                </p>

                {!file && <p className="text-[11px] font-bold text-slate-400 mt-3 uppercase tracking-widest relative z-10 group-hover:text-violet-400 transition-colors">PDF UP TO 20MB</p>}
            </div>
        </div>
    );

    return (
        <div className="min-h-screen bg-[#F8FAFC] text-slate-900 selection:bg-violet-200 font-sans relative overflow-hidden flex flex-col">
            <style>{`
                @keyframes floatItems {
                    0% { transform: translateY(0px); }
                    50% { transform: translateY(-15px); }
                    100% { transform: translateY(0px); }
                }
                @keyframes slowSpin {
                    0% { transform: rotate(0deg); opacity: 0.1; }
                    50% { transform: rotate(180deg); opacity: 0.3; }
                    100% { transform: rotate(360deg); opacity: 0.1; }
                }
            `}</style>

            {/* Anti-Gravity Holographic Background Rays */}
            <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden flex items-center justify-center bg-gradient-to-b from-[#F8FAFC] to-[#F1F5F9]">
                <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] bg-violet-400/20 rounded-full blur-[140px]" style={{ animation: 'slowSpin 25s linear infinite' }}></div>
                <div className="absolute bottom-[-10%] right-[-10%] w-[70%] h-[70%] bg-indigo-400/20 rounded-full blur-[140px]" style={{ animation: 'slowSpin 30s linear infinite reverse' }}></div>
                <div className="absolute top-[30%] left-[20%] w-[40%] h-[40%] bg-blue-300/20 rounded-full blur-[120px]" style={{ animation: 'slowSpin 20s linear infinite' }}></div>
            </div>

            {/* Premium Top Navbar */}
            <div className="sticky top-0 z-50 w-full bg-white/70 backdrop-blur-xl border-b border-white/50 shadow-sm px-6 h-16 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                    <Link href="/dashboard" className="flex items-center gap-2.5 group">
                        <div className="w-8 h-8 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-md shadow-violet-500/20 group-hover:scale-105 transition-transform">
                            <Shield className="w-4 h-4 text-white" />
                        </div>
                        <span className="font-bold text-lg tracking-tight text-slate-900 hidden sm:block">RegIntel AI</span>
                    </Link>
                </div>

                <div className="flex items-center gap-6 ml-10 hidden lg:flex">
                    <Link href="/select-mode" className="text-sm font-bold text-slate-500 hover:text-violet-600 transition-colors flex items-center gap-2">
                        <Upload className="w-4 h-4" />
                        New Analysis
                    </Link>
                    <Link href="/dashboard#analysis-history" className="text-sm font-bold text-slate-500 hover:text-violet-600 transition-colors flex items-center gap-2">
                        <Clock className="w-4 h-4" />
                        History
                    </Link>
                </div>

                <div className="flex-1 max-w-sm mx-6 hidden xl:block">
                    <div className="relative group">
                        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within:text-violet-500 transition-colors" />
                        <input type="text" placeholder="Search..."
                            className="w-full bg-white/50 border border-slate-200 rounded-full py-2 pl-10 pr-4 text-sm text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-violet-500/20 transition-all placeholder:text-slate-400 shadow-inner" />
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    <button className="relative p-2 text-slate-500 hover:text-slate-900 transition-colors rounded-full hover:bg-slate-100">
                        <Bell className="w-5 h-5" />
                        <span className="absolute top-1.5 right-2 w-2 h-2 bg-emerald-500 rounded-full border-2 border-white" />
                    </button>
                    <div className="h-6 border-l border-slate-200 hidden sm:block" />
                    <div className="flex items-center gap-3">
                        <div className="hidden sm:block text-right">
                            <p className="text-sm font-bold text-slate-900 leading-tight">{user?.name || "User"}</p>
                            <button onClick={handleLogout} className="text-[10px] font-bold text-violet-600 uppercase tracking-widest mt-0.5 hover:text-violet-700 transition-colors">Log Out</button>
                        </div>
                        <div className="w-9 h-9 rounded-full bg-slate-50 flex items-center justify-center border border-slate-200 shadow-sm">
                            <User className="w-4 h-4 text-slate-600" />
                        </div>
                    </div>
                </div>
            </div>

            <main className="flex-1 flex flex-col items-center justify-center px-6 py-16 relative z-10 w-full max-w-6xl mx-auto">
                <div className="text-center mb-16 relative">
                    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-violet-100 border border-violet-200 text-violet-800 text-[10px] font-extrabold uppercase tracking-widest mb-6 shadow-sm shadow-violet-500/10">
                        <div className="w-2 h-2 rounded-full bg-violet-500 animate-pulse" />
                        Optical Core Active
                    </div>
                    <h1 className="text-5xl md:text-[4rem] font-extrabold mb-6 tracking-tight font-sans text-slate-900 drop-shadow-sm leading-tight">
                        Intelligence <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-600 to-indigo-500">Setup</span>
                    </h1>
                    <p className="text-slate-500 font-medium text-lg leading-relaxed max-w-xl mx-auto">
                        Drag and drop your regulatory documents below. Our AI will instantly map changes against your internal policy and generate a compliance remediation roadmap.
                    </p>
                </div>

                <div className="w-full grid md:grid-cols-2 gap-8 mb-16 max-w-4xl mx-auto px-4">
                    {mode === 'old' && (
                        <FileUploadCard
                            file={oldFile} setFile={setOldFile} title="Old Regulation" delay={0} icon={FileText}
                            gradientFrom="from-violet-500" gradientTo="to-indigo-500"
                        />
                    )}
                    {mode === 'new' && (
                        <FileUploadCard
                            file={newFile} setFile={setNewFile} title="New Regulation" delay={0} icon={FileCheck}
                            gradientFrom="from-blue-500" gradientTo="to-cyan-500"
                        />
                    )}
                    <FileUploadCard
                        file={policyFile} setFile={setPolicyFile} title="Internal Policy" delay={0.5} icon={Building2}
                        gradientFrom="from-emerald-400" gradientTo="to-teal-500"
                    />
                </div>

                <div className="flex flex-col items-center w-full max-w-[320px] mt-2">
                    <button
                        onClick={handleSubmit}
                        disabled={loading || (mode === 'old' ? (!oldFile || !policyFile) : (!newFile || !policyFile))}
                        className="w-full bg-slate-900 text-white py-4.5 rounded-2xl font-bold transition-all 
                        active:scale-[0.98] disabled:opacity-50 disabled:active:scale-100 flex items-center justify-center gap-3 group 
                        shadow-[0_15px_30px_-5px_rgba(0,0,0,0.3)] hover:shadow-[0_20px_40px_-5px_rgba(0,0,0,0.4)] hover:-translate-y-1 relative overflow-hidden"
                    >
                        <div className="absolute inset-0 w-full h-full bg-gradient-to-r from-violet-600/50 to-indigo-600/50 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
                        <span className="relative z-10 flex items-center justify-center gap-2 font-sans tracking-wide">
                            Analyze Documents
                            <ArrowRight className="w-5 h-5 group-hover:translate-x-1.5 transition-transform" />
                        </span>
                    </button>
                    <p className="text-[10px] font-bold text-slate-400 mt-6 flex items-center justify-center gap-1.5 uppercase tracking-widest px-4">
                        <LockIcon className="w-3.5 h-3.5 text-slate-400" />
                        Enterprise-grade end-to-end encryption.
                    </p>
                </div>
            </main>
        </div>
    );
}

function LockIcon(props) {
    return (
        <svg {...props} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
        </svg>
    );
}

