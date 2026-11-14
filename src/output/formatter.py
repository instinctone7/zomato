"""
Output formatter for the Zomato AI Recommender.

Provides two rendering targets:
- render_cli()       — Rich-based terminal output
- render_streamlit() — Streamlit-based browser UI output

Both consume the unified result dict produced by src.llm.parser.parse_response()
and the UserPreferences dataclass from src.input.parser.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.input.parser import UserPreferences


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _truncate(text: str, max_len: int = 50) -> str:
    """Truncate a string to max_len characters, appending '...' if needed."""
    if not text:
        return text
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


def _fmt_cuisines(cuisines: list[str] | None) -> str:
    """Return a formatted cuisine string; falls back to 'Not specified'."""
    if not cuisines:
        return "Not specified"
    return ", ".join(cuisines)


def _fmt_cost(cost: int | float | None) -> str:
    """Return '₹<amount>' or '₹—' when cost is unavailable."""
    if cost is None:
        return "₹—"
    return f"₹{int(cost):,}"


def _fmt_explanation(explanation: str | None) -> str:
    """Return explanation text, defaulting to a sensible fallback."""
    if not explanation or not explanation.strip():
        return "A strong match for your preferences."
    return explanation.strip()


def _star_bar(rating: float | None, max_stars: int = 5) -> str:
    """Return a unicode star bar string, e.g. '★★★★☆'."""
    if rating is None:
        return "☆" * max_stars
    full = min(round(rating), max_stars)
    return "★" * full + "☆" * (max_stars - full)


# ---------------------------------------------------------------------------
# CLI rendering  (uses Rich)
# ---------------------------------------------------------------------------

def _render_header(prefs: "UserPreferences") -> None:
    """Print a Rich panel as the page header."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    console = Console()

    budget_label = {
        "low":    "Low (< ₹400)",
        "medium": "Medium (₹400–₹1000)",
        "high":   "High (> ₹1000)",
    }.get(getattr(prefs, "budget_tier", "medium"), prefs.budget_tier)

    cuisine_label = getattr(prefs, "cuisine", None) or "Any"
    rating_label  = f"{getattr(prefs, 'min_rating', 0.0):.1f}+"

    subtitle = Text()
    subtitle.append("📍 ", style="bold")
    subtitle.append(prefs.location, style="cyan")
    subtitle.append("   💰 ", style="bold")
    subtitle.append(budget_label, style="green")
    subtitle.append("   🍕 ", style="bold")
    subtitle.append(cuisine_label, style="magenta")
    subtitle.append("   ⭐ ", style="bold")
    subtitle.append(rating_label, style="yellow")

    console.print()
    console.print(
        Panel(
            subtitle,
            title="[bold white]🍽️  Zomato AI Recommendations[/bold white]",
            border_style="bright_blue",
            padding=(1, 3),
        )
    )


