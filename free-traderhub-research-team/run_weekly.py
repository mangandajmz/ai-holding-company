"""run_weekly.py — Weekly entry point for the FreeTraderHub Research Team."""

import os
import sys
import time
from datetime import date

# Ensure project root is on the path when run directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force UTF-8 output so box-drawing characters render on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from crew import build_crew, REPORTS_DIR, TODAY

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

BANNER = r"""
╔══════════════════════════════════════════════════════════════════╗
║          FreeTraderHub Agentic Marketing Research Team           ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║               [Team Lead: Marketing Research Team Lead]          ║
║                            |                                     ║
║        ┌───────────────────┼───────────────────┐                 ║
║        |                   |                   |                 ║
║  [Senior Market    [Community Intel    [Growth Strategy          ║
║   Researcher]       Monitor]            Analyst]                 ║
║        |                   |                   |                 ║
║        └───────────────────┼───────────────────┘                 ║
║                            |                                     ║
║                 [Compliant Content Writer]                       ║
║                                                                  ║
║  Outputs → reports/{TODAY}/                                      ║
║    00_executive_brief.md   (Team Lead)                           ║
║    01_market_research.md   (Researcher)                          ║
║    02_community_monitor.md (Monitor)                             ║
║    03_weekly_strategy.md   (Analyst)                             ║
║    04_content_drafts.md    (Writer)                              ║
╚══════════════════════════════════════════════════════════════════╝
""".replace("{TODAY}", TODAY)

# ---------------------------------------------------------------------------
# Directory setup
# ---------------------------------------------------------------------------

def _ensure_dirs():
    for d in [REPORTS_DIR, "inputs", "memory"]:
        os.makedirs(d, exist_ok=True)

# ---------------------------------------------------------------------------
# Next steps message
# ---------------------------------------------------------------------------

NEXT_STEPS = """
╔══════════════════════════════════════════════════════════════════╗
║                         NEXT STEPS                               ║
╠══════════════════════════════════════════════════════════════════╣
║  1. Read the executive brief:                                    ║
║     reports/{TODAY}/00_executive_brief.md                        ║
║                                                                  ║
║  2. Reply to 3 Reddit threads manually — use the monitor         ║
║     report for suggested threads (DO NOT automate replies).      ║
║                                                                  ║
║  3. Edit and publish the blog post:                              ║
║     reports/{TODAY}/04_content_drafts.md                         ║
║     Fill in any [EDITOR'S NOTE] tags before publishing.          ║
║                                                                  ║
║  4. Post social drafts manually on Twitter/X, LinkedIn, Reddit.  ║
║                                                                  ║
║  5. Friday: drop this week's GSC CSV export into inputs/         ║
║     as gsc_export.csv before the next run.                       ║
╚══════════════════════════════════════════════════════════════════╝
""".replace("{TODAY}", TODAY)

# ---------------------------------------------------------------------------
# Error checklist
# ---------------------------------------------------------------------------

ERROR_CHECKLIST = """
╔══════════════════════════════════════════════════════════════════╗
║                      TROUBLESHOOTING                             ║
╠══════════════════════════════════════════════════════════════════╣
║  Check these common causes:                                      ║
║                                                                  ║
║  □ Is Ollama running?                                            ║
║      ollama serve                                                ║
║                                                                  ║
║  □ Are the models pulled?                                        ║
║      ollama list                                                 ║
║      ollama pull llama3.2                                        ║
║      ollama pull llama3.1:8b                                     ║
║                                                                  ║
║  □ Is the virtual environment activated?                         ║
║      source venv/bin/activate   (Mac/Linux)                      ║
║      venv\\Scripts\\activate      (Windows)                        ║
║                                                                  ║
║  □ Are all packages installed?                                   ║
║      pip install -r requirements.txt                             ║
║                                                                  ║
║  See CLAUDE.md for the full troubleshooting table.               ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    _ensure_dirs()
    print(BANNER)
    print(f"Starting weekly research run for {TODAY}...")
    print(f"Reports will be saved to: {REPORTS_DIR}/\n")

    start = time.time()

    try:
        crew = build_crew()
        result = crew.kickoff()
    except KeyboardInterrupt:
        print("\n\nRun interrupted by user.")
        sys.exit(0)
    except Exception as exc:
        print(f"\n\nERROR: {exc}\n")
        print(ERROR_CHECKLIST)
        raise

    elapsed = time.time() - start
    minutes, seconds = divmod(int(elapsed), 60)

    print(f"\n{'='*66}")
    print(f"  Run complete in {minutes}m {seconds}s")
    print(f"{'='*66}")
    print(NEXT_STEPS)

    return result


if __name__ == "__main__":
    main()
