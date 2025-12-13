#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Textual TUI for batch processing Schwab CSV files.

This module provides an interactive terminal user interface for selecting
and processing multiple Schwab CSV files.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json

from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Header,
    Footer,
    Button,
    Static,
    Label,
    DirectoryTree,
    DataTable,
    ProgressBar,
    ListView,
    ListItem,
    Tree,
)
from textual.containers import Container, Vertical, Horizontal, ScrollableContainer
from textual.binding import Binding
from textual import events
from rich.text import Text
from rich.table import Table as RichTable

from batch import process_multiple_files, BatchOptions, FileProgress, BatchResult


class NavigableDirectoryTree(DirectoryTree):
    """Enhanced DirectoryTree with parent directory navigation capabilities."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.path_change_callback = None

    def set_path_change_callback(self, callback):
        """Set a callback to be called when the path changes."""
        self.path_change_callback = callback

    def _notify_path_change(self):
        """Notify that the path has changed."""
        if self.path_change_callback:
            self.path_change_callback()

    async def on_tree_node_collapsed(self, event: Tree.NodeCollapsed) -> None:
        """Navigate to parent directory when root node is collapsed."""
        event.stop()

        # Only handle root node collapse for parent navigation
        if not event.node.is_root:
            return

        # Get current path and its parent
        current_path = Path(self.path).resolve()
        parent_path = current_path.parent

        # Don't navigate above the filesystem root
        if parent_path != current_path and parent_path.exists() and parent_path.is_dir():
            self.path = str(parent_path)
            await self.reload()
            self._notify_path_change()

    def navigate_to_parent(self) -> bool:
        """
        Navigate to the parent directory.

        Returns:
            True if navigation was successful, False otherwise
        """
        current_path = Path(self.path).resolve()
        parent_path = current_path.parent

        # Check if we can navigate to parent
        if parent_path != current_path and parent_path.exists() and parent_path.is_dir():
            self.path = str(parent_path)
            self.reload()
            self._notify_path_change()
            return True
        return False

    def navigate_to_directory(self, directory_path: str) -> bool:
        """
        Navigate to a specific directory.

        Args:
            directory_path: Path to navigate to

        Returns:
            True if navigation was successful, False otherwise
        """
        try:
            path = Path(directory_path).resolve()
            if path.exists() and path.is_dir():
                self.path = str(path)
                self.reload()
                self._notify_path_change()
                return True
        except (OSError, ValueError):
            pass
        return False

    def get_current_path(self) -> str:
        """Get the current directory path as a string."""
        return str(Path(self.path).resolve())


class PathBreadcrumb(Static):
    """Widget displaying current directory path with navigation breadcrumbs."""

    def __init__(self, initial_path: str = ".", **kwargs):
        super().__init__(**kwargs)
        self.current_path = Path(initial_path).resolve()
        self.update_breadcrumb()

    def update_path(self, new_path: str) -> None:
        """Update the displayed path."""
        self.current_path = Path(new_path).resolve()
        self.update_breadcrumb()

    def update_breadcrumb(self) -> None:
        """Update the breadcrumb display."""
        path_str = str(self.current_path)

        # Truncate very long paths for display
        max_length = 80
        if len(path_str) > max_length:
            # Show beginning and end of path
            path_str = f"{path_str[:30]}...{path_str[-45:]}"

        breadcrumb_text = f"📍 Current Path: {path_str}"
        self.update(breadcrumb_text)

    def get_path_parts(self) -> List[Path]:
        """Get individual path components for potential future navigation."""
        return list(self.current_path.parents)[::-1] + [self.current_path]


def normalize_starting_dir(starting_dir: Optional[str]) -> str:
    """
    Normalize and validate the starting directory path.

    Handles:
    - Relative paths (resolved to absolute)
    - Home directory expansion (~)
    - Path validation (must exist and be a directory)
    - Invalid paths fall back to current directory

    Args:
        starting_dir: Path to normalize (can be None, empty, relative, or absolute)

    Returns:
        Normalized absolute path, or "." if path is invalid
    """
    # Handle None or empty string
    if not starting_dir:
        return "."

    try:
        # Expand user home directory (~)
        path = Path(starting_dir).expanduser()

        # Resolve to absolute path (handles relative paths)
        path = path.resolve()

        # Validate: path must exist and be a directory
        if path.exists() and path.is_dir():
            return str(path)
        else:
            # Invalid path, fall back to current directory
            return "."

    except (OSError, RuntimeError, ValueError):
        # Any path-related error, fall back to current directory
        return "."


@dataclass
class AppState:
    """Application state for the TUI."""

    selected_files: List[str] = field(default_factory=list)
    """List of selected CSV file paths."""

    output_path: str = "output.ndjson"
    """Path to output file."""

    processing_status: str = "idle"
    """Current status: idle, processing, completed, failed."""

    batch_result: Optional[BatchResult] = None
    """Results from batch processing."""

    processing_start_time: Optional[datetime] = None
    """When processing started."""

    processing_end_time: Optional[datetime] = None
    """When processing ended."""

    file_progress: Dict[int, FileProgress] = field(default_factory=dict)
    """Progress information for each file."""

    options: BatchOptions = field(default_factory=BatchOptions)
    """Batch processing options."""


class FileSelectionScreen(Screen):
    """Screen for selecting CSV files to process."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("enter", "select_file", "Toggle Select"),
        Binding("s", "start_processing", "Start Processing"),
        Binding("c", "clear_selection", "Clear All"),
        Binding("o", "set_output", "Set Output"),
        Binding("backspace", "navigate_parent", "Parent Dir"),
        Binding("up", "navigate_parent", "Parent Dir"),
    ]

    def __init__(self, app_state: AppState, starting_dir: str = "."):
        super().__init__()
        self.app_state = app_state
        self.starting_dir = starting_dir

    def compose(self) -> ComposeResult:
        """Compose the file selection screen."""
        yield Header()
        yield Container(
            Static("Select CSV files to process:", id="title"),
            Static("🎯 Multi-Select Mode: ENTER to toggle selection, 's' to start, 'c' to clear all, BACKSPACE/↑ for parent dir", id="help"),
            PathBreadcrumb(self.starting_dir, id="path_breadcrumb"),
            Horizontal(
                Container(
                    Static("📁 Browse Files", id="tree_title"),
                    NavigableDirectoryTree(self.starting_dir, id="file_tree"),
                    id="tree_container",
                ),
                Container(
                    Static("✓ Selected Files (0)", id="selected_title"),
                    ScrollableContainer(id="selected_list"),
                    id="selected_container",
                ),
            ),
            Container(
                Static("No files selected", id="selected_count"),
                Button("Start Processing (s)", id="start_btn", variant="primary"),
                Button("Clear All (c)", id="clear_btn"),
                Button("Quit (q)", id="quit_btn"),
                id="button_bar",
            ),
            id="file_selection_container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Handle screen mount."""
        tree = self.query_one(NavigableDirectoryTree)
        tree.show_root = False
        tree.guide_depth = 3
        tree.set_path_change_callback(self.update_breadcrumb_path)

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """Handle file selection in directory tree."""
        file_path = str(event.path)

        # Only allow CSV files
        if not file_path.endswith('.csv'):
            return

        if file_path in self.app_state.selected_files:
            self.app_state.selected_files.remove(file_path)
        else:
            self.app_state.selected_files.append(file_path)

        # Update UI
        self.update_selection_display()

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        """Handle directory navigation in directory tree."""
        # Update breadcrumb when directory changes
        self.update_breadcrumb_path()

    def update_selection_display(self) -> None:
        """Update the selected files display."""
        count = len(self.app_state.selected_files)

        # Update title
        title = self.query_one("#selected_title", Static)
        title.update(f"✓ Selected Files ({count})")

        # Update selected files list
        selected_list = self.query_one("#selected_list", ScrollableContainer)
        selected_list.remove_children()

        if count > 0:
            for idx, file_path in enumerate(self.app_state.selected_files):
                filename = Path(file_path).name
                selected_list.mount(Static(f"☑ {idx + 1}. {filename}", classes="selected_file"))

            # Update count label
            count_label = self.query_one("#selected_count", Static)
            count_label.update(f"✓ {count} file{'s' if count != 1 else ''} selected")
        else:
            selected_list.mount(Static("(none)", classes="no_selection"))
            count_label = self.query_one("#selected_count", Static)
            count_label.update("No files selected")

    def update_breadcrumb_path(self) -> None:
        """Update the breadcrumb path display."""
        tree = self.query_one(NavigableDirectoryTree)
        breadcrumb = self.query_one(PathBreadcrumb)
        breadcrumb.update_path(tree.get_current_path())

    def action_select_file(self) -> None:
        """Toggle file selection."""
        tree = self.query_one(NavigableDirectoryTree)
        if tree.cursor_node:
            # Simulate file selected event
            pass

    def action_navigate_parent(self) -> None:
        """Navigate to parent directory."""
        tree = self.query_one(NavigableDirectoryTree)
        if tree.navigate_to_parent():
            self.update_breadcrumb_path()

    def action_clear_selection(self) -> None:
        """Clear all selected files."""
        self.app_state.selected_files.clear()
        self.update_selection_display()

    def action_start_processing(self) -> None:
        """Start processing selected files."""
        if not self.app_state.selected_files:
            return

        self.app_state.processing_status = "processing"
        self.app_state.processing_start_time = datetime.now()
        self.app.push_screen(ProcessingScreen(self.app_state))

    def action_set_output(self) -> None:
        """Set output file path."""
        # For now, use default
        pass

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "start_btn":
            self.action_start_processing()
        elif event.button.id == "clear_btn":
            self.action_clear_selection()
        elif event.button.id == "quit_btn":
            self.action_quit()


class ProcessingScreen(Screen):
    """Screen showing processing progress."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state

    def compose(self) -> ComposeResult:
        """Compose the processing screen."""
        yield Header()
        yield Container(
            Static("Processing files...", id="processing_title"),
            Container(id="progress_container"),
            Static("", id="status_text"),
            id="processing_main",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Start processing when screen mounts."""
        self.start_processing()

    def start_processing(self) -> None:
        """Start the batch processing."""
        container = self.query_one("#progress_container", Container)

        # Add progress bar for each file
        for idx, file_path in enumerate(self.app_state.selected_files):
            filename = Path(file_path).name
            container.mount(Static(f"[{idx+1}/{len(self.app_state.selected_files)}] {filename}"))
            container.mount(ProgressBar(id=f"progress_{idx}", total=100))

        # Process files in background
        def progress_callback(progress: FileProgress):
            """Update progress display."""
            self.update_progress(progress)

        # Run processing
        try:
            result = process_multiple_files(
                self.app_state.selected_files,
                self.app_state.output_path,
                self.app_state.options,
                progress_callback=progress_callback,
            )
            self.app_state.batch_result = result
            self.app_state.processing_status = "completed"
            self.app_state.processing_end_time = datetime.now()

            # Show summary screen
            self.app.push_screen(SummaryScreen(self.app_state))

        except Exception as e:
            self.app_state.processing_status = "failed"
            status_text = self.query_one("#status_text", Static)
            status_text.update(f"Error: {str(e)}")

    def update_progress(self, progress: FileProgress) -> None:
        """Update progress display for a file."""
        self.app_state.file_progress[progress.file_index] = progress

        # Update progress bar
        progress_bar_id = f"progress_{progress.file_index}"
        try:
            progress_bar = self.query_one(f"#{progress_bar_id}", ProgressBar)
            if progress.status == "completed":
                progress_bar.update(progress=100)
            elif progress.status == "processing":
                progress_bar.update(progress=50)
            elif progress.status == "failed":
                progress_bar.update(progress=0)
        except:
            pass

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()


class SummaryScreen(Screen):
    """Screen showing processing results summary."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("e", "view_errors", "View Errors"),
        Binding("n", "new_batch", "New Batch"),
    ]

    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state

    def compose(self) -> ComposeResult:
        """Compose the summary screen."""
        yield Header()
        yield ScrollableContainer(
            Static("Processing Complete!", id="summary_title"),
            Container(id="summary_stats"),
            Container(
                Button("View Errors (e)", id="errors_btn", variant="primary"),
                Button("New Batch (n)", id="new_btn"),
                Button("Quit (q)", id="quit_btn"),
                id="summary_buttons",
            ),
            id="summary_container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Display summary statistics."""
        result = self.app_state.batch_result
        if not result:
            return

        stats_container = self.query_one("#summary_stats", Container)

        # Calculate processing time
        if self.app_state.processing_start_time and self.app_state.processing_end_time:
            duration = self.app_state.processing_end_time - self.app_state.processing_start_time
            duration_str = f"{duration.total_seconds():.2f}s"
        else:
            duration_str = "N/A"

        # Create summary table
        stats_text = f"""
Files Processed: {result.successful_files}/{result.total_files}
Failed Files: {result.failed_files}
Total Records: {result.total_records}
Processing Time: {duration_str}
Output File: {self.app_state.output_path}

Validation Issues:
"""
        if result.validation_issues:
            for issue_type, count in sorted(result.validation_issues.items()):
                stats_text += f"  - {issue_type}: {count}\n"
        else:
            stats_text += "  None\n"

        if result.file_errors:
            stats_text += f"\nFailed Files:\n"
            for file_path, error in result.file_errors.items():
                stats_text += f"  - {Path(file_path).name}: {error}\n"

        stats_container.mount(Static(stats_text, id="stats_text"))

    def action_view_errors(self) -> None:
        """View detailed errors."""
        if self.app_state.batch_result and self.app_state.batch_result.validation_issues:
            self.app.push_screen(ErrorReviewScreen(self.app_state))

    def action_new_batch(self) -> None:
        """Start a new batch."""
        # Reset state
        self.app_state.selected_files = []
        self.app_state.processing_status = "idle"
        self.app_state.batch_result = None
        self.app_state.file_progress = {}

        # Return to file selection
        self.app.pop_screen()
        self.app.pop_screen()

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "errors_btn":
            self.action_view_errors()
        elif event.button.id == "new_btn":
            self.action_new_batch()
        elif event.button.id == "quit_btn":
            self.action_quit()


class ErrorReviewScreen(Screen):
    """Screen for reviewing validation errors."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state

    def compose(self) -> ComposeResult:
        """Compose the error review screen."""
        yield Header()
        yield Container(
            Static("Validation Issues", id="error_title"),
            DataTable(id="error_table"),
            Button("Back (ESC)", id="back_btn"),
            id="error_container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Display error table."""
        table = self.query_one(DataTable)
        table.add_columns("Issue Type", "Count")

        result = self.app_state.batch_result
        if result and result.validation_issues:
            for issue_type, count in sorted(result.validation_issues.items()):
                table.add_row(issue_type, str(count))

    def action_back(self) -> None:
        """Go back to summary screen."""
        self.app.pop_screen()

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "back_btn":
            self.action_back()


class SchwabTUI(App):
    """Textual TUI application for batch CSV processing."""

    CSS = """
    #title {
        text-align: center;
        color: $accent;
        text-style: bold;
        padding: 1;
    }

    #help {
        text-align: center;
        color: $text-muted;
        padding-bottom: 1;
    }

    #path_breadcrumb {
        background: $panel;
        color: $accent;
        padding: 0 1;
        text-style: bold;
        border: solid $primary;
        margin-bottom: 1;
    }

    Horizontal {
        height: 1fr;
    }

    #tree_container {
        width: 3fr;
        height: 1fr;
    }

    #selected_container {
        width: 2fr;
        height: 1fr;
        border: solid $accent;
    }

    #tree_title, #selected_title {
        color: $accent;
        text-style: bold;
        padding: 0 1;
        background: $panel;
    }

    #file_tree {
        height: 1fr;
        border: solid $primary;
    }

    #selected_list {
        height: 1fr;
        padding: 1;
    }

    .selected_file {
        color: $success;
        padding: 0 1;
    }

    .no_selection {
        color: $text-muted;
        text-align: center;
        padding: 2;
    }

    #button_bar {
        layout: horizontal;
        height: auto;
        padding: 1;
        align: center middle;
    }

    #selected_count {
        padding: 1;
        text-align: center;
        color: $accent;
        text-style: bold;
    }

    Button {
        margin: 0 1;
    }

    #processing_title, #summary_title, #error_title {
        text-align: center;
        color: $accent;
        text-style: bold;
        padding: 1;
    }

    #progress_container {
        padding: 1;
        height: 1fr;
    }

    #summary_stats {
        padding: 1;
    }

    #summary_buttons {
        layout: horizontal;
        height: auto;
        padding: 1;
        align: center middle;
    }

    #stats_text {
        padding: 1;
    }

    #error_table {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit", show=False),
    ]

    def __init__(self, starting_dir: str = ".", output_path: str = "output.ndjson"):
        super().__init__()
        self.app_state = AppState(output_path=output_path)
        self.starting_dir = normalize_starting_dir(starting_dir)

    def on_mount(self) -> None:
        """Initialize the app."""
        self.title = "Schwab CSV Batch Processor"
        self.sub_title = "Select files to process"
        self.push_screen(FileSelectionScreen(self.app_state, self.starting_dir))

    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()


def run_tui(starting_dir: str = ".", output_path: str = "output.ndjson") -> None:
    """
    Run the TUI application.

    Args:
        starting_dir: Starting directory for file browser
        output_path: Default output file path
    """
    app = SchwabTUI(starting_dir=starting_dir, output_path=output_path)
    app.run()


if __name__ == "__main__":
    run_tui()
