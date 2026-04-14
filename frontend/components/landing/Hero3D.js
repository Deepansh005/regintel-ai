"use client";

import { useRef, useState, useEffect } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

export default function Hero3D() {
  const [isMounted, setIsMounted] = useState(false);
  const containerRef = useRef(null);
  
  useEffect(() => {
    setIsMounted(true);
  }, []);

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end start"],
  });

  const y1 = useTransform(scrollYProgress, [0, 1], [0, 200]);
  const y2 = useTransform(scrollYProgress, [0, 1], [0, -100]);
  const opacity = useTransform(scrollYProgress, [0, 0.8], [1, 0]);

  return (
    <section ref={containerRef} className="relative min-h-[90vh] flex items-center pt-24 pb-20 overflow-hidden">
      {!isMounted ? (
        <div className="absolute inset-0 bg-brand-50/10"></div>
      ) : (
        <>
          {/* Background Elements */}
          <div className="absolute inset-0 noise-bg opacity-40"></div>
          
          <motion.div 
            style={{ y: y1, opacity }}
            className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-4xl h-[600px] bg-gradient-to-b from-brand-300/40 via-brand-400/10 to-transparent blur-[120px] pointer-events-none rounded-full"
          />
          
          <div className="absolute top-20 -right-20 w-[600px] h-[600px] bg-brand-500/10 rounded-full blur-[140px] pointer-events-none animate-pulse duration-[10s]" />
          <div className="absolute top-40 -left-20 w-[500px] h-[500px] bg-cyan-400/10 rounded-full blur-[120px] pointer-events-none animate-pulse duration-[12s]" />

          {/* Floating 3D Elements */}
          <motion.div
            animate={{
              y: [0, -20, 0],
              rotate: [0, 5, 0],
            }}
            transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
            className="absolute top-32 left-[10%] w-24 h-24 glass-card rounded-2xl hidden lg:flex items-center justify-center rotate-12"
          >
            <div className="w-12 h-12 bg-gradient-to-br from-brand-400 to-cyan-400 rounded-xl opacity-80 blur-[2px]"></div>
          </motion.div>

          <motion.div
            animate={{
              y: [0, 30, 0],
              rotate: [0, -10, 0],
            }}
            transition={{ duration: 8, repeat: Infinity, ease: "easeInOut", delay: 1 }}
            className="absolute bottom-40 right-[15%] w-32 h-32 glass-card rounded-3xl hidden lg:flex items-center justify-center -rotate-6"
          >
            <div className="w-16 h-16 rounded-full bg-gradient-to-tr from-brand-600 to-indigo-400 opacity-90 blur-[3px]"></div>
          </motion.div>

          {/* Main Content */}
          <div className="max-w-7xl mx-auto px-6 relative z-10 w-full flex flex-col items-center text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, ease: "easeOut" }}
              className="max-w-4xl mx-auto flex flex-col items-center"
            >
              <motion.div 
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: 0.2, duration: 0.5 }}
                className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/50 backdrop-blur-md border border-brand-200/50 text-brand-700 text-xs font-bold uppercase tracking-widest mb-8 shadow-sm"
              >
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-brand-500"></span>
                </span>
                RegIntel Engine v2.0 Live
              </motion.div>

              <div className="relative">
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[120%] h-[120%] bg-brand-500/10 blur-[80px] rounded-full pointer-events-none -z-10 animate-pulse duration-1000"></div>
                <motion.h1 
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3, duration: 0.8 }}
                  className="text-5xl sm:text-6xl md:text-7xl lg:text-[5.5rem] font-extrabold leading-[1.05] tracking-tight mb-8 text-brand-900 relative z-10"
                >
                  Regulatory Intelligence,<br />
                  <span className="text-gradient">Redefined by AI.</span>
                </motion.h1>
              </div>

              <motion.p 
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.5, duration: 0.8 }}
                className="text-lg md:text-xl xl:text-2xl text-slate-600 leading-relaxed mb-12 max-w-3xl mx-auto font-medium"
              >
                Automate compliance tracking, analyze regulatory updates in seconds, and stay ahead of changes from RBI, SEBI, and global regulators.
              </motion.p>

              <motion.div 
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.6, duration: 0.5 }}
                className="flex flex-col sm:flex-row items-center justify-center gap-4 w-full sm:w-auto"
              >
                <Link
                  href="/register"
                  className="w-full sm:w-auto px-8 py-4 bg-brand-900 rounded-full font-bold text-white flex items-center justify-center gap-2 shadow-[0_0_40px_rgba(124,58,237,0.3)] hover:shadow-[0_0_60px_rgba(124,58,237,0.5)] hover:-translate-y-1 hover:scale-105 transition-all duration-300 active:scale-95 group overflow-hidden relative"
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-brand-600 to-indigo-600 opacity-0 group-hover:opacity-100 rounded-full transition-opacity duration-300"></div>
                  <span className="relative z-10 flex items-center gap-2">
                    Start Free Trial
                    <ArrowRight className="w-5 h-5 group-hover:translate-x-1.5 transition-transform" />
                  </span>
                </Link>
                <button className="w-full sm:w-auto px-8 py-4 bg-white/80 backdrop-blur-md border border-slate-200 rounded-full font-bold hover:bg-white hover:shadow-lg hover:-translate-y-1 hover:scale-105 transition-all duration-300 active:scale-95 text-slate-700">
                  Watch Demo
                </button>
              </motion.div>
            </motion.div>

            {/* Scroll down indicator */}
            <motion.div
               initial={{ opacity: 0 }}
               animate={{ opacity: 1 }}
               transition={{ delay: 1, duration: 1 }}
               className="absolute bottom-10 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2"
            >
              <span className="text-xs font-bold text-slate-400 tracking-widest uppercase">Scroll to explore</span>
              <motion.div 
                animate={{ y: [0, 8, 0] }}
                transition={{ duration: 1.5, repeat: Infinity }}
                className="w-1 h-8 rounded-full bg-gradient-to-b from-brand-300 to-transparent"
              />
            </motion.div>
          </div>
        </>
      )}
    </section>
  );
}
