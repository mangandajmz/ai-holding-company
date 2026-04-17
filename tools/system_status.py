"""
AI Holding Company — Tool: system_status
Checks if Ollama and Docker/OpenClaw services are running.
"""

import subprocess
import platform
from datetime import datetime


def check_ollama() -> dict:
    """Check if Ollama is running and which model is loaded."""
    result = {"running": False, "models": [], "error": None}
    try:
        # Check if ollama process is running
        if platform.system() == "Windows":
            proc = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq ollama.exe"],
                capture_output=True, text=True, timeout=10
            )
            result["running"] = "ollama.exe" in proc.stdout
        else:
            proc = subprocess.run(
                ["pgrep", "-x", "ollama"],
                capture_output=True, text=True, timeout=10
            )
            result["running"] = proc.returncode == 0

        # List loaded models
        if result["running"]:
            models_proc = subprocess.run(
                ["ollama", "list"],
                capture_output=True, text=True, timeout=15
            )
            if models_proc.returncode == 0:
                lines = models_proc.stdout.strip().split("\n")
                if len(lines) > 1:  # Skip header line
                    result["models"] = [
                        line.split()[0] for line in lines[1:] if line.strip()
                    ]
    except Exception as e:
        result["error"] = str(e)
    return result


def check_docker() -> dict:
    """Check if Docker is running and OpenClaw containers are up."""
    result = {"running": False, "openclaw_containers": [], "error": None}
    try:
        # Check Docker daemon
        proc = subprocess.run(
            ["docker", "info"],
            capture_output=True, text=True, timeout=15
        )
        result["running"] = proc.returncode == 0

        if result["running"]:
            # Check for OpenClaw containers
            ps_proc = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}} {{.Status}}",
                 "--filter", "name=openclaw"],
                capture_output=True, text=True, timeout=15
            )
            if ps_proc.returncode == 0 and ps_proc.stdout.strip():
                for line in ps_proc.stdout.strip().split("\n"):
                    if line.strip():
                        result["openclaw_containers"].append(line.strip())
    except FileNotFoundError:
        result["error"] = "Docker not found — is Docker Desktop installed?"
    except Exception as e:
        result["error"] = str(e)
    return result


def system_status() -> str:
    """Full system status report."""
    ollama = check_ollama()
    docker = check_docker()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = f"═══ SYSTEM STATUS — {timestamp} ═══\n\n"

    # Ollama
    ollama_icon = "🟢" if ollama["running"] else "🔴"
    report += f"Ollama: {ollama_icon} {'Running' if ollama['running'] else 'Stopped'}\n"
    if ollama["models"]:
        report += f"  Models: {', '.join(ollama['models'])}\n"
    if ollama["error"]:
        report += f"  Error: {ollama['error']}\n"

    # Docker / OpenClaw
    docker_icon = "🟢" if docker["running"] else "🔴"
    report += f"\nDocker: {docker_icon} {'Running' if docker['running'] else 'Stopped'}\n"
    if docker["openclaw_containers"]:
        report += "  OpenClaw containers:\n"
        for c in docker["openclaw_containers"]:
            report += f"    - {c}\n"
    elif docker["running"]:
        report += "  OpenClaw: No containers found (not started yet?)\n"
    if docker["error"]:
        report += f"  Error: {docker['error']}\n"

    return report


if __name__ == "__main__":
    print(system_status())
