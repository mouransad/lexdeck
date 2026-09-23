"""Scriptable, Git-style command-line interface for Lexdeck."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict
from typing import Annotated, TypeVar

import typer
from lexdeck_core import Card, LexdeckService
from lexdeck_core.repository import CardNotFoundError
from lexdeck_core.service import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from lexdeck_cli import __version__

app = typer.Typer(
    name="lexdeck",
    help="Learn vocabulary from your terminal.",
    no_args_is_help=False,
    add_completion=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool, typer.Option("--version", help="Show the installed Lexdeck version.")
    ] = False,
) -> None:
    """Launch the TUI when no subcommand is given."""
    if version:
        typer.echo(f"Lexdeck {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        launch_tui()


@app.command()
def tui() -> None:
    """Open the full-screen terminal interface."""
    launch_tui()


@app.command()
def add(
    content: Annotated[
        str | None,
        typer.Argument(help="The word, phrase, or question on the front of the card."),
    ] = None,
    meaning: Annotated[
        str | None,
        typer.Option("--meaning", "-m", help="Optional English or Persian meaning."),
    ] = None,
) -> None:
    """Add one card; prompt for missing content in an interactive shell."""
    if content is None:
        if not console.is_terminal:
            raise typer.BadParameter("CONTENT is required when input is not interactive")
        content = Prompt.ask("Content")
        if meaning is None:
            entered = Prompt.ask("Meaning [dim](optional)[/dim]", default="", show_default=False)
            meaning = entered or None
    service = _service()
    card = _handle(lambda: service.add_card(content, meaning))
    console.print(f"[green]Added[/green] [bold]{card.id[:8]}[/bold]")


@app.command("list")
def list_cards(
    query: Annotated[
        str | None, typer.Option("--query", "-q", help="Search content or meaning.")
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", min=1, help="Maximum rows.")] = 50,
    as_json: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON instead of a table.")
    ] = False,
) -> None:
    """List and search cards."""
    cards = _service().list_cards(query=query, limit=limit)
    if as_json:
        typer.echo(json.dumps([_card_json(card) for card in cards], ensure_ascii=False, indent=2))
        return
    table = Table(box=None, header_style="bold cyan", pad_edge=False)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Content", overflow="fold")
    table.add_column("Meaning", overflow="fold")
    for card in cards:
        table.add_row(
            card.id[:8],
            card.prompt,
            card.meaning or "[dim]—[/dim]",
        )
    console.print(table if cards else "[dim]No cards found.[/dim]")


@app.command()
def show(
    card_id: Annotated[str, typer.Argument(help="A full card ID or unique prefix.")],
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Show one card."""
    card = _handle(lambda: _service().get_card(card_id))
    if as_json:
        typer.echo(json.dumps(_card_json(card), ensure_ascii=False, indent=2))
        return
    body = (
        f"[bold]{card.prompt}[/bold]\n\n"
        f"{card.meaning or '[dim]No meaning yet[/dim]'}\n\n"
        f"[dim]Updated:[/dim] {card.updated_at.astimezone().strftime('%Y-%m-%d %H:%M')}"
    )
    console.print(Panel(body, title=card.id[:8], border_style="cyan"))


@app.command()
def edit(
    card_id: Annotated[str, typer.Argument(help="A full card ID or unique prefix.")],
    content: Annotated[str | None, typer.Option("--content", "-c")] = None,
    meaning: Annotated[str | None, typer.Option("--meaning", "-m")] = None,
    clear_meaning: Annotated[bool, typer.Option("--clear-meaning")] = False,
) -> None:
    """Update fields on an existing card."""
    service = _service()
    card = _handle(lambda: service.get_card(card_id))
    updated = _handle(
        lambda: service.edit_card(
            card.id,
            prompt=content if content is not None else card.prompt,
            meaning=None if clear_meaning else (meaning if meaning is not None else card.meaning),
        )
    )
    console.print(f"[green]Updated[/green] [bold]{updated.id[:8]}[/bold]")


@app.command()
def remove(
    card_id: Annotated[str, typer.Argument(help="A full card ID or unique prefix.")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
) -> None:
    """Archive a card without destroying its review history."""
    service = _service()
    card = _handle(lambda: service.get_card(card_id))
    if not yes and not typer.confirm(f"Archive {card.prompt!r}?"):
        raise typer.Abort()
    _handle(lambda: service.remove_card(card.id))
    console.print(f"[yellow]Archived[/yellow] [bold]{card.id[:8]}[/bold]")


@app.command()
def study() -> None:
    """Review every card, choosing random or sorted order at the start."""
    from lexdeck_cli.tui import LexdeckApp

    LexdeckApp(_service(), initial_screen="study").run()


@app.command()
def stats(as_json: Annotated[bool, typer.Option("--json")] = False) -> None:
    """Show learning progress."""
    value = _service().stats()
    if as_json:
        typer.echo(json.dumps(asdict(value), indent=2))
        return
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim")
    table.add_column(style="bold")
    table.add_row("Cards", str(value.total_cards))
    table.add_row("With meanings", str(value.complete_cards))
    table.add_row("Reviewed today", str(value.reviewed_today))
    table.add_row("Remembered today", str(value.remembered_today))
    table.add_row("Streak", f"{value.streak_days} day{'s' if value.streak_days != 1 else ''}")
    console.print(Panel(table, title="Lexdeck progress", border_style="cyan"))


@app.command("data-path")
def data_path() -> None:
    """Print the SQLite database path for backup or inspection."""
    typer.echo(_service().data_path)


def launch_tui() -> None:
    from lexdeck_cli.tui import LexdeckApp

    LexdeckApp(_service()).run()


def _service() -> LexdeckService:
    return _handle(LexdeckService)


T = TypeVar("T")


def _handle(function: Callable[[], T]) -> T:
    try:
        return function()
    except (ValidationError, CardNotFoundError) as error:
        console.print(f"[red]Error:[/red] {error}", highlight=False)
        raise typer.Exit(2) from error


def _card_json(card: Card) -> dict[str, object]:
    return {
        "id": card.id,
        "content": card.prompt,
        "meaning": card.meaning,
        "created_at": card.created_at.isoformat(),
        "updated_at": card.updated_at.isoformat(),
    }
