from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from typing import Iterable, Optional

from power_source import PowerSupply

DEFAULT_ADDRESS = "ASRL5::INSTR"
DEFAULT_BAUD_RATE = 115200
RESTORE_MEMORY_REGISTER = 1
VALID_CHANNELS = (1, 2, 3, 4)
DEFAULT_CHANNELS_TEXT = "1,2,3,4"


@dataclass
class ChannelStatus:
    channel: int
    voltage: Optional[float]
    current: Optional[float]
    output_state: str

def print_check(label: str, ok: bool, details: str) -> None:
    status = "OK" if ok else "FAIL"
    print(f"[{status}] {label}: {details}")

def prompt_text(prompt: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return default if value == "" and default is not None else value

def prompt_int(prompt: str, default: Optional[int] = None, minimum: Optional[int] = None, maximum: Optional[int] = None) -> int:
    while True:
        raw = prompt_text(prompt, str(default) if default is not None else None)
        try:
            value = int(raw)
        except ValueError:
            print_check(prompt, False, f"'{raw}' nem egesz szam.")
            continue

        if minimum is not None and value < minimum:
            print_check(prompt, False, f"{value} kisebb mint a minimum ({minimum}).")
            continue
        if maximum is not None and value > maximum:
            print_check(prompt, False, f"{value} nagyobb mint a maximum ({maximum}).")
            continue
        return value

def prompt_float(prompt: str, default: Optional[float] = None, minimum: Optional[float] = None, maximum: Optional[float] = None) -> float:
    while True:
        raw_default = None if default is None else f"{default}"
        raw = prompt_text(prompt, raw_default)
        try:
            value = float(raw)
        except ValueError:
            print_check(prompt, False, f"'{raw}' nem szam.")
            continue

        if minimum is not None and value < minimum:
            print_check(prompt, False, f"{value} kisebb mint a minimum ({minimum}).")
            continue
        if maximum is not None and value > maximum:
            print_check(prompt, False, f"{value} nagyobb mint a maximum ({maximum}).")
            continue
        return value

def prompt_channels(prompt: str = "Csatornak", default: str = DEFAULT_CHANNELS_TEXT) -> list[int]:
    while True:
        raw = prompt_text(prompt, default)
        try:
            channels = [int(part.strip()) for part in raw.split(",") if part.strip() != ""]
        except ValueError:
            print_check(prompt, False, f"'{raw}' nem olvashato csatornalista.")
            continue

        if not channels:
            print_check(prompt, False, "Legalabb egy csatornat adj meg.")
            continue

        invalid = [channel for channel in channels if channel not in VALID_CHANNELS]
        if invalid:
            print_check(prompt, False, f"Ervenytelen csatornak: {invalid}. Ervenyes: {VALID_CHANNELS}.")
            continue

        return channels

def parse_first_float(raw: str) -> Optional[float]:
    match = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", raw)
    if match is None:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None

def normalize_state(raw: str) -> str:
    cleaned = raw.strip().upper()
    if cleaned in {"1", "ON", "TRUE"}:
        return "ON"
    if cleaned in {"0", "OFF", "FALSE"}:
        return "OFF"
    return cleaned or "UNKNOWN"

class PowerSupplyConsoleTester:
    def __init__(self, address: str, baud_rate: int):
        self.address = address
        self.baud_rate = baud_rate
        self.tap: Optional[PowerSupply] = None

    def connect(self) -> None:
        print(f"Kapcsolodas a taphoz: {self.address} @ {self.baud_rate}")
        self.tap = PowerSupply(self.address, self.baud_rate)
        try:
            self.tap.ps.timeout = 5000
            self.tap.ps.read_termination = "\n"
            self.tap.ps.write_termination = "\n"
        except Exception:
            pass

        try:
            identity = self.tap.ps.query("*IDN?")
            print_check("Kapcsolat", True, f"*IDN? -> {identity.strip()}")
        except Exception as exc:
            print_check("Kapcsolat", False, str(exc))
            raise

    def close(self) -> None:
        if self.tap is None:
            return
        try:
            self.tap.ps.close()
            print_check("Lezaras", True, "A tap kapcsolat lezarva.")
        except Exception as exc:
            print_check("Lezaras", False, str(exc))
        finally:
            self.tap = None

    def require_tap(self) -> PowerSupply:
        if self.tap is None:
            raise RuntimeError("A tap nincs csatlakoztatva.")
        return self.tap

    def query_raw(self, command: str) -> str:
        tap = self.require_tap()
        response = tap.ps.query(command)
        print_check(f"Lekerdezes: {command}", True, response.strip())
        return response

    def write_raw(self, command: str) -> None:
        tap = self.require_tap()
        tap.ps.write(command)
        print_check(f"Kiadas: {command}", True, "A parancs elkuldve.")

    def verify_voltage(self, channel: int, expected: float, tolerance: float = 0.01) -> None:
        tap = self.require_tap()
        raw = tap.ps.query(f":SOURce{channel}:VOLTage?")
        actual = parse_first_float(raw)
        if actual is None:
            print_check(f"Feszultseg ellenorzes Ch{channel}", False, f"Nem olvashato vissza: {raw.strip()}")
            return
        delta = abs(actual - expected)
        ok = delta <= tolerance
        print_check(
            f"Feszultseg ellenorzes Ch{channel}",
            ok,
            f"beallitott={expected:.4f} V, visszaolvasott={actual:.4f} V, eltres={delta:.4f} V",
        )

    def verify_output_state(self, channel: int, expected_on: bool) -> None:
        tap = self.require_tap()
        raw = tap.ps.query(f":OUTPut{channel}:STATe?")
        actual = normalize_state(raw)
        expected = "ON" if expected_on else "OFF"
        ok = actual == expected
        print_check(
            f"Kimenet ellenorzes Ch{channel}",
            ok,
            f"varhato={expected}, visszaolvasott={actual}, raw={raw.strip()}",
        )

    def show_channel_status(self, channels: Iterable[int]) -> None:
        tap = self.require_tap()
        for channel in channels:
            voltage_raw = tap.ps.query(f":SOURce{channel}:VOLTage?")
            current_raw = tap.ps.query(f":SOURce{channel}:CURRent?")
            output_raw = tap.ps.query(f":OUTPut{channel}:STATe?")
            voltage = parse_first_float(voltage_raw)
            current = parse_first_float(current_raw)
            output_state = normalize_state(output_raw)
            print_check(
                f"Status Ch{channel}",
                True,
                f"V={voltage_raw.strip()} ({voltage}), I={current_raw.strip()} ({current}), OUT={output_state}",
            )

    def set_voltage(self, channels: Iterable[int], voltage: float) -> None:
        tap = self.require_tap()
        for channel in channels:
            command = f":SOURce{channel}:VOLTage {voltage}"
            tap.ps.write(command)
            print_check(f"Feszultseg kiadas Ch{channel}", True, command)
            self.verify_voltage(channel, voltage)

    def set_output_state(self, channels: Iterable[int], switch_on: bool) -> None:
        tap = self.require_tap()
        for channel in channels:
            tap.turn_channel_on_off(switch_on, all_channels=False, channels=[channel])
            print_check(
                f"Kimenet kapcsolas Ch{channel}",
                True,
                f"{'ON' if switch_on else 'OFF'} parancs elkuldve.",
            )
            self.verify_output_state(channel, switch_on)

    def all_outputs(self, switch_on: bool) -> None:
        tap = self.require_tap()
        tap.turn_channel_on_off(switch_on, all_channels=True)
        print_check(
            "Osszes kimenet",
            True,
            f"{'ON' if switch_on else 'OFF'} parancs elkuldve.",
        )
        for channel in VALID_CHANNELS:
            self.verify_output_state(channel, switch_on)

    def turn_screen(self, turn_on: bool) -> None:
        tap = self.require_tap()
        tap.turn_screen_on_off(turn_on)
        print_check("Kijelzo", True, f"DISP:ENAB {'ON' if turn_on else 'OFF'} elkuldve.")

    def recall_memory_register(self, register: int = RESTORE_MEMORY_REGISTER) -> None:
        tap = self.require_tap()
        tap.load_memory_register(register)
        print_check("Memoria visszahivas", True, f"*RCL {register} elkuldve.")
        time.sleep(0.5)
        try:
            opc = tap.ps.query("*OPC?")
            print_check("Parancs befejezodott", normalize_state(opc) == "ON" or opc.strip() == "1", f"*OPC? -> {opc.strip()}")
        except Exception as exc:
            print_check("Parancs befejezodott", False, str(exc))
        self.show_channel_status(VALID_CHANNELS)

    def restore_then_shutdown(self, channels: Iterable[int]) -> None:
        self.recall_memory_register(RESTORE_MEMORY_REGISTER)
        self.set_output_state(channels, False)
        print_check(
            "Visszaallas utani lekapcsolas",
            True,
            f"Az {RESTORE_MEMORY_REGISTER}-es memoriaregiszter betoltve, majd a kijelolt csatornak kikapcsolva.",
        )
    def apply_step_to_tap(self, channels: Iterable[int], voltage: float):
        tap = self.require_tap()
        tap.ps.write('*CLS\n')
        time.sleep(0.05)
        for ch in channels:
            #tap.turn_channel_on_off(False, all_channels=False, channels=[ch])
            command1 = f':SOURce{ch}:VOLTage {voltage}\n'
            tap.ps.write(command1)
            command2 = f':SOURce{ch}:APPLy\n'
            tap.ps.write(command2)
            command3 = f':SOURce{ch}:STATe ON\n'
            tap.ps.write(command3)
            command4 = f':OUTPut{ch}:STATe ON\n'
            tap.ps.write(command4)
            #tap.turn_channel_on_off(True, all_channels=False, channels=[ch])
        time.sleep(0.5)
        print_check(f"Feszultseg kiadas Ch{channels}", True, command1)
        print_check(f"Apply parancs Ch{channels}", True, command2)
        print_check(f"Status ON parancs Ch{channels}", True, command3)
        print_check(f"Output ON parancs Ch{channels}", True, command4)
        self.verify_voltage(channels, voltage)

def print_menu() -> None:
    print("\n=== Tap konzolos teszt ===")
    print("1) Eszkoz azonositas")
    print("2) Feszultseg beallitasa csatornakra")
    print("3) Aram beallitasa csatornakra (használt módszer)")
    print("4) Kimenet ON/OFF csatornakra")
    print("5) Osszes kimenet ON/OFF")
    print("6) Memoriaregiszter 1 visszahivasa es visszaellenorzes")
    print("7) Csoportos statusz kiolvasasa")
    print("8) Kijelzo ON/OFF")
    print("9) Nyers SCPI parancs kuldese")
    print("0) Kilepes")

def handle_menu_choice(tester: PowerSupplyConsoleTester, choice: str) -> bool:
    if choice == "1":
        tester.query_raw("*IDN?")
    elif choice == "2":
        channels = prompt_channels()
        voltage = prompt_float("Beallitando feszultseg [V]", 1.0)
        tester.set_voltage(channels, voltage)
    elif choice == "3":
        channels = prompt_channels()
        voltage = prompt_float("Beallitando feszultseg [V]", 1.0)
        tester.apply_step_to_tap(channels, voltage)
    elif choice == "4":
        channels = prompt_channels()
        switch_on = prompt_text("Kimenet bekapcsolva legyen? (y/n)", "y").lower().startswith("y")
        tester.set_output_state(channels, switch_on)
    elif choice == "5":
        switch_on = prompt_text("Osszes kimenet bekapcsolva legyen? (y/n)", "y").lower().startswith("y")
        tester.all_outputs(switch_on)
    elif choice == "6":
        channels = prompt_channels("Erintett csatornak", DEFAULT_CHANNELS_TEXT)
        tester.restore_then_shutdown(channels)
    elif choice == "7":
        channels = prompt_channels("Lekerendo csatornak", DEFAULT_CHANNELS_TEXT)
        tester.show_channel_status(channels)
    elif choice == "8":
        turn_on = prompt_text("Kijelzo bekapcsolva legyen? (y/n)", "y").lower().startswith("y")
        tester.turn_screen(turn_on)
    elif choice == "9":
        command = prompt_text("SCPI parancs")
        if command.endswith("?"):
            tester.query_raw(command)
        else:
            tester.write_raw(command)
            print_check("Nyers parancs", True, "Nincs automatikus visszaellenorzes ehhez a parancshoz.")
    elif choice == "0":
        print_check("Kilepes", True, "Program leall.")
        return False
    else:
        print_check("Valasztas", False, f"Ismeretlen opcio: {choice}")
    return True

def run_console_menu(tester: PowerSupplyConsoleTester) -> None:
    while True:
        print_menu()
        choice = prompt_text("Valasztas", "0")
        if not handle_menu_choice(tester, choice):
            break

def main() -> None:
    tester = PowerSupplyConsoleTester(DEFAULT_ADDRESS, DEFAULT_BAUD_RATE)

    try:
        tester.connect()
        run_console_menu(tester)
    except KeyboardInterrupt:
        print_check("Megszakitas", True, "Ctrl+C fogadva.")
    except Exception as exc:
        print_check("Futasi hiba", False, str(exc))
        raise
    finally:
        tester.close()

if __name__ == "__main__":
    main()