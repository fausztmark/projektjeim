from __future__ import annotations

import argparse
import csv
import math
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import messagebox

try:
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.ticker import MaxNLocator, ScalarFormatter
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise SystemExit(
        "A matplotlib nincs telepítve. Telepítsd, majd futtasd újra a kiertekelo.py-t."
    ) from exc


STEP_HEADER_RE = re.compile(r"feszültség:\s*([-+]?\d+(?:[.,]\d+)?)\s*V", re.IGNORECASE)
AXIS_VOLTAGE = "Feszültség (V)"
AXIS_COUNT = "Beütés"
AXIS_CURRENT = "Áram (mA)"
LEGEND_CHANNELS = "Csatornák"
METADATA_FILE_NAME = "metaadat.csv"


@dataclass(frozen=True)
class MeasurementRecord:
    voltage: float
    count: int
    current_ma: Optional[float]


@dataclass(frozen=True)
class ChannelData:
    channel: int
    csv_path: Path
    txt_path: Path
    records: list[MeasurementRecord]


@dataclass(frozen=True)
class MeasurementGroup:
    prefix: str
    channels: list[ChannelData]


@dataclass(frozen=True)
class MeasurementMetadata:
    prefix: str
    measurement_name: str
    comment: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SNSPD mérési CSV-k elemzése és diagramok rajzolása."
    )
    parser.add_argument(
        "--meresek-txt-dir",
        default=None,
        help="A TXT mérési mappa elérési útja. Alapértelmezés: a szkript melletti meresek_txt mappa.",
    )
    parser.add_argument(
        "--meresek-csv-dir",
        default=None,
        help="A CSV mérési mappa elérési útja. Alapértelmezés: a szkript melletti meresek_csv mappa.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="A képek mentési helye. Alapértelmezés: a meresek mappán belüli kiertekelesek alkönyvtár.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="A mentés után jelenítse is meg az ablakokat.",
    )
    return parser.parse_args()


def resolve_meresek_txt_dir(explicit_dir: Optional[str]) -> Path:
    if explicit_dir is not None:
        return Path(explicit_dir).expanduser().resolve()
    return Path(__file__).resolve().parent / "meresek_txt"


def resolve_meresek_csv_dir(explicit_dir: Optional[str]) -> Path:
    if explicit_dir is not None:
        return Path(explicit_dir).expanduser().resolve()
    return Path(__file__).resolve().parent / "meresek_csv"


def resolve_output_dir(meresek_csv_dir: Path, explicit_dir: Optional[str]) -> Path:
    if explicit_dir is not None:
        return Path(explicit_dir).expanduser().resolve()
    return meresek_csv_dir / "kiertekelesek"


def resolve_metadata_path(base_dir: Path) -> Path:
    return base_dir / METADATA_FILE_NAME


def load_measurement_metadata(metadata_path: Path) -> dict[str, MeasurementMetadata]:
    if not metadata_path.exists():
        return {}

    metadata_by_prefix: dict[str, MeasurementMetadata] = {}
    with metadata_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter=";")
        for row_index, row in enumerate(reader):
            if not row:
                continue

            if row_index == 0 and len(row) >= 2 and row[0].strip().lower() == "mérés neve":
                continue

            if len(row) < 3:
                continue

            measurement_name = row[0].strip()
            prefix = row[1].strip()
            comment = row[-1].strip() if row[-1].strip() else ""
            if not prefix:
                continue

            metadata_by_prefix[prefix] = MeasurementMetadata(
                prefix=prefix,
                measurement_name=measurement_name,
                comment=comment,
            )

    return metadata_by_prefix


def resolve_measurement_title(selected_group: MeasurementGroup, metadata_by_prefix: dict[str, MeasurementMetadata]) -> str:
    metadata = metadata_by_prefix.get(selected_group.prefix)
    if metadata is None or not metadata.measurement_name:
        return selected_group.prefix.replace("_", " ")
    return metadata.measurement_name


def sanitize_title_token(value: str) -> str:
    return re.sub(r"\s+", "_", value.strip())


def sanitize_filename_token(value: str) -> str:
    sanitized = re.sub(r"[<>:\"/\\|?*]", "_", value.strip())
    sanitized = re.sub(r"\s+", "_", sanitized)
    return re.sub(r"_+", "_", sanitized)


def resolve_measurement_timestamp(prefix: str) -> str:
    if "_" not in prefix:
        return prefix

    date_part, time_part = prefix.split("_", 1)
    return f"{date_part} {time_part.replace('.', ':')}"


