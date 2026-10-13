# MintDo ✅

A sophisticated, **offline** to-do list app built natively for **Linux Mint**
(GTK 3 + SQLite — no Electron, no dependencies to install, no account needed).

Made with love for my sister. 🌱

![light] A clean, card-based task list with smart views on the left, quick-add
on top and a full detail editor on the right.

## Features

| Area | What you get |
|---|---|
| **Smart views** | Today (incl. overdue), Upcoming (7 days), All, Starred, Inbox, Completed — each with live counts |
| **Lists** | Colour-coded lists, right-click to rename/recolor/delete (tasks fall back to Inbox) |
| **Quick-add magic** | `!1 buy flowers #gift tomorrow every week` → priority, tag, due date and repeat parsed in one line |
| **Priorities** | P1–P4 with colour chips |
| **Tags** | `#tag` chips on rows, add/remove in the detail panel, searchable |
| **Due dates** | Calendar picker + Today / Tomorrow / Next week shortcuts, overdue shown in red |
| **Recurring tasks** | Daily, weekdays, weekly, monthly — completing spawns the next occurrence automatically |
| **Subtasks** | Step-by-step checklists with `☑ 2/5` progress chips on the parent row |
| **Notes** | Free-form notes per task |
| **Search** | Live search across titles, notes and tags (Ctrl+F) |
| **Sorting** | Recommended, due date, priority, name, newest, manual |
| **Undo** | Toast with **Undo** for every completion, reopen and deletion (Ctrl+Z) |
| **Stats** | Weekly bar chart, done today / this week, and a day **streak** 🔥 |
| **Themes** | Light, dark, or follow your Mint theme (Ctrl+D toggles) |
| **Notifications** | Desktop reminder for due-today/overdue tasks (libnotify) |
| **Backups** | Export/import everything as JSON |
| **Persistence** | Window size, theme and sidebar state remembered |

## Install (Linux Mint)

```bash
./install.sh
```

That's it — no `sudo`, no packages. It adds **MintDo** to your menu
(Accessories) and installs the icon.

Run it without installing:

```bash
python3 -m mintdo
```

Uninstall the launcher (keeps your data):

```bash
./install.sh --uninstall
```

## Windows

MintDo also ships as a **native Windows app** built with Qt (PySide6) — same
features, same SQLite data file, a Windows look-and-feel.

**Easiest — run from source** (needs Python 3.10+):

```
run_windows.bat
```

Double-click it. On first run it installs PySide6 automatically, then starts
MintDo. Or manually:

```bat
pip install -r requirements.txt
py -m mintdo.qt_app
```

**Best — a single .exe with no Python needed.** On a Windows machine:

```bat
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --clean mintdo.spec
```

This produces `dist\MintDo\MintDo.exe` — copy that whole `MintDo` folder
anywhere and run it (add the icon as a Start-menu shortcut if you like).
Data is stored per-user in `%LOCALAPPDATA%\MintDo\mintdo.db`, so any copy of
the app shares the same list.

> The Linux and Windows builds are two front-ends over the *same* code in
> `mintdo/db.py` and `mintdo/quickadd.py`, so a backup exported on one opens
> perfectly on the other.

## Keyboard shortcuts

| Keys | Action |
|---|---|
| `Ctrl+N` | Jump to quick-add |
| `Ctrl+Shift+N` | New list |
| `Ctrl+F` | Search |
| `Ctrl+Z` | Undo last completion/deletion |
| `Ctrl+D` | Toggle dark mode |
| `Ctrl+I` | Stats popover |
| `F1` | Shortcuts window |
| `F2` | Edit the selected task's title |
| `Space` | Tick the selected task on/off |
| `Delete` | Delete the selected task (undoable) |
| `Esc` | Close search |

## Quick-add syntax

Type it all in one line and press Enter:

```
!1 call mum #family friday every week
```

- `!1 … !4` — priority
- `#tag` — one or more tags
- `today`, `tomorrow`, `monday…sunday`, `2026-12-15`, `12/25`
- `every day`, `every weekday`, `every week`, `every month`

## Your data

Everything lives in **one local file**:

```
~/.local/share/mintdo/mintdo.db      (SQLite, WAL mode)
```

Back it up any time with **☰ → Export backup…** (plain JSON).

## Development

```bash
python3 -m unittest discover -s tests   # data layer + Qt UI tests
python3 -m mintdo    --smoke-test       # GTK  build: boots, checks, exits 0
python3 -m mintdo.qt_app --smoke-test   # Qt   build: boots, checks, exits 0
```

The Qt UI tests drive the real widgets head-lessly (`QT_QPA_PLATFORM=offscreen`)
and are skipped automatically if PySide6 isn't installed.

Layout:

```
mintdo/
├── app.py          # GTK  front-end (Linux Mint)
├── qt_app.py       # entry point for the Qt front-end (Windows/Linux)
├── db.py           # SQLite layer: tasks, lists, tags, stats, backup
├── quickadd.py     # one-line parser (!1 #tag tomorrow every week)
├── paths.py        # per-OS data location (XDG / %LOCALAPPDATA%)
├── theme.py        # GTK CSS provider handling (light/dark/system)
├── assets/         # light.css, dark.css, icon.svg, icon.ico
├── ui/             # GTK widgets
│   ├── sidebar.py
│   ├── taskview.py
│   ├── taskrow.py
│   ├── detail.py
│   ├── stats.py
│   ├── dialogs.py
│   └── toast.py
└── qt/             # Qt/PySide6 widgets (mirror of ui/)
    ├── theme.py    # stylesheet generator (light/dark)
    ├── mainwindow.py
    ├── sidebar.py
    ├── taskview.py
    ├── taskrow.py
    ├── detail.py
    ├── stats.py
    ├── dialogs.py
    └── toast.py
```

## Requirements

- **Linux Mint 20+** — stock Python 3 + GTK 3 (PyGObject), all preinstalled.
  `libnotify` is optional (used for reminders).
- **Windows** — Python 3.10+ and `pip install -r requirements.txt` (PySide6),
  or a self-contained `MintDo.exe` built with `mintdo.spec` (no Python needed).
