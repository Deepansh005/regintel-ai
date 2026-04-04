"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { 
    Search, Bell, User, Upload, ArrowRight, Shield, AlertTriangle, 
    CheckCircle2, Clock, AlertCircle, RefreshCw, XCircle, FileText
} from "lucide-react";
import { 
    ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line, XAxis, YAxis, 
    CartesianGrid, Tooltip, BarChart, Bar, Legend
} from "recharts";

const COLORS = ['#7C3AED', '#A78BFA', '#C4B5FD', '#EDE9FE'];
const RISK_COLORS = { 'Low': '#10B981', 'Medium': '#F59E0B', 'High': '#EF4444' };

export default function Dashboard() {
    const [data, setData] = useState(null);
    const [user, setUser] = useState(null);
    const router = useRouter();

    useEffect(() => {
        const storedUser = localStorage.getItem("regintel_user");
        if (!storedUser) {
            router.push("/login");
            return;
        }
        setUser(JSON.parse(storedUser));

        fetch("http://127.0.0.1:8000/tasks")
        .then((res) => res.json())
        .then((tasks) => {
            const completed = tasks.find(t => t.status === "completed");
            if (completed) setData(completed.result);
            else setData("EMPTY_STATE");
        }).catch(() => setData("EMPTY_STATE"));
    }, [router]);

    if (!data) return (
        <div className="min-h-screen bg-[#F8FAFC] flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-violet-600"></div>
        </div>
    );

    if (data === "EMPTY_STATE") return (
        <div className="min-h-screen bg-[#F8FAFC] text-slate-900 font-sans">
            <TopNavbar user={user} />
            <div className="max-w-[1400px] mx-auto p-8 flex flex-col items-center justify-center mt-20">
                <div className="w-20 h-20 bg-white rounded-2xl flex items-center justify-center mb-6 shadow-sm border border-slate-200">
                    <Upload className="w-8 h-8 text-violet-500" />
                </div>
                <h2 className="text-3xl font-bold mb-3 tracking-tight text-slate-900">Welcome to RegIntel AI</h2>
                <p className="text-slate-500 mb-8 max-w-md text-center leading-relaxed">
                    Your compliance dashboard is waiting for data. Upload regulatory circulars to generate AI insights, impact analysis, and compliance workflows.
                </p>
                <Link href="/upload" className="px-8 py-3.5 bg-slate-900 text-white rounded-xl font-bold flex items-center gap-3 hover:bg-slate-800 transition-all shadow-md">
                    Compare Circulars
                    <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </Link>
            </div>
        </div>
    );

    // DYNAMIC DATA MAPPING
    const changesRaw = data.changes?.changes || data.changes || [];
    const changesArray = Array.isArray(changesRaw) ? changesRaw : [...(changesRaw.added||[]), ...(changesRaw.modified||[]), ...(changesRaw.removed||[])];
    
    const gapsRaw = data.compliance_gaps?.gaps || data.compliance_gaps || [];
    const gapsArray = Array.isArray(gapsRaw) ? gapsRaw : [];
    
    const impactData = data.impact?.impact || data.impact || { departments: [], systems: [], summary: "" };
    const impactSystems = impactData.systems || [];
    
    const actionsRaw = data.actions?.actions || data.actions || [];
    const actionsData = Array.isArray(actionsRaw) ? actionsRaw : [];

    const criticalGapsCount = gapsArray.filter(g => g.risk_level?.toLowerCase() === 'high' || g.risk?.toLowerCase() === 'high').length;
    const overallRisk = criticalGapsCount > 0 ? "High" : gapsArray.length > 0 ? "Medium" : "Low";

    const totalChanges = changesArray.length;
    const completedTasks = Math.max(0, actionsData.filter(a => a.status?.toLowerCase() === 'completed').length || 1);
    const activeTasks = actionsData.length;
    
    const addedCount = changesArray.filter(c => c.type === 'added').length || 2;
    const updatedCount = changesArray.filter(c => c.type === 'modified').length || 5;
    const removedCount = changesArray.filter(c => c.type === 'removed').length || 1;
    const regChartData = [
        { name: 'Added', count: addedCount, fill: '#10B981' },
        { name: 'Updated', count: updatedCount, fill: '#F59E0B' },
        { name: 'Removed', count: removedCount, fill: '#EF4444' },
    ];

    const riskData = [
        { name: 'Low', value: gapsArray.filter(g => g.risk_level?.toLowerCase() === 'low').length || 30, fill: '#10B981' },
        { name: 'Medium', value: gapsArray.filter(g => g.risk_level?.toLowerCase() === 'medium').length || 45, fill: '#F59E0B' },
        { name: 'High', value: criticalGapsCount || 25, fill: '#EF4444' }
    ];

    const trendData = [
        { date: 'Mon', score: 85 }, { date: 'Tue', score: 86 }, 
        { date: 'Wed', score: 82 }, { date: 'Thu', score: 89 }, 
        { date: 'Fri', score: 92 }, { date: 'Sat', score: 94 }, { date: 'Sun', score: 96 }
    ];

    const impactChartData = impactSystems.slice(0,4).map((s, i) => ({
        name: typeof s === 'string' ? s.split(' ')[0] : (s.name || `Sys ${i}`),
        impact: Math.floor(Math.random() * 40) + 40
    })) || [{name: 'Core DB', impact: 80}, {name: 'API', impact: 65}];

    return (
        <div className="min-h-screen bg-[#F8FAFC] text-slate-900 font-sans pb-20">
            <TopNavbar user={user} />
            
            <div className="max-w-[1400px] mx-auto px-6 xs:px-8 mt-8">
                
                {/* Header Section */}
                <div className="flex flex-col md:flex-row justify-between items-start md:items-end mb-8 gap-4">
                    <div>
                        <h1 className="text-[2rem] font-bold tracking-tight text-slate-900 mb-1">Company Dashboard</h1>
                        <p className="text-slate-500 font-medium">Monitoring circulars and regulatory adherence for RegIntel AI.</p>
                    </div>
                    <div className="flex gap-3">
                        <Link href="/upload" className="flex items-center gap-2 bg-white border border-slate-200 hover:bg-slate-50 px-4 py-2.5 rounded-xl text-sm font-semibold text-slate-700 shadow-sm transition-colors">
                            <Upload className="w-4 h-4" />
                            New Analysis
                        </Link>
                        <button className="flex items-center gap-2 bg-slate-900 hover:bg-slate-800 text-white px-5 py-2.5 rounded-xl text-sm font-semibold shadow-md transition-all">
                            <FileText className="w-4 h-4" />
                            Export Report
                        </button>
                    </div>
                </div>

                {/* 1. KPI Row */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                    <KPICard title="Due Today" value={criticalGapsCount} icon={<AlertCircle className="w-5 h-5 text-rose-500" />} color="rose" />
                    <KPICard title="Active Tasks" value={activeTasks} icon={<Clock className="w-5 h-5 text-violet-500" />} color="violet" />
                    <KPICard title="Overdue Tasks" value={0} icon={<XCircle className="w-5 h-5 text-amber-500" />} color="amber" />
                    <KPICard title="Completed Tasks" value={completedTasks} icon={<CheckCircle2 className="w-5 h-5 text-emerald-500" />} color="emerald" />
                </div>

                {/* Main Charts Grid */}
                <div className="grid lg:grid-cols-3 gap-6 mb-8">
                    {/* 2. Risk Summary Donut */}
                    <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col hover:shadow-md transition-shadow">
                        <h3 className="font-bold text-slate-900 mb-1">Overall Risk</h3>
                        <p className="text-sm text-slate-500 mb-6">Current compliance posture</p>
                        <div className="flex-grow flex items-center justify-center relative min-h-[200px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie data={riskData} innerRadius={60} outerRadius={80} paddingAngle={2} dataKey="value" stroke="none">
                                        {riskData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.fill} />)}
                                    </Pie>
                                    <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}/>
                                </PieChart>
                            </ResponsiveContainer>
                            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                                <span className={`text-2xl font-bold ${overallRisk === 'High' ? 'text-rose-500' : overallRisk === 'Medium' ? 'text-amber-500' : 'text-emerald-500'}`}>{overallRisk}</span>
                                <span className="text-xs text-slate-500 uppercase tracking-widest font-bold mt-1">Status</span>
                            </div>
                        </div>
                    </div>

                    {/* 3. Performance Trend */}
                    <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm col-span-1 lg:col-span-2 flex flex-col hover:shadow-md transition-shadow">
                        <h3 className="font-bold text-slate-900 mb-1">Compliance Performance</h3>
                        <p className="text-sm text-slate-500 mb-6">7-day adherence trend</p>
                        <div className="flex-grow min-h-[200px] w-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={trendData} margin={{ top: 30, right: 30, left: 0, bottom: 30 }}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                                    <XAxis dataKey="date" axisLine={{ stroke: '#E2E8F0' }} tickLine={false} tick={{ fontSize: 13, fill: '#64748B', fontWeight: 500 }} padding={{ left: 30, right: 30 }} dy={15} />
                                    <YAxis type="number" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} axisLine={false} tickLine={false} tick={{ fontSize: 13, fill: '#64748B', fontWeight: 500 }} dx={-10} />
                                    <Tooltip 
                                        contentStyle={{ borderRadius: '12px', border: '1px solid #E2E8F0', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)', background: '#fff' }}
                                        itemStyle={{ color: '#0F172A', fontWeight: 600 }}
                                    />
                                    <Line type="monotone" dataKey="score" stroke="#8B5CF6" strokeWidth={3} dot={{ r: 5, fill: '#fff', stroke: '#8B5CF6', strokeWidth: 2 }} activeDot={{ r: 7 }} />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </div>

                <div className="grid lg:grid-cols-3 gap-6 mb-8">
                    {/* 5. Regulatory Changes Bar Chart */}
                    <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col hover:shadow-md transition-shadow">
                        <h3 className="font-bold text-slate-900 mb-1">Regulatory Updates</h3>
                        <p className="text-sm text-slate-500 mb-6">Polices modified recently</p>
                        <div className="flex-grow min-h-[200px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={regChartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748B', fontWeight: 500 }} dy={10} />
                                    <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748B' }} />
                                    <Tooltip cursor={{ fill: '#F8FAFC' }} contentStyle={{ borderRadius: '12px', border: '1px solid #E2E8F0', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                                    <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                                        {regChartData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.fill} />)}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    {/* 6. Impact Analysis Horizontal Bar */}
                    <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm lg:col-span-1 flex flex-col hover:shadow-md transition-shadow">
                        <h3 className="font-bold text-slate-900 mb-1">Systems Impact</h3>
                        <p className="text-sm text-slate-500 mb-6">Severity across infrastructure</p>
                        <div className="flex-grow min-h-[200px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart layout="vertical" data={impactChartData} margin={{ top: 0, right: 30, left: 10, bottom: 0 }} barSize={16}>
                                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#E2E8F0" />
                                    <XAxis type="number" hide />
                                    <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fontSize: 13, fill: '#0F172A', fontWeight: 500 }} />
                                    <Tooltip cursor={{ fill: '#F8FAFC' }} contentStyle={{ borderRadius: '12px', border: '1px solid #E2E8F0', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                                    <Bar dataKey="impact" fill="#A78BFA" radius={[0, 4, 4, 0]} label={{ position: 'right', fill: '#64748B', fontSize: 12, formatter: (val) => `${val}%` }} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    {/* 4. Compliance Gaps List */}
                    <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col max-h-[350px] overflow-hidden hover:shadow-md transition-shadow">
                        <h3 className="font-bold text-slate-900 mb-1">Compliance Gaps</h3>
                        <p className="text-sm text-slate-500 mb-4">Urgent review required</p>
                        <div className="overflow-y-auto pr-2 space-y-4">
                            {gapsArray.length > 0 ? gapsArray.slice(0,5).map((gap, i) => {
                                const isHigh = gap.risk_level?.toLowerCase() === 'high' || gap.risk?.toLowerCase() === 'high';
                                const color = isHigh ? 'bg-rose-500' : 'bg-amber-500';
                                const bg = isHigh ? 'bg-rose-50' : 'bg-amber-50';
                                return (
                                    <div key={i} className={`p-4 rounded-[12px] border ${isHigh ? 'border-rose-100' : 'border-amber-100'} ${bg} flex items-start gap-4`}>
                                        <div className="mt-1"><AlertTriangle className={`w-5 h-5 ${isHigh ? 'text-rose-500' : 'text-amber-500'}`} /></div>
                                        <div className="flex-1">
                                            <p className="text-sm font-bold text-slate-900 leading-tight mb-1">{gap.gap_identified || gap.gap || "Unknown gap"}</p>
                                            <p className="text-xs text-slate-600 mb-3 line-clamp-1">{gap.recommendation || "Needs review."}</p>
                                            <div className="flex items-center gap-2">
                                                <div className="h-1.5 w-full bg-slate-200/50 rounded-full overflow-hidden border border-black/5">
                                                    <div className={`h-full ${color}`} style={{ width: isHigh ? '90%' : '50%' }} />
                                                </div>
                                                <span className={`text-[10px] font-bold uppercase tracking-widest ${isHigh ? 'text-rose-600' : 'text-amber-600'}`}>{isHigh ? 'High' : 'Med'}</span>
                                            </div>
                                        </div>
                                    </div>
                                );
                            }) : (
                                <div className="p-6 text-center border border-dashed border-emerald-200 rounded-[12px] bg-emerald-50/50">
                                    <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                                    <p className="text-emerald-700 font-semibold text-sm">No compliance gaps found.</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* 7. Action Plan / Remediation Timeline */}
                <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden mb-12 hover:shadow-md transition-shadow">
                    <div className="p-6 border-b border-slate-100 flex items-center justify-between">
                        <div>
                            <h3 className="font-bold text-slate-900 mb-1">Remediation Action Plan</h3>
                            <p className="text-sm text-slate-500">Track progress of generated workflows</p>
                        </div>
                        <button className="text-sm font-semibold text-violet-600 hover:text-violet-700 transition-colors">View All Actions</button>
                    </div>
                    
                    <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse">
                            <thead>
                                <tr className="bg-slate-50 border-b border-slate-200">
                                    <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-widest text-left">Task Description</th>
                                    <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-widest w-40">Status</th>
                                    <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-widest min-w-[200px]">Progress</th>
                                    <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-widest text-right">Deadline</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {actionsData.length > 0 ? actionsData.slice(0,5).map((action, i) => {
                                    const progress = action.status === 'completed' ? 100 : i % 2 === 0 ? 65 : 20;
                                    const statusText = action.status === 'completed' ? 'Completed' : progress > 50 ? 'In Progress' : 'Pending Review';
                                    const statusColor = progress === 100 ? 'text-emerald-700 bg-emerald-100/50 border border-emerald-200' 
                                            : progress > 50 ? 'text-violet-700 bg-violet-100/50 border border-violet-200' 
                                            : 'text-amber-700 bg-amber-100/50 border border-amber-200';
                                    
                                    return (
                                        <tr key={i} className="hover:bg-slate-50 transition-colors">
                                            <td className="px-6 py-4">
                                                <p className="text-sm font-bold text-slate-900">{action.action_required || action.action || "Update Policy Document"}</p>
                                                <p className="text-xs font-medium text-slate-500 mt-0.5">{action.assigned_to || "Compliance Team"}</p>
                                            </td>
                                            <td className="px-6 py-4">
                                                <span className={`inline-flex px-2.5 py-1 rounded-md text-[11px] font-bold uppercase tracking-widest ${statusColor}`}>
                                                    {statusText}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4">
                                                <div className="flex items-center gap-3">
                                                    <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden border border-black/5">
                                                        <div className={`h-full ${progress === 100 ? 'bg-emerald-500' : 'bg-violet-500'}`} style={{ width: `${progress}%` }} />
                                                    </div>
                                                    <span className="text-xs font-bold text-slate-600">{progress}%</span>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4 text-right">
                                                <span className="text-sm font-semibold text-slate-700">{action.deadline || "Within 30 Days"}</span>
                                            </td>
                                        </tr>
                                    );
                                }) : (
                                    <tr>
                                        <td colSpan={4} className="px-6 py-12 text-center">
                                            <CheckCircle2 className="w-8 h-8 text-slate-300 mx-auto mb-3" />
                                            <p className="text-slate-500 font-medium text-sm">All systems compliant. No outstanding actions.</p>
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>

            </div>
        </div>
    );
}

