from urllib import response

import zmq
import os
import time
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox
from datetime import datetime
from contextlib import ExitStack
from power_source import PowerSupply


# --- MÉRÉSI PARAMÉTEREK ---
#TAP_ADDRESS = 'tcp://169.254.35.236:1026'
IDQ_ADDRESS = 'tcp://172.26.34.114:5555'
TAP_ADDRESSUSB = "ASRL5::INSTR"
BAUD_RATE = 115200

output_dir = os.path.join(os.path.dirname(__file__), "meresek")
LEPES_IDO = 5  #s
RESTORE_MEMORY_REGISTER = 1

class ZMQInstrument:
    def __init__(self, context, address, timeout_ms=5000):
        self.address = address
        self.timeout_ms = timeout_ms
        self._sock = context.socket(zmq.REQ)
        self._sock.setsockopt(zmq.LINGER, 0)
        self._sock.setsockopt(zmq.RCVTIMEO, timeout_ms)
        self._sock.connect(address)

    def test_connection(self):
        """Teszteli a kapcsolatot egy egyszerű query paranccsal."""
        return True, "Válasz érkezett!"
        try:
            self._sock.send_string("*IDN?")
            response = self._sock.recv_string()
            if response:
                return True, f"Válasz érkezett: {response[:50]}..."
            else:
                return False, "Üres válasz érkezett."
        except zmq.error.Again:
            return False, "Timeout: az eszköz nem válaszol (időtúllépés)."
        except Exception as e:
            return False, f"Kapcsolati hiba: {str(e)}"

    def write(self, cmd: str):
        try:
            self._sock.send_string(cmd)
            try:
                _ = self._sock.recv_string()
            except zmq.error.Again:
                pass
        except Exception:
            pass

