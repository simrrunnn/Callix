import { PhoneOff } from "lucide-react";

const BAR_HEIGHTS = [10, 22, 14, 30, 18, 26, 12, 20, 28, 16, 24, 10];

export default function PhoneMockup() {
  return (
    <div className="relative flex justify-center py-10">
      <div className="absolute top-0 h-72 w-72 rounded-t-full bg-gradient-to-b from-[#e9cfae] to-[#f4ebde] sm:h-80 sm:w-80" />

      <div className="relative flex h-[420px] w-56 flex-col items-center justify-between rounded-[2.5rem] border-8 border-ink bg-cream px-4 py-8 shadow-xl">
        <div className="text-center">
          <p className="font-serif text-base font-semibold">Callix</p>
          <p className="mt-1 text-xs text-muted">Speaking...</p>
        </div>

        <div className="flex h-10 items-end gap-1">
          {BAR_HEIGHTS.map((h, i) => (
            <span
              key={i}
              className="w-1 rounded-full bg-accent"
              style={{ height: `${h}px` }}
            />
          ))}
        </div>

        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-500 text-white">
          <PhoneOff className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}
