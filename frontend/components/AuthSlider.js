"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Shield, Loader2 } from "lucide-react";

export default function AuthSlider({ initialIsSignUp = false }) {
    const router = useRouter();
    const [isSignUp, setIsSignUp] = useState(initialIsSignUp);
    
    // Login State
    const [loginEmail, setLoginEmail] = useState("");
    const [loginPassword, setLoginPassword] = useState("");
    const [loginLoading, setLoginLoading] = useState(false);

    // Register State
    const [regName, setRegName] = useState("");
    const [regEmail, setRegEmail] = useState("");
    const [regPassword, setRegPassword] = useState("");
    const [regConfirmPassword, setRegConfirmPassword] = useState("");
    const [regLoading, setRegLoading] = useState(false);

    useEffect(() => {
        const user = localStorage.getItem("regintel_user");
        if (user) router.push("/dashboard");
    }, [router]);

    const toggleMode = (signup) => {
        setIsSignUp(signup);
        window.history.pushState(null, '', signup ? '/register' : '/login');
    };

    const handleLogin = async (e) => {
        e.preventDefault();
        setLoginLoading(true);
        await new Promise(r => setTimeout(r, 1000));

        const users = JSON.parse(localStorage.getItem("regintel_users") || "[]");
        const user = users.find(u => u.email === loginEmail && u.password === loginPassword) 
            || (loginEmail === "demo@example.com" && loginPassword === "password");

        if (user) {
            localStorage.setItem("regintel_user", JSON.stringify({ email: loginEmail, name: user.name || "Demo User" }));
            router.push("/select-mode");
        } else {
            alert("Invalid credentials. Please try again or create an account.");
        }
        setLoginLoading(false);
    };

    const handleRegister = async (e) => {
        e.preventDefault();
        
        if (regPassword !== regConfirmPassword) {
            alert("Passwords do not match!");
            return;
        }

        setRegLoading(true);
        await new Promise(r => setTimeout(r, 1000));

        const users = JSON.parse(localStorage.getItem("regintel_users") || "[]");
        if (users.find(u => u.email === regEmail)) {
            alert("Email already exists. Please sign in instead.");
            setRegLoading(false);
            return;
        }

        users.push({ name: regName, email: regEmail, password: regPassword });
        localStorage.setItem("regintel_users", JSON.stringify(users));
        
        localStorage.setItem("regintel_user", JSON.stringify({ email: regEmail, name: regName }));
        router.push("/select-mode");
    };

    return (
        <div className="min-h-screen bg-white flex font-sans text-slate-900 selection:bg-violet-200">
            {/* Left Side: Branding (Visible on lg screens and up) */}
            <div className="hidden lg:flex w-1/2 p-20 bg-[#F8FAFC] border-r border-slate-200 flex-col relative overflow-hidden justify-between">
                
                {/* Subtle Background Pattern/Gradient */}
                <div className="absolute inset-0 pointer-events-none">
                    <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] bg-violet-600/5 rounded-full blur-[100px]" />
                    <div className="absolute bottom-[10%] right-[-10%] w-[50%] h-[50%] bg-blue-500/5 rounded-full blur-[100px]" />
                </div>

                <div className="relative z-10 flex items-center gap-3">
                    <div className="w-10 h-10 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-violet-500/20">
                        <Shield className="w-5 h-5 text-white" />
                    </div>
                    <span className="font-bold text-xl tracking-tight text-slate-900">RegIntel AI</span>
                </div>

                <div className="relative z-10 flex-grow flex flex-col justify-center max-w-lg mt-10">
                    <h1 className="text-5xl font-extrabold tracking-tight text-slate-900 leading-[1.15] mb-6">
                        Automate your compliance operations <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-600 to-indigo-600">intelligently.</span>
                    </h1>
                    <p className="text-lg text-slate-500 leading-relaxed max-w-md">
                        Join top finance and fintech companies using AI to analyze regulations, track changes, and ensure risk-free compliance.
                    </p>
                    
                    {/* Abstract Decoration Graphic */}
                    <div className="w-full mt-14 bg-white rounded-2xl border border-slate-200 p-6 shadow-sm overflow-hidden transform -rotate-1 hover:rotate-0 transition-transform duration-500">
                        <div className="flex items-center gap-3 mb-5 border-b border-slate-100 pb-4">
                            <div className="w-3 h-3 rounded-full bg-red-400" />
                            <div className="w-3 h-3 rounded-full bg-amber-400" />
                            <div className="w-3 h-3 rounded-full bg-emerald-400" />
                        </div>
                        <div className="space-y-4">
                            <div className="h-3 bg-slate-100 rounded-md w-3/4" />
                            <div className="h-3 bg-slate-100 rounded-md w-1/2" />
                            <div className="h-3 bg-violet-100 rounded-md w-5/6" />
                        </div>
                    </div>
                </div>

                <div className="relative z-10 text-sm font-medium text-slate-400">
                    © 2026 RegIntel AI, Inc.
                </div>
            </div>

            {/* Right Side: Form */}
            <div className="w-full lg:w-1/2 flex items-center justify-center p-8 sm:p-12 md:p-20 relative bg-white lg:bg-transparent">
                
                {/* Mobile Logo Only */}
                <div className="absolute top-8 left-8 lg:hidden flex items-center gap-3">
                    <div className="w-10 h-10 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-violet-500/20">
                        <Shield className="w-5 h-5 text-white" />
                    </div>
                    <span className="font-bold text-xl tracking-tight text-slate-900">RegIntel AI</span>
                </div>

                <div className="w-full max-w-[440px] relative mt-16 lg:mt-0 transition-opacity duration-300">
                    {isSignUp ? (
                        <div className="animate-in fade-in zoom-in-95 duration-300">
                            <div className="mb-10 text-center lg:text-left">
                                <h2 className="text-[2rem] font-bold tracking-tight text-slate-900 mb-2 font-sans">Create your account</h2>
                                <p className="text-slate-500">Start your 14-day free trial</p>
                            </div>

                            <form onSubmit={handleRegister} className="space-y-5">
                                <div className="space-y-1.5">
                                    <label className="text-sm font-semibold text-slate-700">Full Name</label>
                                    <input type="text" required value={regName} onChange={(e) => setRegName(e.target.value)} placeholder="Jane Doe"
                                        className="w-full px-4 py-3 rounded-[12px] bg-white border border-slate-200 text-slate-900 focus:outline-none focus:ring-4 focus:ring-violet-500/10 focus:border-violet-500 transition-all placeholder:text-slate-400 shadow-[0_1px_2px_rgba(0,0,0,0.05)]" />
                                </div>

                                <div className="space-y-1.5">
                                    <label className="text-sm font-semibold text-slate-700">Work Email</label>
                                    <input type="email" required value={regEmail} onChange={(e) => setRegEmail(e.target.value)} placeholder="jane@company.com"
                                        className="w-full px-4 py-3 rounded-[12px] bg-white border border-slate-200 text-slate-900 focus:outline-none focus:ring-4 focus:ring-violet-500/10 focus:border-violet-500 transition-all placeholder:text-slate-400 shadow-[0_1px_2px_rgba(0,0,0,0.05)]" />
                                </div>

                                <div className="space-y-1.5">
                                    <label className="text-sm font-semibold text-slate-700">Password</label>
                                    <input type="password" required value={regPassword} onChange={(e) => setRegPassword(e.target.value)} placeholder="••••••••"
                                        className="w-full px-4 py-3 rounded-[12px] bg-white border border-slate-200 text-slate-900 focus:outline-none focus:ring-4 focus:ring-violet-500/10 focus:border-violet-500 transition-all placeholder:text-slate-400 shadow-[0_1px_2px_rgba(0,0,0,0.05)]" />
                                </div>

                                <div className="space-y-1.5">
                                    <label className="text-sm font-semibold text-slate-700">Confirm Password</label>
                                    <input type="password" required value={regConfirmPassword} onChange={(e) => setRegConfirmPassword(e.target.value)} placeholder="••••••••"
                                        className="w-full px-4 py-3 rounded-[12px] bg-white border border-slate-200 text-slate-900 focus:outline-none focus:ring-4 focus:ring-violet-500/10 focus:border-violet-500 transition-all placeholder:text-slate-400 shadow-[0_1px_2px_rgba(0,0,0,0.05)]" />
                                </div>
                                
                                <button disabled={regLoading} className="w-full mt-2 bg-slate-900 hover:bg-slate-800 text-white rounded-[12px] py-3.5 font-semibold transition-all flex items-center justify-center gap-2 disabled:opacity-70 shadow-md">
                                    {regLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Create Account"}
                                </button>
                            </form>

                            <p className="mt-8 text-center lg:text-left text-sm text-slate-500 font-medium">
                                Already have an account?{" "}
                                <button type="button" onClick={() => toggleMode(false)} className="font-semibold text-violet-600 hover:text-violet-700 transition-colors">
                                    Sign In
                                </button>
                            </p>
                        </div>
                    ) : (
                        <div className="animate-in fade-in zoom-in-95 duration-300">
                            <div className="mb-10 text-center lg:text-left">
                                <h2 className="text-[2rem] font-bold tracking-tight text-slate-900 mb-2 font-sans">Welcome Back</h2>
                                <p className="text-slate-500">Enter your credentials to access your dashboard</p>
                            </div>

                            <form onSubmit={handleLogin} className="space-y-5">
                                <div className="space-y-1.5">
                                    <label className="text-sm font-semibold text-slate-700">Work Email</label>
                                    <input type="email" required value={loginEmail} onChange={(e) => setLoginEmail(e.target.value)} placeholder="jane@company.com"
                                        className="w-full px-4 py-3 rounded-[12px] bg-white border border-slate-200 text-slate-900 focus:outline-none focus:ring-4 focus:ring-violet-500/10 focus:border-violet-500 transition-all placeholder:text-slate-400 shadow-[0_1px_2px_rgba(0,0,0,0.05)]" />
                                </div>

                                <div className="space-y-1.5">
                                    <div className="flex items-center justify-between">
                                        <label className="text-sm font-semibold text-slate-700">Password</label>
                                        <a href="#" className="flex-shrink-0 text-sm font-semibold text-violet-600 hover:text-violet-700 transition-colors">Forgot Password?</a>
                                    </div>
                                    <input type="password" required value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)} placeholder="••••••••"
                                        className="w-full px-4 py-3 rounded-[12px] bg-white border border-slate-200 text-slate-900 focus:outline-none focus:ring-4 focus:ring-violet-500/10 focus:border-violet-500 transition-all placeholder:text-slate-400 shadow-[0_1px_2px_rgba(0,0,0,0.05)]" />
                                </div>
                                
                                <button disabled={loginLoading} className="w-full mt-2 bg-slate-900 hover:bg-slate-800 text-white rounded-[12px] py-3.5 font-semibold transition-all flex items-center justify-center gap-2 disabled:opacity-70 shadow-md transform hover:-translate-y-0.5 active:translate-y-0">
                                    {loginLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Sign In"}
                                </button>
                            </form>

                            <p className="mt-8 text-center lg:text-left text-sm text-slate-500 font-medium">
                                Don't have an account?{" "}
                                <button type="button" onClick={() => toggleMode(true)} className="font-semibold text-violet-600 hover:text-violet-700 transition-colors">
                                    Sign Up
                                </button>
                            </p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
