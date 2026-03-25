"use client";

import { useState, useEffect } from "react";
import { uploadDocuments } from "../../services/api";
import { useRouter } from "next/navigation";
import { Shield, Upload, FileText, CheckCircle2, AlertCircle, Loader2, LogOut, ArrowRight, Zap } from "lucide-react";

export default function UploadPage() {
    const router = useRouter();
    const [oldFile, setOldFile] = useState(null);
    const [newFile, setNewFile] = useState(null);
    const [loading, setLoading] = useState(false);
    const [user, setUser] = useState(null);

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
        if (!oldFile || !newFile) {
            alert("Please select both circulars to analyze.");
            return;
        }

        setLoading(true);

        try {
            console.log("Starting upload...", { oldFile, newFile });
            const data = await uploadDocuments(oldFile, newFile);
            console.log("Upload successful:", data);

            if (data.error) {
                alert("Backend Error: " + data.error);
                setLoading(false);
                return;
            }

            localStorage.setItem("analysisData", JSON.stringify(data));
            router.push("/dashboard");
        } catch (err) {
            console.error("Upload failed:", err);
            alert("Error uploading files: " + err.message);
        }

        setLoading(false);
    };

    if (!user) return null;

    return (
        <div className="min-h-screen bg-[#020617] text-white selection:bg-violet-500/30">
            {/* Top Bar */}
            <div className="border-b border-white/5 bg-white/5 backdrop-blur-xl sticky top-0 z-40">
                <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Shield className="w-6 h-6 text-violet-500" />
                        <span className="font-bold tracking-tight">RegIntel AI</span>
                    </div>
                    <div className="flex items-center gap-4">
                        <span className="text-sm text-slate-400">Hi, {user.name}</span>
                        <button
                            onClick={handleLogout}
                            className="p-2 hover:bg-white/10 rounded-lg text-slate-400 hover:text-white transition-all"
                        >
                            <LogOut className="w-5 h-5" />
                        </button>
                    </div>
                </div>
            </div>

            <main className="max-w-4xl mx-auto px-6 py-20 text-center">
                <h1 className="text-4xl md:text-5xl font-bold mb-6">Compare Regulatory Circulars</h1>
                <p className="text-slate-400 text-lg mb-16 max-w-2xl mx-auto">
                    Upload two PDF versions of a regulation to detect changes, analyze business impact, and generate remediation actions automatically.
                </p>

                <div className="grid md:grid-cols-2 gap-8 mb-12 text-left">
                    {/* Old File Upload */}
                    <div className="space-y-4">
                        <label className="text-sm font-semibold text-slate-300 ml-1 uppercase tracking-wider">Base Circular (Old)</label>
                        <div className={`relative group border-2 border-dashed rounded-3xl p-10 flex flex-col items-center justify-center transition-all ${oldFile ? 'border-violet-500/50 bg-violet-500/5' : 'border-white/10 hover:border-white/20'}`}>
                            <input
                                type="file"
                                accept="application/pdf"
                                className="absolute inset-0 opacity-0 cursor-pointer"
                                onChange={(e) => setOldFile(e.target.files[0])}
                            />
                            <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-4 ${oldFile ? 'bg-violet-500' : 'bg-white/5'}`}>
                                {oldFile ? <CheckCircle2 className="w-8 h-8 text-white" /> : <FileText className="w-8 h-8 text-slate-400" />}
                            </div>
                            <p className="font-medium text-center">{oldFile ? oldFile.name : "Choose Old PDF"}</p>
                            <p className="text-xs text-slate-500 mt-2">Maximum size: 20MB</p>
                        </div>
                    </div>

                    {/* New File Upload */}
                    <div className="space-y-4">
                        <label className="text-sm font-semibold text-slate-300 ml-1 uppercase tracking-wider">New Circular (Update)</label>
                        <div className={`relative group border-2 border-dashed rounded-3xl p-10 flex flex-col items-center justify-center transition-all ${newFile ? 'border-cyan-500/50 bg-cyan-500/5' : 'border-white/10 hover:border-white/20'}`}>
                            <input
                                type="file"
                                accept="application/pdf"
                                className="absolute inset-0 opacity-0 cursor-pointer"
                                onChange={(e) => setNewFile(e.target.files[0])}
                            />
                            <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-4 ${newFile ? 'bg-cyan-500' : 'bg-white/5'}`}>
                                {newFile ? <CheckCircle2 className="w-8 h-8 text-white" /> : <Upload className="w-8 h-8 text-slate-400" />}
                            </div>
                            <p className="font-medium text-center">{newFile ? newFile.name : "Choose New PDF"}</p>
                            <p className="text-xs text-slate-500 mt-2">Maximum size: 20MB</p>
                        </div>
                    </div>
                </div>

                <button
                    onClick={handleSubmit}
                    disabled={loading || !oldFile || !newFile}
                    className="w-full max-w-sm bg-gradient-to-r from-violet-600 to-indigo-600 py-5 rounded-full font-bold text-lg shadow-2xl shadow-violet-500/30 hover:shadow-violet-500/50 transition-all active:scale-95 disabled:opacity-50 flex items-center justify-center gap-3 group mx-auto"
                >
                    {loading ? (
                        <>
                            <Loader2 className="w-6 h-6 animate-spin" />
                            Running AI Analysis...
                        </>
                    ) : (
                        <>
                            Analyze Regulatory Changes
                            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                        </>
                    )}
                </button>

                <div className="mt-12 flex items-center justify-center gap-12 text-slate-500">
                    <div className="flex items-center gap-2">
                        <Shield className="w-5 h-5" />
                        <span className="text-sm">Secure Data</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <Zap className="w-5 h-5" />
                        <span className="text-sm">Instant Results</span>
                    </div>
                </div>
            </main>
        </div>
    );
}
