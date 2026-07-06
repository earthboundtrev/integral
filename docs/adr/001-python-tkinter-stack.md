# ADR-001: Python + Tkinter Stack

**Status:** Accepted  
**Date:** 2026-06-27  
**Deciders:** Product owner

## Context

Need a lightweight local desktop app. Question raised whether C++ is required for performance.

## Decision

Use **Python 3** with **Tkinter/ttk** for all UI. Do not rewrite in C++, Rust, or Electron unless an ADR supersedes this.

## Consequences

- Fast development; agents can implement from specs reliably
- Startup optimization via lazy imports, not language change
- Single `pip install matplotlib` as only non-stdlib dependency for charts

## Agent Rules

- MUST NOT introduce Qt, Electron, Kivy, or web-based UI frameworks
- MUST NOT propose C++ rewrite for performance without measured evidence and new ADR
