# =============================================================================
#  pathwise_app.py  —  Pathwise Learning UI  (v2 — Professional Dark Theme)
#  Built with Python's built-in tkinter library (no extra installs needed).
#
#  HOW THIS FILE IS ORGANISED
#  ──────────────────────────
#  1. CONTENT   ← ✏️  EDIT HERE — all text, questions, hints, labels
#  2. STYLE     ← 🎨  EDIT HERE — colours, fonts, window size
#  3. HELPERS   ← 🔧  Reusable widget factory functions (rarely needs changing)
#  4. APP CLASS ← ⚙️  UI layout and logic (only touch if adding new features)
#  5. ENTRY     ← ▶️  Runs the app
#
#  To run:  python3 pathwise_app.py
# =============================================================================


# =============================================================================
# 1. CONTENT  ✏️
#    Everything your users read lives here.
#    You can change any string without touching the UI code below.
# =============================================================================

APP_TITLE  = "Pathwise — Strings"
PAGE_TITLE = "Strings"
PAGE_SUBTITLE = "Python Fundamentals  ·  Unit 1"  # Subtitle shown under the heading

LESSON_PANEL_LABEL = "📖  Lesson"
TUTOR_PANEL_LABEL  = "🤖  AI Tutor"
PROGRESS_TITLE     = "Progress"

# The first word(s) of the lesson that should appear bold
LESSON_BOLD_PREFIX = "Strings in Python"
LESSON_BODY = (
    "Strings in Python are sequences of characters enclosed in single or double "
    "quotes. They are immutable, meaning once created they cannot be changed in "
    "place — but you can always create new strings from them.\n\n"
    "── Slicing  ──────────────────────\n"
    "  s[start : end]   extract a portion\n"
    "  s[0:3]           first three chars\n"
    "  s[-3:]           last three chars\n"
    "  s[::2]           every other char\n\n"
    "── Common Methods  ───────────────\n"
    "  .upper()   .lower()   .strip()\n"
    "  .split()   .join()    .replace()\n"
    "  .find()    .count()   .startswith()\n\n"
    "── Examples  ─────────────────────\n"
    '  word = "cheese"\n'
    '  word[:3]       →  "che"\n'
    '  word.upper()   →  "CHEESE"\n'
    '  len(word)      →  6'
)

PROMPT_PLACEHOLDER = "Ask Pathwise for help…"

SUBMIT_BTN_LABEL = "Submit Answer"
NEXT_BTN_LABEL   = "Next  →"

FEEDBACK_CORRECT = "✓  Correct!  Nice work."
FEEDBACK_WRONG   = "✗  Not quite — check your syntax and try again."

COMPLETE_TITLE = "Unit Complete!"
COMPLETE_MSG   = "You've finished all questions in this unit. Well done! 🎉"

# ── Questions ─────────────────────────────────────────────────────────────────
# Keys: "unit", "text", "answer" (reference), "accepted" (list), "hint"
# To ADD: copy a block, paste before the closing ], fill in all five fields.
# To REMOVE: delete the entire {...} block including its trailing comma.

QUESTIONS = [
    {
        "unit"    : "Unit 1.0",
        "text"    : 'Slice the first three characters from the string "cheese"',
        "answer"  : '"cheese"[:3]',
        "accepted": ['cheese[:3]', '"cheese"[:3]', "'cheese'[:3]"],
        "hint"    : 'Try square-bracket slice notation → string[start:end]\nExample: "hello"[0:2] gives "he"',
    },
    {
        "unit"    : "Unit 1.1",
        "text"    : 'Convert the string "hello" to uppercase.',
        "answer"  : '"hello".upper()',
        "accepted": ['"hello".upper()', "'hello'.upper()", 'hello.upper()'],
        "hint"    : 'String objects have a built-in method that returns an uppercase copy.\nTry: your_string.upper()',
    },
    {
        "unit"    : "Unit 1.2",
        "text"    : 'Get the length of the string "python".',
        "answer"  : 'len("python")',
        "accepted": ['len("python")', "len('python')", 'len(python)'],
        "hint"    : 'Python has a built-in function that counts items in any sequence.\nTry: len(your_string)',
    },
]


# =============================================================================
# 2. STYLE  🎨
#    Dark professional theme — deep navy background, teal accent, amber highlights.
#    Colours are hex strings (#RRGGBB). Fonts are (family, size, optional weight).
# =============================================================================

