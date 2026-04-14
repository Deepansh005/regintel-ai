"use client";

import { motion } from "framer-motion";
import { FileText, ArrowRight, CheckCircle2 } from "lucide-react";

export default function DemoPreviewCard() {
  return (
    <div className="relative w-full max-w-lg mx-auto transform perspective-1000">
      <motion.div 
        whileHover={{ scale: 1.05, rotateY: -5, rotateX: 5 }}
        transition={{ type: "spring", stiffness: 300, damping: 20 }}
        className="w-full bg-slate-900 rounded-3xl p-6 shadow-2xl overflow-hidden relative border border-slate-700/50 cursor-crosshair"
      >
        {/* Glow effect */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-brand-500/30 rounded-full blur-[80px] -translate-y-1/2 translate-x-1/3"></div>
        <div className="absolute bottom-0 left-0 w-64 h-64 bg-cyan-500/20 rounded-full blur-[80px] translate-y-1/2 -translate-x-1/2"></div>
        
        {/* UI Mockup Header */}
        <div className="flex items-center justify-between mb-6 border-b border-slate-800 pb-4 relative z-10">
          <div className="flex items-center gap-3 text-slate-300">
            <FileText className="w-5 h-5 text-brand-400" />
            <span className="font-mono text-xs font-bold tracking-wider">RBI_Master_Circular_2026.pdf</span>
          </div>
          <div className="flex gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-slate-700"></div>
            <div className="w-2.5 h-2.5 rounded-full bg-slate-700"></div>
            <div className="w-2.5 h-2.5 rounded-full bg-slate-700"></div>
          </div>
        </div>

        {/* Mock Content */}
        <div className="space-y-4 relative z-10">
          {/* Item 1 */}
          <div className="bg-slate-800/50 p-4 rounded-xl border border-slate-700/50 flex gap-4 items-start">
            <div className="mt-1">
               <motion.div
                 initial={{ scale: 0 }}
                 whileInView={{ scale: 1 }}
                 transition={{ delay: 0.2, type: "spring" }}
                 viewport={{ once: true }}
               >
                 <CheckCircle2 className="w-5 h-5 text-emerald-400" />
               </motion.div>
            </div>
            <div>
              <h5 className="text-sm font-bold text-white mb-1">Capital Requirement Clause 4.2</h5>
              <div className="flex items-center gap-2 text-xs">
                <span className="text-slate-400 line-through">Requires 8%</span>
                <ArrowRight className="w-3 h-3 text-brand-400" />
                <span className="text-emerald-300 font-mono bg-emerald-400/20 px-1 py-0.5 rounded">Requires 10.5%</span>
              </div>
            </div>
          </div>

          {/* Item 2 */}
          <div className="bg-slate-800/50 p-4 rounded-xl border border-slate-700/50 flex gap-4 items-start opacity-70">
            <div className="mt-1 w-5 h-5 rounded-full bg-slate-700 flex items-center justify-center">
              <span className="text-[10px] text-slate-400">2</span>
            </div>
            <div>
              <div className="h-4 w-3/4 bg-slate-700 rounded mb-2"></div>
              <div className="h-3 w-1/2 bg-slate-700/50 rounded"></div>
            </div>
          </div>
        </div>
        
        {/* Animated simulation cursor */}
        <motion.div
           initial={{ x: 100, y: 150, opacity: 0 }}
           animate={{ x: [100, 20, 20], y: [150, 40, 40], opacity: [0, 1, 0] }}
           transition={{ duration: 4, repeat: Infinity, times: [0, 0.4, 1] }}
           className="absolute z-50 w-6 h-6 filter drop-shadow-md"
        >
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M5.5 3.21V20.8C5.5 21.45 6.27 21.8 6.75 21.36L11.44 17.02L15.34 23.36C15.54 23.69 15.98 23.8 16.32 23.6L18.42 22.31C18.76 22.1 18.89 21.67 18.69 21.34L14.73 14.88H20.08C20.69 14.88 21.01 14.15 20.6 13.7L6.59 2.76C6.12 2.39 5.5 2.74 5.5 3.21Z" fill="white" stroke="black" strokeWidth="1"/>
          </svg>
        </motion.div>
      </motion.div>
    </div>
  );
}