def format_diagram_type(diagram_type: str) -> str:
    return diagram_type.replace("_", " ")


def build_diagram_title(measurement_name: str, diagram_type: str, measurement_timestamp: str) -> str:
    return f"{measurement_name} - {format_diagram_type(diagram_type)} - {measurement_timestamp}"


def build_diagram_file_name(measurement_name: str, diagram_type: str, measurement_timestamp: str) -> str:
    return (
        f"{sanitize_filename_token(measurement_name)}_-_"
        f"{sanitize_filename_token(diagram_type)}_-_"
        f"{sanitize_filename_token(measurement_timestamp)}.png"
    )


def discover_measurement_groups(meresek_txt_dir: Path, meresek_csv_dir: Path) -> list[MeasurementGroup]:
    grouped_files: dict[str, list[tuple[int, Path, Optional[Path]]]] = defaultdict(list)

    for txt_path in sorted(meresek_txt_dir.glob("*_CH*_meres.txt")):
        match = re.search(r"^(.*)_CH(\d+)_meres\.txt$", txt_path.name, re.IGNORECASE)
        if match is None:
            continue

        prefix = match.group(1)
        channel = int(match.group(2))
        csv_path = meresek_csv_dir / txt_path.with_suffix(".csv").name
        grouped_files[prefix].append((channel, txt_path, csv_path if csv_path.exists() else None))

    measurement_groups: list[MeasurementGroup] = []
    for prefix, file_triplets in sorted(grouped_files.items(), key=lambda item: item[0], reverse=True):
        channel_data = [build_channel_data(channel, txt_path, csv_path) for channel, txt_path, csv_path in sorted(file_triplets, key=lambda item: item[0])]
        measurement_groups.append(MeasurementGroup(prefix=prefix, channels=channel_data))

    return measurement_groups


def list_measurement_groups(meresek_txt_dir: Path, meresek_csv_dir: Path) -> list[MeasurementGroup]:
    groups = discover_measurement_groups(meresek_txt_dir, meresek_csv_dir)
    if not groups:
        raise FileNotFoundError(
            f"Nem találtam feldolgozható méréscsoportot ebben a mappában: {meresek_txt_dir}"
        )
    return groups


