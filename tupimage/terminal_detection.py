"""
Terminal detection utilities for tupimage.

This module provides functions to detect terminal emulators that support
the Kitty graphics protocol and generate stable terminal instance identifiers.
"""

import os
import re
import subprocess
from typing import Optional, Tuple

import psutil


def get_terminal_executable_names():
    """Get a list of terminal emulator names used to search for the terminal PID."""
    # First, official Kitty graphics protocol supporting terminals.
    terminals = {
        "kitty",
        "st",
        "ghostty",
        "konsole",
        "warp",
        "wayst",
        "wezterm",
    }

    terminals.add("sshd")
    terminals.add("tmux")
    terminals.add("tmux: server")

    # Add $TERM_PROGRAM
    term_program = os.environ.get("TERM_PROGRAM")
    if term_program:
        terminals.add(term_program)

    # Add $TERM without -256color suffix
    term = os.environ.get("TERM")
    if term:
        term = term.replace("-256color", "")
        if len(term.replace("-", "")) >= 2:
            terminals.add(term)

    return terminals


def get_terminal_and_shell_pid() -> Optional[Tuple[int, str, int]]:
    """
    Try to get the PID of the terminal emulator process and the pid of the shell running
    within it.

    The pid of the shell is the pid of the terminal's child that is the ancestor of the
    current process (or the current process itself).

    Returns:
        A triple `(term_pid, term_name, shell_pid)` or None if not found.
    """
    try:
        terminals = get_terminal_executable_names()
        process = psutil.Process()
        while process is not None:
            child_process = process
            process = process.parent()
            if process is not None and process.name() in terminals:
                return process.pid, process.name(), child_process.pid
    except Exception:
        pass

    return None


def is_inside_tmux() -> bool:
    """Check if we are running inside a local tmux."""
    # First, $TMUX must be set
    tmux = os.environ.get("TMUX")
    if tmux is None or tmux == "":
        return False
    # Also check that we are actually running within a local tmux, and there is no other
    # terminal between them.
    pidnamepid = get_terminal_and_shell_pid()
    return pidnamepid is None or "tmux" in pidnamepid[1]


def tmux_display_message(message: str) -> str:
    """Execute tmux display-message command and return the result."""
    result = subprocess.run(
        ["tmux", "display-message", "-p", message],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def remove_bad_chars(string: str) -> str:
    """Remove characters that are not safe for use in identifiers."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", string)


def detect_terminal_info() -> Tuple[str, str, str]:
    """
    Detect terminal name, terminal ID, and session ID.

    Returns:
        Tuple[str, str, str]: (terminal_name, terminal_id, session_id)
    """
    # Check if we're inside tmux.
    if is_inside_tmux():
        # Handle tmux/screen case
        try:
            data = tmux_display_message(
                "#{client_termname}||||#{client_pid}||||#{pid}_#{session_id}"
            ).split("||||")

            terminal_name = data[0]
            terminal_id = f"tmux-client-{data[0]}-{data[1]}"
            session_id = f"tmux-{data[2]}"

            return (
                remove_bad_chars(terminal_name),
                remove_bad_chars(terminal_id),
                remove_bad_chars(session_id),
            )
        except Exception:
            # If tmux command fails, fall back to the regular terminal detection.
            pass

    # Handle regular terminal case
    terminal_name = os.environ.get("TERM", "unknown-terminal")

    pidnamepid = get_terminal_and_shell_pid()
    if pidnamepid is not None:
        # Use the shell pid if available.
        _, _, shell_pid = pidnamepid
        terminal_id = terminal_name + "-" + str(shell_pid)
    else:
        # Otherwise use $WINDOWID.
        terminal_id = (
            terminal_name + "-windowid-" + os.environ.get("WINDOWID", "unknown-window")
        )

    # Use $TERM for the terminal name, use terminal_id for both terminal and session id.
    return (terminal_name, remove_bad_chars(terminal_id), remove_bad_chars(terminal_id))
