"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ScanSearch, FileCheck2, Bot } from "lucide-react";

export default function InteractiveFeatures() {
  const [activeTab, setActiveTab] = useState(0);

  const features = [
    {
      title: "Real-time Delta Scanning",
      description: "Our AI visually highlights every line, clause, and subsection that has changed between historical circulars and new releases.",
      icon: ScanSearch,
      highlight: "from-blue-500 to-cyan-400",
      imageMock: (
        <div className="w-full h-full bg-slate-900 rounded-xl p-4 flex flex-col font-mono text-xs text-slate-300 shadow-2xl overflow-hidden relative">
          <div className="absolute inset-0 bg-grid-pattern opacity-10"></div>
          <div className="flex gap-2 mb-4 border-b border-slate-700 pb-2">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
          </div>
          <div className="space-y-3">
            <p className="opacity-50 line-through decoration-red-500">Old Clause: Liquidity Coverage Ratio (LCR) requirement remains at 100%.</p>
            <motion.p 
              initial={{ backgroundPosition: "200% 0" }}
              animate={{ backgroundPosition: "0% 0" }}
              transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
              className="bg-green-500/20 text-green-300 p-2 border-l-2 border-green-500 w-fit"
            >
              New Clause: LCR requirement increased to 110% effective immediately.
            </motion.p>
            <p className="opacity-50">Impact: High</p>
          </div>
        </div>
      )
    },
    {
      title: "Impact Matrix Generation",
      description: "Automatically maps new regulatory clauses to your internal team departments and existing policies.",
      icon: FileCheck2,
      highlight: "from-violet-500 to-indigo-500",
      imageMock: (
        <div className="w-full h-full bg-white rounded-xl p-6 shadow-2xl flex flex-col gap-4">
           <div className="h-8 w-1/3 bg-slate-100 rounded-lg animate-pulse"></div>
           <div className="grid grid-cols-2 gap-4">
             <div className="h-24 bg-violet-50 rounded-xl border border-violet-100 p-3">
                <div className="text-violet-800 font-bold mb-2">Compliance Dept</div>
                <div className="h-2 bg-violet-200 rounded w-3/4 mb-2"></div>
                <div className="h-2 bg-violet-200 rounded w-1/2"></div>
             </div>
             <div className="h-24 bg-indigo-50 rounded-xl border border-indigo-100 p-3">
                <div className="text-indigo-800 font-bold mb-2">Risk Team</div>
                <div className="h-2 bg-indigo-200 rounded w-full mb-2"></div>
                <div className="h-2 bg-indigo-200 rounded w-2/3"></div>
             </div>
           </div>
        </div>
      )
    },
    {
      title: "AI Action Plans",
      description: "From dense legal text to a step-by-step Kanban board of Jira-ready tasks for your engineering and legal teams.",
      icon: Bot,
      highlight: "from-emerald-500 to-teal-400",
      imageMock: (
        <div className="w-full h-full bg-slate-50 rounded-xl p-4 shadow-2xl overflow-hidden">
          <div className="flex gap-4">
             <div className="w-1/3 space-y-3">
                <div className="text-xs font-bold text-slate-400 uppercase">To Do</div>
                <motion.div animate={{ y: [0, -5, 0] }} transition={{ duration: 3, repeat: Infinity }} className="h-20 bg-white shadow-sm rounded-lg border border-slate-200 p-2">
                  <div className="h-2 bg-emerald-200 rounded mb-2 w-1/4"></div>
                  <div className="h-3 bg-slate-200 rounded mb-2 w-full"></div>
                  <div className="h-3 bg-slate-200 rounded w-5/6"></div>
                </motion.div>
                <div className="h-20 bg-white shadow-sm rounded-lg border border-slate-200 p-2 opacity-50"></div>
             </div>
             <div className="w-1/3 space-y-3">
               <div className="text-xs font-bold text-slate-400 uppercase">In Progress</div>
               <div className="h-24 bg-white shadow-sm rounded-lg border border-slate-200 p-2"></div>
             </div>
          </div>
        </div>
      )
    }
  ];

  return (
    <section className="py-32 bg-white relative">
      <div className="absolute top-0 right-0 w-1/2 h-full bg-slate-50 -z-10 rounded-l-[100px]"></div>
      
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex flex-col lg:flex-row gap-16 items-center">
          
          <div className="w-full lg:w-1/2 space-y-4">
            <h2 className="text-4xl md:text-5xl font-extrabold mb-8 tracking-tight text-slate-900">
              Beyond Document Parsing
            </h2>
            
            <div className="space-y-4">
              {features.map((feature, idx) => {
                const isActive = activeTab === idx;
                const Icon = feature.icon;
                return (
                  <div 
                    key={idx}
                    onClick={() => setActiveTab(idx)}
                    className={`p-6 rounded-2xl cursor-pointer transition-all duration-300 border-2 ${
                      isActive 
                        ? "bg-white border-violet-500 shadow-xl scale-[1.02]" 
                        : "bg-slate-50 border-transparent hover:bg-slate-100 opacity-70 hover:opacity-100"
                    }`}
                  >
                    <div className="flex gap-4">
                      <div className={`mt-1 flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center ${
                        isActive ? `bg-gradient-to-br ${feature.highlight} text-white shadow-lg` : "bg-slate-200 text-slate-500"
                      }`}>
                        <Icon className="w-6 h-6" />
                      </div>
                      <div>
                        <h4 className={`text-xl font-bold mb-2 ${isActive ? "text-slate-900" : "text-slate-700"}`}>
                          {feature.title}
                        </h4>
                        {isActive && (
                           <motion.p 
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            className="text-slate-500 font-medium leading-relaxed"
                           >
                            {feature.description}
                           </motion.p>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          
          <div className="w-full lg:w-1/2">
            <div className="relative w-full aspect-square md:aspect-[4/3] rounded-[2rem] bg-slate-100 overflow-hidden shadow-2xl border-4 border-white">
              <AnimatePresence mode="wait">
                <motion.div
                  key={activeTab}
                  initial={{ opacity: 0, scale: 0.95, y: 20 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 1.05, y: -20 }}
                  transition={{ duration: 0.5, ease: "easeOut" }}
                  className="absolute inset-0 p-8"
                >
                  <div className="w-full h-full relative">
                    {/* Glowing backdrop matching the active tab */}
                    <div className={`absolute inset-0 bg-gradient-to-br ${features[activeTab].highlight} opacity-20 blur-3xl -z-10`}></div>
                    {features[activeTab].imageMock}
                  </div>
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
