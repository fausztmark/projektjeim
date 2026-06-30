from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import random
import tkinter as tk
from tkinter import messagebox, ttk


APP_TITLE = "Social Game Suite"
APP_FONT = "Segoe UI"
BG_MAIN = "#f4efe8"
BG_DARK = "#1e1a17"
BG_CARD = "#ffffff"
BG_SUBCARD = "#fbf8f4"
BG_ACCENT = "#d78b43"
FG_MAIN = "#1f1b18"
FG_MUTED = "#5b5047"
FG_LIGHT = "#fff8f1"

STYLE_ROOT = "Root.TFrame"
STYLE_HEADER = "Header.TFrame"
STYLE_CARD = "Card.TFrame"
STYLE_SUBCARD = "SubCard.TFrame"
STYLE_ACCENT = "Accent.TFrame"
STYLE_TITLE = "Title.TLabel"
STYLE_SUBTITLE = "Subtitle.TLabel"
STYLE_SECTION = "Section.TLabel"
STYLE_INFO = "Info.TLabel"
STYLE_ACCENT_BUTTON = "Accent.TButton"
STYLE_SOFT_BUTTON = "Soft.TButton"

SELECTION_NONE_HU = "Kiválasztott lap: nincs"
SELECTION_NONE_EN = "Selected card: none"
COMBO_SELECTED_EVENT = "<<ComboboxSelected>>"


class Language(str, Enum):
    HU = "hu"
    EN = "en"


class GameType(str, Enum):
    BUS = "bus"
    HORSE_RACE = "horse_race"


@dataclass
class Player:
    name: str
    drink: str
    drinks_taken: int = 0


@dataclass
class GameConfig:
    language: Language
    game_type: GameType
    players: list[Player] = field(default_factory=list)


