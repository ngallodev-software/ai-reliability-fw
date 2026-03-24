import abc
import time
from rich.console import Console
from rich.panel import Panel

console = Console()

class BaseLLMClient(abc.ABC):
    @abc.abstractmethod
    async def call(self, prompt: str, model: str | None = None) -> dict:
        pass

class CLIProvider(BaseLLMClient):
    """
    Harness for web-based subscriptions or local models via CLI.
    Enables manual 'inference' while automating the workflow logic.
    """
    async def call(self, prompt: str, model: str | None = None) -> dict:
        console.print(Panel(prompt, title=f"[bold cyan]Prompt for {model}[/]", border_style="cyan"))
        console.print("[yellow]Please paste the LLM response below and press ENTER (then Ctrl+D on a new line to submit):[/]")
        
        start_time = time.time()
        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass
        
        response_text = "\n".join(lines)
        latency = int((time.time() - start_time) * 1000)
        
        return {
            "response_raw": response_text,
            "latency_ms": latency,
            "provider": "MANUAL_CLI",
            "model": model
        }