import time
import os
import sys
from pathlib import Path

# A szkript a meglévő vezerlo.py modulból használja a vezérlőt.
# Ha ezt a fájlt a projekt gyökérből futtatod, ez a sor biztosítja, hogy a same-folder modulok elérhetők legyenek.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vezerlo import MeasurementController, IDQ_ADDRESS, TAP_ADDRESSUSB, output_dir_txt, output_dir_csv


# -----------------------------------------------------------------------------
# GLOBÁLIS MÉRÉSI PARAMÉTEREK
# -----------------------------------------------------------------------------
# Ide írhatod be a mérési sorozatot. A script a listában lévő elemeket
# egymás után futtatja le, a vezérlő többször futtatása nélkül.
#
# Minden mérés egy dict, amelynek mezői:
#   - name: a mérés neve (opcionális)
#   - channels: kiválasztott csatornák listája, például [1, 2]
#   - fesz_start: kezdő feszültség [V]
#   - fesz_end: végső feszültség [V]
#   - fesz_step: lépésköz [V]
#   - db_start: kezdő csillapítás [dB]
#   - db_end: végső csillapítás [dB]
#   - db_step: csillapítás lépésköz [dB]
#
# Példa:
#   MEASUREMENT_SEQUENCE = [
#       {"name": "1. mérés", "channels": [1, 2], "fesz_start": 1.0, "fesz_end": 2.0, "fesz_step": 0.1, "db_start": 10, "db_end": 15, "db_step": 2},
#       {"name": "2. mérés", "channels": [1, 2], "fesz_start": 2.2, "fesz_end": 3.0, "fesz_step": 0.1, "db_start": 8, "db_end": 12, "db_step": 1},
#   ]

MEASUREMENT_SEQUENCE = [
    {
        "name": "DCR felterkepezes",
        "channels": [1, 2, 3, 4],
        "fesz_start": 1.0,
        "fesz_end": 3.0,
        "fesz_step": 0.02,
    },
    {
        "name": "DCR specifialt",
        "channels": [1, 2, 3, 4],
        "fesz_start": 1.0,
        "fesz_end": 2.0,
        "fesz_step": 0.005,
    },
]

def generate_values(start, end, step):
    """Létrehoz egy [start, end] intervallumban lévő értéksorozatot step méretben."""
    if step <= 0:
        raise ValueError(f"A lépésköznek pozitívnak kell lennie: {step}")
    if end < start:
        raise ValueError(f"A végérték nem lehet kisebb a kezdőértéknél: {start} -> {end}")

    values = []
    current = float(start)
    eps = abs(step) * 1e-6
    while current <= float(end) + eps:
        values.append(round(current, 6))
        current += float(step)

    if not values:
        values = [round(float(start), 6)]
    return values


def build_channel_steps_for_measurement(measurement):
    """Egy méréshez felépíti a controller.channel_steps formátumát."""
    selected_channels = measurement.get("channels", [1])
    if not selected_channels:
        raise ValueError(f"A mérésben nincs kiválasztott csatorna: {measurement}")

    fesz_values = generate_values(
        measurement["fesz_start"],
        measurement["fesz_end"],
        measurement["fesz_step"],
    )
    db_values = generate_values(
        measurement["db_start"],
        measurement["db_end"],
        measurement["db_step"],
    )

    channel_steps = {}
    for ch in selected_channels:
        steps = []
        for voltage in fesz_values:
            for db in db_values:
                steps.append({"fesz": voltage, "db": db})
        channel_steps[ch] = steps

    return channel_steps


def run_measurements_sequentially(controller, measurements=None):
    """A vezérlő egyetlen példányával lefuttatja a sorozatot."""
    if measurements is None:
        measurements = MEASUREMENT_SEQUENCE

    if not measurements:
        raise ValueError("Nincs megadva mérési sorozat.")

    for index, measurement in enumerate(measurements, start=1):
        name = measurement.get("name", f"{index}. mérés")
        channels = measurement.get("channels", [1])

        controller.channel_steps = build_channel_steps_for_measurement(measurement)
        controller.log_callback(f"\n=== {name} ({index}/{len(measurements)}) ===")
        controller.log_callback(
            f"Csatornák: {channels}; fesz: {measurement['fesz_start']} -> {measurement['fesz_end']} / {measurement['fesz_step']} V; "
            f"db: {measurement['db_start']} -> {measurement['db_end']} / {measurement['db_step']} dB"
        )

        controller.start(channels)
        while controller.fut:
            time.sleep(0.5)

        time.sleep(1.0)

    controller.log_callback("\n=== Minden mérés lefutott. ===")


def main():
    controller = MeasurementController(
        idq_address=IDQ_ADDRESS,
        tap_address=TAP_ADDRESSUSB,
        output_dir=output_dir_txt,
        step_time=5,
        log_callback=lambda message: print(message),
        on_finished=lambda: None,
        on_error=lambda error: print(f"HIBA: {error}"),
    )

    print("Mérési sorozat indítása...")
    run_measurements_sequentially(controller, MEASUREMENT_SEQUENCE)


if __name__ == "__main__":
    main()
