"use client";

import { useRef, useEffect, useState } from "react";
import { useInView, motion } from "framer-motion";

function Counter({ from = 0, to, duration = 2 }) {
  const [count, setCount] = useState(from);
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });

  useEffect(() => {
    if (isInView) {
      let start = null;
      const step = (timestamp) => {
        if (!start) start = timestamp;
        const progress = Math.min((timestamp - start) / (duration * 1000), 1);
        
        // Easing function: easeOutQuart
        const easeProgress = 1 - Math.pow(1 - progress, 4);
        setCount(Math.floor(easeProgress * (to - from) + from));
        
        if (progress < 1) {
          window.requestAnimationFrame(step);
        }
      };
      window.requestAnimationFrame(step);
    }
  }, [isInView, from, to, duration]);

  const formattedCount = new Intl.NumberFormat('en-US').format(count);
  // Add '+' manually if the original 'to' target had it in string form visually
  return <span ref={ref}>{formattedCount}</span>;
}

export default function StatsCounter() {
  return (
    <section className="py-20 relative overflow-hidden bg-brand-900 border-t border-brand-800 shadow-inner">
      <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-overlay"></div>
      <div className="max-w-7xl mx-auto px-6 relative z-10">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-12 text-center divide-y md:divide-y-0 md:divide-x divide-brand-800">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="flex flex-col items-center pt-8 md:pt-0">
            <h3 className="text-5xl md:text-6xl font-extrabold text-white mb-2 drop-shadow-[0_0_20px_rgba(255,255,255,0.2)]">
              <Counter to={10000} />+
            </h3>
            <p className="text-brand-300 font-bold tracking-widest uppercase text-sm">Documents Processed</p>
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.2 }} className="flex flex-col items-center pt-8 md:pt-0">
            <h3 className="text-5xl md:text-6xl font-extrabold text-white mb-2 drop-shadow-[0_0_20px_rgba(255,255,255,0.2)]">
              <Counter to={95} />%
            </h3>
            <p className="text-brand-300 font-bold tracking-widest uppercase text-sm">Mapping Accuracy</p>
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.4 }} className="flex flex-col items-center pt-8 md:pt-0">
            <h3 className="text-5xl md:text-6xl font-extrabold text-white mb-2 drop-shadow-[0_0_20px_rgba(255,255,255,0.2)]">
              <Counter to={50} />+
            </h3>
            <p className="text-brand-300 font-bold tracking-widest uppercase text-sm">Financial Institutions</p>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