class MeasurementGroupDialog:
    def __init__(self, groups: list[MeasurementGroup]):
        self.groups = groups
        self.selected_group: Optional[MeasurementGroup] = None
        self.root = tk.Tk()
        self.root.title("Mérés kiválasztása")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.on_cancel)

        container = tk.Frame(self.root, padx=12, pady=12)
        container.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            container,
            text="Válaszd ki, melyik mérést szeretnéd betölteni:",
            font=("Arial", 11, "bold"),
            anchor="w",
            justify="left",
        ).pack(fill=tk.X, pady=(0, 10))

        self.listbox = tk.Listbox(container, width=52, height=min(12, max(4, len(groups))))
        self.listbox.pack(fill=tk.BOTH, expand=True)

        for group in groups:
            channel_text = ", ".join(f"Ch{channel_data.channel}" for channel_data in group.channels)
            self.listbox.insert(tk.END, f"{group.prefix}   [{channel_text}]")

        if groups:
            self.listbox.selection_set(0)
            self.listbox.activate(0)

        self.listbox.bind("<Double-Button-1>", lambda _event: self.on_ok())

        button_row = tk.Frame(container, pady=10)
        button_row.pack(fill=tk.X)
        tk.Button(button_row, text="Betöltés", command=self.on_ok, width=12).pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(button_row, text="Mégse", command=self.on_cancel, width=12).pack(side=tk.RIGHT)

    def on_ok(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("Választás szükséges", "Válassz ki egy méréscsoportot.")
            return

        self.selected_group = self.groups[selection[0]]
        self.root.destroy()

    def on_cancel(self):
        self.selected_group = None
        self.root.destroy()

    def show(self) -> Optional[MeasurementGroup]:
        self.root.mainloop()
        return self.selected_group


def choose_measurement_group(groups: list[MeasurementGroup]) -> MeasurementGroup:
    try:
        dialog = MeasurementGroupDialog(groups)
        selected_group = dialog.show()
        if selected_group is None:
            raise SystemExit("Nem történt mérésválasztás.")
        return selected_group
    except tk.TclError:
        print("A grafikus választó nem indítható el, terminálos választásra váltok.")
        print("Elérhető mérések:")
        for index, group in enumerate(groups, start=1):
            channel_text = ", ".join(f"Ch{channel_data.channel}" for channel_data in group.channels)
            print(f"{index}. {group.prefix}  [{channel_text}]")

        while True:
            raw_choice = input("Melyik mérést szeretnéd betölteni? Írd be a számát: ").strip()
            try:
                choice = int(raw_choice)
            except ValueError:
                print("Érvénytelen választás, számot adj meg.")
                continue

            if not 1 <= choice <= len(groups):
                print(f"A választás 1 és {len(groups)} között lehet.")
                continue

            return groups[choice - 1]


def parse_voltage_from_header(line: str) -> Optional[float]:
    match = STEP_HEADER_RE.search(line)
    if match is None:
        return None
    raw_value = match.group(1).replace(",", ".")
    try:
        return float(raw_value)
    except ValueError:
        return None


def parse_integer_with_thousands_separator(raw_value: str) -> Optional[int]:
    cleaned_value = raw_value.strip().replace(".", "").replace(",", "")
    if not re.fullmatch(r"[-+]?\d+", cleaned_value):
        return None

    try:
        return int(cleaned_value)
    except ValueError:
        return None


def parse_measurement_txt(txt_path: Path) -> list[tuple[float, int]]:
    records: list[tuple[float, int]] = []
    current_voltage: Optional[float] = None

    with txt_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue

            parsed_voltage = parse_voltage_from_header(line)
            if parsed_voltage is not None:
                current_voltage = parsed_voltage
                continue

            if current_voltage is None:
                continue

            match = re.search(r"CH\d+:\s*([-+]?\d[\d.,]*)", line)
            if match is None:
                continue

            count_value = parse_integer_with_thousands_separator(match.group(1))
            if count_value is None:
                continue

            records.append((current_voltage, count_value))

    return records


def extract_voltage_sequence(txt_path: Path) -> List[Optional[float]]:
    voltages: List[Optional[float]] = []
    current_voltage: Optional[float] = None

    with txt_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue

            parsed_voltage = parse_voltage_from_header(line)
            if parsed_voltage is not None:
                current_voltage = parsed_voltage
                continue

            if "---" in line:
                voltages.append(current_voltage)

    return voltages


def parse_current_csv(csv_path: Path) -> list[float]:
    rows: list[float] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter=";")
        for row in reader:
            if not row:
                continue

            first_cell = row[0].strip().lower()
            if first_cell in {"datum", "date", "timestamp"}:
                continue

            if len(row) >= 4:
                current_raw = row[3]
            elif len(row) >= 3:
                current_raw = row[2]
            else:
                continue

            try:
                current_value = float(current_raw.replace(",", "."))
            except ValueError:
                continue

            rows.append(current_value)

    return rows


def build_channel_data(channel: int, txt_path: Path, csv_path: Optional[Path]) -> ChannelData:
    txt_records = parse_measurement_txt(txt_path)
    current_values = parse_current_csv(csv_path) if csv_path is not None and csv_path.exists() else []

    if current_values and len(current_values) != len(txt_records):
        raise ValueError(
            f"Eltérő sor darabszám a {csv_path.name} és {txt_path.name} között: "
            f"CSV={len(current_values)}, TXT minták={len(txt_records)}"
        )

    records: list[MeasurementRecord] = []
    for index, (voltage, count_value) in enumerate(txt_records):
        current_value = current_values[index] if index < len(current_values) else None
        records.append(
            MeasurementRecord(
                voltage=voltage,
                count=count_value,
                current_ma=current_value,
            )
        )

    if not records:
        raise ValueError(f"Nem sikerült mérési rekordokat kinyerni ebből: {txt_path}")

    return ChannelData(channel=channel, csv_path=csv_path or txt_path.with_suffix(".csv"), txt_path=txt_path, records=records)


def group_records_by_voltage(records: list[MeasurementRecord]) -> dict[float, list[MeasurementRecord]]:
    grouped: dict[float, list[MeasurementRecord]] = defaultdict(list)
    for record in records:
        grouped[record.voltage].append(record)
    return dict(sorted(grouped.items(), key=lambda item: item[0]))


def prepare_channel_palette(channels: list[int]) -> dict[int, str]:
    cmap = plt.get_cmap("tab10")
    return {channel: cmap(index % 10) for index, channel in enumerate(sorted(channels))}


