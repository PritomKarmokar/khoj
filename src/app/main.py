# Standard Packages
import os
import sys
import locale

import logging
import threading
import warnings
from importlib.metadata import version

# Ignore non-actionable warnings
warnings.filterwarnings("ignore", message=r"snapshot_download.py has been made private", category=FutureWarning)
warnings.filterwarnings("ignore", message=r"legacy way to download files from the HF hub,", category=FutureWarning)

# External Packages
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import schedule
import django

from fastapi.staticfiles import StaticFiles
from rich.logging import RichHandler
from django.core.asgi import get_asgi_application
from django.core.management import call_command

# Internal Packages
from khoj.configure import configure_routes, initialize_server, configure_middleware
from khoj.utils import state
from khoj.utils.cli import cli

# Initialize Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
django.setup()

# Initialize Django Database
call_command("migrate", "--noinput")

# Initialize the Application Server
app = FastAPI()

# Get Django Application
django_app = get_asgi_application()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["app://obsidian.md", "http://localhost:*", "https://app.khoj.dev/*", "app://khoj.dev"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set Locale
locale.setlocale(locale.LC_ALL, "")

# Setup Logger
rich_handler = RichHandler(rich_tracebacks=True)
rich_handler.setFormatter(fmt=logging.Formatter(fmt="%(message)s", datefmt="[%X]"))
logging.basicConfig(handlers=[rich_handler])

logger = logging.getLogger("khoj")


def run():
    # Turn Tokenizers Parallelism Off. App does not support it.
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    # Load config from CLI
    state.cli_args = sys.argv[1:]
    args = cli(state.cli_args)
    set_state(args)

    # Create app directory, if it doesn't exist
    state.config_file.parent.mkdir(parents=True, exist_ok=True)

    # Set Logging Level
    if args.verbose == 0:
        logger.setLevel(logging.INFO)
    elif args.verbose >= 1:
        logger.setLevel(logging.DEBUG)

    # Set Log File
    fh = logging.FileHandler(state.config_file.parent / "khoj.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)

    logger.info("🌘 Starting Khoj")

    # Setup task scheduler
    poll_task_scheduler()

    # Start Server
    configure_routes(app)

    #  Mount Django and Static Files
    app.mount("/django", django_app, name="django")
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # Configure Middleware
    configure_middleware(app)

    initialize_server(args.config)
    start_server(app, host=args.host, port=args.port, socket=args.socket)


def set_state(args):
    state.config_file = args.config_file
    state.config = args.config
    state.verbose = args.verbose
    state.host = args.host
    state.port = args.port
    state.demo = args.demo
    state.khoj_version = version("khoj-assistant")


def start_server(app, host=None, port=None, socket=None):
    logger.info("🌖 Khoj is ready to use")
    if socket:
        uvicorn.run(app, proxy_headers=True, uds=socket, log_level="debug", use_colors=True, log_config=None)
    else:
        uvicorn.run(app, host=host, port=port, log_level="debug", use_colors=True, log_config=None)
    logger.info("🌒 Stopping Khoj")


def poll_task_scheduler():
    timer_thread = threading.Timer(60.0, poll_task_scheduler)
    timer_thread.daemon = True
    timer_thread.start()
    schedule.run_pending()


if __name__ == "__main__":
    run()
