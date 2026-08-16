import { Link } from "react-router-dom";
import PhoneMockup from "./PhoneMockup";

export default function Hero() {
  return (
    <section className="mx-auto max-w-6xl px-6 pb-16 pt-6">
      <div className="grid items-center gap-10 md:grid-cols-2">
        <div>
          <span className="inline-block rounded-full bg-badge-bg px-4 py-1.5 text-xs font-medium tracking-wide text-badge-text">
            AI VOICE AGENT
          </span>

          <h1 className="mt-6 font-serif text-4xl font-semibold leading-tight sm:text-5xl">
            AI Voice Agent for Smarter Customer Conversations
          </h1>

          <p className="mt-5 max-w-md text-muted">
            Handle calls, answer questions, and resolve issues -- 24/7. Our AI
            voice agent sounds natural, understands intents, and delivers
            real results.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              to="/demo"
              className="rounded-full bg-ink px-6 py-3 text-sm font-medium text-cream transition hover:opacity-90"
            >
              Get a Demo
            </Link>
            <a
              href="#features"
              className="rounded-full border border-line px-6 py-3 text-sm font-medium transition hover:bg-cream-alt"
            >
              See Features
            </a>
          </div>
        </div>

        <PhoneMockup />
      </div>
    </section>
  );
}
