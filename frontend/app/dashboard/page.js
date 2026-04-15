"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { fetchTasks, clearTaskHistory, deleteOldTasks, fetchChunkDetails } from "../../services/api";
import {
    Search, Bell, User, Upload, ArrowRight, Shield, AlertTriangle,
    CheckCircle2, Clock, AlertCircle, RefreshCw, XCircle, FileText, Eye
} from "lucide-react";
import {
    ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line, XAxis, YAxis,
    CartesianGrid, Tooltip, BarChart, Bar
} from "recharts";
import SourceViewerModal from "../../components/SourceViewerModal";

function toArray(value) {
    return Array.isArray(value) ? value : [];
}

function parseMaybeJson(value) {
    if (typeof value !== 'string') return value;
    const trimmed = value.trim();
    if (!trimmed) return value;
    if (!(trimmed.startsWith('{') || trimmed.startsWith('['))) return value;

    try {
        return JSON.parse(trimmed);
    } catch (error) {
        return value;
    }
}

function unwrapTaskResult(source) {
    const parsed = parseMaybeJson(source);
    if (!parsed || typeof parsed !== 'object') {
        return parsed || {};
    }

    return parsed.result && typeof parsed.result === 'object'
        ? parsed.result
        : parsed.analysis && typeof parsed.analysis === 'object'
            ? parsed.analysis
            : parsed.data && typeof parsed.data === 'object'
                ? parsed.data
                : parsed;
}

function pickLatestCompletedTask(tasks) {
    const completedTasks = toArray(tasks).filter((task) => task?.status === 'completed');
    if (completedTasks.length === 0) {
        return null;
    }

    return completedTasks.reduce((latest, task) => {
        if (!latest) return task;
        const latestTime = new Date(latest.updated_at || latest.created_at || 0).getTime();
        const taskTime = new Date(task.updated_at || task.created_at || 0).getTime();
        return taskTime >= latestTime ? task : latest;
    }, null);
}

function firstNonEmpty(...values) {
    for (const value of values) {
        const text = String(value ?? '').trim();
        if (text) return text;
    }
    return '';
}

function normalizeLevel(value, fallback = 'Medium') {
    const level = String(value || '').trim().toLowerCase();
    if (level === 'high') return 'High';
    if (level === 'medium') return 'Medium';
    if (level === 'low') return 'Low';
    return fallback;
}

function normalizeChangeType(value) {
    const type = String(value || '').trim().toLowerCase();
    if (type === 'added' || type === 'missing_requirement') return 'added';
    if (type === 'removed' || type === 'extra_policy_rule') return 'removed';
    return 'modified';
}

function normalizeChanges(payload) {
    const root = unwrapTaskResult(payload);
    const changes = toArray(root?.changes);

    const mapped = changes
        .filter((item) => item && typeof item === 'object')
        .map((item, index) => {
            const type = normalizeChangeType(item?.type);
            const title = firstNonEmpty(item?.title, item?.field, item?.section, item?.category);
            const summary = firstNonEmpty(
                item?.summary,
                item?.evidence,
                item?.change,
                item?.old || item?.new ? `${String(item?.old || '').trim()} -> ${String(item?.new || '').trim()}` : ''
            );
            const source = firstNonEmpty(item?.source, item?.type === 'extra_policy_rule' ? 'POLICY' : 'RBI');

            if (!title || !summary || !source) {
                console.warn('Skipped invalid change item from backend:', { index, item });
                return null;
            }

            return {
                title,
                type,
                summary,
                source,
                source_chunks: Array.isArray(item?.source_chunks) ? item.source_chunks : [],
            };
        })
        .filter(Boolean);

    return mapped;
}

function normalizeGaps(payload) {
    const root = unwrapTaskResult(payload);
    const gaps = toArray(root?.compliance_gaps);

    const seen = new Map();
    return gaps
        .filter((item) => item && typeof item === 'object')
        .map((item, index) => {
            const title = firstNonEmpty(item?.title, item?.issue, item?.gap);
            const severity = normalizeLevel(item?.severity || item?.risk || item?.risk_level, 'Medium');
            const description = firstNonEmpty(
                item?.description,
                item?.reason,
                item?.regulation_requirement || item?.policy_current_state
                    ? `Requirement: ${String(item?.regulation_requirement || '').trim()} Current policy: ${String(item?.policy_current_state || '').trim()}`
                    : ''
            );
            const recommendation = firstNonEmpty(
                item?.recommendation,
                item?.regulation_requirement ? `Align policy controls to: ${String(item?.regulation_requirement).trim()}` : ''
            );

            if (!title || !severity || !description || !recommendation) {
                console.warn('Skipped invalid compliance gap item from backend:', { index, item });
                return null;
            }

            const base = String(item.id || title || `gap-${index}`).trim();
            const count = (seen.get(base) || 0) + 1;
            seen.set(base, count);

            return {
                title,
                severity,
                description,
                recommendation,
                source_chunks: Array.isArray(item?.source_chunks) ? item.source_chunks : [],
                _ui_key: `${base}-${count}`,
            };
        })
        .filter(Boolean);
}

function normalizeImpacts(payload) {
    const root = unwrapTaskResult(payload);
    const impacts = toArray(root?.impacts);

    return impacts
        .filter((item) => item && typeof item === 'object')
        .flatMap((item, index) => {
            const severity = normalizeLevel(item?.severity || item?.impact_level, 'Medium');
            const reason = firstNonEmpty(item?.reason, item?.description, item?.summary);

            const explicitDepartment = firstNonEmpty(item?.department);
            const deptList = explicitDepartment
                ? [explicitDepartment]
                : toArray(item?.impacted_departments).map((d) => String(d || '').trim()).filter(Boolean);

            if (!reason || deptList.length === 0) {
                console.warn('Skipped invalid impact item from backend:', { index, item });
                return [];
            }

            return deptList.map((department) => ({
                department,
                severity,
                reason,
                source_chunks: Array.isArray(item?.source_chunks) ? item.source_chunks : [],
            }));
        })
        .filter(Boolean);
}