class MeasurementController:
    def __init__(
        self,
        idq_address,
        tap_address,
        output_dir,
        step_time,
        step_definitions=None,
        log_callback=None,
        on_finished=None,
        on_error=None,
    ):
        self.idq_address = idq_address
        self.tap_address = tap_address
        self.baud_rate = BAUD_RATE
        self.output_dir = output_dir
        self.step_time = step_time
        self.channel_steps = step_definitions or {}
        self.log_callback = log_callback
        self.on_finished = on_finished
        self.on_error = on_error
        self.fut = False
        self.leallitas_kerve = False

    def start(self, selected_channels):
        if self.fut:
            return
        self.fut = True
        self.leallitas_kerve = False
        szal = threading.Thread(
            target=self.run_measurement,
            args=(selected_channels,),
            daemon=True,
        )
        szal.start()

    def stop(self):
        if self.fut:
            self.leallitas_kerve = True
            if self.log_callback is not None:
                self.log_callback("Mérés leállítása kérve...")

    def write_step_header(self, file_handle, feszultseg, csillapitas):
        header = f"\nfeszültség: {feszultseg} V; csillapítás: {csillapitas} dB:\n"
        file_handle.write(header)
        file_handle.flush()

    def format_step_label(self, channel, step):
        return (
            f"Ch{channel}: feszültség: {step['fesz']} V; csillapítás: {step['db']} dB"
        )

    def get_channel_step(self, channel, step_index):
        steps = self.channel_steps.get(channel, [])
        if not steps:
            return None
        if step_index < len(steps):
            return steps[step_index]
        return steps[-1]

    def get_max_step_count(self, selected_channels):
        max_steps = 0
        for ch in selected_channels:
            max_steps = max(max_steps, len(self.channel_steps.get(ch, [])))
        return max_steps

    def collect_step_map(self, selected_channels, step_index):
        step_map = {}
        for ch in selected_channels:
            step = self.get_channel_step(ch, step_index)
            if step is not None:
                step_map[ch] = step
        return step_map

    def write_step_outputs(self, all_file_handle, channel_file_handles, step_map):
        if self.log_callback is not None:
            self.log_callback("\n\n")
        all_file_handle.write("\n\n")
        all_file_handle.flush()

        for ch, step in step_map.items():
            self.write_step_header(channel_file_handles[ch], step['fesz'], step['db'])

    def apply_step_to_tap(self, tap, step_map):
        tap.ps.write('*CLS\n')
        time.sleep(0.05)
        for ch, step in step_map.items():
            #tap.turn_channel_on_off(False, all_channels=False, channels=[ch])
            tap.ps.write(f':SOURce{ch}:VOLTage {step["fesz"]}\n')
            tap.ps.write(f':SOURce{ch}:APPLy\n')
            tap.ps.write(f':SOURce{ch}:STATe ON\n')
            tap.ps.write(f':OUTPut{ch}:STATe ON\n')
            #tap.turn_channel_on_off(True, all_channels=False, channels=[ch])
        time.sleep(0.5)

    def write_measurement_samples(self, t_c, selected_channels, all_file_handle, channel_file_handles):
        csatorna_szamlalok = self.sample_channels(t_c, selected_channels)
        timestamp = time.strftime('%Y.%m.%d. %H:%M:%S')
        counter_str = ' '.join([f"Ch{ch}:{csatorna_szamlalok[ch]:,}".replace(',', '.') for ch in selected_channels])
        log_line = f"{timestamp} --- {counter_str}"

        if self.log_callback is not None:
            self.log_callback(log_line)
        all_file_handle.write(log_line + "\n")
        all_file_handle.flush()

        for ch in selected_channels:
            ch_line = f"{timestamp} --- CH{ch}: {csatorna_szamlalok[ch]:,}".replace(',', '.')
            channel_file_handles[ch].write(ch_line + "\n")
            channel_file_handles[ch].flush()

    def sample_channels(self, idq_card, selected_channels):
        csatorna_szamlalok = {}
        for ch in selected_channels:
            try:
                idq_card._sock.send_string(f'INPUt{ch}:COUNter?')
                raw_data = idq_card._sock.recv_string()
                n = int(raw_data.strip())
            except Exception:
                n = 0
            csatorna_szamlalok[ch] = n
        return csatorna_szamlalok

    def restore_tap_outputs(self, tapegyseg):
        try:
            tapegyseg.load_memory_register(RESTORE_MEMORY_REGISTER)
            if self.log_callback is not None:
                self.log_callback(f"Tápegység visszaállítva az {RESTORE_MEMORY_REGISTER}-es memóriaregiszterből.")
        except Exception as exc:
            if self.log_callback is not None:
                self.log_callback(f"Hiba a tápegység visszaállítása vagy kikapcsolása közben: {exc}")

    def turn_off_tap_channels(self, tapegyseg, selected_channels):
        try:
            if hasattr(tapegyseg, 'turn_channel_on_off'):
                tapegyseg.turn_channel_on_off(False, all_channels=False, channels=selected_channels)
            else:
                for ch in selected_channels:
                    tapegyseg.ps.write(f':OUTPut{ch}:STATe OFF')

            for ch in selected_channels:
                if self.log_callback is not None:
                    self.log_callback(f"Tápegység Ch{ch} kikapcsolva.")
        except Exception as exc:
            if self.log_callback is not None:
                self.log_callback(f"Hiba a tápegység csatornáinak kikapcsolása közben: {exc}")

    def process_measurement_steps(self, tap, t_c, selected_channels, all_file_handle, channel_file_handles):
        max_steps = self.get_max_step_count(selected_channels)

        for step_index in range(max_steps):
            if self.leallitas_kerve:
                if self.log_callback is not None:
                    self.log_callback("Mérés megszakítva a felhasználó által.")
                break

            step_map = self.collect_step_map(selected_channels, step_index)

            if not step_map:
                break

            self.write_step_outputs(all_file_handle, channel_file_handles, step_map)
            self.apply_step_to_tap(tap, step_map)

            start_time = time.time()
            while (time.time() - start_time) < self.step_time:
                if self.leallitas_kerve:
                    break

                self.write_measurement_samples(t_c, selected_channels, all_file_handle, channel_file_handles)

                time.sleep(1)

            if self.leallitas_kerve:
                break

    def run_measurement(self, selected_channels):
        tap = None
        t_c = None
        context = None

        try:
            context = zmq.Context()
            if self.log_callback is not None:
                self.log_callback(f"Kapcsolódás (ZMQ): {self.idq_address} ...")
            try:
                t_c = ZMQInstrument(context, self.idq_address)
                success, msg = t_c.test_connection()
                if not success:
                    raise ConnectionError(f"IDQ eszköz ({self.idq_address}) - {msg}")
                if self.log_callback is not None:
                    self.log_callback(f"✓ IDQ eszköz elérhető. {msg}")
            except Exception as e:
                raise ConnectionError(f"IDQ eszköz ({self.idq_address}) kapcsolati hiba: {str(e)}")
            if self.log_callback is not None:
                self.log_callback(f"Kapcsolódás a tápegységhez: {self.tap_address} ...")
            try:
                if isinstance(self.tap_address, str) and self.tap_address.upper().startswith("ASRL"):
                    tap = PowerSupply(self.tap_address, self.baud_rate)
                    try:
                        _ = tap.ps.query('*IDN?\n')
                        if self.log_callback is not None:
                            self.log_callback("✓ Tápegység (USB) elérhető.")
                    except Exception as e:
                        raise ConnectionError(f"TAP USB eszköz nem válaszol: {e}")
                else:
                    tap = ZMQInstrument(context, self.tap_address)
                    success, msg = tap.test_connection()
                    if not success:
                        raise ConnectionError(f"TAP eszköz ({self.tap_address}) - {msg}")
                    if self.log_callback is not None:
                        self.log_callback(f"✓ TAP eszköz elérhető. {msg}")
            except Exception as e:
                raise ConnectionError(f"TAP eszköz ({self.tap_address}) kapcsolati hiba: {str(e)}")
            
            for ch in selected_channels:
                try:
                    t_c.write(f'INPUt{ch}:counter:MODE CYCLE')
                except Exception:
                    pass
            try:
                tap.turn_channel_on_off(True, all_channels=False, channels=selected_channels)
            except Exception:
                pass
            if self.log_callback is not None:
                self.log_callback("Műszerek készen állnak. Kimenetek BE.")

            os.makedirs(self.output_dir, exist_ok=True)

            all_file_path, channel_file_paths = self.build_output_paths(selected_channels)

            with ExitStack() as stack:
                all_file_handle = stack.enter_context(open(all_file_path, 'w', encoding='utf-8', buffering=1))
                channel_file_handles = {ch: stack.enter_context(open(path, 'w', encoding='utf-8', buffering=1)) for ch, path in channel_file_paths.items()}

                self.process_measurement_steps(
                    tap,
                    t_c,
                    selected_channels,
                    all_file_handle,
                    channel_file_handles,
                )

            if self.log_callback is not None:
                self.log_callback(f"Összesített fájl: {all_file_path}")
            for ch in selected_channels:
                if self.log_callback is not None:
                    self.log_callback(f"Csatornafájl Ch{ch}: {channel_file_paths[ch]}")

            if self.log_callback is not None:
                self.log_callback("\n--- Mérés vége. Visszaállás az 1-es memóriaregiszterből. ---")
            self.restore_tap_outputs(tap)
            self.turn_off_tap_channels(tap, selected_channels)

            if self.on_finished is not None:
                self.on_finished()

        except Exception as e:
            if self.log_callback is not None:
                self.log_callback(f"HIBA: {str(e)}")
            if self.on_error is not None:
                self.on_error(e)

        finally:
            if t_c is not None:
                try:
                    t_c._sock.close()
                except Exception:
                    pass
            if tap is not None:
                tap.ps.close()
                tap.close_power_supply()
            if context is not None:
                try:
                    context.term()
                except Exception:
                    pass
            self.fut = False

    def build_output_paths(self, selected_channels):
        meres_ido = datetime.now().strftime("%Y.%m.%d_%H.%M")
        all_file_path = os.path.join(self.output_dir, f"{meres_ido}_meres.txt")
        channel_file_paths = {
            ch: os.path.join(self.output_dir, f"{meres_ido}_CH{ch}_meres.txt")
            for ch in selected_channels
        }
        return all_file_path, channel_file_paths

class SNSPDControlGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SNSPD Feszültség Szabályozó és Naplózó")
        self.root.geometry("980x760")
        self.label = tk.Label(root, text="SNSPD Mérési Folyamat", font=("Arial", 14, "bold"))
        self.label.pack(pady=10)
        csatorna_keret = tk.Frame(root)
        csatorna_keret.pack(pady=5)
        self.csatorna_valtozok = []
        self.channel_frames = {}
        self.channel_param_vars = {}
        for i in range(4):
            var = tk.IntVar(value=1)
            cb = tk.Checkbutton(csatorna_keret, text=f"Ch{i+1}", variable=var)
            cb.pack(side=tk.LEFT, padx=5)
            self.csatorna_valtozok.append(var)
            var.trace_add("write", lambda *_args, ch=i + 1: self.toggle_channel_config_visibility(ch))

        self.channel_config_container = tk.Frame(root)
        self.channel_config_container.pack(fill=tk.X, padx=10, pady=10)
        for i in range(1, 5):
            self.create_channel_config_block(i)

        self.inditas_gomb = tk.Button(root, text="Mérés Indítása", command=self.start_thread, bg="green", fg="white", font=("Arial", 12))
        self.inditas_gomb.pack(pady=5)

        self.leallitas_gomb = tk.Button(root, text="Mérés Leállítása", command=lambda: self.controller.stop(), bg="red", fg="white", font=("Arial", 12))
        self.leallitas_gomb.pack(pady=5)
        self.leallitas_gomb.config(state=tk.DISABLED)

        self.naplo_terulet = scrolledtext.ScrolledText(root, width=70, height=15)
        self.naplo_terulet.pack(pady=10, padx=10)

        self.controller = MeasurementController(
            idq_address=IDQ_ADDRESS,
            tap_address=TAP_ADDRESSUSB,
            output_dir=output_dir,
            step_time=LEPES_IDO,
            log_callback=lambda message: self.root.after(0, lambda: (self.naplo_terulet.insert(tk.END, message + "\n"), self.naplo_terulet.see(tk.END))),
            on_finished=lambda: self.root.after(0, lambda: (
                self.inditas_gomb.config(state=tk.NORMAL),
                self.leallitas_gomb.config(state=tk.DISABLED),
                self.channel_config_container.pack(fill=tk.X, padx=10, pady=10),
                messagebox.showinfo("Kész", "A mérési sorozat lefutott. A tápegység visszaállt az 1-es memóriaregiszterből, majd a csatornák kikapcsoltak.")
            )),
            on_error=lambda error: self.root.after(0, lambda: (
                self.inditas_gomb.config(state=tk.NORMAL),
                self.leallitas_gomb.config(state=tk.DISABLED),
                messagebox.showerror("Hiba", f"Hiba történt: {error}")
            )),
        )

    def create_channel_config_block(self, ch):
        frame = tk.LabelFrame(self.channel_config_container, text=f"Ch{ch} beállítások", padx=8, pady=6)
        frame.pack(fill=tk.X, pady=5)

        values = {
            'fesz_min': tk.StringVar(value="1.0"),
            'fesz_max': tk.StringVar(value="1.2"),
            'fesz_step': tk.StringVar(value="0.1"),
            'db_min': tk.StringVar(value="10"),
            'db_max': tk.StringVar(value="15"),
            'db_step': tk.StringVar(value="2"),
        }
        self.channel_frames[ch] = frame
        self.channel_param_vars[ch] = values

        params = [
            ("Feszültség (V)", 'fesz_min', 'fesz_max', 'fesz_step'),
            ("Csillapítás (dB)", 'db_min', 'db_max', 'db_step'),
        ]
        for label, min_key, max_key, step_key in params:
            param_frame = tk.Frame(frame)
            param_frame.pack(side=tk.LEFT, padx=10, pady=2)
            tk.Label(param_frame, text=label, font=("Arial", 9)).pack()
            values_frame = tk.Frame(param_frame)
            values_frame.pack()
            tk.Label(values_frame, text="Min:", font=("Arial", 8)).pack(side=tk.LEFT, padx=2)
            tk.Entry(values_frame, width=6, textvariable=values[min_key]).pack(side=tk.LEFT, padx=2)
            tk.Label(values_frame, text="Max:", font=("Arial", 8)).pack(side=tk.LEFT, padx=2)
            tk.Entry(values_frame, width=6, textvariable=values[max_key]).pack(side=tk.LEFT, padx=2)
            tk.Label(values_frame, text="Lépés:", font=("Arial", 8)).pack(side=tk.LEFT, padx=2)
            tk.Entry(values_frame, width=6, textvariable=values[step_key]).pack(side=tk.LEFT, padx=2)

    def toggle_channel_config_visibility(self, ch):
        frame = self.channel_frames.get(ch)
        if frame is None:
            return

        try:
            selected = bool(self.csatorna_valtozok[ch - 1].get())
        except Exception:
            selected = False

        if selected:
            frame.pack(fill=tk.X, pady=5)
        else:
            frame.pack_forget()

    def generate_values(self, min_v, max_v, step_v):
        if step_v <= 0:
            raise ValueError("A lépésköznek pozitívnak kell lennie.")
        if max_v < min_v:
            raise ValueError("A max érték nem lehet kisebb a min értéknél.")

        values = []
        value = min_v
        eps = abs(step_v) * 1e-6
        while value <= max_v + eps:
            values.append(round(value, 6))
            value += step_v

        if not values:
            values = [round(min_v, 6)]
        return values

    def build_channel_steps(self, selected_channels):
        channel_steps = {}
        for ch in selected_channels:
            values = self.channel_param_vars[ch]

            v_min = float(values['fesz_min'].get())
            v_max = float(values['fesz_max'].get())
            v_step = float(values['fesz_step'].get())

            db_min = float(values['db_min'].get())
            db_max = float(values['db_max'].get())
            db_step = float(values['db_step'].get())

            v_values = self.generate_values(v_min, v_max, v_step)
            db_values = self.generate_values(db_min, db_max, db_step)

            count = max(len(v_values), len(db_values))
            steps = []
            for i in range(count):
                v = v_values[min(i, len(v_values) - 1)]
                db = db_values[min(i, len(db_values) - 1)]
                steps.append({'fesz': v, 'db': db})

            channel_steps[ch] = steps

        return channel_steps

    def start_thread(self):
        if not self.controller.fut:
            try:
                selected_channels = [i + 1 for i, v in enumerate(self.csatorna_valtozok) if v.get()]
                if not selected_channels:
                    raise ValueError("Legalább egy csatornát ki kell választani.")

                channel_steps = self.build_channel_steps(selected_channels)
                if not channel_steps:
                    raise ValueError("Nem sikerült csatornánkénti léptetési listát létrehozni.")

                self.controller.channel_steps = channel_steps

                self.inditas_gomb.config(state=tk.DISABLED)
                self.leallitas_gomb.config(state=tk.NORMAL)
                self.channel_config_container.pack_forget()
                self.controller.start(selected_channels)
            except Exception as exc:
                messagebox.showerror("Hibás beállítás", str(exc))

if __name__ == "__main__":
    root = tk.Tk()
    app = SNSPDControlGUI(root)
    root.mainloop()