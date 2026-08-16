import { Link } from "react-router-dom";
import { Play } from "lucide-react";

const WAVE_HEIGHTS = [
  6, 10, 16, 22, 12, 28, 18, 24, 14, 20, 30, 16, 10, 22, 18, 8, 14, 20, 10, 6, 10, 8, 6, 10, 8,
];

export default function DemoSection() {
  return (
    <section className="mx-auto max-w-4xl px-6 pb-20">
      <div className="rounded-3xl bg-cream-alt px-8 py-14 text-center">
        <h2 className="font-serif text-3xl font-semibold sm:text-4xl">
          See it in action
        </h2>
        <p className="mt-3 text-muted">Get one customized for your business</p>

        <div className="mx-auto mt-8 flex max-w-xl items-center gap-4 rounded-2xl bg-white px-5 py-4 shadow-sm">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-cream-alt">
            <Play className="h-4 w-4" fill="currentColor" strokeWidth={0} />
          </div>
          <div className="flex flex-1 items-center gap-0.75">
            {WAVE_HEIGHTS.map((h, i) => (
              <span
                key={i}
                className="w-1 rounded-full bg-accent/70"
                style={{ height: `${h}px` }}
              />
            ))}
          </div>
        </div>
        <div className="mx-auto mt-1 flex max-w-xl justify-between text-xs text-muted">
          <span>00:00</span>
          <span>00:30</span>
        </div>

        <Link
          to="/demo"
          className="mt-8 inline-block rounded-full bg-ink px-7 py-3 text-sm font-medium text-cream transition hover:opacity-90"
        >
          Try a Custom Demo
        </Link>
      </div>
    </section>
  );
}
