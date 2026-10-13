"""Shared, UI-toolkit-neutral constants used by the GTK and Qt front-ends."""
from __future__ import annotations

# view key -> (title, subtitle, empty-state (icon, headline, hint))
VIEW_META = {
    "today": ("Today", "Due today or overdue",
              ("🌤️", "You're all caught up",
               "Nothing is due today — enjoy the calm.")),
    "upcoming": ("Upcoming", "The next seven days",
                 ("📅", "Nothing on the horizon",
                  "New due dates show up here.")),
    "all": ("All Tasks", "Every open task",
            ("📝", "No tasks yet", "Add one with the box above ⬆")),
    "starred": ("Starred", "Tasks you pinned",
                ("⭐", "No stars yet", "Tap ☆ on a task to pin it here.")),
    "inbox": ("Inbox", "Tasks that aren't in a list",
              ("📥", "Inbox zero", "Tasks without a list land here.")),
    "completed": ("Completed", "Finished tasks",
                  ("🎉", "Nothing completed yet",
                   "Completed tasks show up here.")),
}


def count_note(n: int) -> str:
    return f"{n} task" + ("s" if n != 1 else "")
