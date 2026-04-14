"use client";

import { motion } from "framer-motion";
import { UploadCloud, FileSearch, GitCompare, BrainCircuit, LineChart } from "lucide-react";

const steps = [
  { id: "step-1", title: "Upload", icon: UploadCloud, color: "text-blue-500", bg: "bg-blue-100", border: "border-blue-200" },
  { id: "step-2", title: "Parse", icon: FileSearch, color: "text-indigo-500", bg: "bg-indigo-100", border: "border-indigo-200" },
  { id: "step-3", title: "Compare", icon: GitCompare, color: "text-violet-500", bg: "bg-violet-100", border: "border-violet-200" },
  { id: "step-4", title: "Analyze", icon: BrainCircuit, color: "text-fuchsia-500", bg: "bg-fuchsia-100", border: "border-fuchsia-200" },
  { id: "step-5", title: "Output", icon: LineChart, color: "text-emerald-500", bg: "bg-emerald-100", border: "border-emerald-200" },
];

export default function WorkflowVisualizer() {
  return (
    <section className="py-24 relative overflow-hidden">
      <div className="absolute inset-0 bg-grid-pattern opacity-30 pointer-events-none"></div>
      
      <div className="max-w-7xl mx-auto px-6 relative z-10">
        <div className="text-center max-w-2xl mx-auto mb-20">
          <motion.h2 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-4xl md:text-5xl font-extrabold mb-6 tracking-tight text-slate-900"
          >
            The RegIntel AI Pipeline
          </motion.h2>
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
            className="text-slate-500 text-lg leading-relaxed font-medium"
          >
            Millions of data points processed, mapped, and simplified for your compliance team in seconds.
          </motion.p>
        </div>

        <div className="relative mt-20">
          {/* Connecting Line */}
          <div className="absolute top-1/2 left-[10%] right-[10%] h-1 bg-slate-200 -translate-y-1/2 hidden md:block rounded-full overflow-hidden">
            <motion.div 
              initial={{ width: "0%" }}
              whileInView={{ width: "100%" }}
              viewport={{ once: true, margin: "-100px" }}
              transition={{ duration: 1.5, ease: "easeInOut" }}
              className="h-full bg-gradient-to-r from-blue-500 via-violet-500 to-emerald-500 drop-shadow-[0_0_8px_rgba(139,92,246,0.5)]"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-8 md:gap-0 relative z-10">
            {steps.map((step, index) => {
              const Icon = step.icon;
              return (
                <motion.div 
                  key={step.id}
                  initial={{ opacity: 0, y: 30, scale: 0.9 }}
                  whileInView={{ opacity: 1, y: 0, scale: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: index * 0.2 + 0.5, duration: 0.6, type: "spring", bounce: 0.4 }}
                  whileHover={{ y: -15 }}
                  className="flex flex-col items-center relative group"
                >
                  <div className={`w-20 h-20 rounded-2xl flex items-center justify-center bg-white border-2 shadow-float relative cursor-pointer group-hover:scale-110 transition-transform duration-300 ${step.border} z-10`}>
                    <motion.div
                       animate={{ rotate: [0, 5, -5, 0] }}
                       transition={{ duration: 4, repeat: Infinity, ease: "linear", delay: index }}
                    >
                      <Icon className={`w-10 h-10 ${step.color}`} strokeWidth={2.5} />
                    </motion.div>
                    
                    {/* Glow effect behind icon */}
                    <div className={`absolute inset-0 ${step.bg} blur-xl opacity-0 group-hover:opacity-60 transition-opacity duration-300 -z-10 rounded-2xl`}></div>
                  </div>
                  
                  <div className="mt-6 text-center">
                    <span className="text-sm font-bold text-slate-400 block mb-1 uppercase tracking-widest">Step 0{index + 1}</span>
                    <h4 className="text-xl font-extrabold text-slate-900">{step.title}</h4>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
