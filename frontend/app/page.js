"use client";

import Link from "next/link";
import { Shield, Zap, BarChart3, ArrowRight } from "lucide-react";
import Hero3D from "../components/landing/Hero3D";
import FeatureTiltCard from "../components/landing/FeatureTiltCard";
import WorkflowVisualizer from "../components/landing/WorkflowVisualizer";
import InteractiveFeatures from "../components/landing/InteractiveFeatures";
import AnimatedSection from "../components/landing/AnimatedSection";
import InfiniteLogoMarquee from "../components/landing/InfiniteLogoMarquee";
import StatsCounter from "../components/landing/StatsCounter";
import WhySection from "../components/landing/WhySection";
import TestimonialsSlider from "../components/landing/TestimonialsSlider";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-surface-100 text-surface-900 selection:bg-brand-200 font-sans font-medium overflow-hidden">
      {/* Navbar - Keep consistent but slightly elevated */}
      <nav className="fixed top-0 w-full z-50 border-b border-white/20 bg-white/60 backdrop-blur-xl shadow-sm transition-all duration-300">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-2.5 group cursor-pointer">
            <div className="w-10 h-10 bg-gradient-to-br from-brand-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-brand-500/20 group-hover:scale-105 transition-transform">
              <Shield className="w-6 h-6 text-white" />
            </div>
            <span className="text-xl font-extrabold tracking-tight text-slate-900 group-hover:text-brand-600 transition-colors">RegIntel AI</span>
          </div>

          <div className="hidden md:flex items-center gap-8 text-sm font-bold text-slate-500">
            <a href="#features" className="hover:text-brand-600 hover:scale-105 transition-all">Features</a>
            <a href="#workflow" className="hover:text-brand-600 hover:scale-105 transition-all">How it Works</a>
            <a href="#demo" className="hover:text-brand-600 hover:scale-105 transition-all">Solutions</a>
          </div>

          <div className="flex items-center gap-4">
            <Link
              href="/login"
              className="px-5 py-2 text-sm font-bold text-slate-600 hover:text-slate-900 transition-colors"
            >
              Sign In
            </Link>
            <Link
              href="/register"
              className="px-6 py-3 text-sm font-bold bg-surface-900 text-white rounded-full hover:bg-brand-900 transition-all shadow-float hover:shadow-glow active:scale-95"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Main Hero Section (3D & Highly visual) */}
      <div className="pt-8"></div>
      <Hero3D />

      {/* Rolling Logos Strip */}
      <InfiniteLogoMarquee />

      {/* 3D Features Matrix */}
      <section id="features" className="py-32 relative z-20">
        <AnimatedSection>
          <div className="max-w-7xl mx-auto px-6">
            <div className="text-center max-w-2xl mx-auto mb-20">
              <h2 className="text-4xl md:text-5xl font-extrabold mb-6 tracking-tight text-slate-900">
                Built for Precise Compliance
              </h2>
              <p className="text-slate-500 text-lg leading-relaxed font-medium">
                Advanced AI inference engines designed to silently handle the complexity of modern financial regulations.
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-8">
              <AnimatedSection delay={0.1} className="h-[320px]">
                <FeatureTiltCard
                  icon={<Zap className="w-8 h-8" />}
                  color="violet"
                  title="Instant Comparison"
                  description="Identify exactly what changed between two versions of any regulatory circular in seconds."
                />
              </AnimatedSection>
              <AnimatedSection delay={0.3} className="h-[320px]">
                <FeatureTiltCard
                  icon={<Shield className="w-8 h-8" />}
                  color="indigo"
                  title="Impact Analysis"
                  description="Get automated mapping of changes to your departments, systems, and internal policies."
                />
              </AnimatedSection>
              <AnimatedSection delay={0.5} className="h-[320px]">
                <FeatureTiltCard
                  icon={<BarChart3 className="w-8 h-8" />}
                  color="cyan"
                  title="Actionable Insights"
                  description="Transform abstract rules into step-by-step compliance tasks assigned to your teams."
                />
              </AnimatedSection>
            </div>
          </div>
        </AnimatedSection>
      </section>

      {/* Stats Counter Section */}
      <StatsCounter />

      {/* Why RegIntel Section */}
      <WhySection />

      {/* Interactive Workflow */}
      <div id="workflow">
        <WorkflowVisualizer />
      </div>

      {/* Interactive Feature Demo */}
      <div id="demo">
         <InteractiveFeatures />
      </div>

      {/* Testimonials */}
      <TestimonialsSlider />

      {/* CTA Section */}
      <section className="pt-56 pb-48 relative overflow-hidden bg-gradient-to-b from-surface-50 via-brand-950 to-surface-900 border-none">
        {/* Low opacity noise */}
        <div className="absolute inset-0 noise-bg opacity-[0.15] mix-blend-overlay z-0" />
        
        {/* Floating blur shapes for premium depth */}
        <div className="absolute top-1/4 left-1/4 w-[30rem] h-[30rem] bg-brand-600/20 rounded-full blur-[140px] mix-blend-screen pointer-events-none animate-blob z-0"></div>
        <div className="absolute bottom-1/4 right-1/4 w-[25rem] h-[25rem] bg-cyan-600/20 rounded-full blur-[140px] mix-blend-screen pointer-events-none animate-blob animation-delay-2000 z-0"></div>
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[40rem] h-[40rem] bg-indigo-500/10 rounded-full blur-[180px] pointer-events-none z-0"></div>
        
        <div className="max-w-4xl mx-auto px-6 relative z-10 text-center mt-10">
          <AnimatedSection>
            <h2 className="text-5xl md:text-6xl font-black mb-8 tracking-tight text-white drop-shadow-sm">
              Ready to automate compliance?
            </h2>
            <p className="text-xl text-brand-100/90 mb-14 font-medium max-w-2xl mx-auto">
              Join leading financial institutions that have cut compliance research time by 85%.
            </p>
            <div className="relative inline-block">
              {/* Soft radial glow strictly behind CTA button */}
              <div className="absolute inset-0 bg-brand-400 blur-2xl opacity-40 rounded-full mix-blend-screen animate-pulse scale-150 duration-2000"></div>
              
              <Link
                href="/register"
                className="relative z-10 inline-flex items-center justify-center gap-3 px-10 py-5 bg-gradient-to-r from-brand-600 via-indigo-500 to-cyan-500 text-white font-extrabold rounded-full text-lg shadow-[0_0_40px_rgba(124,58,237,0.4)] hover:shadow-[0_0_60px_rgba(99,102,241,0.6)] hover:scale-105 transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)] active:scale-95 group border border-white/20"
              >
                <span className="absolute inset-0 bg-gradient-to-r from-brand-500 via-indigo-400 to-cyan-400 opacity-0 group-hover:opacity-100 rounded-full transition-opacity duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]"></span>
                <span className="relative z-10 flex items-center gap-2">
                  Start Your Free Trial
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </span>
              </Link>
            </div>
          </AnimatedSection>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 bg-surface-900 border-t border-white/5 relative z-10">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="flex items-center gap-3 opacity-80 hover:opacity-100 transition-opacity">
            <div className="w-8 h-8 bg-gradient-to-br from-brand-500 to-indigo-500 rounded-lg flex items-center justify-center shadow-sm relative overflow-hidden group">
                <div className="absolute inset-0 bg-white/20 opacity-0 group-hover:opacity-100 transition-opacity"></div>
                <Shield className="w-4 h-4 text-white relative z-10" />
            </div>
            <span className="font-extrabold text-white tracking-tight">RegIntel AI</span>
          </div>
          <p className="text-sm text-slate-400 font-medium tracking-wide">© 2026 RegIntel AI. All rights reserved.</p>
          <div className="flex items-center gap-8 text-sm font-bold text-slate-400">
            <a href="#" className="hover:text-white transition-colors">Privacy</a>
            <a href="#" className="hover:text-white transition-colors">Terms</a>
            <a href="#" className="hover:text-white transition-colors">Security</a>
          </div>
        </div>
      </footer>
    </div>
  );
}