# ── Colour palette ────────────────────────────────────────────────────────────
# Backgrounds
BG           = "#0F1117"   # App background — near-black navy
SIDEBAR_BG   = "#161B27"   # Slightly lighter for the right sidebar
PANEL_BG     = "#1E2435"   # Card / panel fill — dark slate
PANEL_BORDER = "#2E3650"   # Subtle border around cards
NAVBAR_BG    = "#151A28"   # Top navigation bar

# Accents
ACCENT_TEAL  = "#00C9A7"   # Electric teal — primary accent (buttons, highlights)
ACCENT_AMBER = "#FFB627"   # Warm amber — active question, selected state
ACCENT_BLUE  = "#4C8BF5"   # Cornflower blue — secondary accents, links

# Text
TEXT_PRIMARY  = "#E8ECF4"  # Main text — bright white-blue
TEXT_MUTED    = "#6B7A99"  # Secondary / placeholder text
TEXT_CODE     = "#A8D8B9"  # Code / monospace text — light green

# Feedback
SUCCESS_BG  = "#0D2B1E"    # Dark green background for correct feedback
SUCCESS_FG  = "#34D399"    # Bright green text
SUCCESS_BDR = "#1A5C3A"    # Green border
ERROR_BG    = "#2B0D0D"    # Dark red background for wrong feedback
ERROR_FG    = "#F87171"    # Bright red text
ERROR_BDR   = "#5C1A1A"    # Red border

# Buttons
BTN_PRIMARY_BG    = "#00C9A7"   # Teal fill (submit)
BTN_PRIMARY_FG    = "#0F1117"   # Dark text on teal
BTN_PRIMARY_HOVER = "#00A88A"   # Darker teal on hover
BTN_SECONDARY_BG  = "#2E3650"   # Dark fill (next, disabled state)
BTN_SECONDARY_FG  = "#E8ECF4"
BTN_SECONDARY_HOV = "#3E4A6A"
BTN_DISABLED_BG   = "#1E2435"
BTN_DISABLED_FG   = "#3A4460"

# Progress sidebar states
PROG_ACTIVE_BG  = "#1A2540"    # Active unit row background
PROG_ACTIVE_FG  = "#FFB627"    # Amber text for active unit
PROG_DONE_FG    = "#34D399"    # Green for completed units
PROG_PENDING_FG = "#4A5568"    # Grey for not-yet-attempted

# Code editor area
CODE_BG         = "#141824"    # Darker background for the answer box
CODE_CURSOR     = "#00C9A7"    # Teal cursor in the answer box
CODE_SELECT     = "#2A3F5F"    # Selection highlight

# ── Fonts  (family, size, optional weight) ────────────────────────────────────
FONT_TITLE    = ("Georgia",      22, "bold")   # Main page heading
FONT_SUBTITLE = ("Georgia",      10, "italic") # Subtitle below heading
FONT_HEAD     = ("Georgia",      11, "bold")   # Panel headings
FONT_BODY     = ("Courier New",  10)           # Lesson content (monospace)
FONT_UI       = ("Helvetica Neue", 10)         # General labels
FONT_BTN      = ("Helvetica Neue", 10, "bold") # Button labels
FONT_UNIT     = ("Helvetica Neue", 10)         # Progress sidebar units
FONT_CODE     = ("Courier New",  13)           # Answer box code entry
FONT_FEEDBACK = ("Helvetica Neue", 10, "bold") # Feedback messages
FONT_BADGE    = ("Helvetica Neue",  8, "bold") # Small badge labels

# ── Window ────────────────────────────────────────────────────────────────────
WINDOW_SIZE = "1280x760"
WINDOW_MIN  = (1024, 640)


# =============================================================================
# 3. HELPERS  🔧
# =============================================================================

import tkinter as tk
from tkinter import ttk, messagebox


def card(parent, **kw):
    """
    Returns a tk.Frame styled as a dark rounded card with a coloured border.
    Pass extra kwargs to override defaults, e.g. card(root, bg=SIDEBAR_BG).
    """
    kw.setdefault("bg", PANEL_BG)
    kw.setdefault("bd", 0)
    kw.setdefault("relief", "flat")
    kw.setdefault("highlightbackground", PANEL_BORDER)
    kw.setdefault("highlightthickness", 1)
    return tk.Frame(parent, **kw)


