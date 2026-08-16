import { Link } from "react-router-dom";
import { AudioWaveform } from "lucide-react";

const links = ["Home", "Features", "Use Cases", "Pricing", "About"];

export default function Navbar() {
  return (
    <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
      <div className="flex items-center gap-2 font-serif text-lg font-semibold">
        <AudioWaveform className="h-5 w-5" strokeWidth={2.5} />
        VoiceAgent
      </div>

      <nav className="hidden items-center gap-8 text-sm text-ink/80 md:flex">
        {links.map((label) => (
          <a key={label} href="#" className="hover:text-ink">
            {label}
          </a>
        ))}
      </nav>

      <Link
        to="/demo"
        className="rounded-full bg-ink px-5 py-2.5 text-sm font-medium text-cream transition hover:opacity-90"
      >
        Book a Demo
      </Link>
    </header>
  );
}