def determine_voltage_tick_decimals(voltages: list[float]) -> int:
    unique_voltages = sorted(set(voltages))
    if len(unique_voltages) < 2:
        return 2

    min_step = min(
        b - a
        for a, b in zip(unique_voltages, unique_voltages[1:])
        if b - a > 0
    )
    if min_step >= 1:
        return 0
    if min_step >= 0.1:
        return 1
    return 2


def format_voltage_tick(value: float, decimals: int) -> str:
    return f"{value:.{decimals}f}"


def is_whole_or_half(value: float) -> bool:
    scaled = round(value * 2)
    return abs(value * 2 - scaled) < 1e-9


def style_voltage_tick_labels(tick_labels, tick_values: list[float]) -> None:
    for tick_label, tick_value in zip(tick_labels, tick_values):
        if is_whole_or_half(tick_value):
            tick_label.set_fontweight("semibold")
            tick_label.set_fontsize(tick_label.get_fontsize() + 2)
            x_position, y_position = tick_label.get_position()
            tick_label.set_position((x_position, y_position - 0.03))


def set_voltage_axis_ticks(ax, voltages: list[float]) -> None:
    if not voltages:
        return

    decimals = determine_voltage_tick_decimals(voltages)
    unique_voltages = sorted(set(voltages))
    ax.set_xticks(unique_voltages)
    tick_labels = ax.set_xticklabels([format_voltage_tick(voltage, decimals) for voltage in unique_voltages])
    style_voltage_tick_labels(tick_labels, unique_voltages)


def annotate_axis(ax, xlabel: str, ylabel: str, title: str) -> None:
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.25)


def prepare_log_count_axis(ax, count_values: list[float]) -> float:
    positive_values = [value for value in count_values if value > 0]
    lowest_positive = min(positive_values) if positive_values else 1.0
    floor_value = max(1.0, lowest_positive / 10.0)
    highest_value = max(max(count_values), lowest_positive) if count_values else 1.0

    ax.set_yscale("log", base=10, nonpositive="clip")
    ax.set_ylim(bottom=floor_value, top=max(highest_value * 1.25, floor_value * 10))

    formatter = ScalarFormatter()
    formatter.set_scientific(False)
    formatter.set_useOffset(False)
    ax.yaxis.set_major_formatter(formatter)

    if any(value <= 0 for value in count_values):
        ax.axhline(floor_value, color="gray", linestyle="--", linewidth=1.0, alpha=0.45)

    return floor_value


def compute_log_floor_value(count_values: list[float]) -> float:
    positive_values = [value for value in count_values if value > 0]
    lowest_positive = min(positive_values) if positive_values else 1.0
    return max(1.0, lowest_positive / 10.0)


def normalize_counts_for_log_display(count_values: list[float], floor_value: float) -> list[float]:
    return [value if value > 0 else floor_value for value in count_values]


def mean_by_voltage(records: list[MeasurementRecord]) -> list[tuple[float, float]]:
    grouped = group_records_by_voltage(records)
    return [(voltage, mean(record.count for record in voltage_records)) for voltage, voltage_records in grouped.items()]


def mean_current_by_voltage(records: list[MeasurementRecord]) -> list[tuple[float, float]]:
    grouped = group_records_by_voltage([record for record in records if record.current_ma is not None])
    return [
        (voltage, mean(record.current_ma for record in voltage_records if record.current_ma is not None))
        for voltage, voltage_records in grouped.items()
        if any(record.current_ma is not None for record in voltage_records)
    ]