def primary_btn(parent, text, command, width=None):
    """
    Teal primary action button (used for Submit Answer).
    Darkens on hover.
    """
    b = tk.Button(
        parent, text=text, command=command,
        bg=BTN_PRIMARY_BG, fg=BTN_PRIMARY_FG, font=FONT_BTN,
        relief="flat", cursor="hand2", bd=0,
        activebackground=BTN_PRIMARY_HOVER, activeforeground=BTN_PRIMARY_FG,
        padx=18, pady=8,
    )
    if width:
        b.config(width=width)
    b.bind("<Enter>", lambda e: b.config(bg=BTN_PRIMARY_HOVER))
    b.bind("<Leave>", lambda e: b.config(bg=BTN_PRIMARY_BG))
    return b


def secondary_btn(parent, text, command, width=None):
    """
    Dark secondary button (used for Next →).
    Lightens on hover.
    """
    b = tk.Button(
        parent, text=text, command=command,
        bg=BTN_SECONDARY_BG, fg=BTN_SECONDARY_FG, font=FONT_BTN,
        relief="flat", cursor="hand2", bd=0,
        activebackground=BTN_SECONDARY_HOV, activeforeground=BTN_SECONDARY_FG,
        padx=18, pady=8,
    )
    if width:
        b.config(width=width)
    b.bind("<Enter>", lambda e: b.config(bg=BTN_SECONDARY_HOV))
    b.bind("<Leave>", lambda e: b.config(bg=BTN_SECONDARY_BG))
    return b


def section_label(parent, text):
    """Small uppercase teal section label (used above panels)."""
    return tk.Label(
        parent, text=text.upper(), font=FONT_BADGE,
        bg=BG, fg=ACCENT_TEAL, anchor="w",
        padx=2, pady=0,
    )


def ttk_dark_scrollbar(parent, orient, command):
    """
    Creates a ttk scrollbar styled for the dark theme.
    Note: Full ttk theming is limited on some platforms; this sets what it can.
    """
    style = ttk.Style()
    style.theme_use("default")
    style.configure(
        "Dark.Vertical.TScrollbar",
        background=PANEL_BORDER,
        troughcolor=PANEL_BG,
        arrowcolor=TEXT_MUTED,
        borderwidth=0,
    )
    style.configure(
        "Dark.Horizontal.TScrollbar",
        background=PANEL_BORDER,
        troughcolor=PANEL_BG,
        arrowcolor=TEXT_MUTED,
        borderwidth=0,
    )
    style_name = (
        "Dark.Vertical.TScrollbar"
        if orient == "vertical"
        else "Dark.Horizontal.TScrollbar"
    )
    return ttk.Scrollbar(parent, orient=orient, command=command, style=style_name)


# =============================================================================
# 4. APP CLASS  ⚙️
#    Three-column layout: Left (lesson + tutor) | Centre (Q&A) | Right (progress)
#    Only edit this section if you're adding or removing UI features.
# =============================================================================

