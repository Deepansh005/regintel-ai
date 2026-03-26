"use client";

import { useState, useEffect } from "react";
import { uploadDocuments } from "../../services/api";
import { useRouter } from "next/navigation";
import { Shield, Upload, FileText, CheckCircle2, AlertCircle, Loader2, LogOut, ArrowRight, FileCheck, Building2 } from "lucide-react";

export default function UploadPage() {
    const router = useRouter();
    const [oldFile, setOldFile] = useState(null);
    const [newFile, setNewFile] = useState(null);
    const [policyFile, setPolicyFile] = useState(null);
    const [loading, setLoading] = useState(false);
    const [user, setUser] = useState(null);
    const [progress, setProgress] = useState(0);

    useEffect(() => {
        const storedUser = localStorage.getItem("regintel_user");
        if (!storedUser) {
            router.push("/login");
        } else {
            setUser(JSON.parse(storedUser));
        }
    }, [router]);

    const handleLogout = () => {
        localStorage.removeItem("regintel_user");
        router.push("/");
    };

    const handleSubmit = async () => {
        if (!oldFile || !newFile || !policyFile) {
            alert("Please upload Old Regulation, New Regulation, and Internal Policy.");
            return;
        }

        setLoading(true);

        // Fake progress animation
        const interval = setInterval(() => {
            setProgress((prev) => {
                if (prev >= 90) return 90;
                return prev + Math.floor(Math.random() * 10);
            });
        }, 300);

        try {
            console.log("Starting upload...", { oldFile, newFile, policyFile });
            const data = await uploadDocuments(oldFile, newFile, policyFile);
            console.log("Upload successful:", data);

            clearInterval(interval);
            setProgress(100);

            if (data.error) {
                alert("Backend Error: " + data.error);
                setLoading(false);
                setProgress(0);
                return;
            }

            // Small delay to show 100% completion before redirect
            setTimeout(() => {
                localStorage.setItem("analysisData", JSON.stringify(data));
                router.push("/dashboard");
            }, 800);
            
        } catch (err) {
            clearInterval(interval);
            setProgress(0);
            console.error("Upload failed:", err);
            alert("Error uploading files: " + err.message);
            setLoading(false);
        }
    };

    if (!user) return null;

    if (loading) {
        return (
            <div className="min-h-screen bg-[#020617] text-white flex flex-col items-center justify-center p-6 selection:bg-violet-500/30">
                <div className="w-full max-w-lg bg-white/5 border border-white/10 p-10 rounded-[2.5rem] backdrop-blur-xl text-center relative overflow-hidden">
                    <div className="absolute top-0 left-0 w-full h-1 bg-white/5">
                        <div 
                            className="h-full bg-gradient-to-r from-violet-600 via-indigo-500 to-cyan-400 transition-all duration-300 ease-out" 
                            style={{ width: `${progress}%` }}
                        />
                    </div>
                    
                    <div className="relative">
                        <div className="w-24 h-24 mx-auto mb-8 relative">
                            <div className="absolute inset-0 border-4 border-violet-500/20 rounded-full"></div>
                            <div className="absolute inset-0 border-4 border-violet-500 border-t-transparent rounded-full animate-spin"></div>
                            <div className="absolute inset-0 flex items-center justify-center">
                                <Shield className="w-8 h-8 text-violet-400 animate-pulse" />
                            </div>
                        </div>

                        <h2 className="text-2xl font-bold mb-3 tracking-wide">Analyzing with AI...</h2>
                        <p className="text-slate-400 text-sm mb-8 leading-relaxed">
                            Cross-referencing {oldFile?.name}, {newFile?.name}, and {policyFile?.name} against our regulatory knowledge base to detect compliance gaps and impact.
                        </p>

                        <div className="space-y-4">
                            <div className="flex items-center justify-between text-xs font-medium text-slate-500 bg-black/20 p-3 rounded-xl border border-white/5">
                                <span className={progress > 10 ? "text-violet-400" : ""}>Extracting text...</span>
                                {progress > 10 ? <CheckCircle2 className="w-4 h-4 text-violet-400" /> : <Loader2 className="w-4 h-4 animate-spin opacity-50" />}
                            </div>
                            <div className="flex items-center justify-between text-xs font-medium text-slate-500 bg-black/20 p-3 rounded-xl border border-white/5">
                                <span className={progress > 40 ? "text-indigo-400" : ""}>Analyzing changes...</span>
                                {progress > 40 ? <CheckCircle2 className="w-4 h-4 text-indigo-400" /> : <Loader2 className="w-4 h-4 animate-spin opacity-50" />}
                            </div>
                            <div className="flex items-center justify-between text-xs font-medium text-slate-500 bg-black/20 p-3 rounded-xl border border-white/5">
                                <span className={progress > 70 ? "text-cyan-400" : ""}>Generating insights & remediation roadmap...</span>
                                {progress > 70 ? <CheckCircle2 className="w-4 h-4 text-cyan-400" /> : <Loader2 className="w-4 h-4 animate-spin opacity-50" />}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    const FileUploadCard = ({ file, setFile, title, icon: Icon, colorClass, borderClass, bgClass }) => (
        <div className="space-y-4 flex-1">
            <label className="text-xs font-bold text-slate-400 uppercase tracking-widest pl-1">{title}</label>
            <div className={`relative group border-2 border-dashed rounded-3xl p-8 flex flex-col items-center justify-center transition-all min-h-[220px] ${file ? borderClass + ' ' + bgClass : 'border-white/10 hover:border-white/20 bg-white/5'}`}>
                <input
                    type="file"
                    accept="application/pdf"
                    className="absolute inset-0 opacity-0 cursor-pointer z-10"
                    onChange={(e) => setFile(e.target.files[0])}
                />
                <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mb-5 transition-transform group-hover:scale-110 shadow-xl ${file ? colorClass : 'bg-black/40'}`}>
                    {file ? <CheckCircle2 className="w-8 h-8 text-white" /> : <Icon className={`w-8 h-8 ${file ? 'text-white' : 'text-slate-400'}`} />}
                </div>
                <p className={`font-semibold text-center px-4 ${file ? 'text-white' : 'text-slate-300'}`}>
                    {file ? file.name : `Select ${title}`}
                </p>
                {!file && <p className="text-[11px] text-slate-500 mt-3 uppercase tracking-wider">PDF up to 20MB</p>}
            </div>
        </div>
    );

    return (
        <div className="min-h-screen bg-[#020617] text-white selection:bg-violet-500/30">
            {/* Top Bar */}
            <div className="border-b border-white/5 bg-[#020617]/80 backdrop-blur-xl sticky top-0 z-40">
                <div className="max-w-[90rem] mx-auto px-6 h-16 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/20">
                            <Shield className="w-5 h-5 text-white" />
                        </div>
                        <span className="font-bold tracking-tight text-lg">RegIntel AI</span>
                    </div>
                    <div className="flex items-center gap-6">
                        <div className="flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                            <span className="text-xs font-semibold text-slate-400 tracking-wider uppercase">System Operational</span>
                        </div>
                        <div className="w-px h-6 bg-white/10"></div>
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-sm font-bold text-slate-300">
                                {user?.name ? user.name.charAt(0).toUpperCase() : 'U'}
                            </div>
                            <span className="text-sm font-medium text-slate-300 hidden md:block">{user?.name}</span>
                        </div>
                        <button
                            onClick={handleLogout}
                            className="p-2 hover:bg-white/10 rounded-lg text-slate-400 hover:text-white transition-all ml-2"
                            title="Sign out"
                        >
                            <LogOut className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </div>

            <main className="max-w-6xl mx-auto px-6 py-16">
                <div className="max-w-3xl mb-12">
                    <h1 className="text-4xl md:text-5xl font-bold mb-4 tracking-tight">Intelligence Setup</h1>
                    <p className="text-slate-400 text-lg leading-relaxed">
                        Drag and drop your regulatory documents below. Our AI will instantly map changes against your internal policy and generate a compliance remediation roadmap.
                    </p>
                </div>

                <div className="grid md:grid-cols-3 gap-6 mb-12">
                    <FileUploadCard 
                        file={oldFile} 
                        setFile={setOldFile} 
                        title="Old Regulation" 
                        icon={FileText}
                        colorClass="bg-violet-500"
                        borderClass="border-violet-500/50"
                        bgClass="bg-violet-500/5"
                    />
                    <FileUploadCard 
                        file={newFile} 
                        setFile={setNewFile} 
                        title="New Regulation" 
                        icon={FileCheck}
                        colorClass="bg-indigo-500"
                        borderClass="border-indigo-500/50"
                        bgClass="bg-indigo-500/5"
                    />
                    <FileUploadCard 
                        file={policyFile} 
                        setFile={setPolicyFile} 
                        title="Internal Policy" 
                        icon={Building2}
                        colorClass="bg-cyan-500"
                        borderClass="border-cyan-500/50"
                        bgClass="bg-cyan-500/5"
                    />
                </div>

                <div className="border-t border-white/5 pt-10 flex flex-col items-center">
                    <button
                        onClick={handleSubmit}
                        disabled={loading || !oldFile || !newFile || !policyFile}
                        className="w-full max-w-md bg-white text-black py-4 rounded-full font-bold text-lg hover:bg-slate-200 transition-all active:scale-95 disabled:opacity-50 disabled:hover:bg-white flex items-center justify-center gap-3 group shadow-[0_0_40px_-10px_rgba(255,255,255,0.3)]"
                    >
                        Analyze Documents
                        <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                    </button>
                    <p className="text-sm text-slate-500 mt-6 flex items-center gap-2">
                        <LockIcon className="w-4 h-4" />
                        Enterprise-grade end-to-end encryption.
                    </p>
                </div>
            </main>
        </div>
    );
}

function LockIcon(props) {
  return (
    <svg {...props} xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
      <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
    </svg>
  );
}