def plot_voltage_count(channels: list[ChannelData], output_path: Path, diagram_title: str, suptitle: str) -> None:
    fig, ax = plt.subplots(figsize=(12, 7))
    palette = prepare_channel_palette([channel.channel for channel in channels])
    plotted_counts: list[float] = []
    plotted_voltages: list[float] = []

    for channel_data in channels:
        points = mean_by_voltage(channel_data.records)
        voltages = [point[0] for point in points]
        counts = [point[1] for point in points]
        plotted_voltages.extend(voltages)
        plotted_counts.extend(counts)
        color = palette[channel_data.channel]
        ax.scatter(voltages, counts, color=color, s=35, alpha=0.85, label=f"Ch{channel_data.channel}")
        ax.plot(voltages, counts, color=color, alpha=0.6, linewidth=1.5)

    floor_value = prepare_log_count_axis(ax, plotted_counts)
    for line in ax.lines:
        line.set_ydata(normalize_counts_for_log_display(list(line.get_ydata()), floor_value))
    for collection in ax.collections:
        offsets = collection.get_offsets()
        if len(offsets) == 0:
            continue
        offsets[:, 1] = [value if value > 0 else floor_value for value in offsets[:, 1]]
        collection.set_offsets(offsets)
    set_voltage_axis_ticks(ax, plotted_voltages)
    fig.suptitle(suptitle, fontsize=14, fontweight="bold")
    annotate_axis(ax, AXIS_VOLTAGE, AXIS_COUNT, diagram_title)
    ax.legend(title=LEGEND_CHANNELS)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def plot_voltage_current(channels: list[ChannelData], output_path: Path, diagram_title: str, suptitle: str) -> None:
    fig, ax = plt.subplots(figsize=(12, 7))
    palette = prepare_channel_palette([channel.channel for channel in channels])
    plotted_any = False
    plotted_voltages: list[float] = []

    for channel_data in channels:
        points = mean_current_by_voltage(channel_data.records)
        if not points:
            continue
        plotted_any = True
        voltages = [point[0] for point in points]
        currents = [point[1] for point in points]
        plotted_voltages.extend(voltages)
        color = palette[channel_data.channel]
        ax.scatter(voltages, currents, color=color, s=35, alpha=0.85, label=f"Ch{channel_data.channel}")
        ax.plot(voltages, currents, color=color, alpha=0.6, linewidth=1.5)

    if not plotted_any:
        plt.close(fig)
        return

    set_voltage_axis_ticks(ax, plotted_voltages)
    fig.suptitle(suptitle, fontsize=14, fontweight="bold")
    annotate_axis(ax, AXIS_VOLTAGE, AXIS_CURRENT, diagram_title)
    ax.legend(title=LEGEND_CHANNELS)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def plot_current_count(channels: list[ChannelData], output_path: Path, diagram_title: str, suptitle: str) -> None:
    fig, ax = plt.subplots(figsize=(12, 7))
    palette = prepare_channel_palette([channel.channel for channel in channels])
    plotted_any = False
    plotted_counts: list[float] = []

    for channel_data in channels:
        filtered_records = [record for record in channel_data.records if record.current_ma is not None]
        if not filtered_records:
            continue
        plotted_any = True
        color = palette[channel_data.channel]
        currents = [record.current_ma for record in filtered_records]
        counts = [record.count for record in filtered_records]
        plotted_counts.extend(counts)
        ax.scatter(currents, counts, color=color, s=24, alpha=0.7, label=f"Ch{channel_data.channel}")

    if not plotted_any:
        plt.close(fig)
        return

    floor_value = prepare_log_count_axis(ax, plotted_counts)
    for collection in ax.collections:
        offsets = collection.get_offsets()
        if len(offsets) == 0:
            continue
        offsets[:, 1] = [value if value > 0 else floor_value for value in offsets[:, 1]]
        collection.set_offsets(offsets)
    fig.suptitle(suptitle, fontsize=14, fontweight="bold")
    annotate_axis(ax, AXIS_CURRENT, AXIS_COUNT, diagram_title)
    ax.legend(title=LEGEND_CHANNELS)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def plot_boxplot(channels: list[ChannelData], output_path: Path, diagram_title: str, suptitle: str) -> None:
    fig, ax = plt.subplots(figsize=(13, 7))
    palette = prepare_channel_palette([channel.channel for channel in channels])
    # --- plotted_counts = [record.count for channel_data in channels for record in channel_data.records] ---
    # --- floor_value = compute_log_floor_value(plotted_counts) ---

    all_voltages = sorted({record.voltage for channel_data in channels for record in channel_data.records})
    if not all_voltages:
        raise ValueError("Nincsenek feszültségértékek a boxplothoz.")

    channel_count = len(channels)
    if channel_count == 1:
        offsets = {channels[0].channel: 0.0}
    else:
        total_width = 0.72
        step = total_width / max(channel_count - 1, 1)
        start = -total_width / 2
        offsets = {
            channel_data.channel: start + index * step
            for index, channel_data in enumerate(channels)
        }

    box_width = 0.12 if channel_count > 1 else 0.22
    legend_handles: list[Patch] = []

    for channel_data in channels:
        grouped = group_records_by_voltage(channel_data.records)
        color = palette[channel_data.channel]
        legend_handles.append(Patch(facecolor=color, edgecolor="black", label=f"Ch{channel_data.channel}"))

        for voltage in all_voltages:
            voltage_records = grouped.get(voltage)
            if not voltage_records:
                continue

            position = voltage + offsets[channel_data.channel]
            values = [record.count for record in voltage_records]
            ax.boxplot(
                # --- normalice_counts_for_log_display(values, floor_value) ---,
                values,
                positions=[position],
                widths=box_width,
                patch_artist=True,
                showfliers=False,
                boxprops={"facecolor": color, "alpha": 0.55, "edgecolor": "black"},
                medianprops={"color": "black", "linewidth": 1.4},
                whiskerprops={"color": color, "linewidth": 1.1},
                capprops={"color": color, "linewidth": 1.1},
            )

    ax.set_xticks(all_voltages)
    tick_labels = ax.set_xticklabels([f"{voltage:g}" for voltage in all_voltages])
    style_voltage_tick_labels(tick_labels, all_voltages)
    x_range = max(all_voltages) - min(all_voltages)
    x_padding = max(0.05, x_range * 0.02)
    ax.set_xlim(min(all_voltages) - x_padding, max(all_voltages) + x_padding)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    y_formatter = ScalarFormatter()
    y_formatter.set_scientific(False)
    y_formatter.set_useOffset(False)
    ax.yaxis.set_major_formatter(y_formatter)
    # --- prepare_lock_count_axis(ax, plotted_counts) ---
    fig.suptitle(suptitle, fontsize=14, fontweight="bold")
    annotate_axis(ax, AXIS_VOLTAGE, AXIS_COUNT, diagram_title)
    ax.legend(handles=legend_handles, title=LEGEND_CHANNELS, loc="best")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def ensure_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)


