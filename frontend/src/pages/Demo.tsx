import { useState, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  BarVisualizer,
  VoiceAssistantControlBar,
  DisconnectButton,
  useVoiceAssistant,
} from "@livekit/components-react";
import "@livekit/components-styles";
import { ArrowLeft, PhoneOff } from "lucide-react";
import { fetchCallToken, type TokenResponse } from "../lib/api";

export default function Demo() {
  const [session, setSession] = useState<TokenResponse | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startCall = useCallback(async () => {
    setConnecting(true);
    setError(null);
    try {
      const res = await fetchCallToken();
      setSession(res);
    } catch {
      setError("Could not reach Callix. Please try again in a moment.");
    } finally {
      setConnecting(false);
    }
  }, []);

  return (
    <div className="flex min-h-screen flex-col items-center bg-cream px-6 py-10 text-ink">
      <div className="mb-10 flex w-full max-w-lg items-center">
        <Link to="/" className="flex items-center gap-1.5 text-sm text-muted hover:text-ink">
          <ArrowLeft className="h-4 w-4" />
          Back
        </Link>
      </div>

      {!session ? (
        <div className="flex max-w-md flex-1 flex-col items-center justify-center text-center">
          <span className="inline-block rounded-full bg-badge-bg px-4 py-1.5 text-xs font-medium tracking-wide text-badge-text">
            LIVE DEMO
          </span>
          <h1 className="mt-6 font-serif text-3xl font-semibold sm:text-4xl">
            Talk to Callix, our salon voice agent
          </h1>
          <p className="mt-4 text-muted">
            Click below to start a live call, right in your browser. Ask it to
            book, reschedule, or cancel an appointment, or ask a question about
            the salon's services.
          </p>

          <button
            onClick={startCall}
            disabled={connecting}
            className="mt-8 rounded-full bg-ink px-7 py-3 text-sm font-medium text-cream transition hover:opacity-90 disabled:opacity-60"
          >
            {connecting ? "Connecting..." : "Start Call"}
          </button>

          {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
        </div>
      ) : (
        <LiveKitRoom
          token={session.token}
          serverUrl={session.url}
          connect
          audio
          video={false}
          onDisconnected={() => setSession(null)}
          className="flex flex-1 flex-col items-center justify-center"
        >
          <CallPanel />
          <RoomAudioRenderer />
        </LiveKitRoom>
      )}
    </div>
  );
}

function CallPanel() {
  const { state, audioTrack } = useVoiceAssistant();

  return (
    <div className="flex w-full max-w-md flex-col items-center rounded-3xl bg-cream-alt px-8 py-12 text-center">
      <p className="font-serif text-xl font-semibold">Callix</p>
      <p className="mt-1 text-sm capitalize text-muted">{state ?? "connecting"}</p>

      <div className="mt-8 h-24 w-full">
        <BarVisualizer state={state} barCount={12} trackRef={audioTrack} />
      </div>

      <div className="mt-8 flex items-center gap-4">
        <VoiceAssistantControlBar controls={{ leave: false }} />
        <DisconnectButton className="flex h-11 w-11 items-center justify-center rounded-full bg-red-500 text-white transition hover:opacity-90">
          <PhoneOff className="h-4 w-4" />
        </DisconnectButton>
      </div>
    </div>
  );
}