function normalizeActions(payload) {
    const normalized = unwrapTaskResult(payload);
    const actions = toArray(normalized?.actions);
    const seen = new Map();
    return actions
        .filter((item) => item && typeof item === 'object')
        .map((item, index) => {
            const title = firstNonEmpty(item?.title, item?.action, item?.step, item?.action_required);
            const description = firstNonEmpty(item?.description, item?.summary, title ? `Execute: ${title}` : '');
            const department = firstNonEmpty(item?.department, item?.owner);
            const priority = normalizeLevel(item?.priority, 'Medium');

            if (!title || !description || !department || !priority) {
                console.warn('Skipped invalid action item from backend:', { index, item });
                return null;
            }

            const base = String(item.id || title || `action-${index}`).trim();
            const count = (seen.get(base) || 0) + 1;
            seen.set(base, count);

            return {
                title,
                description,
                department,
                priority,
                status: String(item?.status || 'Pending').trim(),
                deadline: String(item?.deadline || 'Current compliance cycle').trim(),
                source_chunks: Array.isArray(item?.source_chunks) ? item.source_chunks : [],
                _ui_key: `${base}-${count}`,
            };
        })
        .filter(Boolean);
}

function normalizeComplianceTrend(payload) {
    const normalized = unwrapTaskResult(payload);
    const trendRoot = normalized?.compliance_trend
        ?? normalized?.impact_analysis?.compliance_trend
        ?? [];

    const rawTrend = Array.isArray(trendRoot)
        ? trendRoot
        : Array.isArray(trendRoot?.trend)
            ? trendRoot.trend
            : Array.isArray(trendRoot?.data)
                ? trendRoot.data
                : [];

    return rawTrend
        .map((item, index) => ({
            date: item?.day || item?.date || item?.name || `Point ${index + 1}`,
            score: Number(item?.value ?? item?.score ?? item?.compliance_score ?? 0)
        }))
        .filter((item) => Number.isFinite(item.score));
}

function normalizeImpactedDepartments(payload, impacts) {
    const impactDepartments = toArray(impacts)
        .map((impact) => impact?.department)
        .filter(Boolean);

    return [...new Set(impactDepartments.map((entry) => String(entry).trim()).filter(Boolean))];
}

function normalizeDepartmentRisk(payload, impacts) {
    const normalized = unwrapTaskResult(payload);
    const direct = toArray(normalized?.department_risk)
        .map((item) => ({
            department: String(item?.department || '').trim(),
            risk_percent: Number(item?.risk_percent || 0),
        }))
        .filter((item) => item.department);

    if (direct.length > 0) {
        return direct
            .map((item) => ({
                department: item.department,
                risk_percent: Math.max(0, Math.min(100, Math.round(item.risk_percent))),
            }))
            .sort((a, b) => b.risk_percent - a.risk_percent);
    }

    console.warn('Missing department_risk in backend payload. Falling back to impact-count normalization.');
    const counts = new Map();
    toArray(impacts).forEach((impact) => {
        const department = String(impact?.department || '').trim();
        if (!department) return;
        counts.set(department, (counts.get(department) || 0) + 1);
    });

    const total = Array.from(counts.values()).reduce((sum, value) => sum + value, 0);
    if (!total) return [];

    let allocated = 0;
    const sorted = Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
    return sorted.map(([department, count], index) => {
        let risk_percent = index === sorted.length - 1
            ? Math.max(0, 100 - allocated)
            : Math.round((count / total) * 100);
        allocated += risk_percent;
        return {
            department,
            risk_percent: Math.max(0, Math.min(100, risk_percent)),
        };
    });
}

function formatStatus(status) {
    const value = (status || '').toString().toLowerCase();
    if (value === 'completed') return 'Completed';
    if (value === 'in_progress' || value === 'in-progress') return 'In Progress';
    if (value === 'overdue') return 'Overdue';
    if (value === 'blocked') return 'Blocked';
    return 'Pending';
}

function getRiskValue(gap) {
    return (gap?.severity || '').toString().toLowerCase();
}

function getCompletionScore(result) {
    const gaps = normalizeGaps(unwrapTaskResult(result));
    const high = gaps.filter((g) => getRiskValue(g) === 'high').length;
    const medium = gaps.filter((g) => getRiskValue(g) === 'medium').length;
    const low = gaps.filter((g) => getRiskValue(g) === 'low').length;
    const penalty = (high * 25) + (medium * 10) + (low * 4);
    return Math.max(0, 100 - penalty);
}

const HIGHLIGHT_STOP_WORDS = new Set([
    'the', 'and', 'for', 'with', 'that', 'this', 'from', 'into', 'have', 'has', 'are', 'was', 'were', 'will', 'shall',
    'must', 'should', 'may', 'can', 'could', 'would', 'does', 'done', 'your', 'their', 'them', 'its', 'about', 'into',
    'upon', 'under', 'over', 'than', 'then', 'when', 'where', 'what', 'which', 'who', 'whom', 'been', 'being', 'also',
]);

function extractHighlightTerms(...values) {
    const terms = [];

    values.flat().forEach((value) => {
        String(value || '')
            .split(/[^A-Za-z0-9]+/)
            .map((term) => term.trim().toLowerCase())
            .filter((term) => term.length > 3 && !HIGHLIGHT_STOP_WORDS.has(term))
            .forEach((term) => terms.push(term));
    });

    return [...new Set(terms)];
}