class SocialGame(ABC):
    def __init__(self, config: GameConfig) -> None:
        self.config = config
        self.turn_index = 0
        self.round_number = 0
        self.last_result = ""

    @property
    def current_player(self) -> Player:
        return self.config.players[self.turn_index]

    def _advance_turn(self) -> None:
        if self.config.players:
            self.turn_index = (self.turn_index + 1) % len(self.config.players)

    @abstractmethod
    def setup(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def play_round(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def is_finished(self) -> bool:
        raise NotImplementedError

    def run(self) -> None:
        raise NotImplementedError("Use the GUI to control rounds.")


class BusGame(SocialGame):
    def setup(self) -> None:
        self.turn_index = 0
        self.round_number = 0
        self.last_result = ""
        self.current_guess: str | None = None
        self._prepare_round()

    def _build_deck(self) -> list[tuple[str, str]]:
        suits = ["hearts", "diamonds", "clubs", "spades"]
        ranks = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
        return [(rank, suit) for suit in suits for rank in ranks]

    def _card_color(self, suit: str) -> str:
        return "red" if suit in {"hearts", "diamonds"} else "black"

    def _prepare_round(self) -> None:
        self._deck = self._build_deck()
        random.shuffle(self._deck)
        self.current_guess = None

    def choose_guess(self, guess: str) -> None:
        self.current_guess = guess

    def draw_next_card(self) -> tuple[str, str]:
        if not self._deck:
            self._prepare_round()
        return self._deck.pop()

    def complete_round(self, guess: str, card: tuple[str, str]) -> str:
        player = self.current_player
        rank, suit = card
        actual = self._card_color(suit)
        correct = guess == actual
        if not correct:
            player.drinks_taken += 1

        self.round_number += 1
        self.last_result = (
            f"Bus round {self.round_number}: {player.name} guessed {guess}, drew {rank} of {suit}. "
            f"Result: {'safe' if correct else player.name + ' drinks 1'}"
        )
        self._advance_turn()
        self._prepare_round()
        return self.last_result

    def play_round(self) -> str:
        if not self.config.players:
            self.last_result = "No players configured."
            return self.last_result

        guess = self.current_guess or random.choice(["red", "black"])
        card = self.draw_next_card()
        return self.complete_round(guess, card)

    def is_finished(self) -> bool:
        return False


class HorseRaceGame(SocialGame):
    def setup(self) -> None:
        self.turn_index = 0
        self.round_number = 0
        self.last_result = ""
        self.track_length = 10
        self.horses = ["red", "black", "green", "yellow"]
        self._prepare_round()

    def _prepare_round(self) -> None:
        self._deck = self._build_deck()
        random.shuffle(self._deck)
        self.progress = dict.fromkeys(self.horses, 0)
        self.winner: str | None = None
        self.current_bet: str | None = None

    def _build_deck(self) -> list[tuple[str, str]]:
        suits = ["hearts", "diamonds", "clubs", "spades"]
        ranks = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
        return [(rank, suit) for suit in suits for rank in ranks]

    def choose_bet(self, suit: str) -> None:
        self.current_bet = suit

    def draw_next_card(self) -> tuple[str, str]:
        if not self._deck:
            self._prepare_round()
        return self._deck.pop()

    def advance_horse(self, suit: str) -> None:
        self.progress[suit] += 1
        if self.progress[suit] >= self.track_length:
            self.winner = suit

    def race_step(self) -> tuple[str, str, str | None]:
        card = self.draw_next_card()
        rank, suit = card
        self.advance_horse(suit)
        return rank, suit, self.winner

    def play_round(self) -> str:
        if not self.config.players:
            self.last_result = "No players configured."
            return self.last_result

        self.current_bet = self.current_bet or random.choice(self.horses)
        while self.winner is None:
            self.race_step()

        player = self.current_player
        if self.current_bet != self.winner:
            player.drinks_taken += 1

        self.round_number += 1
        self.last_result = (
            f"Horse race round {self.round_number}: {player.name} bet on {self.current_bet}, winner was {self.winner}. "
            f"Result: {'deal/pass' if self.current_bet == self.winner else player.name + ' drinks 1'}"
        )
        self._advance_turn()
        self._prepare_round()
        return self.last_result

    def is_finished(self) -> bool:
        return False


def choose_language() -> Language:
    return Language.HU


def choose_game() -> GameType:
    return GameType.BUS


def get_player_count() -> int:
    return 0


def collect_players(count: int) -> list[Player]:
    return [Player(name=f"Player {index + 1}", drink="Water") for index in range(count)]


def build_game(config: GameConfig) -> SocialGame:
    if config.game_type == GameType.BUS:
        return BusGame(config)
    return HorseRaceGame(config)


class GameWindowBase:
    def __init__(self, app: "SocialDrinkingApp", config: GameConfig, window_title: str) -> None:
        self.app = app
        self.config = config
        self.language = config.language
        self.window = tk.Toplevel(app.root)
        self.window.title(f"{APP_TITLE} - {window_title}")
        self.window.geometry("1240x820")
        self.window.minsize(1120, 720)
        self.window.configure(bg=BG_MAIN)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.transient(app.root)
        self.window.lift()
        self.window.focus_force()

        self.player_var = tk.StringVar()
        self.result_var = tk.StringVar()
        self.message_var = tk.StringVar()

        self.main = ttk.Frame(self.window, style=STYLE_ROOT, padding=24)
        self.main.pack(fill="both", expand=True)
        self.main.columnconfigure(0, weight=3)
        self.main.columnconfigure(1, weight=2)

        self.header = ttk.Frame(self.main, style=STYLE_CARD, padding=12)
        self.header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        self.header.columnconfigure(0, weight=1)

        self.title_label = ttk.Label(self.header, style=STYLE_SECTION)
        self.title_label.grid(row=0, column=0, sticky="w")
        self.player_label = ttk.Label(self.header, textvariable=self.player_var, style=STYLE_INFO)
        self.player_label.grid(row=1, column=0, sticky="w", pady=(8, 0))

        self.close_button = ttk.Button(self.header, text="×", style=STYLE_SOFT_BUTTON, command=self.close, width=3)
        self.close_button.grid(row=0, column=1, rowspan=2, sticky="e")

        self.body_left = ttk.Frame(self.main, style=STYLE_ROOT)
        self.body_left.grid(row=1, column=0, sticky="nsew", padx=(0, 14))
        self.body_left.columnconfigure(0, weight=1)
        self.body_left.rowconfigure(1, weight=1)

        self.body_right = ttk.Frame(self.main, style=STYLE_ROOT)
        self.body_right.grid(row=1, column=1, sticky="nsew")
        self.body_right.columnconfigure(0, weight=1)

        self.result_card = ttk.Frame(self.body_right, style=STYLE_CARD, padding=20)
        self.result_card.grid(row=0, column=0, sticky="ew")
        self.result_card.columnconfigure(0, weight=1)
        self.result_label = ttk.Label(self.result_card, textvariable=self.result_var, style=STYLE_INFO, wraplength=360, justify="left")
        self.result_label.grid(row=0, column=0, sticky="w")

        self.message_card = ttk.Frame(self.body_right, style=STYLE_CARD, padding=20)
        self.message_card.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        self.message_card.columnconfigure(0, weight=1)
        self.message_card.rowconfigure(2, weight=1)
        self.message_title = ttk.Label(self.message_card, style=STYLE_SECTION)
        self.message_title.grid(row=0, column=0, sticky="w")
        self.message_label = ttk.Label(self.message_card, textvariable=self.message_var, style=STYLE_INFO, wraplength=360, justify="left")
        self.message_label.grid(row=1, column=0, sticky="w", pady=(12, 0))

    def t(self, key: str) -> str:
        return TEXTS[self.language][key]

    def _language_title(self, hu: str, en: str) -> str:
        return hu if self.language == Language.HU else en

    def refresh_turn(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        if self.app.game_window is self:
            self.app.game_window = None
        self.window.destroy()


class BusGameWindow(GameWindowBase):
    def __init__(self, app: "SocialDrinkingApp", config: GameConfig) -> None:
        window_title = "Busz" if config.language == Language.HU else "Bus"
        super().__init__(app, config, window_title)
        self.game = BusGame(config)
        self.game.setup()
        self.selected_guess: str | None = None
        self._build_ui()
        self.refresh_turn()

    def _build_ui(self) -> None:
        self.body_left.columnconfigure(0, weight=1)

        self.deck_card = ttk.Frame(self.body_left, style=STYLE_CARD, padding=20)
        self.deck_card.grid(row=0, column=0, sticky="ew")
        self.deck_card.columnconfigure((0, 1), weight=1)

        self.card_display = tk.Label(self.deck_card, text="", bg=BG_SUBCARD, fg=FG_MAIN, font=(APP_FONT, 26, "bold"), width=8, height=3, relief="flat")
        self.card_display.grid(row=0, column=0, rowspan=2, sticky="w")

        self.deck_info = ttk.Label(self.deck_card, text="", style=STYLE_INFO)
        self.deck_info.grid(row=0, column=1, sticky="w", padx=(16, 0))
        self.turn_info = ttk.Label(self.deck_card, text="", style=STYLE_SECTION)
        self.turn_info.grid(row=1, column=1, sticky="w", padx=(16, 0), pady=(8, 0))

        self.choice_card = ttk.Frame(self.body_left, style=STYLE_CARD, padding=20)
        self.choice_card.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        self.choice_card.columnconfigure((0, 1), weight=1)

        self.choice_title = ttk.Label(self.choice_card, text=self._language_title("Fogadj színre", "Pick a color"), style=STYLE_SECTION)
        self.choice_title.grid(row=0, column=0, columnspan=2, sticky="w")

        self.red_button = ttk.Button(self.choice_card, text="Red", command=lambda: self._choose_guess("red"))
        self.red_button.grid(row=1, column=0, sticky="ew", pady=(14, 0), padx=(0, 8))

        self.black_button = ttk.Button(self.choice_card, text="Black", command=lambda: self._choose_guess("black"))
        self.black_button.grid(row=1, column=1, sticky="ew", pady=(14, 0), padx=(8, 0))

        self.action_card = ttk.Frame(self.body_left, style=STYLE_CARD, padding=20)
        self.action_card.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        self.action_card.columnconfigure(0, weight=1)

        self.draw_button = ttk.Button(self.action_card, style=STYLE_ACCENT_BUTTON, command=self._play_round)
        self.draw_button.grid(row=0, column=0, sticky="ew")

        self.reset_button = ttk.Button(self.action_card, text=self._language_title("Következő játékos", "Next player"), style=STYLE_SOFT_BUTTON, command=self.refresh_turn)
        self.reset_button.grid(row=1, column=0, sticky="ew", pady=(10, 0))

    def refresh_turn(self) -> None:
        player = self.game.current_player
        self.player_var.set(f"{self._language_title('Jelenlegi játékos', 'Current player')}: {player.name}")
        self.turn_info.configure(text=f"{player.name} · {player.drink}")
        self.deck_info.configure(text=self._language_title("Válassz színt, majd húzz egy lapot.", "Pick a color, then draw a card."))
        self.draw_button.configure(text=self._language_title("Lap húzása", "Draw card"))

    def _choose_guess(self, guess: str) -> None:
        self.selected_guess = guess
        self.message_var.set(self._language_title("Fogadás kiválasztva", "Bet selected") + f": {guess.title()}")

    def _play_round(self) -> None:
        if self.selected_guess is None:
            messagebox.showwarning(self._language_title("Figyelem", "Warning"), self._language_title("Válassz egy színt.", "Choose a color first."))
            return

        card = self.game.draw_next_card()
        result = self.game.complete_round(self.selected_guess, card)
        self.card_display.configure(text=f"{card[0]}\n{card[1].title()}")
        self.result_var.set(result)
        self.message_var.set(result)
        self.selected_guess = None
        self.refresh_turn()

    def refresh_turn(self) -> None:
        if not self.game.config.players:
            return
        player = self.game.current_player
        self.player_var.set(f"{self._language_title('Jelenlegi játékos', 'Current player')}: {player.name}")
        self.turn_info.configure(text=f"{player.name} · {player.drink}")
        self.deck_info.configure(text=self._language_title("Kattints egy színre, majd húzz lapot.", "Pick a color, then draw a card."))
        self.draw_button.configure(text=self._language_title("Lap húzása", "Draw card"))


class HorseRaceGameWindow(GameWindowBase):
    def __init__(self, app: "SocialDrinkingApp", config: GameConfig) -> None:
        window_title = "Lóverseny" if config.language == Language.HU else "Horse Race"
        super().__init__(app, config, window_title)
        self.game = HorseRaceGame(config)
        self.game.setup()
        self.phase = "betting"
        self.selected_bet: str | None = None
        self.betting_player: Player | None = None
        self.bet_amount_var = tk.IntVar(value=1)
        self.bets_by_index: dict[int, tuple[str, int]] = {}
        self.winner_pools: dict[int, int] = {}
        self.settlement_messages: list[str] = []
        self.settlement_winner_var = tk.StringVar()
        self.settlement_loser_var = tk.StringVar()
        self.settlement_amount_var = tk.IntVar(value=1)
        self.settlement_summary_var = tk.StringVar(value="")
        self.board_width = 860
        self.board_height = 460
        self.token_items: dict[str, tuple[int, int]] = {}
        self._build_ui()
        self._draw_board()
        self.refresh_turn()

    def _build_ui(self) -> None:
        self.body_left.columnconfigure(0, weight=1)
        self.body_left.rowconfigure(1, weight=1)

        self.bet_card = ttk.Frame(self.body_left, style=STYLE_CARD, padding=20)
        self.bet_card.grid(row=0, column=0, sticky="ew")
        self.bet_card.columnconfigure(0, weight=1)

        self.bet_title = ttk.Label(self.bet_card, text=self._language_title("Válassz A lapot", "Choose your A card"), style=STYLE_SECTION)
        self.bet_title.grid(row=0, column=0, sticky="w")

        self.bet_hint = ttk.Label(self.bet_card, text=self._language_title("Válassz egy francia kártyalapot, majd véglegesíts.", "Pick a French card, then finalize."), style=STYLE_INFO)
        self.bet_hint.grid(row=1, column=0, sticky="w", pady=(8, 0))

        self.amount_row = ttk.Frame(self.bet_card, style=STYLE_CARD)
        self.amount_row.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        self.amount_row.columnconfigure(1, weight=1)

        self.amount_label = ttk.Label(self.amount_row, text=self._language_title("Korty", "Sips"), style=STYLE_INFO)
        self.amount_label.grid(row=0, column=0, sticky="w")
        self.amount_spin = ttk.Spinbox(self.amount_row, from_=1, to=20, textvariable=self.bet_amount_var, width=8, justify="center")
        self.amount_spin.grid(row=0, column=1, sticky="w", padx=(12, 0))
        self.bet_amount_var.trace_add("write", lambda *_: self._update_confirm_state())

        self.bet_row = ttk.Frame(self.bet_card, style=STYLE_CARD)
        self.bet_row.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        self.bet_row.columnconfigure((0, 1, 2, 3), weight=1)

        self.bet_buttons: dict[str, tk.Button] = {}
        bet_specs = [
            ("hearts", "A\n♥", "#b83a48", "#ffffff"),
            ("diamonds", "A\n♦", "#b83a48", "#ffffff"),
            ("clubs", "A\n♣", "#000000", "#ffffff"),
            ("spades", "A\n♠", "#000000", "#ffffff"),
        ]
        for column, (suit, label, bg_color, fg_color) in enumerate(bet_specs):
            button = tk.Button(
                self.bet_row,
                text=label,
                bg=bg_color,
                fg=fg_color,
                activebackground=bg_color,
                activeforeground=fg_color,
                relief="flat",
                font=(APP_FONT, 14, "bold"),
                padx=12,
                pady=12,
                command=lambda selected=suit: self._choose_bet(selected),
            )
            button.grid(row=0, column=column, sticky="ew", padx=6)
            self.bet_buttons[suit] = button

        self.confirm_button = ttk.Button(self.bet_card, text=self.t("finalize_continue"), style=STYLE_ACCENT_BUTTON, command=self._finalize_bet_and_continue, state="disabled")
        self.confirm_button.grid(row=4, column=0, sticky="ew", pady=(16, 0))

        self.selection_label = ttk.Label(self.bet_card, text=self._language_title(SELECTION_NONE_HU, SELECTION_NONE_EN), style=STYLE_INFO)
        self.selection_label.grid(row=5, column=0, sticky="w", pady=(10, 0))

        self.board_card = ttk.Frame(self.body_left, style=STYLE_CARD, padding=18)
        self.board_card.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        self.board_card.columnconfigure(0, weight=1)
        self.board_card.rowconfigure(0, weight=1)

        self.board = tk.Canvas(self.board_card, width=self.board_width, height=self.board_height, bg="#fbfaf7", highlightthickness=0)
        self.board.grid(row=0, column=0, sticky="nsew")

        self.action_card = ttk.Frame(self.body_left, style=STYLE_CARD, padding=20)
        self.action_card.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        self.action_card.columnconfigure(0, weight=1)

        self.draw_button = ttk.Button(self.action_card, style=STYLE_ACCENT_BUTTON, command=self._start_race, state="disabled")
        self.draw_button.grid(row=0, column=0, sticky="ew")

        self.round_info = ttk.Label(self.action_card, text="", style=STYLE_INFO)
        self.round_info.grid(row=1, column=0, sticky="w", pady=(10, 0))

        self.card_display = tk.Label(self.body_right, text="", bg=BG_SUBCARD, fg=FG_MAIN, font=(APP_FONT, 34, "bold"), width=8, height=3, relief="flat")
        self.card_display.grid(row=0, column=0, sticky="ew")

        self.turn_detail = ttk.Label(self.body_right, text="", style=STYLE_INFO, wraplength=360, justify="left")
        self.turn_detail.grid(row=1, column=0, sticky="nw", pady=(14, 0))

        self.board_status = ttk.Label(self.body_right, text="", style=STYLE_SECTION, wraplength=360, justify="left")
        self.board_status.grid(row=2, column=0, sticky="nw", pady=(14, 0))

        self.settlement_card = ttk.Frame(self.body_right, style=STYLE_CARD, padding=20)
        self.settlement_card.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        self.settlement_card.columnconfigure(1, weight=1)
        self.settlement_card.grid_remove()

        self.settlement_title = ttk.Label(self.settlement_card, text=self._language_title("Szétosztás", "Settlement"), style=STYLE_SECTION)
        self.settlement_title.grid(row=0, column=0, columnspan=2, sticky="w")

        self.winner_combo_label = ttk.Label(self.settlement_card, text=self._language_title("Nyertes", "Winner"), style=STYLE_INFO)
        self.winner_combo_label.grid(row=1, column=0, sticky="w", pady=(12, 0))
        self.winner_combo = ttk.Combobox(self.settlement_card, state="readonly", textvariable=self.settlement_winner_var)
        self.winner_combo.grid(row=1, column=1, sticky="ew", pady=(12, 0))
        self.winner_combo.bind(COMBO_SELECTED_EVENT, lambda _event: self._sync_settlement_amount())

        self.loser_combo_label = ttk.Label(self.settlement_card, text=self._language_title("Büntetett", "Loser"), style=STYLE_INFO)
        self.loser_combo_label.grid(row=2, column=0, sticky="w", pady=(12, 0))
        self.loser_combo = ttk.Combobox(self.settlement_card, state="readonly", textvariable=self.settlement_loser_var)
        self.loser_combo.grid(row=2, column=1, sticky="ew", pady=(12, 0))

        self.settlement_amount_label = ttk.Label(self.settlement_card, text=self._language_title("Korty", "Sips"), style=STYLE_INFO)
        self.settlement_amount_label.grid(row=3, column=0, sticky="w", pady=(12, 0))
        self.settlement_amount_spin = ttk.Spinbox(self.settlement_card, from_=1, to=20, textvariable=self.settlement_amount_var, width=8, justify="center")
        self.settlement_amount_spin.grid(row=3, column=1, sticky="w", pady=(12, 0))

        self.allocate_button = ttk.Button(self.settlement_card, text=self._language_title("Hozzáadás", "Allocate"), style=STYLE_ACCENT_BUTTON, command=self._apply_settlement_allocation)
        self.allocate_button.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(14, 0))

        self.settlement_summary_label = ttk.Label(self.settlement_card, textvariable=self.settlement_summary_var, style=STYLE_INFO, wraplength=360, justify="left")
        self.settlement_summary_label.grid(row=5, column=0, columnspan=2, sticky="w", pady=(12, 0))

        self.finish_round_button = ttk.Button(self.settlement_card, text=self._language_title("Új kör", "New round"), style=STYLE_SOFT_BUTTON, command=self._start_new_round)
        self.finish_round_button.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(14, 0))

    def _choose_bet(self, suit: str) -> None:
        self.selected_bet = suit
        self.betting_player = self.game.current_player
        for selected_suit, button in self.bet_buttons.items():
            button.configure(relief="raised" if selected_suit != suit else "sunken")
        self.selection_label.configure(text=self._language_title("Kiválasztott lap", "Selected card") + f": A {self._suit_symbol(suit)} · {self.bet_amount_var.get()} {self._language_title('korty', 'sips')}")
        self.message_var.set(self._language_title("Fogadás kiválasztva", "Bet selected") + f": A {self._suit_symbol(suit)} · {self.bet_amount_var.get()} {self._language_title('korty', 'sips')}")
        self._update_confirm_state()

    def _draw_board(self) -> None:
        self.board.delete("all")
        self.track_start_x = 120
        self.track_finish_x = self.board_width - 100
        self.track_step = (self.track_finish_x - self.track_start_x) / max(1, self.game.track_length)
        self.lane_y = {
            "hearts": 80,
            "diamonds": 170,
            "clubs": 260,
            "spades": 350,
        }
        symbols = {
            "hearts": "A ♥",
            "diamonds": "A ♦",
            "clubs": "A ♣",
            "spades": "A ♠",
        }

        self.board.create_line(self.track_finish_x, 40, self.track_finish_x, self.board_height - 40, fill=BG_ACCENT, width=4)
        self.board.create_text(self.track_finish_x + 28, 20, text="FINISH", fill=BG_ACCENT, font=(APP_FONT, 10, "bold"))

        self.token_items = {}
        for suit, y in self.lane_y.items():
            self.board.create_line(80, y, self.track_finish_x, y, fill="#d9d0c7", width=2)
            self.board.create_text(30, y, text=suit.title(), fill=FG_MAIN, anchor="w", font=(APP_FONT, 12, "bold"))
            rect = self.board.create_rectangle(self.track_start_x - 34, y - 20, self.track_start_x + 6, y + 20, fill=self._suit_color(suit), outline="")
            text = self.board.create_text(self.track_start_x - 14, y, text=f"A {symbols[suit]}", fill="#ffffff", font=(APP_FONT, 12, "bold"))
            self.token_items[suit] = (rect, text)

    def _suit_color(self, suit: str) -> str:
        return {
            "hearts": "#b83a48",
            "diamonds": "#b83a48",
            "clubs": "#000000",
            "spades": "#000000",
        }[suit]

    def _set_controls_state(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in self.bet_buttons.values():
            button.configure(state=state)
        self.amount_spin.configure(state=state)

    def _start_race(self) -> None:
        self.game.current_bet = None
        self.result_var.set(self._language_title("A verseny fut...", "The race is running..."))
        self.board_status.configure(text=self._language_title("Laphúzás indul", "Card drawing starts"))
        self._set_controls_state(False)
        self.confirm_button.configure(state="disabled")
        self.draw_button.configure(state="disabled")
        self._animate_next_draw()

    def _animate_next_draw(self) -> None:
        rank, suit, winner = self.game.race_step()
        self.card_display.configure(text=f"{rank}\n{self._suit_symbol(suit)}")
        self.board_status.configure(text=self._language_title("Húzott lap", "Drawn card") + f": {rank} {suit.title()}")
        self._move_token(suit, winner)

    def _move_token(self, suit: str, winner: str | None) -> None:
        rect, text = self.token_items[suit]
        self.board.move(rect, self.track_step, 0)
        self.board.move(text, self.track_step, 0)
        self.window.after(260, lambda: self._after_move(winner))

    def _after_move(self, winner: str | None) -> None:
        if winner is None:
            self._animate_next_draw()
            return

        self._finish_race(winner)

    def _finish_race(self, winner: str) -> None:
        self.game.round_number += 1
        self.game.last_result = f"Winner: {winner}"
        self.result_var.set(self.game.last_result)
        self.message_var.set(self.game.last_result)
        self._prepare_settlement(winner)
        self.game._prepare_round()
        self.selected_bet = None
        self.betting_player = None
        for button in self.bet_buttons.values():
            button.configure(relief="raised")
        self._set_controls_state(False)
        self.confirm_button.configure(state="disabled")
        self.draw_button.configure(state="disabled")
        self.selection_label.configure(text=self._language_title(SELECTION_NONE_HU, SELECTION_NONE_EN))
        self._draw_board()
        self.refresh_turn()
        self._show_settlement_phase()

    def _suit_symbol(self, suit: str) -> str:
        return {
            "hearts": "♥",
            "diamonds": "♦",
            "clubs": "♣",
            "spades": "♠",
        }[suit]

    def refresh_turn(self) -> None:
        player = self.game.current_player
        self.player_var.set(f"{self._language_title('Jelenlegi játékos', 'Current player')}: {player.name}")
        self.turn_detail.configure(text=f"{player.name} · {player.drink}")
        if self.phase == "betting":
            self.round_info.configure(text=self._language_title("Válassz A lapot és a kortyot, majd véglegesíts.", "Pick an A card and sip count, then finalize."))
            self.draw_button.configure(text=self.t("finalize_continue"))
            self.message_var.set(self._language_title("Most ő következik.", "This player is next."))
        elif self.phase == "settlement":
            self.round_info.configure(text=self._language_title("Most a nyertesek osztják szét a saját tétjüket.", "Now winners distribute their own bet."))

    def _update_confirm_state(self) -> None:
        if self.phase != "betting":
            self.confirm_button.configure(state="disabled")
            return
        has_bet = self.selected_bet is not None and int(self.bet_amount_var.get()) > 0
        self.confirm_button.configure(state="normal" if has_bet else "disabled")

    def _finalize_bet_and_continue(self) -> None:
        if self.phase != "betting":
            return
        if self.selected_bet is None:
            messagebox.showwarning(self._language_title("Figyelem", "Warning"), self._language_title("Válassz egy A lapot.", "Choose an A card first."))
            return

        amount = max(1, int(self.bet_amount_var.get()))
        current_index = self.game.turn_index
        current_player = self.game.current_player
        self.bets_by_index[current_index] = (self.selected_bet, amount)
        self.message_var.set(f"{current_player.name}: A {self._suit_symbol(self.selected_bet)} · {amount} {self._language_title('korty', 'sips')}")

        self.selected_bet = None
        self.betting_player = None
        self.bet_amount_var.set(1)
        for button in self.bet_buttons.values():
            button.configure(relief="raised")

        if len(self.bets_by_index) < len(self.game.config.players):
            self.game._advance_turn()
            self.refresh_turn()
            self.selection_label.configure(text=self._language_title(SELECTION_NONE_HU, SELECTION_NONE_EN))
            self._update_confirm_state()
            return

        self.phase = "race"
        self._set_controls_state(False)
        self.confirm_button.configure(state="disabled")
        self.draw_button.configure(state="disabled")
        self.window.after(250, self._start_race)

    def _prepare_settlement(self, winning_suit: str) -> None:
        self.phase = "settlement"
        winning_indices = [index for index, (suit, _) in self.bets_by_index.items() if suit == winning_suit]
        losing_indices = [index for index in self.bets_by_index if index not in winning_indices]

        self.winner_pools = {index: self.bets_by_index[index][1] for index in winning_indices}
        for loser_index in losing_indices:
            self.game.config.players[loser_index].drinks_taken += self.bets_by_index[loser_index][1]

        winner_lines = [f"{self.game.config.players[index].name}: {amount}" for index, amount in self.winner_pools.items()]
        loser_lines = [f"{self.game.config.players[index].name}: {self.bets_by_index[index][1]}" for index in losing_indices]
        self.settlement_messages = []
        summary = [
            self._language_title("Nyertesek", "Winners") + ": " + (", ".join(winner_lines) if winner_lines else self._language_title("nincs", "none")),
            self._language_title("Vesztesek", "Losers") + ": " + (", ".join(loser_lines) if loser_lines else self._language_title("nincs", "none")),
        ]
        self.settlement_summary_var.set("\n".join(summary))

        winner_values = [self._player_display(index, self.winner_pools[index]) for index in self.winner_pools]
        loser_values = [self._player_display(index, self.bets_by_index[index][1]) for index in losing_indices]
        self.settlement_winner_map = {self._player_display(index, self.winner_pools[index]): index for index in self.winner_pools}
        self.settlement_loser_map = {self._player_display(index, self.bets_by_index[index][1]): index for index in losing_indices}
        self.winner_combo.configure(values=winner_values)
        self.loser_combo.configure(values=loser_values)

        if winner_values:
            self.settlement_winner_var.set(winner_values[0])
        else:
            self.settlement_winner_var.set("")
        if loser_values:
            self.settlement_loser_var.set(loser_values[0])
        else:
            self.settlement_loser_var.set("")
        self._sync_settlement_amount()
        self.settlement_card.grid()

    def _show_settlement_phase(self) -> None:
        self.settlement_card.grid()

    def _player_display(self, index: int, amount: int) -> str:
        player = self.game.config.players[index]
        return f"{index + 1}. {player.name} ({amount})"

    def _sync_settlement_amount(self) -> None:
        winner_label = self.settlement_winner_var.get()
        winner_index = getattr(self, "settlement_winner_map", {}).get(winner_label)
        remaining = self.winner_pools.get(winner_index, 0) if winner_index is not None else 0
        self.settlement_amount_spin.configure(from_=1, to=max(1, remaining))
        if remaining > 0:
            self.settlement_amount_var.set(min(max(1, self.settlement_amount_var.get()), remaining))
        else:
            self.settlement_amount_var.set(1)

    def _apply_settlement_allocation(self) -> None:
        winner_label = self.settlement_winner_var.get()
        loser_label = self.settlement_loser_var.get()
        winner_index = getattr(self, "settlement_winner_map", {}).get(winner_label)
        loser_index = getattr(self, "settlement_loser_map", {}).get(loser_label)
        if winner_index is None or loser_index is None:
            return

        remaining = self.winner_pools.get(winner_index, 0)
        if remaining <= 0:
            return

        amount = min(max(1, int(self.settlement_amount_var.get())), remaining)
        self.winner_pools[winner_index] = remaining - amount
        self.game.config.players[loser_index].drinks_taken += amount
        self.settlement_messages.append(
            f"{self.game.config.players[winner_index].name} -> {self.game.config.players[loser_index].name}: {amount}"
        )

        if self.winner_pools[winner_index] <= 0:
            del self.winner_pools[winner_index]

        winner_values = [self._player_display(index, self.winner_pools[index]) for index in self.winner_pools]
        self.settlement_winner_map = {self._player_display(index, self.winner_pools[index]): index for index in self.winner_pools}
        self.settlement_loser_map = dict(getattr(self, "settlement_loser_map", {}))
        self.winner_combo.configure(values=winner_values)
        if winner_values:
            self.settlement_winner_var.set(winner_values[0])
        else:
            self.settlement_winner_var.set("")
        self._sync_settlement_amount()

        self.settlement_summary_var.set(
            self.settlement_summary_var.get() + ("\n" if self.settlement_summary_var.get() else "") + "; ".join(self.settlement_messages)
        )
        self.settlement_messages.clear()

    def _start_new_round(self) -> None:
        self.phase = "betting"
        self.selected_bet = None
        self.betting_player = None
        self.bets_by_index.clear()
        self.winner_pools.clear()
        self.settlement_messages.clear()
        self.settlement_summary_var.set("")
        self.settlement_card.grid_remove()
        self.game.setup()
        self._draw_board()
        self._set_controls_state(True)
        for button in self.bet_buttons.values():
            button.configure(relief="raised")
        self.bet_amount_var.set(1)
        self.confirm_button.configure(state="disabled")
        self.draw_button.configure(state="disabled")
        self.selection_label.configure(text=self._language_title(SELECTION_NONE_HU, SELECTION_NONE_EN))
        self.refresh_turn()

    def _advance_and_refresh_next_player(self) -> None:
        self.game._advance_turn()
        self.refresh_turn()


def open_game_window(app: "SocialDrinkingApp", config: GameConfig) -> GameWindowBase:
    if config.game_type == GameType.BUS:
        return BusGameWindow(app, config)
    return HorseRaceGameWindow(app, config)


TEXTS: dict[Language, dict[str, str]] = {
    Language.HU: {
        "app_title": APP_TITLE,
        "app_subtitle": "Busz és Lóverseny - party játék",
        "language": "Nyelv",
        "game": "Játék",
        "player_count": "Játékosok száma",
        "players": "Játékosok",
        "name": "Név",
        "drink": "Ital",
        "add_player": "Játékos hozzáadása",
        "edit_player": "Játékos mentése",
        "start": "Játék indítása",
        "next_round": "Következő kör",
        "finalize_continue": "Véglegesítés és tovább",
        "reset": "Újrakezdés",
        "ready": "Készen áll",
        "missing_fields": "Töltsd ki a nevet és az italt.",
        "need_players": "Adj meg legalább 2 játékost.",
        "started": "A játék elindult.",
        "select_player": "Kattints egy játékosra a szerkesztéshez.",
        "empty_players": "Még nincs játékos.",
    },
    Language.EN: {
        "app_title": APP_TITLE,
        "app_subtitle": "Party game for Bus and Horse Race",
        "language": "Language",
        "game": "Game",
        "player_count": "Players",
        "players": "Players",
        "name": "Name",
        "drink": "Drink",
        "add_player": "Add player",
        "edit_player": "Save player",
        "start": "Start game",
        "next_round": "Next round",
        "finalize_continue": "Finalize and continue",
        "reset": "Reset",
        "ready": "Ready",
        "missing_fields": "Please fill in name and drink.",
        "need_players": "Add at least 2 players.",
        "started": "Game started.",
        "select_player": "Click a player to edit them.",
        "empty_players": "No players yet.",
    },
}


class SocialDrinkingApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("1100x760")
        self.root.minsize(980, 680)
        self.root.configure(bg=BG_MAIN)

        self.language_var = tk.StringVar(value=Language.HU.value)
        self.game_var = tk.StringVar(value=GameType.BUS.value)
        self.player_count_var = tk.IntVar(value=4)
        self.name_var = tk.StringVar()
        self.drink_var = tk.StringVar()
        self.status_var = tk.StringVar(value="")
        self.selected_player_index: int | None = None
        self.active_game: SocialGame | None = None
        self.game_window: GameWindowBase | None = None

        self.players: list[Player] = []
        self.player_cards: list[ttk.Frame] = []
        self.player_labels: list[tk.Label] = []

        self._setup_styles()
        self._build_ui()
        self._refresh_language()
        self._sync_player_count()

    def _setup_styles(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(STYLE_ROOT, background=BG_MAIN)
        style.configure(STYLE_HEADER, background=BG_DARK)
        style.configure(STYLE_CARD, background=BG_CARD)
        style.configure(STYLE_SUBCARD, background=BG_SUBCARD)
        style.configure(STYLE_ACCENT, background=BG_ACCENT)
        style.configure(STYLE_TITLE, background=BG_DARK, foreground=FG_LIGHT, font=(APP_FONT, 26, "bold"))
        style.configure(STYLE_SUBTITLE, background=BG_DARK, foreground="#d9c8b6", font=(APP_FONT, 10))
        style.configure(STYLE_SECTION, background=BG_CARD, foreground=FG_MAIN, font=(APP_FONT, 12, "bold"))
        style.configure(STYLE_INFO, background=BG_CARD, foreground=FG_MUTED, font=(APP_FONT, 10))
        style.configure(STYLE_ACCENT_BUTTON, font=(APP_FONT, 10, "bold"), padding=(18, 10), background=BG_ACCENT, foreground="#ffffff")
        style.map(STYLE_ACCENT_BUTTON, background=[("active", "#c2752a")])
        style.configure(STYLE_SOFT_BUTTON, font=(APP_FONT, 10), padding=(14, 9))
        style.configure("TCombobox", padding=8)
        style.configure("TEntry", padding=8)

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        header = ttk.Frame(self.root, style=STYLE_HEADER, padding=(30, 26))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        self.title_label = ttk.Label(header, text=APP_TITLE, style=STYLE_TITLE)
        self.title_label.grid(row=0, column=0, sticky="w")
        self.subtitle_label = ttk.Label(header, text="Elegant party game controller", style=STYLE_SUBTITLE)
        self.subtitle_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

        badge = ttk.Frame(header, style=STYLE_ACCENT, padding=(14, 10))
        badge.grid(row=0, column=1, rowspan=2, sticky="e")
        self.badge_label = ttk.Label(badge, text="READY", background=BG_ACCENT, foreground="#ffffff", font=(APP_FONT, 10, "bold"))
        self.badge_label.pack()

        main = ttk.Frame(self.root, style=STYLE_ROOT, padding=24)
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        left = ttk.Frame(main, style=STYLE_ROOT)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        left.columnconfigure(0, weight=1)

        controls = ttk.Frame(left, style=STYLE_CARD, padding=22)
        controls.grid(row=0, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)

        self.language_label = ttk.Label(controls, style=STYLE_SECTION)
        self.language_label.grid(row=0, column=0, sticky="w")
        language_box = ttk.Combobox(controls, state="readonly", values=[Language.HU.value, Language.EN.value], textvariable=self.language_var, width=10)
        language_box.grid(row=0, column=1, sticky="e")
        language_box.bind(COMBO_SELECTED_EVENT, lambda _event: self._refresh_language())

        self.game_label = ttk.Label(controls, style=STYLE_SECTION)
        self.game_label.grid(row=1, column=0, sticky="w", pady=(18, 0))
        game_box = ttk.Combobox(controls, state="readonly", values=[GameType.BUS.value, GameType.HORSE_RACE.value], textvariable=self.game_var)
        game_box.grid(row=1, column=1, sticky="e", pady=(18, 0))
        game_box.bind(COMBO_SELECTED_EVENT, lambda _event: self._handle_game_change())

        self.player_count_label = ttk.Label(controls, style=STYLE_SECTION)
        self.player_count_label.grid(row=2, column=0, sticky="w", pady=(18, 0))
        count_display = ttk.Label(controls, textvariable=self.player_count_var, style=STYLE_INFO, anchor="e")
        count_display.grid(row=2, column=1, sticky="e", pady=(18, 0))

        form = ttk.Frame(left, style=STYLE_CARD, padding=22)
        form.grid(row=1, column=0, sticky="ew", pady=14)
        form.columnconfigure(1, weight=1)

        self.name_label = ttk.Label(form, style=STYLE_SECTION)
        self.name_label.grid(row=0, column=0, sticky="w")
        name_entry = ttk.Entry(form, textvariable=self.name_var)
        name_entry.grid(row=0, column=1, sticky="ew", padx=(16, 0))

        self.drink_label = ttk.Label(form, style=STYLE_SECTION)
        self.drink_label.grid(row=1, column=0, sticky="w", pady=(14, 0))
        drink_entry = ttk.Entry(form, textvariable=self.drink_var)
        drink_entry.grid(row=1, column=1, sticky="ew", padx=(16, 0), pady=(14, 0))

        button_row = ttk.Frame(form, style=STYLE_CARD)
        button_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        button_row.columnconfigure((0, 1, 2), weight=1)

        self.add_button = ttk.Button(button_row, style=STYLE_SOFT_BUTTON, command=self._add_player)
        self.add_button.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.start_button = ttk.Button(button_row, style=STYLE_ACCENT_BUTTON, command=self._start_or_next_round)
        self.start_button.grid(row=0, column=1, sticky="ew", padx=10)
        self.reset_button = ttk.Button(button_row, style=STYLE_SOFT_BUTTON, command=self._reset_form)
        self.reset_button.grid(row=0, column=2, sticky="ew", padx=(10, 0))

        right = ttk.Frame(main, style=STYLE_ROOT)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        status_card = ttk.Frame(right, style=STYLE_CARD, padding=22)
        status_card.grid(row=0, column=0, sticky="ew")
        status_card.columnconfigure(0, weight=1)
        self.status_title = ttk.Label(status_card, style=STYLE_SECTION)
        self.status_title.grid(row=0, column=0, sticky="w")
        self.status_value = ttk.Label(status_card, textvariable=self.status_var, style=STYLE_INFO, wraplength=320, justify="left")
        self.status_value.grid(row=1, column=0, sticky="w", pady=(14, 0))

        players_card = ttk.Frame(right, style=STYLE_CARD, padding=22)
        players_card.grid(row=1, column=0, sticky="nsew", pady=(14, 0))
        players_card.columnconfigure(0, weight=1)
        players_card.rowconfigure(1, weight=1)

        self.players_label = ttk.Label(players_card, style=STYLE_SECTION)
        self.players_label.grid(row=0, column=0, sticky="w")

        self.players_canvas = tk.Canvas(players_card, highlightthickness=0, bg=BG_CARD)
        self.players_canvas.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        self.players_scrollbar = ttk.Scrollbar(players_card, orient="vertical", command=self.players_canvas.yview)
        self.players_scrollbar.grid(row=1, column=1, sticky="ns", pady=(16, 0))
        self.players_canvas.configure(yscrollcommand=self.players_scrollbar.set)

        self.players_inner = ttk.Frame(self.players_canvas, style=STYLE_CARD)
        self.players_window = self.players_canvas.create_window((0, 0), window=self.players_inner, anchor="nw")
        self.players_inner.bind("<Configure>", lambda _event: self.players_canvas.configure(scrollregion=self.players_canvas.bbox("all")))
        self.players_canvas.bind("<Configure>", self._resize_players_inner)

        self.root.bind("<Return>", lambda _event: self._add_player())
        self.root.bind("<Escape>", lambda _event: self._reset_form())

    def _resize_players_inner(self, event: tk.Event[tk.Misc]) -> None:
        self.players_canvas.itemconfigure(self.players_window, width=event.width)

    def _current_language(self) -> Language:
        return Language(self.language_var.get())

    def _text(self, key: str) -> str:
        return TEXTS[self._current_language()][key]

    def _refresh_language(self) -> None:
        self.title_label.configure(text=self._text("app_title"))
        self.subtitle_label.configure(text=self._text("app_subtitle"))
        self.language_label.configure(text=self._text("language"))
        self.game_label.configure(text=self._text("game"))
        self.player_count_label.configure(text=self._text("player_count"))
        self.name_label.configure(text=self._text("name"))
        self.drink_label.configure(text=self._text("drink"))
        self.add_button.configure(text=self._text("edit_player") if self.selected_player_index is not None else self._text("add_player"))
        self.start_button.configure(text=self._text("next_round") if self.active_game is not None else self._text("start"))
        self.reset_button.configure(text=self._text("reset"))
        self.players_label.configure(text=self._text("players"))
        self.status_title.configure(text=self._text("ready"))
        if not self.status_var.get():
            self.status_var.set(self._text("select_player"))

    def _handle_game_change(self) -> None:
        self.active_game = None
        self.status_var.set("")
        self._refresh_language()

    def _sync_player_count(self) -> None:
        count = max(2, int(self.player_count_var.get()))
        self.player_count_var.set(count)

        while len(self.players) < count:
            index = len(self.players) + 1
            self.players.append(Player(name=f"Player {index}", drink="Water"))
        while len(self.players) > count:
            self.players.pop()

        self._reset_game_state()
        self._refresh_player_list()

    def _reset_game_state(self) -> None:
        self.active_game = None
        self.start_button.configure(text=self._text("start"))
        self.status_var.set(self._text("select_player"))

    def _reset_form(self) -> None:
        self.name_var.set("")
        self.drink_var.set("")
        self.selected_player_index = None
        self.add_button.configure(text=self._text("add_player"))
        self._refresh_player_list()

    def _add_player(self) -> None:
        name = self.name_var.get().strip()
        drink = self.drink_var.get().strip()
        if not name or not drink:
            messagebox.showwarning(self._text("ready"), self._text("missing_fields"))
            return

        if self.selected_player_index is None:
            self.players.append(Player(name=name, drink=drink))
        else:
            player = self.players[self.selected_player_index]
            player.name = name
            player.drink = drink

        self.player_count_var.set(max(2, len(self.players)))
        self.name_var.set("")
        self.drink_var.set("")
        self.selected_player_index = None
        self.add_button.configure(text=self._text("add_player"))
        self._reset_game_state()
        self._refresh_player_list()

    def _refresh_player_list(self) -> None:
        for child in self.players_inner.winfo_children():
            child.destroy()

        self.player_cards.clear()
        self.player_labels.clear()

        if not self.players:
            empty = ttk.Label(self.players_inner, text=self._text("empty_players"), style=STYLE_INFO)
            empty.grid(row=0, column=0, sticky="w")
            return

        current_turn_player = self.active_game.current_player if self.active_game is not None and self.active_game.config.players else None

        for index, player in enumerate(self.players):
            card = ttk.Frame(self.players_inner, style=STYLE_SUBCARD, padding=(16, 12))
            card.grid(row=index, column=0, sticky="ew", pady=6)
            card.columnconfigure(1, weight=1)
            self._bind_player_card(card, index)

            is_current_turn = current_turn_player is not None and current_turn_player == player
            pill_bg = BG_ACCENT if is_current_turn else BG_DARK
            pill = tk.Label(card, text=str(index + 1).zfill(2), bg=pill_bg, fg=FG_LIGHT, font=(APP_FONT, 10, "bold"), padx=10, pady=6)
            pill.grid(row=0, column=0, rowspan=2, sticky="n")
            self._bind_player_card(pill, index)

            name = ttk.Label(card, text=player.name, style=STYLE_SECTION)
            name.grid(row=0, column=1, sticky="w", padx=(14, 0))
            self._bind_player_card(name, index)

            drink = ttk.Label(card, text=f"{player.drink} · {player.drinks_taken} drinks", style=STYLE_INFO)
            drink.grid(row=1, column=1, sticky="w", padx=(14, 0), pady=(2, 0))
            self._bind_player_card(drink, index)

            self.player_cards.append(card)
            self.player_labels.append(name)

    def _bind_player_card(self, widget: tk.Widget, index: int) -> None:
        widget.bind("<Button-1>", lambda _event, selected=index: self._select_player(selected))

    def _select_player(self, index: int) -> None:
        player = self.players[index]
        self.selected_player_index = index
        self.name_var.set(player.name)
        self.drink_var.set(player.drink)
        self.add_button.configure(text=self._text("edit_player"))

    def _start_or_next_round(self) -> None:
        if len(self.players) < 2:
            messagebox.showwarning(self._text("ready"), self._text("need_players"))
            return

        if self.game_window is not None and self.game_window.window.winfo_exists():
            self.game_window.window.lift()
            self.game_window.window.focus_force()
            return

        config = GameConfig(language=self._current_language(), game_type=GameType(self.game_var.get()), players=self.players)
        self.game_window = open_game_window(self, config)
        self.status_var.set(self._text("started"))

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = SocialDrinkingApp()
    app.run()


if __name__ == "__main__":
    main()
