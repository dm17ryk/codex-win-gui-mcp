from __future__ import annotations


class WinGuiError(RuntimeError):
    """Base class for harness errors."""


class SessionNotInitializedError(WinGuiError):
    """Raised when an active session is required but missing."""


class WindowResolutionError(WinGuiError):
    """Raised when a target window cannot be resolved."""


class FocusError(WinGuiError):
    """Raised when a window cannot be focused or restored."""


class ScreenshotError(WinGuiError):
    """Raised when screenshot capture fails."""


class CoordinateTranslationError(WinGuiError):
    """Raised when viewport coordinates cannot be translated safely."""


class UIAutomationError(WinGuiError):
    """Raised when a UIA lookup or action fails."""


class AssertionFailedError(WinGuiError):
    """Raised when an assertion helper fails."""


class AdapterError(WinGuiError):
    """Raised when an adapter cannot satisfy a semantic request."""