class PathwiseApp(tk.Tk):
    """
    Main application window.

    State:
      q_index   (int) — index of the currently displayed question
      completed (set) — question indices the student has answered correctly
    """

    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.configure(bg=BG)
        self.geometry(WINDOW_SIZE)
        self.minsize(*WINDOW_MIN)
        self.resizable(True, True)

        self.q_index   = 0
        self.completed = set()

        self._build_navbar()
        self._build_columns()
        self._load_question()

    # ── Top navigation bar ────────────────────────────────────────────────────

    def _build_navbar(self):
        """
        Dark top bar containing the course title, subtitle, and a teal
        accent line at the bottom to give a branded header feel.
        """
        navbar = tk.Frame(self, bg=NAVBAR_BG, height=72)
        navbar.pack(fill="x", side="top")
        navbar.pack_propagate(False)  # Keep fixed height

        # Left side: logo dot + title
        left = tk.Frame(navbar, bg=NAVBAR_BG)
        left.pack(side="left", padx=24, pady=0, fill="y")

        # Coloured logo dot
        dot = tk.Label(left, text="●", font=("Helvetica Neue", 20),
                       bg=NAVBAR_BG, fg=ACCENT_TEAL)
        dot.pack(side="left", padx=(0, 10))

        title_col = tk.Frame(left, bg=NAVBAR_BG)
        title_col.pack(side="left", fill="y", pady=14)

        tk.Label(title_col, text=PAGE_TITLE, font=FONT_TITLE,
                 bg=NAVBAR_BG, fg=TEXT_PRIMARY).pack(anchor="w")
        tk.Label(title_col, text=PAGE_SUBTITLE, font=FONT_SUBTITLE,
                 bg=NAVBAR_BG, fg=TEXT_MUTED).pack(anchor="w")

        # Right side: lesson counter badge
        right = tk.Frame(navbar, bg=NAVBAR_BG)
        right.pack(side="right", padx=24, fill="y")

        badge_frame = tk.Frame(right, bg=PANEL_BG,
                               highlightbackground=PANEL_BORDER,
                               highlightthickness=1)
        badge_frame.pack(side="right", pady=20)

        total = len(QUESTIONS)
        tk.Label(badge_frame,
                 text=f"  {total} Questions  ",
                 font=FONT_BADGE, bg=PANEL_BG, fg=ACCENT_TEAL,
                 pady=4).pack()

        # Teal accent line under the entire navbar
        accent_line = tk.Frame(self, bg=ACCENT_TEAL, height=2)
        accent_line.pack(fill="x", side="top")

    # ── Three-column grid ─────────────────────────────────────────────────────

    def _build_columns(self):
        """
        Outer grid: left (3 parts) | centre (4 parts) | right (2 parts).
        Column weights control horizontal stretching on window resize.
        """
        root = tk.Frame(self, bg=BG)
        root.pack(fill="both", expand=True, padx=16, pady=14)
        root.columnconfigure(0, weight=3, minsize=270)
        root.columnconfigure(1, weight=4, minsize=360)
        root.columnconfigure(2, weight=2, minsize=190)
        root.rowconfigure(0, weight=1)

        self._build_left(root)
        self._build_center(root)
        self._build_right(root)

    # ── LEFT column ───────────────────────────────────────────────────────────

    def _build_left(self, root):
        """
        Two stacked cards:
          • Lesson text  — read-only, scrollable, monospace code style
          • AI Tutor     — chat output + prompt entry + send button
        """
        col = tk.Frame(root, bg=BG)
        col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        col.rowconfigure(0, weight=3)
        col.rowconfigure(1, weight=2)
        col.columnconfigure(0, weight=1)

        # ── Lesson panel ─────────────────────────────────────────────────────
        section_label(col, LESSON_PANEL_LABEL).grid(
            row=0, column=0, sticky="sw", pady=(0, 4))

        lesson_card = card(col)
        lesson_card.grid(row=0, column=0, sticky="nsew", pady=(18, 0))
        lesson_card.rowconfigure(0, weight=1)
        lesson_card.columnconfigure(0, weight=1)

        # Thin teal top border stripe on the card
        tk.Frame(lesson_card, bg=ACCENT_TEAL, height=3).grid(
            row=0, column=0, columnspan=2, sticky="ew")

        self.lesson_text = tk.Text(
            lesson_card, wrap="word", font=FONT_BODY,
            bg=PANEL_BG, fg=TEXT_CODE, bd=0, relief="flat",
            padx=14, pady=12, state="normal",
            insertbackground=ACCENT_TEAL,
            selectbackground=CODE_SELECT, selectforeground=TEXT_PRIMARY,
        )
        self.lesson_text.grid(row=1, column=0, sticky="nsew")

        sb1 = ttk_dark_scrollbar(lesson_card, "vertical", self.lesson_text.yview)
        sb1.grid(row=1, column=1, sticky="ns")
        self.lesson_text.config(yscrollcommand=sb1.set)

        # Bold prefix + rest of body
        self.lesson_text.tag_configure(
            "bold", font=("Courier New", 10, "bold"), foreground=TEXT_PRIMARY)
        self.lesson_text.tag_configure(
            "heading", foreground=ACCENT_TEAL, font=("Courier New", 9, "bold"))
        self.lesson_text.insert("end", LESSON_BOLD_PREFIX, "bold")
        self.lesson_text.insert("end", LESSON_BODY[len(LESSON_BOLD_PREFIX):])
        self.lesson_text.config(state="disabled")  # Read-only

        # ── AI Tutor panel ────────────────────────────────────────────────────
        section_label(col, TUTOR_PANEL_LABEL).grid(
            row=1, column=0, sticky="sw", pady=(12, 4))

        tutor_card = card(col)
        tutor_card.grid(row=1, column=0, sticky="nsew")
        tutor_card.rowconfigure(0, weight=1)
        tutor_card.rowconfigure(1, weight=0)
        tutor_card.columnconfigure(0, weight=1)

        # Amber top stripe on the tutor panel to visually distinguish it
        tk.Frame(tutor_card, bg=ACCENT_AMBER, height=3).grid(
            row=0, column=0, columnspan=3, sticky="ew")

        # Chat output area
        self.prompt_out = tk.Text(
            tutor_card, wrap="word", font=FONT_UI,
            bg=PANEL_BG, fg=TEXT_PRIMARY, bd=0, relief="flat",
            padx=12, pady=10, state="disabled",
            selectbackground=CODE_SELECT,
        )
        self.prompt_out.grid(row=1, column=0, columnspan=2, sticky="nsew")

        sb2 = ttk_dark_scrollbar(tutor_card, "vertical", self.prompt_out.yview)
        sb2.grid(row=1, column=2, sticky="ns")
        self.prompt_out.config(yscrollcommand=sb2.set)

        # Configure text tags for chat messages
        self.prompt_out.tag_configure("you",  foreground=ACCENT_AMBER,
                                      font=("Helvetica Neue", 10, "bold"))
        self.prompt_out.tag_configure("hint", foreground=ACCENT_TEAL,
                                      font=("Courier New", 10))

        # Input row
        input_row = tk.Frame(tutor_card, bg=PANEL_BG)
        input_row.grid(row=2, column=0, columnspan=3,
                       sticky="ew", padx=10, pady=10)
        input_row.columnconfigure(0, weight=1)

        # Entry with dark background and teal focus ring
        entry_frame = tk.Frame(input_row, bg=CODE_BG,
                               highlightbackground=PANEL_BORDER,
                               highlightthickness=1)
        entry_frame.grid(row=0, column=0, sticky="ew")
        entry_frame.columnconfigure(0, weight=1)

        self.prompt_entry = tk.Entry(
            entry_frame, font=FONT_UI, bg=CODE_BG, fg=TEXT_PRIMARY,
            relief="flat", bd=0, insertbackground=ACCENT_TEAL,
        )
        self.prompt_entry.grid(row=0, column=0, sticky="ew",
                               ipady=7, padx=10, pady=2)
        self.prompt_entry.insert(0, PROMPT_PLACEHOLDER)
        self.prompt_entry.config(fg=TEXT_MUTED)
        self.prompt_entry.bind("<FocusIn>",  self._clear_placeholder)
        self.prompt_entry.bind("<FocusOut>", self._restore_placeholder)
        self.prompt_entry.bind("<Return>",   lambda e: self._send_prompt())

        # Highlight entry frame border on focus
        self.prompt_entry.bind(
            "<FocusIn>",
            lambda e: (entry_frame.config(highlightbackground=ACCENT_TEAL),
                       self._clear_placeholder(e)), add="+")
        self.prompt_entry.bind(
            "<FocusOut>",
            lambda e: (entry_frame.config(highlightbackground=PANEL_BORDER),
                       self._restore_placeholder(e)), add="+")

        send_btn = tk.Button(
            input_row, text="▶", font=("Helvetica Neue", 12, "bold"),
            bg=ACCENT_TEAL, fg=BTN_PRIMARY_FG, relief="flat", cursor="hand2",
            activebackground=BTN_PRIMARY_HOVER, activeforeground=BTN_PRIMARY_FG,
            padx=12, pady=6, command=self._send_prompt,
        )
        send_btn.grid(row=0, column=1, padx=(8, 0))

    def _clear_placeholder(self, _):
        """Clears grey placeholder when the entry gains focus."""
        if self.prompt_entry.get() == PROMPT_PLACEHOLDER:
            self.prompt_entry.delete(0, "end")
            self.prompt_entry.config(fg=TEXT_PRIMARY)

    def _restore_placeholder(self, _):
        """Restores placeholder when the entry loses focus and is empty."""
        if not self.prompt_entry.get():
            self.prompt_entry.insert(0, PROMPT_PLACEHOLDER)
            self.prompt_entry.config(fg=TEXT_MUTED)

    def _send_prompt(self):
        """
        Handles a student message to the AI Tutor.
        Echoes their message in amber and replies with the pre-written hint in teal.
        To connect a real AI: replace the `response` assignment with an API call.
        """
        txt = self.prompt_entry.get().strip()
        if not txt or txt == PROMPT_PLACEHOLDER:
            return

        q = QUESTIONS[self.q_index]

        self.prompt_out.config(state="normal")
        self.prompt_out.insert("end", "You:  ", "you")
        self.prompt_out.insert("end", txt + "\n")
        self.prompt_out.insert("end", f"\n💡 {q['unit']} hint:\n", "hint")
        self.prompt_out.insert("end", q["hint"] + "\n\n")
        self.prompt_out.see("end")
        self.prompt_out.config(state="disabled")

        self.prompt_entry.delete(0, "end")

    # ── CENTRE column ─────────────────────────────────────────────────────────

    def _build_center(self, root):
        """
        Three stacked sections:
          • Question card  — heading + question body text
          • Answer card    — code editor + feedback strip
          • Button row     — Submit (teal) + Next (dark)
        """
        col = tk.Frame(root, bg=BG)
        col.grid(row=0, column=1, sticky="nsew", padx=10)
        col.rowconfigure(0, weight=2)
        col.rowconfigure(1, weight=3)
        col.rowconfigure(2, weight=0)
        col.columnconfigure(0, weight=1)

        # ── Question card ─────────────────────────────────────────────────────
        q_card = card(col)
        q_card.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        q_card.rowconfigure(2, weight=1)
        q_card.columnconfigure(0, weight=1)

        # Blue accent stripe at top of question card
        tk.Frame(q_card, bg=ACCENT_BLUE, height=3).grid(
            row=0, column=0, sticky="ew")

        # "Question N" heading
        self.q_label_unit = tk.Label(
            q_card, text="Question 1", font=FONT_HEAD,
            bg=PANEL_BG, fg=ACCENT_BLUE, pady=10,
        )
        self.q_label_unit.grid(row=1, column=0)

        # Question body text
        self.q_label_text = tk.Label(
            q_card, text="", font=("Helvetica Neue", 13),
            bg=PANEL_BG, fg=TEXT_PRIMARY,
            wraplength=420, justify="center", pady=10, padx=24,
        )
        self.q_label_text.grid(row=2, column=0, sticky="nsew")

        # ── Answer / code editor card ─────────────────────────────────────────
        ans_card = card(col, bg=CODE_BG,
                        highlightbackground=PANEL_BORDER,
                        highlightthickness=1)
        ans_card.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        ans_card.rowconfigure(1, weight=1)
        ans_card.columnconfigure(0, weight=1)

        # Editor header bar (mimics an IDE tab strip)
        editor_bar = tk.Frame(ans_card, bg="#0D1120", height=32)
        editor_bar.grid(row=0, column=0, sticky="ew")
        editor_bar.grid_propagate(False)

        # Traffic-light style dots
        for colour in ("#FF5F57", "#FEBC2E", "#28C840"):
            tk.Label(editor_bar, text="●", font=("Helvetica Neue", 10),
                     bg="#0D1120", fg=colour).pack(side="left", padx=(8, 0), pady=6)

        tk.Label(editor_bar, text="answer.py",
                 font=("Courier New", 9), bg="#0D1120",
                 fg=TEXT_MUTED).pack(side="left", padx=14)

        # Editable answer text area
        self.answer_text = tk.Text(
            ans_card, wrap="word", font=FONT_CODE,
            bg=CODE_BG, fg=TEXT_CODE, bd=0, relief="flat",
            padx=16, pady=14,
            insertbackground=CODE_CURSOR,
            selectbackground=CODE_SELECT, selectforeground=TEXT_PRIMARY,
        )
        self.answer_text.grid(row=1, column=0, sticky="nsew")

        # Line number gutter (decorative — shows "›" prompt symbol)
        gutter = tk.Text(
            ans_card, width=3, font=FONT_CODE,
            bg="#141824", fg="#2E3650", bd=0, relief="flat",
            padx=6, pady=14, state="disabled",
        )
        gutter.grid(row=1, column=1, sticky="ns")
        gutter.config(state="normal")
        for i in range(1, 20):
            gutter.insert("end", f"{i}\n")
        gutter.config(state="disabled")

        # Feedback strip at the bottom of the answer card
        self.feedback_frame = tk.Frame(ans_card, bg=CODE_BG, height=36)
        self.feedback_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.feedback_frame.grid_propagate(False)

        self.feedback_label = tk.Label(
            self.feedback_frame, text="", font=FONT_FEEDBACK,
            bg=CODE_BG, fg=TEXT_MUTED, anchor="w", padx=16,
        )
        self.feedback_label.pack(fill="both", expand=True)

        # ── Button row ────────────────────────────────────────────────────────
        btn_row = tk.Frame(col, bg=BG)
        btn_row.grid(row=2, column=0, pady=(0, 4))

        self.submit_btn = primary_btn(btn_row, SUBMIT_BTN_LABEL,
                                      self._submit, width=16)
        self.submit_btn.pack(side="left", padx=(0, 10))

        self.next_btn = secondary_btn(btn_row, NEXT_BTN_LABEL,
                                      self._next_question, width=10)
        self.next_btn.pack(side="left")
        self._disable_next()

    def _disable_next(self):
        """Greys out the Next button and removes hover effects."""
        self.next_btn.config(
            state="disabled", bg=BTN_DISABLED_BG,
            fg=BTN_DISABLED_FG, cursor="arrow",
        )
        self.next_btn.unbind("<Enter>")
        self.next_btn.unbind("<Leave>")

    def _enable_next(self):
        """Re-enables the Next button with full hover effects."""
        self.next_btn.config(
            state="normal", bg=BTN_SECONDARY_BG,
            fg=BTN_SECONDARY_FG, cursor="hand2",
        )
        self.next_btn.bind("<Enter>", lambda e: self.next_btn.config(bg=BTN_SECONDARY_HOV))
        self.next_btn.bind("<Leave>", lambda e: self.next_btn.config(bg=BTN_SECONDARY_BG))

    def _submit(self):
        """
        Checks the student's answer.
        Normalises by stripping spaces, lowercasing, and removing quotes.
        Shows a coloured feedback strip: green (correct) or red (wrong).
        """
        raw = self.answer_text.get("1.0", "end").strip()
        if not raw:
            return

        q          = QUESTIONS[self.q_index]
        normalised = raw.replace(" ", "").lower().strip('"\'')

        correct = any(
            raw.replace(" ", "") == a.replace(" ", "") or
            normalised == a.replace(" ", "").lower().strip('"\'')
            for a in q["accepted"]
        )

        if correct:
            # Green feedback strip
            self.feedback_frame.config(bg=SUCCESS_BG,
                                       highlightbackground=SUCCESS_BDR,
                                       highlightthickness=1)
            self.feedback_label.config(
                text=f"  {FEEDBACK_CORRECT}",
                fg=SUCCESS_FG, bg=SUCCESS_BG,
            )
            self.completed.add(self.q_index)
            self._update_progress()
            self._enable_next()
        else:
            # Red feedback strip
            self.feedback_frame.config(bg=ERROR_BG,
                                       highlightbackground=ERROR_BDR,
                                       highlightthickness=1)
            self.feedback_label.config(
                text=f"  {FEEDBACK_WRONG}",
                fg=ERROR_FG, bg=ERROR_BG,
            )

    def _next_question(self):
        """Advances to the next question, or shows the completion dialog."""
        if self.q_index < len(QUESTIONS) - 1:
            self.q_index += 1
            self._load_question()
        else:
            messagebox.showinfo(COMPLETE_TITLE, COMPLETE_MSG)

    def _load_question(self):
        """
        Resets the centre panel for self.q_index:
          • Updates heading and body text
          • Clears answer box and feedback strip
          • Disables Next button
          • Clears tutor chat
          • Refreshes the progress sidebar
        """
        q = QUESTIONS[self.q_index]
        self.q_label_unit.config(text=f"Question {self.q_index + 1}")
        self.q_label_text.config(text=q["text"])
        self.answer_text.delete("1.0", "end")

        # Reset feedback strip to neutral
        self.feedback_frame.config(bg=CODE_BG, highlightthickness=0)
        self.feedback_label.config(text="", bg=CODE_BG)

        self._disable_next()
        self._update_progress()

        # Clear tutor chat for the new question
        self.prompt_out.config(state="normal")
        self.prompt_out.delete("1.0", "end")
        self.prompt_out.config(state="disabled")

    # ── RIGHT column ──────────────────────────────────────────────────────────

    def _build_right(self, root):
        """
        Progress sidebar with one row per question.
        Each row shows a coloured state indicator dot + unit label.
        Clicking any row jumps to that question.

        Row colours:
          Active    → amber text, highlighted row background
          Completed → green text + ✓ indicator
          Pending   → muted grey text + ○ indicator
        """
        col = tk.Frame(root, bg=BG)
        col.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        col.rowconfigure(0, weight=1)
        col.columnconfigure(0, weight=1)

        prog_card = card(col, bg=SIDEBAR_BG)
        prog_card.grid(row=0, column=0, sticky="nsew")
        prog_card.columnconfigure(0, weight=1)

        # Amber accent stripe at the top of the sidebar
        tk.Frame(prog_card, bg=ACCENT_AMBER, height=3).pack(fill="x")

        # Header
        header = tk.Frame(prog_card, bg=SIDEBAR_BG)
        header.pack(fill="x", padx=16, pady=(14, 10))

        tk.Label(header, text=PROGRESS_TITLE, font=FONT_HEAD,
                 bg=SIDEBAR_BG, fg=TEXT_PRIMARY).pack(side="left")

        # Completed counter badge (e.g. "1 / 3")
        self.progress_badge = tk.Label(
            header, text=f"0 / {len(QUESTIONS)}",
            font=FONT_BADGE, bg=PANEL_BG,
            fg=ACCENT_TEAL, padx=8, pady=3,
        )
        self.progress_badge.pack(side="right")

        # Separator
        tk.Frame(prog_card, bg=PANEL_BORDER, height=1).pack(fill="x", padx=16)

        # One row per question
        self.unit_rows   = []   # outer frame for each row
        self.unit_dot    = []   # coloured indicator dot label
        self.unit_labels = []   # unit name label

        for i, q in enumerate(QUESTIONS):
            row_frame = tk.Frame(
                prog_card, bg=SIDEBAR_BG, cursor="hand2",
            )
            row_frame.pack(fill="x", padx=0, pady=0)

            # State indicator dot
            dot = tk.Label(row_frame, text="○", font=("Helvetica Neue", 14),
                           bg=SIDEBAR_BG, fg=PROG_PENDING_FG, padx=14, pady=12)
            dot.pack(side="left")

            # Unit name
            lbl = tk.Label(
                row_frame, text=q["unit"], font=FONT_UNIT,
                bg=SIDEBAR_BG, fg=PROG_PENDING_FG, pady=12, anchor="w",
            )
            lbl.pack(side="left", fill="x", expand=True)

            # Bind click on the whole row
            for widget in (row_frame, dot, lbl):
                widget.bind("<Button-1>", lambda e, idx=i: self._jump_to(idx))

            self.unit_rows.append(row_frame)
            self.unit_dot.append(dot)
            self.unit_labels.append(lbl)

        # Spacer at the bottom
        tk.Frame(prog_card, bg=SIDEBAR_BG).pack(fill="both", expand=True)

        self._update_progress()

    def _jump_to(self, idx):
        """Navigates directly to the question at index idx."""
        self.q_index = idx
        self._load_question()

    def _update_progress(self):
        """
        Refreshes every progress row to show current state:
          Active    → amber text, highlighted background row, ▶ dot
          Completed → green text, ✓ dot
          Pending   → muted text, ○ dot
        Also updates the "N / total" badge counter.
        """
        for i, (row, dot, lbl) in enumerate(
                zip(self.unit_rows, self.unit_dot, self.unit_labels)):
            if i == self.q_index:
                # Currently active
                row.config(bg=PROG_ACTIVE_BG)
                dot.config(text="▶", fg=ACCENT_AMBER, bg=PROG_ACTIVE_BG)
                lbl.config(fg=PROG_ACTIVE_FG, font=("Helvetica Neue", 10, "bold"),
                           bg=PROG_ACTIVE_BG)
            elif i in self.completed:
                # Completed correctly
                row.config(bg=SIDEBAR_BG)
                dot.config(text="✓", fg=PROG_DONE_FG, bg=SIDEBAR_BG)
                lbl.config(fg=PROG_DONE_FG, font=FONT_UNIT, bg=SIDEBAR_BG)
            else:
                # Not yet attempted
                row.config(bg=SIDEBAR_BG)
                dot.config(text="○", fg=PROG_PENDING_FG, bg=SIDEBAR_BG)
                lbl.config(fg=PROG_PENDING_FG, font=FONT_UNIT, bg=SIDEBAR_BG)

        # Update the completed counter badge
        self.progress_badge.config(text=f"{len(self.completed)} / {len(QUESTIONS)}")


# =============================================================================
# 5. ENTRY  ▶️
# =============================================================================

if __name__ == "__main__":
    app = PathwiseApp()
    app.mainloop()