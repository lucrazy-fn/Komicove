"""Typography used by the redesigned desktop shell and library."""

import platform


FAMILY = "Segoe UI" if platform.system() == "Windows" else "DejaVu Sans"


def heading(size=22):
    return (FAMILY, size, "bold")


def section(size=13):
    return (FAMILY, size, "bold")


def body(size=10, *, bold=False):
    return (FAMILY, size, "bold" if bold else "normal")


def caption(size=9, *, bold=False):
    return (FAMILY, size, "bold" if bold else "normal")
