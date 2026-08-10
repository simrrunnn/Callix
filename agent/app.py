"""
Gradio-wrapped entrypoint for the Day-1 connectivity spike, used only for
the Hugging Face Space deployment.

Why this exists instead of just deploying connectivity_spike.py directly:
Docker-SDK Spaces currently require a payment method on file before you can
create one, even on the free CPU tier. Gradio-SDK Spaces don't. The agent
logic itself is unchanged (see connectivity_spike.py) -- this file only
changes how the process is started, to fit HF's Gradio runtime instead of a
Dockerfile we control directly.

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
from livekit import agents

from connectivity_spike import entrypoint


@spaces.GPU(duration=30)
def check_zerogpu() -> str:
    """Request a short ZeroGPU allocation to verify the Space setup."""
    return "ZeroGPU is available. The LiveKit worker is running on CPU."


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    with gr.Blocks(title="Voice Agent Connectivity Spike") as demo:
        gr.Markdown(
            "## Voice agent connectivity spike\n\n"
            "This Space runs a background LiveKit agent worker, not an "
            "interactive UI. It registers "
            "with the LiveKit Cloud project configured via this Space's "
            "secrets and waits for a room to be dispatched to it. Check "
            "this Space's **Logs** tab for connection status.\n\n"
            "Use the button below to verify that ZeroGPU can be allocated."
        )
        check_gpu_button = gr.Button("Check ZeroGPU")
        gpu_status = gr.Textbox(label="ZeroGPU status", interactive=False)
        check_gpu_button.click(fn=check_zerogpu, outputs=gpu_status)

    demo.launch(server_name="0.0.0.0", server_port=7860, prevent_thread_lock=True)

    # The worker CLI parses sys.argv itself; force it into "start"
    # (production) mode regardless of how Hugging Face actually invokes
    # this script.
    sys.argv = [sys.argv[0], "start"]
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":
    main()
