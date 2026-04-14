"use client";

import { useRef, useState } from "react";
import { motion } from "framer-motion";
import { Quote } from "lucide-react";

const testimonials = [
  {
    quote: "RegIntel literally cut our compliance review time from weeks to hours. The delta highlighting is pinpoint accurate every time.",
    name: "Rajiv S.",
    role: "Chief Compliance Officer",
    company: "FinCorp India"
  },
  {
    quote: "The ability to instantly map SEBI circulars directly to our Jira boards for the engineering team is nothing short of magic.",
    name: "Meera K.",
    role: "VP Risk & Engineering",
    company: "SecurePay Assets"
  },
  {
    quote: "We don't need a massive legal team just to track RBI updates anymore. RegIntel gives us actionable insights faster than any human could.",
    name: "Amit V.",
    role: "Head of Operations",
    company: "NeoBank Solutions"
  }
];

export default function TestimonialSlider() {
  const containerRef = useRef(null);

  return (
    <section className="py-32 relative bg-surface-50 overflow-hidden">
      <div className="max-w-7xl mx-auto px-6 relative z-10">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center max-w-2xl mx-auto mb-20"
        >
          <h2 className="text-4xl md:text-5xl font-extrabold mb-6 tracking-tight text-slate-900">
            Trusted by the Best
          </h2>
          <p className="text-slate-500 text-lg leading-relaxed font-medium">
            Hear from industry leaders who have transformed their regulatory pipelines.
          </p>
        </motion.div>

        {/* Drag container */}
        <motion.div ref={containerRef} className="cursor-grab active:cursor-grabbing overflow-hidden mask-edges -mx-6 px-6">
          <motion.div 
            drag="x" 
            dragConstraints={containerRef}
            dragElastic={0.1}
            initial={{ x: 100 }}
            whileInView={{ x: 0 }}
            transition={{ type: "spring", stiffness: 50 }}
            className="flex gap-8 w-max px-20 pb-10 pt-4"
          >
            {testimonials.map((t, idx) => (
              <motion.div 
                key={idx}
                whileHover={{ y: -10, scale: 1.02 }}
                className="w-[400px] flex-shrink-0 bg-white/70 backdrop-blur-xl border border-white p-10 rounded-[2rem] shadow-glass shadow-brand-500/5 relative group"
              >
                <div className="absolute top-8 right-8 text-brand-200/50 group-hover:text-brand-300 transition-colors">
                  <Quote className="w-12 h-12 fill-current" />
                </div>
                <div className="relative z-10">
                  <p className="text-lg text-slate-700 font-medium leading-relaxed mb-8">
                    "{t.quote}"
                  </p>
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-full bg-gradient-to-tr from-brand-500 to-indigo-500 flex items-center justify-center text-white font-bold text-lg shadow-md">
                      {t.name.charAt(0)}
                    </div>
                    <div>
                      <h4 className="font-extrabold text-slate-900">{t.name}</h4>
                      <p className="text-sm font-medium text-slate-500">{t.role}, <span className="text-brand-600">{t.company}</span></p>
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
