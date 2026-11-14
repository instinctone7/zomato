"""
CLI entry-point for the Zomato AI Recommender.

Usage (flags):
    python src/main.py --location Bangalore --budget medium \\
                       --cuisine Italian --rating 4.0 \\
                       --prefs "quiet, good for a date"

Usage (interactive):
    python src/main.py

Flags:
    --location          City / locality
    --budget            low | medium | high
    --cuisine           Cuisine type (default: Any)
    --rating            Minimum rating float (default: 3.0)
    --prefs             Free-text extra preferences
    --dry-run           Print the built prompt and exit (no LLM call)
    --max-candidates    Max restaurants passed to LLM (default: 20)
    --top-n             Max recommendations to return (default: 5)
"""

import argparse
import sys


def _parse_args() -> argparse.Namespace:
    """Define and parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="zomato-ai",
        description="🍽️  AI-powered restaurant recommendations powered by Groq + LLaMA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--location",       type=str,   default=None,  help="City or locality")
    parser.add_argument("--budget",         type=str,   default=None,  choices=["low", "medium", "high"])
    parser.add_argument("--cuisine",        type=str,   default=None,  help="Cuisine type (default: Any)")
    parser.add_argument("--rating",         type=float, default=None,  help="Minimum rating (default: 3.0)")
    parser.add_argument("--prefs",          type=str,   default=None,  help="Extra preferences (free text)")
    parser.add_argument("--dry-run",        action="store_true",       help="Print prompt and exit without calling LLM")
    parser.add_argument("--max-candidates", type=int,   default=20,    help="Max candidates to pass to LLM")
    parser.add_argument("--top-n",          type=int,   default=5,     help="Max recommendations to return")
    return parser.parse_args()


def _has_flags(args: argparse.Namespace) -> bool:
    """Return True if the user passed at least one input flag."""
    return any([args.location, args.budget, args.cuisine, args.rating, args.prefs])


def _collect_from_args(args: argparse.Namespace) -> dict:
    """Build a raw-preferences dict from CLI flags."""
    return {
        "location": args.location or "",
        "budget":   args.budget   or "medium",
        "cuisine":  args.cuisine  or "Any",
        "rating":   args.rating   if args.rating is not None else 3.0,
        "prefs":    args.prefs    or "",
    }


def _collect_interactive() -> dict:
    """Prompt the user interactively for all required fields."""
    from rich.prompt import FloatPrompt, Prompt

    print()
    location = Prompt.ask("📍 City / Location")
    budget   = Prompt.ask("💰 Budget", choices=["low", "medium", "high"], default="medium")
    cuisine  = Prompt.ask("🍕 Cuisine (press Enter for any)", default="Any")
    rating   = FloatPrompt.ask("⭐ Minimum rating", default=3.0)
    prefs    = Prompt.ask("📝 Any other preferences? (optional)", default="")
    return {
        "location": location,
        "budget":   budget,
        "cuisine":  cuisine,
        "rating":   float(rating),
        "prefs":    prefs,
    }


def main() -> None:
    """Main pipeline entry-point."""
    from rich.console import Console
    from rich.spinner import Spinner  # noqa: F401 — used via Live

    console = Console()

    # ------------------------------------------------------------------
    # 1. Parse arguments
    # ------------------------------------------------------------------
    try:
        args = _parse_args()
    except SystemExit:
        raise

    # ------------------------------------------------------------------
    # 2. Load & preprocess dataset
    # ------------------------------------------------------------------
    from rich.live import Live
    from rich.text import Text

    with Live(Text("⏳ Loading dataset...", style="dim"), refresh_per_second=10, transient=True):
        from src.data.loader import load_dataset
        from src.data.preprocessor import preprocess
        raw_df = load_dataset()
        df     = preprocess(raw_df)

    console.print(f"[dim]✓ Dataset loaded — {len(df):,} restaurants[/dim]")

    # ------------------------------------------------------------------
    # 3. Collect user preferences
    # ------------------------------------------------------------------
    if _has_flags(args):
        raw = _collect_from_args(args)
    else:
        raw = _collect_interactive()

    # ------------------------------------------------------------------
    # 4. Parse preferences
    # ------------------------------------------------------------------
    from src.input.parser import parse_preferences

    try:
        prefs = parse_preferences({**raw, "min_rating": raw["rating"], "extra_prefs": raw["prefs"]})
    except ValueError as exc:
        console.print(f"\n[bold red]❌ Invalid input:[/bold red] {exc}")
        sys.exit(1)

    # ------------------------------------------------------------------
    # 5. Filter candidates
    # ------------------------------------------------------------------
    from src.filter.engine import get_candidates

    filter_result = get_candidates(df, prefs, max_candidates=args.max_candidates)
    candidates    = filter_result["candidates"]

    console.print(f"[dim]✓ {len(candidates)} candidate restaurants found[/dim]")

    if filter_result.get("fallback_triggered"):
        reason = filter_result.get("fallback_reason", "Filters relaxed.")
        console.print(f"[bold yellow]⚠️  Fallback triggered:[/bold yellow] [yellow]{reason}[/yellow]")

    if not candidates:
        console.print(
            "\n[bold red]😞 No restaurants found for your preferences.[/bold red]\n"
            "[dim]Try a different city, broader budget, or lower rating threshold.[/dim]"
        )
        sys.exit(0)

    # ------------------------------------------------------------------
    # 6. Build prompt
    # ------------------------------------------------------------------
    from src.prompt.builder import build_prompt
    from src.prompt.templates import SYSTEM_PROMPT

    user_prompt = build_prompt(prefs, candidates)

    # Dry-run: print prompt and exit
    if args.dry_run:
        console.rule("[bold]SYSTEM PROMPT[/bold]")
        console.print(SYSTEM_PROMPT)
        console.rule("[bold]USER PROMPT[/bold]")
        console.print(user_prompt)
        sys.exit(0)

    # ------------------------------------------------------------------
    # 7. Call LLM
    # ------------------------------------------------------------------
    from src.llm.client import LLMError, LLMTimeoutError, call_llm

    raw_llm_response: str | None = None

    with Live(Text("🤖 Asking AI to rank restaurants...", style="cyan"), refresh_per_second=10, transient=True):
        try:
            raw_llm_response = call_llm(SYSTEM_PROMPT, user_prompt)
        except LLMTimeoutError as exc:
            console.print(f"\n[bold yellow]⚠️  LLM timed out:[/bold yellow] [yellow]{exc}[/yellow]")
            console.print("[dim]Falling back to unranked filter results.[/dim]")
        except LLMError as exc:
            console.print(f"\n[bold yellow]⚠️  LLM error:[/bold yellow] [yellow]{exc}[/yellow]")
            console.print("[dim]Falling back to unranked filter results.[/dim]")

    # ------------------------------------------------------------------
    # 8. Parse LLM response
    # ------------------------------------------------------------------
    from src.llm.parser import parse_response

    result = parse_response(raw_llm_response or "", candidates)

    # Propagate fallback info into result for formatter
    if filter_result.get("fallback_triggered"):
        result["fallback_triggered"] = True
        result["fallback_reason"]    = filter_result.get("fallback_reason", "")

    # ------------------------------------------------------------------
    # 9. Render CLI output
    # ------------------------------------------------------------------
    if not result.get("recommendations"):
        console.print(
            "\n[bold red]😞 No recommendations could be generated.[/bold red]\n"
            "[dim]Try adjusting your preferences.[/dim]"
        )
        sys.exit(0)

    from src.output.formatter import render_cli
    render_cli(result, prefs)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