def evaluate_measurements(meresek_txt_dir: Path, meresek_csv_dir: Path, output_dir: Path, show_plots: bool) -> None:
    groups = list_measurement_groups(meresek_txt_dir, meresek_csv_dir)
    selected_group = choose_measurement_group(groups)
    channels = selected_group.channels
    ensure_output_dir(output_dir)

    metadata_path = resolve_metadata_path(Path(__file__).resolve().parent)
    metadata_by_prefix = load_measurement_metadata(metadata_path)
    measurement_name = resolve_measurement_title(selected_group, metadata_by_prefix)
    measurement_timestamp = resolve_measurement_timestamp(selected_group.prefix)

    voltage_count_path = output_dir / build_diagram_file_name(
        measurement_name,
        "feszultseg_beutes",
        measurement_timestamp,
    )
    boxplot_path = output_dir / build_diagram_file_name(
        measurement_name,
        "feszultseg_beutes_boxplot",
        measurement_timestamp,
    )
    voltage_current_path = output_dir / build_diagram_file_name(
        measurement_name,
        "feszultseg_aram",
        measurement_timestamp,
    )
    current_count_path = output_dir / build_diagram_file_name(
        measurement_name,
        "aram_beutes",
        measurement_timestamp,
    )

    plot_voltage_count(
        channels,
        voltage_count_path,
        build_diagram_title(measurement_name, "feszultseg_beutes", measurement_timestamp),
        measurement_name,
    )
    plot_boxplot(
        channels,
        boxplot_path,
        build_diagram_title(measurement_name, "feszultseg_beutes_boxplot", measurement_timestamp),
        measurement_name,
    )
    plot_voltage_current(
        channels,
        voltage_current_path,
        build_diagram_title(measurement_name, "feszultseg_aram", measurement_timestamp),
        measurement_name,
    )
    plot_current_count(
        channels,
        current_count_path,
        build_diagram_title(measurement_name, "aram_beutes", measurement_timestamp),
        measurement_name,
    )

    print(f"Elkészültek a diagramok ide: {output_dir}")
    print(f"- {voltage_count_path.name}")
    print(f"- {boxplot_path.name}")
    print(f"- {voltage_current_path.name}")
    print(f"- {current_count_path.name}")

    if show_plots:
        plt.show()


def main() -> None:
    args = parse_args()
    meresek_txt_dir = resolve_meresek_txt_dir(args.meresek_txt_dir)
    meresek_csv_dir = resolve_meresek_csv_dir(args.meresek_csv_dir)
    output_dir = resolve_output_dir(meresek_csv_dir, args.output_dir)
    evaluate_measurements(meresek_txt_dir, meresek_csv_dir, output_dir, args.show)


if __name__ == "__main__":
    main()