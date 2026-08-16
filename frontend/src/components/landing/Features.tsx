import { Phone, MessageCircleQuestion, CalendarCheck, TimerReset } from "lucide-react";

const features = [
  {
    icon: Phone,
    title: "Handle Calls",
    description:
      "Answer incoming calls professionally and ensure no customer is missed.",
  },
  {
    icon: MessageCircleQuestion,
    title: "Answer Questions",
    description:
      "Provide accurate answers to customer queries using your business knowledge.",
  },
  {
    icon: CalendarCheck,
    title: "Book & Manage",
    description: "Schedule, reschedule, or cancel appointments and manage bookings.",
  },
  {
    icon: TimerReset,
    title: "Escalate Smartly",
    description: "Transfer complex issues to the right human agent when needed.",
  },
];

export default function Features() {
  return (
    <section id="features" className="mx-auto max-w-6xl px-6 py-16">
      <h2 className="text-center font-serif text-3xl font-semibold sm:text-4xl">
        What our voice agent can do
      </h2>

      <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {features.map(({ icon: Icon, title, description }) => (
          <div
            key={title}
            className="rounded-2xl border border-line bg-white/40 p-6 text-center"
          >
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-cream-alt">
              <Icon className="h-6 w-6" strokeWidth={1.75} />
            </div>
            <h3 className="mt-5 font-serif text-lg font-semibold">{title}</h3>
            <p className="mt-2 text-sm text-muted">{description}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
