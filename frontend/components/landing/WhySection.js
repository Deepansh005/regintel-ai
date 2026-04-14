"use client";

import { motion } from "framer-motion";
import DemoPreviewCard from "./DemoPreviewCard";
import AnimatedSection from "./AnimatedSection";

export default function WhySection() {
  return (
    <section className="py-32 relative overflow-hidden bg-white">
      <div className="absolute inset-0 bg-gradient-to-b from-surface-50 to-white pointer-events-none"></div>
      
      <div className="max-w-7xl mx-auto px-6 relative z-10">
        <AnimatedSection>
          <div className="text-center max-w-2xl mx-auto mb-24">
            <span className="text-brand-600 font-bold tracking-widest text-sm uppercase mb-4 block">Why RegIntel AI</span>
            <h2 className="text-4xl md:text-5xl font-extrabold mb-6 tracking-tight text-slate-900">
              The unfair advantage for compliance teams.
            </h2>
          </div>
        </AnimatedSection>

        {/* Feature Row 1 */}
        <div className="flex flex-col lg:flex-row items-center gap-16 mb-32">
          <div className="flex-1 space-y-8">
            <AnimatedSection delay={0.1}>
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-100 to-indigo-100 flex items-center justify-center border border-brand-200/50 shadow-sm mb-6">
                <span className="text-2xl font-black text-brand-600">01</span>
              </div>
              <h3 className="text-3xl font-extrabold text-slate-900 mb-4 tracking-tight">Real-time Delta Extraction</h3>
              <p className="text-lg text-slate-500 font-medium leading-relaxed">
                Stop playing spot-the-difference with 500-page PDFs. Our AI instantly highlights exact clauses that were modified, added, or removed.
              </p>
              <ul className="mt-6 space-y-3">
                {['Automatic cross-referencing', 'Side-by-side comparison', 'Version control history'].map((item, i) => (
                  <li key={i} className="flex items-center gap-3 text-slate-700 font-medium font-sm">
                    <div className="w-1.5 h-1.5 rounded-full bg-brand-500"></div>
                    {item}
                  </li>
                ))}
              </ul>
            </AnimatedSection>
          </div>
          <div className="flex-1 w-full">
            <AnimatedSection delay={0.2} className="relative">
              <DemoPreviewCard />
            </AnimatedSection>
          </div>
        </div>

        {/* Feature Row 2 */}
        <div className="flex flex-col lg:flex-row-reverse items-center gap-16">
          <div className="flex-1 space-y-8">
            <AnimatedSection delay={0.1}>
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-cyan-100 to-teal-100 flex items-center justify-center border border-cyan-200/50 shadow-sm mb-6">
                <span className="text-2xl font-black text-cyan-600">02</span>
              </div>
              <h3 className="text-3xl font-extrabold text-slate-900 mb-4 tracking-tight">Automated Impact Matrix</h3>
              <p className="text-lg text-slate-500 font-medium leading-relaxed">
                Map regulatory changes directly to the teams, systems, and internal policies they affect. Go from unstructured data to actionable tasks.
              </p>
            </AnimatedSection>
          </div>
          <div className="flex-1 w-full relative">
            <AnimatedSection delay={0.2}>
              <div className="w-full max-w-lg mx-auto relative group perspective-1000">
                <motion.div 
                  whileHover={{ rotateY: 5, rotateX: -5 }}
                  className="glass-card p-2 rounded-3xl border border-white/50 shadow-glass"
                >
                  <img src="https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=1000&auto=format&fit=crop" alt="Dashboard Chart" className="rounded-2xl opacity-80 mix-blend-multiply grayscale group-hover:grayscale-0 transition-all duration-500"/>
                  <div className="absolute inset-0 bg-gradient-to-tr from-cyan-500/20 to-brand-500/20 opacity-0 group-hover:opacity-100 transition-duration-500 rounded-3xl pointer-events-none"></div>
                </motion.div>
              </div>
            </AnimatedSection>
          </div>
        </div>

      </div>
    </section>
  );
}
