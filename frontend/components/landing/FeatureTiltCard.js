"use client";

import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";

export default function FeatureTiltCard({ icon, title, description, color = "violet" }) {
  const x = useMotionValue(0);
  const y = useMotionValue(0);

  const mouseXSpring = useSpring(x, { stiffness: 150, damping: 15 });
  const mouseYSpring = useSpring(y, { stiffness: 150, damping: 15 });

  const rotateX = useTransform(mouseYSpring, [-0.5, 0.5], ["15deg", "-15deg"]);
  const rotateY = useTransform(mouseXSpring, [-0.5, 0.5], ["-15deg", "15deg"]);

  const handleMouseMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    
    const xPct = mouseX / width - 0.5;
    const yPct = mouseY / height - 0.5;
    
    x.set(xPct);
    y.set(yPct);
  };

  const handleMouseLeave = () => {
    x.set(0);
    y.set(0);
  };

  const glowColors = {
    violet: "from-violet-500/20 via-brand-400/5 to-transparent",
    indigo: "from-indigo-500/20 via-blue-400/5 to-transparent",
    cyan: "from-cyan-500/20 via-teal-400/5 to-transparent",
  };
  
  const iconBgGlow = {
    violet: "bg-violet-400/20",
    indigo: "bg-indigo-400/20",
    cyan: "bg-cyan-400/20",
  };

  const iconColors = {
    violet: "text-violet-600 bg-violet-50 border-violet-100",
    indigo: "text-indigo-600 bg-indigo-50 border-indigo-100",
    cyan: "text-cyan-600 bg-cyan-50 border-cyan-100",
  };

  return (
    <motion.div
      style={{
        rotateX,
        rotateY,
        transformStyle: "preserve-3d",
      }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      whileHover={{ y: -6, scale: 1.02 }}
      transition={{ ease: [0.4, 0, 0.2, 1], duration: 0.3 }}
      className={`relative p-8 rounded-[2xl] bg-gradient-to-b from-white/80 to-white/40 backdrop-blur-2xl border border-white/60 shadow-[0_8px_30px_rgb(0,0,0,0.04)] hover:shadow-[0_20px_40px_rgba(124,58,237,0.15)] group cursor-pointer overflow-hidden isolate h-full flex flex-col`}
    >
      {/* Light Reflection (Inner highlight) */}
      <div className="absolute top-0 left-0 w-full h-[200px] bg-gradient-to-b from-white/60 to-transparent pointer-events-none rounded-t-[2rem]"></div>
      
      {/* Dynamic Inner Hover Glow */}
      <motion.div 
        className={`absolute inset-0 bg-gradient-to-br ${glowColors[color]} opacity-0 group-hover:opacity-100 transition-opacity duration-500 -z-10`}
      />
      
      {/* Border Glow line */}
      <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-white to-transparent opacity-80"></div>

      {/* Floating Icon Wrapper */}
      <div 
        style={{ transform: "translateZ(50px)" }}
        className="relative mb-8 mt-2"
      >
        <div className={`absolute -inset-2 ${iconBgGlow[color]} rounded-full blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500`}></div>
        <motion.div 
           animate={{ y: [0, -4, 0] }}
           transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
           className={`w-14 h-14 rounded-2xl flex items-center justify-center border shadow-sm relative z-10 transition-colors duration-300 ${iconColors[color]}`}
        >
          {icon}
        </motion.div>
      </div>
      
      <div style={{ transform: "translateZ(30px)" }} className="flex-grow flex flex-col">
        <h3 className="text-2xl font-black mb-4 text-slate-900 tracking-tight leading-tight group-hover:text-brand-900 transition-colors duration-300">{title}</h3>
        <p className="text-slate-600 leading-relaxed font-semibold">
          {description}
        </p>
      </div>

      {/* Decorative background element showing depth */}
      <div className="absolute -bottom-10 -right-10 w-40 h-40 bg-gradient-to-tl from-brand-100/40 to-transparent rounded-full blur-2xl -z-10 group-hover:scale-150 transition-transform duration-700"></div>
    </motion.div>
  );
}
