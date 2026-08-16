import Navbar from "../components/landing/Navbar";
import Hero from "../components/landing/Hero";
import Features from "../components/landing/Features";
import DemoSection from "../components/landing/DemoSection";

export default function Landing() {
  return (
    <div className="min-h-screen bg-cream text-ink">
      <Navbar />
      <Hero />
      <Features />
      <DemoSection />
    </div>
  );
}
