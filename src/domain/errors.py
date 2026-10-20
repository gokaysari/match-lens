"""Explicit domain error codes (never silent drops)."""

from __future__ import annotations


class DomainError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")
