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
"""

import logging
import sys

import gradio as gr
from dotenv import load_dotenv
from livekit import agents

from connectivity_spike import entrypoint

load_dotenv()
logging.basicConfig(level=logging.INFO)

with gr.Blocks(title="Voice Agent Connectivity Spike") as demo:
    gr.Markdown(
        "## Voice agent connectivity spike\n\n"
        "This Space runs a background LiveKit agent worker, not an "
        "interactive UI -- there's nothing to click here. It registers "
        "with the LiveKit Cloud project configured via this Space's "
        "secrets and waits for a room to be dispatched to it. Check this "
        "Space's **Logs** tab for connection status."
    )

demo.launch(server_name="0.0.0.0", server_port=7860, prevent_thread_lock=True)

# The worker CLI parses sys.argv itself; force it into "start" (production)
# mode regardless of how Hugging Face actually invokes this script.
sys.argv = [sys.argv[0], "start"]
agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