def _render_card(rec: dict, rank: int) -> None:
    """Print a Rich panel for a single restaurant recommendation."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    console = Console()

    name        = _truncate(rec.get("name", "Unknown"), 50)
    location    = rec.get("location", "—")
    cuisines    = _fmt_cuisines(rec.get("cuisines", []))
    rating      = rec.get("rating")
    votes       = rec.get("votes", rec.get("rating_count", None))
    cost        = _fmt_cost(rec.get("cost_for_two"))
    delivery    = rec.get("delivery", None)
    booking     = rec.get("table_booking", None)
    explanation = _fmt_explanation(rec.get("explanation"))
    trade_off   = rec.get("trade_offs", "")

    stars = _star_bar(rating)
    rating_str = f"{rating:.1f}" if rating is not None else "—"
    votes_str  = f"({votes:,} votes)" if votes else ""

    # ----- Build panel content -----
    content = Text()

    # Restaurant meta
    content.append(f"📍 {location}   ", style="dim")
    content.append(f"🍕 {cuisines}\n", style="dim")
    content.append(f"{stars}  ", style="yellow")
    content.append(f"{rating_str} / 5  {votes_str}\n", style="yellow")
    content.append(f"💰 Cost for 2: {cost}", style="green")

    if delivery is not None:
        deliv_label = "✅" if delivery else "❌"
        content.append(f"   🛵 Delivery: {deliv_label}", style="dim")
    if booking is not None:
        book_label = "✅" if booking else "❌"
        content.append(f"   📅 Booking: {book_label}", style="dim")
    content.append("\n\n")

    # AI explanation
    content.append("🤖 ", style="bold cyan")
    content.append(explanation + "\n", style="italic")

    # Trade-off (optional)
    if trade_off and trade_off.strip():
        content.append("\n⚠️  Trade-off: ", style="bold yellow")
        content.append(trade_off.strip(), style="yellow")

    console.print(
        Panel(
            content,
            title=f"[bold]#{rank}  {name}[/bold]",
            border_style="green" if rank == 1 else "blue",
            padding=(1, 2),
        )
    )


def _render_summary(summary: str) -> None:
    """Print the AI-generated summary in italic."""
    from rich.console import Console
    from rich.text import Text

    console = Console()
    console.print()
    t = Text("💬 ", style="bold")
    t.append(summary.strip(), style="italic dim")
    console.print(t)


def _render_fallback_warning(reason: str) -> None:
    """Print an amber fallback warning."""
    from rich.console import Console

    console = Console()
    console.print(
        f"\n[bold yellow]⚠️  Relaxed filters applied:[/bold yellow] [yellow]{reason}[/yellow]"
    )


def render_cli(result: dict, prefs: "UserPreferences") -> None:
    """
    Render full CLI output for a recommendation result.

    Args:
        result: Dict from parse_response() with keys:
                - recommendations: list[dict]
                - summary: str
                - ai_ranking: bool
                - fallback_triggered: bool (optional)
                - fallback_reason: str (optional)
        prefs:  UserPreferences instance from parse_preferences().
    """
    from rich.console import Console

    console = Console()

    _render_header(prefs)

    # Fallback warning (before results)
    if result.get("fallback_triggered"):
        _render_fallback_warning(result.get("fallback_reason", "Filters relaxed to find matches."))

    recs = result.get("recommendations", [])

    if not recs:
        console.print("\n[bold red]😞 No restaurants found matching your criteria.[/bold red]")
        console.print("[dim]Try adjusting your budget, cuisine, or location.[/dim]")
        return

    ai_ranked = result.get("ai_ranking", False)
    console.print(
        f"\n[bold]Found [cyan]{len(recs)}[/cyan] recommendations"
        f"{'  [dim](AI-ranked)[/dim]' if ai_ranked else ''}[/bold]"
    )

    for rec in recs:
        _render_card(rec, rank=rec.get("rank", recs.index(rec) + 1))

    summary = result.get("summary", "")
    if summary and summary.strip():
        _render_summary(summary)

    console.print()


# ---------------------------------------------------------------------------
# Streamlit rendering
# ---------------------------------------------------------------------------

def render_streamlit(result: dict) -> None:
    """
    Render full Streamlit UI for a recommendation result.

    Must be called from within an active Streamlit session.
    Requires `import streamlit as st` to work.

    Args:
        result: Dict from parse_response() with keys:
                - recommendations: list[dict]
                - summary: str
                - ai_ranking: bool
                - fallback_triggered: bool (optional)
                - fallback_reason: str (optional)
    """
    import streamlit as st  # lazy import — only in Streamlit context

    recs = result.get("recommendations", [])

    if result.get('notice'):
        st.info(result['notice'])

    # Fallback warning
    if result.get("fallback_triggered"):
        reason = result.get("fallback_reason", "Filters relaxed to find matches.")
        st.warning(f"⚠️ Relaxed filters applied: {reason}")

    if not recs:
        st.error("😞 No restaurants found matching your criteria. Try adjusting your preferences.")
        return

    ai_ranked = result.get("ai_ranking", False)
    st.markdown(
        f"### Found **{len(recs)}** recommendations"
        + ("  `AI-ranked`" if ai_ranked else "")
    )

    for rec in recs:
        rank        = rec.get("rank", recs.index(rec) + 1)
        name        = _truncate(rec.get("name", "Unknown"), 50)
        location    = rec.get("location", "—")
        cuisines    = _fmt_cuisines(rec.get("cuisines", []))
        rating      = rec.get("rating")
        votes       = rec.get("votes", rec.get("rating_count", None))
        cost        = rec.get("cost_for_two")
        explanation = _fmt_explanation(rec.get("explanation"))
        trade_off   = rec.get("trade_offs", "")
        delivery    = rec.get("has_online_delivery", None)
        booking     = rec.get("has_table_booking", None)

        stars = "⭐" * (round(rating) if rating else 0)
        rating_str = f"{rating:.1f}" if rating is not None else "—"

        with st.container():
            col1, col2 = st.columns([3, 1])

            with col1:
                st.subheader(f"{stars}  #{rank} — {name}")
                meta_parts = [f"📍 {location}", f"🍕 {cuisines}"]
                if delivery is not None:
                    meta_parts.append("🛵 Delivery: " + ("✅" if delivery else "❌"))
                if booking is not None:
                    meta_parts.append("📅 Booking: " + ("✅" if booking else "❌"))
                st.caption("   |   ".join(meta_parts))

            with col2:
                votes_help = f"{votes:,} votes" if votes else None
                st.metric("Rating", f"{rating_str} / 5", help=votes_help)
                st.metric("Cost for 2", _fmt_cost(cost))

            with st.expander("🤖 Why this restaurant?"):
                st.write(explanation)
                if trade_off and trade_off.strip():
                    st.warning(f"⚠️ Trade-off: {trade_off.strip()}")

            st.divider()

    summary = result.get("summary", "")
    if summary and summary.strip():
        st.markdown("---")
        st.markdown(f"💬 *{summary.strip()}*")