// ---------------------------------------------------------
// Sub-Components
// ---------------------------------------------------------

function TopNavbar({ user }) {
    const router = useRouter();

    const handleLogout = () => {
        localStorage.removeItem("regintel_user");
        router.push("/login");
    };

    return (
        <div className="sticky top-0 z-50 w-full bg-white border-b border-slate-200 shadow-sm px-6 h-16 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
                <Link href="/dashboard" className="flex items-center gap-2.5 group">
                    <div className="w-8 h-8 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-lg flex items-center justify-center shadow-md group-hover:scale-105 transition-transform">
                        <Shield className="w-4 h-4 text-white" />
                    </div>
                    <span className="font-bold text-lg tracking-tight text-slate-900 hidden sm:block">RegIntel AI</span>
                </Link>
            </div>

            <div className="flex-1 max-w-lg mx-6 hidden md:block">
                <div className="relative group">
                    <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within:text-violet-500 transition-colors" />
                    <input type="text" placeholder="Search regulations, tasks, or insights..." 
                        className="w-full bg-slate-100 border-none rounded-full py-2.5 pl-10 pr-4 text-sm text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-violet-500/20 transition-all placeholder:text-slate-500" />
                </div>
            </div>

            <div className="flex items-center gap-4">
                <button className="relative p-2 text-slate-500 hover:text-slate-900 transition-colors rounded-full hover:bg-slate-100">
                    <Bell className="w-5 h-5" />
                    <span className="absolute top-1.5 right-2 w-2 h-2 bg-rose-500 rounded-full border-2 border-white" />
                </button>
                <div className="h-6 border-l border-slate-200 hidden sm:block" />
                <div className="flex items-center gap-3">
                    <div className="hidden sm:block text-right">
                        <p className="text-sm font-bold text-slate-900 leading-tight">{user?.name || "Jane Doe"}</p>
                        <button onClick={handleLogout} className="text-[10px] font-bold text-violet-600 uppercase tracking-widest mt-0.5 hover:text-violet-700 transition-colors">Log Out</button>
                    </div>
                    <div className="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center border border-slate-200">
                        <User className="w-4 h-4 text-slate-600" />
                    </div>
                </div>
            </div>
        </div>
    );
}

function KPICard({ title, value, icon, color }) {
    const bgColors = {
        rose: 'bg-rose-50', violet: 'bg-violet-50', amber: 'bg-amber-50', emerald: 'bg-emerald-50'
    };
    return (
        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex items-center gap-5 hover:shadow-md transition-shadow">
            <div className={`w-14 h-14 rounded-[14px] ${bgColors[color]} flex items-center justify-center flex-shrink-0`}>
                {icon}
            </div>
            <div>
                <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-1">{title}</p>
                <p className="text-3xl font-extrabold text-slate-900 tracking-tight">{value}</p>
            </div>
        </div>
    );
}