export default function Dashboard() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [banner, setBanner] = useState(null);
    const [isClearingHistory, setIsClearingHistory] = useState(false);
    const [isDeletingOld, setIsDeletingOld] = useState(false);
    const [sourceViewer, setSourceViewer] = useState({
        open: false,
        title: "",
        chunks: [],
        loading: false,
        highlightTerms: [],
    });
    const [history, setHistory] = useState([]);
    const [currentTaskId, setCurrentTaskId] = useState(null);
    const [user, setUser] = useState(null);
    const router = useRouter();

    const closeSourceViewer = () => {
        setSourceViewer({
            open: false,
            title: "",
            chunks: [],
            loading: false,
            highlightTerms: [],
        });
    };

    const openSourceViewer = async ({ title, sourceChunks, highlightValues = [] }) => {
        const chunkIds = [...new Set((Array.isArray(sourceChunks) ? sourceChunks : []).filter(Boolean))];

        if (chunkIds.length === 0) {
            setBanner({ type: "error", message: "No source chunks are available for this item." });
            return;
        }

        const highlightTerms = extractHighlightTerms(highlightValues, title);
        setSourceViewer({
            open: true,
            title: title || "Source Details",
            chunks: [],
            loading: true,
            highlightTerms,
        });

        try {
            const response = await fetchChunkDetails(chunkIds);
            setSourceViewer((current) => ({
                ...current,
                chunks: Array.isArray(response?.chunks) ? response.chunks : [],
                loading: false,
            }));
        } catch (err) {
            console.error("Failed to fetch chunk details:", err);
            setSourceViewer((current) => ({
                ...current,
                chunks: [],
                loading: false,
            }));
            setBanner({ type: "error", message: "Unable to load source details." });
        }
    };

    const loadDashboardData = async (activeRef = { current: true }) => {
        const response = await fetchTasks();
        console.log("Dashboard API response:", response);

        if (!activeRef.current) return;

        setData(null);
        setCurrentTaskId(null);

        const tasks = Array.isArray(response) ? response : [];
        setHistory(tasks);
        const completed = pickLatestCompletedTask(tasks);

        if (completed) {
            const normalizedResult = unwrapTaskResult(completed.result);
            console.log("Dashboard selected task result:", normalizedResult);
            console.log("FULL API:", normalizedResult);
            console.log("ACTIONS PATH CHECK:", {
                actions1: normalizedResult?.actions,
                actions2: normalizedResult?.result?.actions,
                actions3: normalizedResult?.analysis?.actions,
                actions4: normalizedResult?.generated_actions,
                actions5: normalizedResult?.remediation_actions,
            });
            setData(normalizedResult);
            setCurrentTaskId(completed.task_id);
        } else {
            setData("EMPTY_STATE");
        }
    };

    useEffect(() => {
        const storedUser = localStorage.getItem("regintel_user");
        if (!storedUser) {
            router.push("/login");
            return;
        }

        setUser(JSON.parse(storedUser));
        setLoading(true);
        setError(null);
        setData(null);
        setHistory([]);
        setCurrentTaskId(null);

        const activeRef = { current: true };

        loadDashboardData(activeRef)
            .then(() => {
                if (!activeRef.current) return;
                setLoading(false);
            })
            .catch((err) => {
                console.error("Dashboard load error:", err);
                if (!activeRef.current) return;
                setError("Unable to load dashboard data");
                setData("EMPTY_STATE");
                setLoading(false);
            });

        return () => {
            activeRef.current = false;
        };
    }, [router]);

    if (loading || data === null) return (
        <div className="min-h-screen bg-[#F8FAFC] flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-violet-600"></div>
        </div>
    );

    if (error && data === "EMPTY_STATE") return (
        <div className="min-h-screen bg-[#F8FAFC] text-slate-900 font-sans">
            <TopNavbar user={user} />
            <div className="max-w-[1400px] mx-auto p-8 mt-16">
                <div className="bg-white border border-rose-200 rounded-2xl p-8 text-center shadow-sm">
                    <AlertTriangle className="w-8 h-8 text-rose-500 mx-auto mb-3" />
                    <h2 className="text-xl font-bold text-slate-900 mb-2">Dashboard data unavailable</h2>
                    <p className="text-slate-500 mb-6">{error}. Please retry after your analysis completes.</p>
                    <Link href="/select-mode" className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 transition-colors">
                        <Upload className="w-4 h-4" />
                        Start New Analysis
                    </Link>
                </div>
            </div>
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
                <Link href="/select-mode" className="px-8 py-3.5 bg-slate-900 text-white rounded-xl font-bold flex items-center gap-3 hover:bg-slate-800 transition-all shadow-md">
                    Compare Circulars
                    <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </Link>
            </div>
        </div>
    );

    // DYNAMIC DATA MAPPING (BACKEND-DRIVEN)
    const normalizedData = unwrapTaskResult(data);
    const changesArray = normalizeChanges(normalizedData);
    const changesList = changesArray;
    const gapsArray = normalizeGaps(normalizedData);
    const impactsArray = normalizeImpacts(normalizedData);
    console.log("IMPACTS:", normalizedData?.impacts);
    const impactSystems = [...new Set(toArray(impactsArray).map((impact) => impact?.department).filter(Boolean))];
    const impactSourceChunks = [...new Set(toArray(impactsArray).flatMap((impact) => toArray(impact?.source_chunks)).filter(Boolean))];
    const departmentRisk = normalizeDepartmentRisk(normalizedData, impactsArray);
    const actionsData = normalizeActions(normalizedData);
    const complianceTrendData = normalizeComplianceTrend(normalizedData);
    console.log("Dashboard mapped data:", {
        changes: changesList,
        compliance_gaps: gapsArray,
        impacts: impactsArray,
        actions: actionsData,
        department_risk: departmentRisk,
    });
    console.log("FULL API DATA:", normalizedData);
    console.log("Rendered changes:", changesList.length);
    console.log("Rendered impacts:", impactsArray.length);
    console.log("Rendered compliance gaps:", gapsArray.length);
    console.log("Rendered actions:", actionsData.length);

    const criticalGapsCount = gapsArray.filter((g) => getRiskValue(g) === 'high').length;
    const overallRisk = criticalGapsCount > 0 ? "High" : gapsArray.length > 0 ? "Medium" : "Low";

    const completedTasks = actionsData.filter((a) => (a.status || '').toLowerCase() === 'completed').length;
    const activeTasks = actionsData.filter((a) => (a.status || '').toLowerCase() !== 'completed').length;
    const dueTodayCount = actionsData.filter((a) => (a.priority || '').toLowerCase() === 'high').length || criticalGapsCount;
    const overdueCount = actionsData.filter((a) => (a.status || '').toLowerCase() === 'overdue').length;

    const counts = {
        added: changesList.filter((c) => c.type === 'added').length,
        removed: changesList.filter((c) => c.type === 'removed').length,
        modified: changesList.filter((c) => c.type === 'modified').length,
    };

    const riskData = [
        { name: 'Low', value: gapsArray.filter((g) => getRiskValue(g) === 'low').length, fill: '#10B981' },
        { name: 'Medium', value: gapsArray.filter((g) => getRiskValue(g) === 'medium').length, fill: '#F59E0B' },
        { name: 'High', value: criticalGapsCount, fill: '#EF4444' }
    ];

    const historyScores = history
        .filter((t) => t.status === 'completed' && t.result)
        .reverse()
        .map((t, index) => ({
            date: new Date(t.created_at || Date.now()).toLocaleDateString('en-US', { weekday: 'short' }) || `Run ${index + 1}`,
            score: getCompletionScore(t.result)
        }));

    const trendData = complianceTrendData.length > 0 ? complianceTrendData : historyScores;

    const severityCounts = toArray(impactsArray).reduce((acc, imp) => {
        const severity = (imp?.severity || '').toString().trim().toLowerCase();
        if (severity === 'high') acc.High += 1;
        else if (severity === 'medium') acc.Medium += 1;
        else if (severity === 'low') acc.Low += 1;
        return acc;
    }, { High: 0, Medium: 0, Low: 0 });

    const impactChartData = [
        { name: 'High', value: severityCounts.High },
        { name: 'Medium', value: severityCounts.Medium },
        { name: 'Low', value: severityCounts.Low },
    ];

    const hasTrendData = trendData.length > 0;
    const hasImpactData = impactChartData.some((item) => Number(item?.value || 0) > 0);
    const hasActions = actionsData.length > 0;
    const policyCompliant = changesArray.length === 0 && gapsArray.length === 0 && impactsArray.length === 0 && actionsData.length === 0;

    const handleClearHistory = async () => {
        const confirmed = window.confirm("Are you sure you want to delete all task history?");
        if (!confirmed) return;

        setIsClearingHistory(true);
        setBanner(null);

        try {
            const result = await clearTaskHistory();
            console.log("Clear history response:", result);
            setHistory([]);
            setCurrentTaskId(null);
            setData({});
            setBanner({ type: "success", message: "Task history cleared successfully" });
        } catch (err) {
            console.error("Clear history failed:", err);
            setBanner({ type: "error", message: "Failed to clear task history" });
        } finally {
            setIsClearingHistory(false);
        }
    };

    const handleDeleteOldTasks = async () => {
        const confirmed = window.confirm("Delete tasks older than 7 days?");
        if (!confirmed) return;

        setIsDeletingOld(true);
        setBanner(null);

        try {
            const result = await deleteOldTasks(7);
            console.log("Delete old tasks response:", result);
            const activeRef = { current: true };
            await loadDashboardData(activeRef);
            setBanner({ type: "success", message: `Deleted ${result?.deleted_tasks ?? 0} old tasks` });
        } catch (err) {
            console.error("Delete old tasks failed:", err);
            setBanner({ type: "error", message: "Failed to delete old tasks" });
        } finally {
            setIsDeletingOld(false);
        }
    };

    const handleReloadData = async () => {
        setLoading(true);
        setError(null);

        const activeRef = { current: true };

        try {
            await loadDashboardData(activeRef);
        } catch (err) {
            console.error("Reload data failed:", err);
            setError("Unable to reload dashboard data");
            setData("EMPTY_STATE");
        } finally {
            setLoading(false);
        }
    };

    const handleExport = (format) => {
        if (!currentTaskId) {
            alert("No analysis data available to export.");
            return;
        }
        window.open(`http://127.0.0.1:8000/export/${currentTaskId}/${format}`, '_blank');
    };

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900 font-sans pb-20 relative overflow-hidden">
            {/* Ambient Background Enhancements */}
            <div className="fixed inset-0 pointer-events-none z-0">
                <div className="absolute inset-0 noise-bg opacity-[0.03] mix-blend-overlay"></div>
                <div className="absolute top-[-10%] left-[-10%] w-[40vw] h-[40vw] bg-violet-400/20 rounded-full blur-[120px] mix-blend-multiply opacity-50 animate-blob"></div>
                <div className="absolute top-[20%] right-[-10%] w-[35vw] h-[35vw] bg-cyan-400/20 rounded-full blur-[120px] mix-blend-multiply opacity-50 animate-blob" style={{ animationDelay: '2s' }}></div>
                <div className="absolute bottom-[-10%] left-[20%] w-[40vw] h-[40vw] bg-rose-400/10 rounded-full blur-[120px] mix-blend-multiply opacity-50 animate-blob" style={{ animationDelay: '4s' }}></div>
            </div>

            <div className="relative z-10 w-full h-full">
                <TopNavbar user={user} />

                <div className="max-w-[1400px] mx-auto px-6 xs:px-8 mt-8">

                    {/* Header Section */}
                    <div className="flex flex-col md:flex-row justify-between items-start md:items-end mb-8 gap-4">
                        <div className="relative z-10">
                            <h1 className="text-[2.25rem] font-black tracking-tight text-slate-900 mb-1 drop-shadow-sm">Company Dashboard</h1>
                            <p className="text-slate-500 font-medium">Monitoring circulars and regulatory adherence for RegIntel AI.</p>
                        </div>
                        <div className="flex flex-wrap gap-3 relative z-10">
                            <button
                                onClick={handleClearHistory}
                                disabled={isClearingHistory || isDeletingOld}
                                className="flex items-center gap-2 bg-white/80 backdrop-blur-md border border-rose-200 hover:bg-rose-50 hover:border-rose-300 disabled:opacity-50 text-rose-600 px-4 py-2.5 rounded-xl text-sm font-bold shadow-[0_2px_10px_rgba(225,29,72,0.05)] hover:shadow-[0_4px_15px_rgba(225,29,72,0.1)] transition-all"
                            >
                                {isClearingHistory ? <RefreshCw className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
                                Clear History
                            </button>
                            <button
                                onClick={handleDeleteOldTasks}
                                disabled={isClearingHistory || isDeletingOld}
                                className="flex items-center gap-2 bg-white/80 backdrop-blur-md border border-amber-200 hover:bg-amber-50 hover:border-amber-300 disabled:opacity-50 text-amber-600 px-4 py-2.5 rounded-xl text-sm font-bold shadow-[0_2px_10px_rgba(217,119,6,0.05)] hover:shadow-[0_4px_15px_rgba(217,119,6,0.1)] transition-all"
                            >
                                {isDeletingOld ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Clock className="w-4 h-4" />}
                                Delete Old (7 days)
                            </button>
                            <button
                                onClick={handleReloadData}
                                disabled={loading}
                                className="flex items-center gap-2 bg-white/80 backdrop-blur-md border border-slate-200 hover:bg-slate-50 disabled:opacity-50 text-slate-700 px-4 py-2.5 rounded-xl text-sm font-bold shadow-[0_2px_10px_rgba(0,0,0,0.02)] hover:shadow-[0_4px_15px_rgba(0,0,0,0.06)] transition-all"
                            >
                                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                                Reload Data
                            </button>
                            <Link href="/select-mode" className="flex items-center gap-2 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white px-5 py-2.5 rounded-xl text-sm font-bold shadow-[0_4px_14px_rgba(124,58,237,0.3)] hover:shadow-[0_6px_20px_rgba(124,58,237,0.4)] hover:-translate-y-0.5 transition-all">
                                <Upload className="w-4 h-4" />
                                New Analysis
                            </Link>
                        <div className="relative group/export">
                            <button className="flex items-center gap-2 bg-slate-900 hover:bg-slate-800 text-white px-5 py-2.5 rounded-xl text-sm font-semibold shadow-md transition-all">
                                <FileText className="w-4 h-4" />
                                Export Report
                            </button>
                            <div className="absolute right-0 top-full mt-2 w-40 bg-white border border-slate-200 rounded-xl shadow-xl opacity-0 invisible group-hover/export:opacity-100 group-hover/export:visible transition-all z-30 overflow-hidden">
                                <button onClick={() => handleExport('pdf')} className="w-full text-left px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 border-b border-slate-100 flex items-center gap-2">
                                    <div className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                                    Export as PDF
                                </button>
                                <button onClick={() => handleExport('docx')} className="w-full text-left px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 flex items-center gap-2">
                                    <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                                    Export as Word
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                {banner && (
                    <div className={`mb-6 rounded-xl border px-4 py-3 text-sm font-medium ${banner.type === 'success' ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-rose-50 border-rose-200 text-rose-700'}`}>
                        {banner.message}
                    </div>
                )}

                {policyCompliant && (
                    <div className="mb-6 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">
                        Policy is compliant.
                    </div>
                )}

                {/* 1. KPI Row */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                    <KPICard title="Due Today" value={dueTodayCount} icon={<AlertCircle className="w-5 h-5 text-rose-500" />} color="rose" />
                    <KPICard title="Active Tasks" value={activeTasks} icon={<Clock className="w-5 h-5 text-violet-500" />} color="violet" />
                    <KPICard title="Overdue Tasks" value={overdueCount} icon={<XCircle className="w-5 h-5 text-amber-500" />} color="amber" />
                    <KPICard title="Completed Tasks" value={completedTasks} icon={<CheckCircle2 className="w-5 h-5 text-emerald-500" />} color="emerald" />
                </div>

                {/* Main Charts Grid */}
                <div className="grid lg:grid-cols-3 gap-6 mb-8">
                    {/* 2. Risk Summary Donut */}
                    <div className="group bg-white/70 backdrop-blur-xl rounded-2xl p-6 border border-white shadow-[0_4px_24px_rgba(0,0,0,0.02)] flex flex-col hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)] transition-all duration-300 relative overflow-hidden">
                        <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-rose-500/5 to-transparent rounded-bl-full pointer-events-none"></div>
                        <h3 className="font-bold text-slate-900 mb-1 drop-shadow-sm">Overall Risk</h3>
                        <p className="text-sm text-slate-500 mb-6 relative z-10">Current compliance posture</p>
                        <div className="flex-grow flex items-center justify-center relative min-h-[200px] z-10 group-hover:scale-105 transition-transform duration-500">
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie data={riskData} innerRadius={60} outerRadius={80} paddingAngle={4} dataKey="value" stroke="rgba(255,255,255,0.5)" strokeWidth={2} cornerRadius={5} animationDuration={1000} animationEasing="ease-out">
                                        {riskData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.fill} className="hover:opacity-80 transition-opacity" />)}
                                    </Pie>
                                    <Tooltip contentStyle={{ borderRadius: '16px', border: '1px solid rgba(255,255,255,0.5)', boxShadow: '0 10px 40px -10px rgba(0,0,0,0.1)', background: 'rgba(255,255,255,0.9)', backdropFilter: 'blur(8px)' }} />
                                </PieChart>
                            </ResponsiveContainer>
                            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                                <span className={`text-[1.75rem] font-black ${overallRisk === 'High' ? 'text-rose-500 drop-shadow-[0_2px_10px_rgba(244,63,94,0.3)]' : overallRisk === 'Medium' ? 'text-amber-500 drop-shadow-[0_2px_10px_rgba(245,158,11,0.3)]' : 'text-emerald-500 drop-shadow-[0_2px_10px_rgba(16,185,129,0.3)]'}`}>{overallRisk}</span>
                                <span className="text-[10px] text-slate-400 uppercase tracking-[0.2em] font-extrabold mt-1">Status</span>
                            </div>
                        </div>
                    </div>

                    {/* 3. Performance Trend */}
                    <div className="group bg-white/70 backdrop-blur-xl rounded-2xl p-6 border border-white shadow-[0_4px_24px_rgba(0,0,0,0.02)] col-span-1 lg:col-span-2 flex flex-col hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)] transition-all duration-300 relative overflow-hidden">
                        <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-br from-violet-500/5 to-transparent rounded-bl-full pointer-events-none"></div>
                        <h3 className="font-bold text-slate-900 mb-1 drop-shadow-sm">Compliance Performance</h3>
                        <p className="text-sm text-slate-500 mb-6">7-day adherence trend</p>
                        {hasTrendData ? (
                            <div className="flex-grow min-h-[200px] w-full relative z-10">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={trendData} margin={{ top: 30, right: 30, left: 0, bottom: 30 }}>
                                        <defs>
                                            <linearGradient id="colorScore" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#8B5CF6" stopOpacity={0.3}/>
                                                <stop offset="95%" stopColor="#8B5CF6" stopOpacity={0}/>
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" opacity={0.5} />
                                        <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fontSize: 13, fill: '#64748B', fontWeight: 500 }} padding={{ left: 30, right: 30 }} dy={15} />
                                        <YAxis type="number" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} axisLine={false} tickLine={false} tick={{ fontSize: 13, fill: '#64748B', fontWeight: 500 }} dx={-10} />
                                        <Tooltip
                                            contentStyle={{ borderRadius: '16px', border: '1px solid rgba(255,255,255,0.5)', boxShadow: '0 10px 40px -10px rgba(0,0,0,0.1)', background: 'rgba(255,255,255,0.9)', backdropFilter: 'blur(8px)' }}
                                            itemStyle={{ color: '#0F172A', fontWeight: 700 }}
                                            cursor={{ stroke: '#8B5CF6', strokeWidth: 1, strokeDasharray: '4 4' }}
                                        />
                                        <Line type="monotone" dataKey="score" stroke="url(#colorScore)" strokeWidth={0} fill="url(#colorScore)" />
                                        <Line type="monotone" dataKey="score" stroke="#8B5CF6" strokeWidth={4} dot={{ r: 6, fill: '#fff', stroke: '#8B5CF6', strokeWidth: 3 }} activeDot={{ r: 8, fill: '#8B5CF6', stroke: '#fff', strokeWidth: 3 }} animationDuration={1500} animationEasing="ease-in-out" />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        ) : (
                            <div className="flex-grow min-h-[200px] border border-dashed border-slate-200/60 bg-slate-50/50 rounded-2xl flex items-center justify-center text-sm font-medium text-slate-500 backdrop-blur-sm relative z-10">
                                No data available
                            </div>
                        )}
                    </div>
                </div>

                <div className="grid lg:grid-cols-3 gap-6 mb-8">
                    {/* 5. Regulatory Changes List */}
                    <div className="group bg-white/70 backdrop-blur-xl rounded-2xl p-6 border border-white shadow-[0_4px_24px_rgba(0,0,0,0.02)] flex flex-col max-h-[400px] hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)] transition-all duration-300">
                        <h3 className="font-bold text-slate-900 mb-1">Regulatory Changes</h3>
                        <p className="text-sm text-slate-500 mb-4">Recent policy deltas from latest analysis</p>

                        <div className="flex items-center gap-2 mb-4 text-xs font-semibold text-slate-600">
                            <span className="px-2 py-1 rounded-full bg-green-100 text-green-700">Added: {counts.added}</span>
                            <span className="px-2 py-1 rounded-full bg-red-100 text-red-700">Removed: {counts.removed}</span>
                            <span className="px-2 py-1 rounded-full bg-yellow-100 text-yellow-700">Modified: {counts.modified}</span>
                        </div>

                        <div className="overflow-y-auto pr-2">
                            {changesList.length > 0 ? (
                                changesList.map((item, index) => (
                                    <div key={`${item.section || 'change'}-${index}`} className="border-b border-slate-100 pb-2 mb-2 last:border-b-0 last:mb-0">
                                        <div className="flex justify-between items-center gap-3">
                                            <span className="font-medium text-sm text-slate-800 truncate">
                                                {item.title}
                                            </span>

                                            <div className="flex items-center gap-2">
                                                <span className={`text-xs px-2 py-1 rounded-full capitalize ${item.type === 'added'
                                                        ? 'bg-green-100 text-green-700'
                                                        : item.type === 'removed'
                                                            ? 'bg-red-100 text-red-700'
                                                            : 'bg-yellow-100 text-yellow-700'
                                                    }`}>
                                                    {item.type || 'modified'}
                                                </span>
                                                <button
                                                    type="button"
                                                    onClick={() => openSourceViewer({
                                                        title: item.section || item.category || 'Regulatory Change Source',
                                                        sourceChunks: item.source_chunks,
                                                        highlightValues: [item.summary, item.source, item.title],
                                                    })}
                                                    disabled={!Array.isArray(item.source_chunks) || item.source_chunks.length === 0}
                                                    className="inline-flex items-center gap-1 rounded-full border border-slate-200 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-slate-600 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                                                >
                                                    <Eye className="h-3.5 w-3.5" />
                                                    View Source
                                                </button>
                                            </div>
                                        </div>

                                        <p className="text-sm text-gray-600 mt-1">
                                            {item.summary}
                                        </p>
                                    </div>
                                ))
                            ) : (
                                <p className="text-sm text-slate-500">No changes detected</p>
                            )}
                        </div>
                    </div>

                    {/* 6. Impact Analysis Horizontal Bar */}
                    <div className="group bg-white/70 backdrop-blur-xl rounded-2xl p-6 border border-white shadow-[0_4px_24px_rgba(0,0,0,0.02)] lg:col-span-1 flex flex-col hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)] transition-all duration-300">
                        <div className="flex items-center justify-between gap-3 mb-1">
                            <h3 className="font-bold text-slate-900">Impact Severity</h3>
                            <button
                                type="button"
                                onClick={() => openSourceViewer({
                                    title: 'Impact Source Details',
                                    sourceChunks: impactSourceChunks,
                                    highlightValues: [impactSystems.join(' ')],
                                })}
                                disabled={!impactSourceChunks.length}
                                className="inline-flex items-center gap-1 rounded-full border border-slate-200 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-slate-600 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                                <Eye className="h-3.5 w-3.5" />
                                View Source
                            </button>
                        </div>
                        <p className="text-sm text-slate-500 mb-6">Severity distribution of detected impacts</p>
                        {hasImpactData ? (
                            <div className="flex-grow min-h-[200px]">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart layout="vertical" data={impactChartData} margin={{ top: 0, right: 24, left: 0, bottom: 0 }} barSize={16}>
                                        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#E2E8F0" />
                                        <XAxis type="number" hide />
                                        <YAxis
                                            dataKey="name"
                                            type="category"
                                            width={130}
                                            interval={0}
                                            axisLine={false}
                                            tickLine={false}
                                            tick={{ fontSize: 13, fill: '#0F172A', fontWeight: 500 }}
                                        />
                                        <Tooltip cursor={{ fill: '#F8FAFC' }} contentStyle={{ borderRadius: '12px', border: '1px solid #E2E8F0', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                                        <Bar dataKey="value" fill="#A78BFA" radius={[0, 4, 4, 0]} label={{ position: 'right', fill: '#64748B', fontSize: 12 }} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        ) : (
                            <div className="flex-grow min-h-[200px] border border-dashed border-slate-200 rounded-xl flex items-center justify-center text-sm font-medium text-slate-500">
                                No data available
                            </div>
                        )}
                    </div>

                    {/* 4. Compliance Gaps List */}
                    <div className="group bg-white/70 backdrop-blur-xl rounded-2xl p-6 border border-white shadow-[0_4px_24px_rgba(0,0,0,0.02)] flex flex-col max-h-[400px] hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)] transition-all duration-300">
                        <h3 className="font-bold text-slate-900 mb-1">Compliance Gaps</h3>
                        <p className="text-sm text-slate-500 mb-4">Urgent review required</p>
                        <div className="overflow-y-auto pr-2 space-y-4">
                            {gapsArray.length > 0 ? gapsArray.map((gap, i) => {
                                const severity = (gap.severity || '').toLowerCase();
                                const isHigh = severity === 'high';
                                const color = isHigh ? 'bg-rose-500' : 'bg-amber-500';
                                const bg = isHigh ? 'bg-rose-50' : 'bg-amber-50';
                                return (
                                    <div key={gap._ui_key || `${currentTaskId || 'gap'}-${i}`} className={`p-4 rounded-[12px] border ${isHigh ? 'border-rose-100' : 'border-amber-100'} ${bg} flex items-start gap-4`}>
                                        <div className="mt-1"><AlertTriangle className={`w-5 h-5 ${isHigh ? 'text-rose-500' : 'text-amber-500'}`} /></div>
                                        <div className="flex-1">
                                            <p className="text-sm font-bold text-slate-900 leading-tight mb-1">{gap.title}</p>
                                            <p className="text-xs text-slate-600 mb-3 line-clamp-2">{gap.description}</p>
                                            <div className="flex items-center justify-between gap-3">
                                                <div className="h-1.5 w-full bg-slate-200/50 rounded-full overflow-hidden border border-black/5">
                                                    <div className={`h-full ${color}`} style={{ width: severity === 'low' ? '35%' : isHigh ? '90%' : '60%' }} />
                                                </div>
                                                <div className="flex items-center gap-2 shrink-0">
                                                    <span className={`text-[10px] font-bold uppercase tracking-widest ${isHigh ? 'text-rose-600' : 'text-amber-600'}`}>{gap.severity}</span>
                                                    <button
                                                        type="button"
                                                        onClick={() => openSourceViewer({
                                                            title: 'Compliance Gap Source Details',
                                                            sourceChunks: gap.source_chunks,
                                                            highlightValues: [gap.title, gap.description, gap.recommendation],
                                                        })}
                                                        disabled={!Array.isArray(gap.source_chunks) || gap.source_chunks.length === 0}
                                                        className="inline-flex items-center gap-1 rounded-full border border-slate-200 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-slate-600 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                                                    >
                                                        <Eye className="h-3.5 w-3.5" />
                                                        View Source
                                                    </button>
                                                </div>
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

                <div className="group bg-white/70 backdrop-blur-xl rounded-2xl border border-white shadow-[0_4px_24px_rgba(0,0,0,0.02)] p-6 mb-8 hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)] transition-all duration-300">
                    <h3 className="font-bold text-slate-900 mb-1 drop-shadow-sm">Impacted Departments</h3>
                    <p className="text-sm text-slate-500 mb-4">Teams affected by current regulatory updates</p>
                    {departmentRisk.length > 0 ? (
                        <div className="space-y-3">
                            {departmentRisk.map((item, idx) => {
                                const percent = Math.max(0, Math.min(100, Number(item?.risk_percent || 0)));
                                const colorClass = percent > 70
                                    ? 'bg-rose-500'
                                    : percent >= 40
                                        ? 'bg-amber-400'
                                        : 'bg-emerald-500';

                                const textColor = percent > 70
                                    ? 'text-rose-700'
                                    : percent >= 40
                                        ? 'text-amber-700'
                                        : 'text-emerald-700';

                                return (
                                    <div key={`${item.department}-${idx}`} className="rounded-xl border border-slate-200 px-3 py-2.5 bg-slate-50/60">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className="text-sm font-semibold text-slate-900">{item.department}</span>
                                            <span className={`text-xs font-bold ${textColor}`}>{percent}%</span>
                                        </div>
                                        <div className="h-2 w-full bg-slate-200 rounded-full overflow-hidden">
                                            <div className={`h-full ${colorClass}`} style={{ width: `${percent}%` }} />
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    ) : (
                        <div className="border border-dashed border-slate-200 rounded-xl px-4 py-6 text-sm font-medium text-slate-500 text-center">
                            No data available
                        </div>
                    )}
                </div>

                {/* 7. Action Plan / Remediation Timeline */}
                <div className="group bg-white/70 backdrop-blur-xl rounded-2xl border border-white shadow-[0_4px_24px_rgba(0,0,0,0.02)] overflow-hidden mb-12 hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)] transition-all duration-300">
                    <div className="p-6 border-b border-slate-100 flex items-center justify-between">
                        <div>
                            <h3 className="font-bold text-slate-900 mb-1">Remediation Action Plan</h3>
                            <p className="text-sm text-slate-500">Track progress of generated workflows</p>
                        </div>
                        <button className="text-sm font-semibold text-violet-600 hover:text-violet-700 transition-colors">View All Actions</button>
                    </div>

                    <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
                        <table className="w-full text-left border-collapse">
                            <thead>
                                <tr className="bg-slate-50 border-b border-slate-200">
                                    <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-widest text-left">Title</th>
                                    <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-widest min-w-[300px]">Description</th>
                                    <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-widest w-40">Status</th>
                                    <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-widest text-right">Deadline</th>
                                    <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-widest text-right">Source</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {hasActions ? actionsData.map((action, i) => {
                                    const status = String(action?.status || '').toLowerCase();
                                    const statusText = formatStatus(action?.status);
                                    const statusColor = status === 'completed' ? 'text-emerald-700 bg-emerald-100/50 border border-emerald-200'
                                        : status === 'in_progress' || status === 'in-progress' ? 'text-violet-700 bg-violet-100/50 border border-violet-200'
                                            : status === 'overdue' || status === 'blocked' ? 'text-rose-700 bg-rose-100/50 border border-rose-200'
                                                : 'text-amber-700 bg-amber-100/50 border border-amber-200';
                                    const title = action?.title;
                                    const description = action?.description;
                                    const deadline = action?.deadline;
                                    const actionSourceChunks = Array.isArray(action?.source_chunks) ? action.source_chunks : [];

                                    return (
                                        <tr key={action._ui_key || `${currentTaskId || 'action'}-${i}`} className="hover:bg-slate-50 transition-colors">
                                            <td className="px-6 py-4">
                                                <p className="text-sm font-bold text-slate-900">{title}</p>
                                            </td>
                                            <td className="px-6 py-4">
                                                <p className="text-sm text-slate-600 leading-relaxed">{description}</p>
                                            </td>
                                            <td className="px-6 py-4">
                                                <span className={`inline-flex px-2.5 py-1 rounded-md text-[11px] font-bold uppercase tracking-widest ${statusColor}`}>
                                                    {statusText}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4 text-right">
                                                <span className="text-sm font-semibold text-slate-700">{deadline}</span>
                                            </td>
                                            <td className="px-6 py-4 text-right">
                                                <button
                                                    type="button"
                                                    onClick={() => openSourceViewer({
                                                        title: title,
                                                        sourceChunks: actionSourceChunks,
                                                        highlightValues: [title, description],
                                                    })}
                                                    disabled={actionSourceChunks.length === 0}
                                                    className="inline-flex items-center gap-1 rounded-full border border-slate-200 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-slate-600 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                                                >
                                                    <Eye className="h-3.5 w-3.5" />
                                                    View Source
                                                </button>
                                            </td>
                                        </tr>
                                    );
                                }) : (
                                    <tr>
                                        <td colSpan={5} className="px-6 py-12 text-center">
                                            <CheckCircle2 className="w-8 h-8 text-slate-300 mx-auto mb-3" />
                                            <p className="text-slate-500 font-medium text-sm">No actions generated</p>
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* 8. Recent Analysis History Section */}
                <div id="analysis-history" className="group bg-white/70 backdrop-blur-xl rounded-2xl border border-white shadow-[0_4px_24px_rgba(0,0,0,0.02)] overflow-hidden mb-12 hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)] transition-all duration-300">
                    <div className="p-6 border-b border-slate-100 flex items-center justify-between">
                        <div>
                            <h3 className="font-bold text-slate-900 mb-1">Recent Analysis History</h3>
                            <p className="text-sm text-slate-500">View and access your previous compliance runs</p>
                        </div>
                    </div>

                    <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse">
                            <thead>
                                <tr className="bg-slate-50 border-b border-slate-200">
                                    <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-widest text-left">Analysis ID</th>
                                    <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-widest">Status</th>
                                    <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-widest">Timestamp</th>
                                    <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-widest text-right">Action</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {history.length > 0 ? history.slice().reverse().map((task, i) => (
                                    <tr key={task.task_id || `${task.created_at || 'task'}-${i}`} className="hover:bg-slate-50 transition-colors">
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center">
                                                    <FileText className="w-4 h-4 text-slate-500" />
                                                </div>
                                                <span className="text-sm font-bold text-slate-900 font-mono truncate max-w-[120px]">{task.task_id}</span>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className={`inline-flex px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-widest 
                                                ${task.status === 'completed' ? 'text-emerald-700 bg-emerald-100/50 border border-emerald-200'
                                                    : task.status === 'failed' ? 'text-rose-700 bg-rose-100/50 border border-rose-200'
                                                        : 'text-violet-700 bg-violet-100/50 border border-violet-200'}`}>
                                                {task.status}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-sm font-semibold text-slate-500">
                                            {new Date(task.created_at || Date.now()).toLocaleString()}
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <button className="text-violet-600 hover:text-violet-700 text-sm font-bold">View Details</button>
                                        </td>
                                    </tr>
                                )) : (
                                    <tr>
                                        <td colSpan={4} className="px-6 py-12 text-center text-slate-500 font-medium text-sm">No analysis history found.</td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>

            </div>
            </div>

            <SourceViewerModal
                isOpen={sourceViewer.open}
                title={sourceViewer.title}
                chunks={sourceViewer.chunks}
                loading={sourceViewer.loading}
                highlightTerms={sourceViewer.highlightTerms}
                onClose={closeSourceViewer}
            />
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
        <div className="sticky top-0 z-50 w-full bg-white/70 backdrop-blur-2xl border-b border-slate-200/60 shadow-[0_2px_20px_rgba(0,0,0,0.02)] px-6 h-18 flex items-center justify-between transition-all duration-300 py-3">
            <div className="flex items-center gap-2.5">
                <Link href="/dashboard" className="flex items-center gap-2.5 group">
                    <div className="w-9 h-9 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-violet-500/30 group-hover:scale-105 group-hover:shadow-violet-500/50 transition-all duration-300 relative overflow-hidden">
                        <div className="absolute inset-0 bg-white/20 opacity-0 group-hover:opacity-100 transition-opacity"></div>
                        <Shield className="w-5 h-5 text-white relative z-10" />
                    </div>
                    <span className="font-extrabold text-xl tracking-tight text-slate-900 hidden sm:block group-hover:text-violet-600 transition-colors">RegIntel AI</span>
                </Link>
            </div>

            <div className="flex items-center gap-6 ml-10 hidden lg:flex">
                <Link href="/select-mode" className="text-sm font-bold text-slate-500 hover:text-violet-600 transition-colors flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-violet-50/50">
                    <Upload className="w-4 h-4" />
                    New Analysis
                </Link>
                <button
                    onClick={() => document.getElementById('analysis-history')?.scrollIntoView({ behavior: 'smooth' })}
                    className="text-sm font-bold text-slate-500 hover:text-violet-600 transition-colors flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-violet-50/50"
                >
                    <Clock className="w-4 h-4" />
                    History
                </button>
            </div>

            <div className="flex-1 max-w-sm mx-6 hidden xl:block">
                <div className="relative group">
                    <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within:text-violet-500 transition-colors" />
                    <input type="text" placeholder="Search insights, documents, gaps..."
                        className="w-full bg-slate-100/50 border border-slate-200/50 rounded-full py-2.5 pl-10 pr-4 text-sm text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:bg-white transition-all placeholder:text-slate-400 hover:bg-slate-100/80 shadow-inner" />
                </div>
            </div>

            <div className="flex items-center gap-4">
                <button className="relative p-2.5 text-slate-500 hover:text-violet-600 transition-all rounded-full hover:bg-violet-50">
                    <Bell className="w-5 h-5 flex-shrink-0 group-hover:animate-swing" />
                    <span className="absolute top-2 right-2 w-2 h-2 bg-rose-500 rounded-full border-2 border-white animate-pulse" />
                </button>
                <div className="h-6 border-l border-slate-200 hidden sm:block" />
                <div className="flex items-center gap-3 bg-slate-50 hover:bg-slate-100 border border-slate-100 hover:border-slate-200 rounded-full pl-4 pr-1.5 py-1.5 transition-all cursor-pointer">
                    <div className="hidden sm:block text-right">
                        <p className="text-sm font-extrabold text-slate-900 leading-tight">{user?.name || "Jane Doe"}</p>
                        <button onClick={handleLogout} className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-0.5 hover:text-rose-600 transition-colors">Log Out</button>
                    </div>
                    <div className="w-9 h-9 rounded-full bg-gradient-to-r from-violet-100 to-indigo-100 flex items-center justify-center border border-white shadow-sm shrink-0">
                        <User className="w-4 h-4 text-violet-600" />
                    </div>
                </div>
            </div>
        </div>
    );
}

function KPICard({ title, value, icon, color }) {
    const bgColors = {
        rose: 'bg-rose-500/10 text-rose-600 border-rose-500/20',
        violet: 'bg-violet-500/10 text-violet-600 border-violet-500/20',
        amber: 'bg-amber-500/10 text-amber-600 border-amber-500/20',
        emerald: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20'
    };
    return (
        <div className="group bg-white/70 backdrop-blur-xl rounded-2xl p-6 border border-white shadow-[0_4px_24px_rgba(0,0,0,0.02)] flex items-center gap-5 hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)] hover:-translate-y-1 transition-all duration-300 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-white/40 to-transparent rounded-bl-full pointer-events-none mix-blend-overlay"></div>
            <div className={`w-14 h-14 rounded-2xl ${bgColors[color]} flex items-center justify-center flex-shrink-0 border shadow-inner group-hover:scale-110 transition-transform duration-300`}>
                {icon}
            </div>
            <div className="relative z-10">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-1 group-hover:text-slate-700 transition-colors">{title}</p>
                <p className="text-3xl font-black text-slate-900 tracking-tight">{value}</p>
            </div>
        </div>
    );
}
