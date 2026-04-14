"use client";

export default function InfiniteLogoMarquee() {
  const logos = ["RBI", "SEBI", "BSE", "NSE", "IRDAI", "PFRDA", "FSDC"];
  
  return (
    <div className="py-12 border-y border-brand-100 bg-white/40 backdrop-blur-md relative overflow-hidden flex w-full">
      <div className="absolute inset-0 mask-edges pointer-events-none z-10"></div>
      
      <div className="flex whitespace-nowrap group w-max">
        {/* We animate this entire container moving from 0 to -50% and doubling its content seamlessly */}
        <div className="animate-scrolling-logos flex w-max items-center justify-around group-hover:[animation-play-state:paused] opacity-60 grayscale hover:grayscale-0 transition-all duration-700">
          {[...logos, ...logos].map((logo, index) => (
            <div key={index} className="mx-12 lg:mx-20 flex items-center justify-center">
              <span className="font-display font-black text-3xl md:text-4xl tracking-tighter text-slate-800 hover:text-brand-600 transition-colors drop-shadow-sm cursor-default">
                {logo}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
