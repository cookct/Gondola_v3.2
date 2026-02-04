"""
Core foundations for Venice CLI: Colors, UI, and Model definitions
"""
import os
import threading
import difflib

# Available models with capability flags for agent behavior
MODELS = {
    "claude-opus-45": {
        "name": "Claude Opus 4.5",
        "type": "text",
        "description": "Function Calling · Reasoning · Vision · Code",
        "strength": "Elite Logic & Code",
        "rank": 1,
        "context_limit": 203000,
        "price_in": 6.00,
        "price_out": 30.00,
        # Agent capabilities
        "native_function_calling": True,
        "max_agent_turns": 50,  # Very capable, can handle complex tasks
        "needs_explicit_stop": False
    },
    "openai-gpt-52-codex": {
        "name": "GPT-5.2 Code",
        "type": "text",
        "description": "Function Calling · Reasoning · Vision · Code",
        "strength": "Elite Coding Agent",
        "rank": 1,
        "context_limit": 262000,
        "price_in": 2.19,
        "price_out": 17.50,
        "max_tokens": 32000,
        "stream_timeout": 180,
        "native_function_calling": True,
        "max_agent_turns": 50,
        "needs_explicit_stop": False
    },
    "claude-sonnet-45": {
        "name": "Claude Sonnet 4.5",
        "type": "text",
        "description": "Function Calling · Reasoning · Vision · Code",
        "strength": "High Intelligence",
        "rank": 2,
        "context_limit": 203000,
        "price_in": 3.75,
        "price_out": 18.75,
        "max_tokens": 32000,
        "stream_timeout": 180,
        "native_function_calling": True,
        "max_agent_turns": 40,
        "needs_explicit_stop": False
    },
    "qwen3-235b-a22b-instruct-2507": {
        "name": "Qwen 3 235B",
        "type": "text",
        "description": "Function Calling",
        "strength": "Strong Generalist",
        "rank": 2,
        "context_limit": 131000,
        "price_in": 0.15,
        "price_out": 0.75,
        "max_tokens": 20000,
        "stream_timeout": 120,
        # Qwen needs more guidance to stop
        "native_function_calling": True,
        "max_agent_turns": 15,  # Reduced - tends to loop
        "needs_explicit_stop": True,  # Needs checkpoint reminders
        "checkpoint_turns": [5, 10, 13]
    },
    "grok-code-fast-1": {
        "name": "Grok Code Fast",
        "type": "text",
        "description": "Function Calling · Reasoning · Code",
        "strength": "Fast Coding",
        "rank": 2,
        "context_limit": 262000,
        "price_in": 0.25,
        "price_out": 1.87,
        "native_function_calling": True,
        "max_agent_turns": 25,
        "needs_explicit_stop": False
    },
    "minimax-m21": {
        "name": "MiniMax M2.1",
        "type": "text",
        "description": "Function Calling · Reasoning · Code",
        "strength": "Balanced Logic",
        "rank": 3,
        "context_limit": 203000,
        "price_in": 0.40,
        "price_out": 1.60,
        "native_function_calling": True,
        "max_agent_turns": 20,
        "needs_explicit_stop": True,
        "checkpoint_turns": [8, 15]
    },
    "zai-org-glm-4.7": {
        "name": "GLM 4.7",
        "type": "text",
        "description": "Function Calling · Reasoning",
        "strength": "Reliable Standard",
        "rank": 3,
        "context_limit": 203000,
        "price_in": 0.55,
        "price_out": 2.65,
        "native_function_calling": True,
        "max_agent_turns": 20,
        "needs_explicit_stop": True,
        "checkpoint_turns": [8, 15]
    },
    "llama-3.3-70b": {
        "name": "Llama 3.3 70B",
        "type": "text",
        "description": "Function Calling",
        "strength": "Open Source Leader",
        "rank": 3,
        "context_limit": 131000,
        "price_in": 0.70,
        "price_out": 2.80,
        "max_tokens": 20000,
        "stream_timeout": 120,
        "native_function_calling": True,
        "max_agent_turns": 15,
        "needs_explicit_stop": True,
        "checkpoint_turns": [5, 10, 13]
    },
    "google-gemma-3-27b-it": {
        "name": "Gemma 3 27B",
        "type": "text",
        "description": "Function Calling · Vision",
        "strength": "Fast & Efficient",
        "rank": 4,
        "context_limit": 203000,
        "price_in": 0.12,
        "price_out": 0.20,
        "max_tokens": 20000,
        "stream_timeout": 120,
        # Gemma uses text-based tools despite Venice's claim
        "native_function_calling": False,  # Actually outputs tools as text
        "max_agent_turns": 10,  # Short leash - tends to hallucinate
        "needs_explicit_stop": True,
        "checkpoint_turns": [3, 6, 8],
        "strip_hallucinated_output": True  # Remove fake tool outputs from response
    },
    "qwen-image": {
        "name": "Qwen Image",
        "type": "image",
        "description": "Image Editing & Generation",
        "strength": "Visual Creativity",
        "rank": 0,
        "context_limit": 0,
        "price_in": 0.04,
        "price_out": 0.04,
        "native_function_calling": False,
        "max_agent_turns": 1
    },
    "grok-imagine": {
        "name": "Grok Imagine",
        "type": "image",
        "description": "Image Generation",
        "strength": "Creative Generation",
        "rank": 0,
        "context_limit": 0,
        "price_in": 0.04,
        "price_out": 0.04,
        "native_function_calling": False,
        "max_agent_turns": 1
    },
    "grok-imagine-edit": {
        "name": "Grok Imagine Edit",
        "type": "image-edit",
        "description": "Image Editing with Input Image",
        "strength": "Creative Editing",
        "rank": 0,
        "context_limit": 0,
        "price_in": 0.04,
        "price_out": 0.04,
        "native_function_calling": False,
        "max_agent_turns": 1
    }
}


