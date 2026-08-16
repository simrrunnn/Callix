"""
Gradio-wrapped entrypoint for the real voice pipeline (voice_agent.py +
pipeline_agents.py: state machine, RAG, Supabase persistence), used only
for the Hugging Face Space deployment. Previously wrapped
connectivity_spike.py (the Day-1 connectivity-only spike, still in this
repo for reference but no longer what gets deployed here).

Why this exists instead of just deploying voice_agent.py directly:
Docker-SDK Spaces currently require a payment method on file before you can
create one, even on the free CPU tier. Gradio-SDK Spaces don't. The agent
logic itself is unchanged (see voice_agent.py / pipeline_agents.py) -- this
file only changes how the process is started, to fit HF's Gradio runtime
instead of a Dockerfile we control directly.

Hugging Face routes external traffic to exactly one port per Space, and
Gradio needs that port for its own UI -- so Gradio's web server is what
satisfies HF's "is this Space alive" check here, not the LiveKit worker's
own built-in health endpoint (which still runs, just on an internal-only
port that HF never forwards). gradio's launch(prevent_thread_lock=True)
starts Gradio's server on a background thread and returns immediately, so
the LiveKit worker's CLI -- which wants to own the main thread for its own
signal handling -- runs there afterward and keeps the process alive.

Everything below is guarded by `if __name__ == "__main__":` for a reason
that bit us in production, not just style: the LiveKit worker spawns
separate OS processes to run jobs, and Python's multiprocessing does this
by re-importing this same file in each child process. Unguarded top-level
code (our original mistake) re-runs in every one of those child processes
too -- including demo.launch() -- so each job spawned a second Gradio
server fighting the first one for the same port, crash-looping the whole
worker the moment a real job (an actual room join) showed up. Python sets
a different internal module name for that re-import, which is exactly what
this guard checks for, so the launch code now runs exactly once, only in
the real top-level process.
"""

import logging
import sys

import gradio as gr
import spaces
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from livekit import agents
from starlette.middleware import Middleware

from api.calls import router as calls_router
from api.dashboard import router as dashboard_router
from voice_agent import entrypoint


@spaces.GPU(duration=30)
def check_zerogpu() -> str:
    """Request a short ZeroGPU allocation to verify the Space setup."""
    return "ZeroGPU is available. The LiveKit worker is running on CPU."


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    with gr.Blocks(title="Voice Agent") as demo:
        gr.Markdown(
            "## Voice agent -- inbound call handling\n\n"
            "This Space runs a background LiveKit agent worker, not an "
            "interactive UI. It handles booking/rescheduling appointments, "
            "answers questions grounded in a knowledge base (RAG), and "
            "persists calls/turns/appointments to Supabase. It registers "
            "with the LiveKit Cloud project configured via this Space's "
            "secrets and waits for a room to be dispatched to it. Check "
            "this Space's **Logs** tab for connection status.\n\n"
            "Use the button below to verify that ZeroGPU can be allocated."
        )
        check_gpu_button = gr.Button("Check ZeroGPU")
        gpu_status = gr.Textbox(label="ZeroGPU status", interactive=False)
        check_gpu_button.click(fn=check_zerogpu, outputs=gpu_status)

    # launch() unconditionally rebuilds `self.app` (App.create_app(...)) and
    # reassigns demo.app to the new object -- so anything attached to
    # demo.app *before* calling launch() is silently discarded. Middleware
    # has to be baked in at construction time instead (Starlette builds the
    # middleware stack once, at startup), which is why it's passed via
    # app_kwargs here rather than demo.app.add_middleware(...) after the
    # fact (that hangs -- confirmed live). allow_origins=["*"] is
    # intentionally permissive for now since the Render frontend's exact
    # domain isn't known yet; these endpoints have no authentication at all,
    # which is an acceptable simplification for a demo with synthetic data
    # but would need tightening (specific origin + real auth) before ever
    # handling real customer data.
    # ssr_mode is forced off: Gradio defaults it from the GRADIO_SSR_MODE env
    # var, which Hugging Face's Space runtime sets to true. When SSR is on,
    # Gradio puts a Node.js proxy in front of the app on the public port,
    # forwarding only paths it recognizes (like /gradio_api/*) to the actual
    # Python/FastAPI backend -- anything else, including our custom /api/*
    # routes, falls back to the proxy's own SPA shell HTML and never reaches
    # FastAPI at all. Confirmed live: after a Space restart, /api/token
    # started returning a cached SPA page instead of a token, with the
    # startup log showing "Running on local URL: http://0.0.0.0:7860, with
    # SSR (Node proxy -> Python :7861)" -- the giveaway that requests were
    # being served by the Node layer, never reaching Python.
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        prevent_thread_lock=True,
        ssr_mode=False,
        app_kwargs={
            "middleware": [
                Middleware(
                    CORSMiddleware,
                    allow_origins=["*"],
                    allow_methods=["*"],
                    allow_headers=["*"],
                )
            ]
        },
    )

    # Routers, unlike middleware, are safe to attach after launch() -- they
    # go on the final demo.app object that launch() just created, and
    # Starlette's router isn't "baked" the way the middleware stack is.
    demo.app.include_router(calls_router)
    demo.app.include_router(dashboard_router)

    # The worker CLI parses sys.argv itself; force it into "start"
    # (production) mode regardless of how Hugging Face actually invokes
    # this script.
    sys.argv = [sys.argv[0], "start"]
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":
    main()