def get_model_config(model_id: str) -> dict:
    """Get model configuration with defaults for missing fields."""
    config = MODELS.get(model_id, {})
    return {
        'name': config.get('name', model_id),
        'context_limit': config.get('context_limit', 32000),
        'native_function_calling': config.get('native_function_calling', True),
        'max_agent_turns': config.get('max_agent_turns', 20),
        'needs_explicit_stop': config.get('needs_explicit_stop', False),
        'checkpoint_turns': config.get('checkpoint_turns', []),
        'strip_hallucinated_output': config.get('strip_hallucinated_output', False),
        'max_tokens': config.get('max_tokens'),
        'stream_timeout': config.get('stream_timeout', 120),
    }

class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GREY = "\033[90m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"

class UI:
    """Clean CLI output formatting with thread-safe printer"""
    _printer = print
    _printer_lock = threading.Lock()

    @classmethod
    def set_printer(cls, printer_func):
        """Thread-safe printer function setter"""
        with cls._printer_lock:
            cls._printer = printer_func

    @classmethod
    def print(cls, *args, **kwargs):
        """Thread-safe print that prevents race conditions in output"""
        sep = kwargs.get('sep', ' ')
        end = kwargs.get('end', '\n')
        text = sep.join(str(arg) for arg in args) + end
        
        # FIXED: Hold lock during both printer retrieval AND call
        # This prevents race condition where printer could be changed
        # between reading _printer and calling it
        with cls._printer_lock:
            printer = cls._printer
            printer(text)

    TOP_LEFT = "┌"
    TOP_RIGHT = "┐"
    BOT_LEFT = "└"
    BOT_RIGHT = "┘"
    HORIZONTAL = "─"
    VERTICAL = "│"

    @staticmethod
    def header(text, color=Colors.CYAN):
        width = 60
        UI.print(f"\n{color}{UI.TOP_LEFT}{UI.HORIZONTAL * (width-2)}{UI.TOP_RIGHT}{Colors.RESET}", end='')
        UI.print(f"\n{color}{UI.VERTICAL}{Colors.RESET} {Colors.BOLD}{text}{Colors.RESET}{' ' * (width - len(text) - 4)}{color}{UI.VERTICAL}{Colors.RESET}", end='')
        UI.print(f"\n{color}{UI.BOT_LEFT}{UI.HORIZONTAL * (width-2)}{UI.BOT_RIGHT}{Colors.RESET}")

    @staticmethod
    def step_start(step_num, total, description):
        UI.print(f"\n{Colors.YELLOW}{UI.TOP_LEFT}{UI.HORIZONTAL} STEP {step_num}/{total}: {description}{Colors.RESET}")

    @staticmethod
    def step_detail(text):
        UI.print(f"{Colors.YELLOW}{UI.VERTICAL}{Colors.RESET}  {text}")

    @staticmethod
    def step_done(message="Done"):
        UI.print(f"{Colors.GREEN}{UI.BOT_LEFT}{UI.HORIZONTAL} ✓ {message}{Colors.RESET}")

    @staticmethod
    def step_error(message):
        UI.print(f"{Colors.RED}{UI.BOT_LEFT}{UI.HORIZONTAL} ✗ {message}{Colors.RESET}")

    @staticmethod
    def success(text):
        UI.print(f"\n{Colors.GREEN}{Colors.BOLD}✓ {text}{Colors.RESET}")

    @staticmethod
    def error(text):
        UI.print(f"\n{Colors.RED}{Colors.BOLD}✗ {text}{Colors.RESET}")

    @staticmethod
    def warning(text):
        UI.print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")

    @staticmethod
    def info(text):
        UI.print(f"{Colors.CYAN}ℹ {text}{Colors.RESET}")

    @staticmethod
    def thinking():
        UI.print(f"{Colors.GREY}Thinking...{Colors.RESET}", end="")

    @staticmethod
    def clear_thinking():
        UI.print("\r" + " " * 20 + "\r", end="")

    @staticmethod
    def reasoning(text):
        UI.print(f"{Colors.GREY}{text}{Colors.RESET}", end="")

    @staticmethod
    def diff(old_lines, new_lines, filename=""):
        if filename:
            UI.print(f"{Colors.CYAN}  Diff for {filename}:{Colors.RESET}")
        diff = difflib.unified_diff(old_lines, new_lines, lineterm='', n=2)
        for line in diff:
            if line.startswith('+++') or line.startswith('---'):
                UI.print(f"{Colors.BOLD}{line}{Colors.RESET}")
            elif line.startswith('+'):
                UI.print(f"{Colors.GREEN}  {line}{Colors.RESET}")
            elif line.startswith('-'):
                UI.print(f"{Colors.RED}  {line}{Colors.RESET}")
            elif line.startswith('@@'):
                UI.print(f"{Colors.CYAN}  {line}{Colors.RESET}")
            else:
                UI.print(f"  {line}")

    @staticmethod
    def file_tree(files, root=""):
        if not files:
            UI.print(f"{Colors.GREY}  (empty){Colors.RESET}")
            return
        for f in sorted(files)[:50]:
            indent = "  "
            icon = "📄" if "." in os.path.basename(f) else "📁"
            UI.print(f"{Colors.WHITE}{indent}{icon} {f}{Colors.RESET}")

    @staticmethod
    def prompt():
        return input(f"\n{Colors.CYAN}{Colors.BOLD}You:{Colors.RESET} ")

    @staticmethod
    def confirm(message="Proceed?"):
        response = input(f"\n{Colors.YELLOW}{message} (y/n): {Colors.RESET}").strip().lower()
        return response in ('y', 'yes')

    @staticmethod
    def model_selector(models, current_model):
        """Interactive model selector with arrow keys"""
        import sys
        import tty
        import termios

        model_ids = list(models.keys())
        current_idx = model_ids.index(current_model) if current_model in model_ids else 0

        def get_key():
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
                if ch == '\x1b':  # Escape sequence
                    ch2 = sys.stdin.read(1)
                    ch3 = sys.stdin.read(1)
                    if ch2 == '[':
                        if ch3 == 'A': return 'up'
                        if ch3 == 'B': return 'down'
                return ch
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        def render():
            # Clear and redraw
            print(f"\n{Colors.CYAN}{Colors.BOLD}Select Model:{Colors.RESET} (↑/↓ to move, Enter to select, q to cancel)\n")
            for i, model_id in enumerate(model_ids):
                model = models[model_id]
                prefix = f"{Colors.GREEN}▶ " if i == current_idx else "  "
                suffix = Colors.RESET
                if i == current_idx:
                    print(f"{prefix}{Colors.BOLD}{model['name']}{suffix} - {model['description']}")
                    print(f"    {Colors.GREY}({model_id}){Colors.RESET}")
                else:
                    print(f"{prefix}{model['name']}{suffix} - {Colors.GREY}{model['description']}{Colors.RESET}")

        render()

        while True:
            key = get_key()
            if key == 'up' and current_idx > 0:
                current_idx -= 1
            elif key == 'down' and current_idx < len(model_ids) - 1:
                current_idx += 1
            elif key == '\r' or key == '\n':  # Enter
                print(f"\n{Colors.GREEN}✓ Selected: {models[model_ids[current_idx]]['name']}{Colors.RESET}")
                return model_ids[current_idx]
            elif key == 'q' or key == '\x1b':  # q or Escape
                print(f"\n{Colors.GREY}Cancelled{Colors.RESET}")
                return None

            # Move cursor up and redraw
            lines_to_clear = len(model_ids) + 3
            print(f"\033[{lines_to_clear}A\033[J", end="")
            render()
