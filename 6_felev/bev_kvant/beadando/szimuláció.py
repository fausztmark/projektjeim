import tkinter as tk
from tkinter import messagebox
import time
import random
from qiskit import QuantumCircuit, transpile
from qiskit_aer import Aer

nodes = {}
connections = []
connection_value_labels = {}
eve_arrows = {}
eve_arrow_activated = set()
connection_ever_active = set()
output_frame = None
node_counter = 0
first_selection = None
second_selection = None
Eve_mode = False
selected_tap_connection = None
active_Eve = None
move_mode = False
move_selected_node = None
bb84_mode = False
message_mode = False
message_source = None
message_target = None
connection_last_key_bits = {}
bb84_connection_data = {}
connection_security = {}
BUTTON_ONE_EVENT = "<Button-1>"

def clear_node_selection_outline():
    for nid in nodes:
        canvas.itemconfig(nodes[nid]["rect"], outline="black", width=2)

def highlight_node(n_id, color="#00f2ff"):
    clear_node_selection_outline()
    canvas.itemconfig(nodes[n_id]["rect"], outline=color, width=4)

def update_connection_positions():
    for n1, n2, line_id, _, _ in connections:
        canvas.coords(line_id, nodes[n1]["x"], nodes[n1]["y"], nodes[n2]["x"], nodes[n2]["y"])
    refresh_eve_arrows()

def _delete_eve_arrow(line_id):
    if line_id in eve_arrows:
        canvas.delete(eve_arrows[line_id])
        del eve_arrows[line_id]
    eve_arrow_activated.discard(line_id)

def _sync_eve_arrow(line_id, n1, n2, is_tapped, tapped_by):
    if not is_tapped or tapped_by not in nodes or nodes[tapped_by]["type"] != "Eve":
        _delete_eve_arrow(line_id)
        return

    x1 = nodes[tapped_by]["x"]
    y1 = nodes[tapped_by]["y"]
    x2 = (nodes[n1]["x"] + nodes[n2]["x"]) / 2
    y2 = (nodes[n1]["y"] + nodes[n2]["y"]) / 2
    color = "red" if line_id in eve_arrow_activated else "gray"

    if line_id in eve_arrows:
        arrow_id = eve_arrows[line_id]
        canvas.coords(arrow_id, x1, y1, x2, y2)
        canvas.itemconfig(arrow_id, fill=color, width=2, arrow=tk.LAST)
    else:
        eve_arrows[line_id] = canvas.create_line(x1, y1, x2, y2, fill=color, width=2, arrow=tk.LAST)

    canvas.tag_raise(eve_arrows[line_id])

def refresh_eve_arrows():
    valid_line_ids = {line_id for _, _, line_id, _, _ in connections}
    for line_id in eve_arrows.keys():
        if line_id not in valid_line_ids:
            _delete_eve_arrow(line_id)

    for n1, n2, line_id, is_tapped, tapped_by in connections:
        _sync_eve_arrow(line_id, n1, n2, is_tapped, tapped_by)

def _remove_target_connections(target):
    kept_connections = []

    for n1, n2, line_id, is_tapped, tapped_by in connections:
        if n1 == target or n2 == target:
            canvas.delete(line_id)
            connection_ever_active.discard(line_id)
            eve_arrow_activated.discard(line_id)
            connection_last_key_bits.pop(line_id, None)
            bb84_connection_data.pop(line_id, None)
            connection_security.pop(line_id, None)
            continue

        cleaned_tapped_by = None if tapped_by == target else tapped_by
        kept_connections.append((n1, n2, line_id, is_tapped, cleaned_tapped_by))

    return kept_connections

def _clear_target_selection(target):
    global first_selection, second_selection, move_selected_node, active_Eve

    if first_selection == target:
        first_selection = None
    if second_selection == target:
        second_selection = None
    if move_selected_node == target:
        move_selected_node = None
    if active_Eve == target:
        active_Eve = None

def _handle_message_mode_selection(n_id):
    global message_source, message_target

    if message_source is None:
        if not is_node_in_active_connection(n_id):
            lbl_status.config(text="Ez a gép még nem volt aktív kapcsolatban. Válassz másikat!", fg="red")
            return

        message_source = n_id
        highlight_node(n_id, color="#4b0082")
        lbl_status.config(text=f"Forrás: {n_id}. Válaszd ki a célt (aktív kapcsolatban legyen vele)!", fg="#4b0082")
        return

    if n_id == message_source:
        lbl_status.config(text="A cél nem lehet ugyanaz, mint a forrás.", fg="red")
        return

    if not has_active_connection_between(message_source, n_id):
        lbl_status.config(text="A két gép között nincs már aktív kapcsolat. Válassz másik célt!", fg="red")
        return

    message_target = n_id
    canvas.itemconfig(nodes[n_id]["rect"], outline="#4b0082", width=4)
    src, dst = message_source, message_target
    deactivate_message_mode(status_text=f"Üzenetablak megnyitva: {src} -> {dst}", status_color="#4b0082")
    show_message_window(src, dst)

def _handle_move_mode_selection(n_id):
    global move_selected_node

    move_selected_node = n_id
    highlight_node(n_id, color="#ff9800")
    lbl_status.config(text=f"Mozgatandó gép: {n_id}. Kattints új helyre!", fg="#b35a00")
    return True

def _handle_default_node_selection(n_id):
    global first_selection, second_selection

    if first_selection is None:
        first_selection = n_id
        highlight_node(n_id, color="#00f2ff")
        lbl_status.config(text=f"Első gép: {first_selection}. Válassz egy másodikat!")
        return

    if second_selection is None:
        if n_id == first_selection:
            lbl_status.config(text="Hiba: Ugyanazt a gépet választottad!", fg="red")
            first_selection = None
            canvas.itemconfig(nodes[n_id]["rect"], outline="black", width=2)
            return

        second_selection = n_id
        canvas.itemconfig(nodes[n_id]["rect"], outline="#00f2ff", width=4)
        lbl_status.config(text=f"Második gép: {second_selection}. Kattints a KAPCSOLAT gombra!")

def _finalize_connection_visuals(line_id, n1, n2, is_tapped, tapped_by, outcome_bit, conn_index):
    canvas.itemconfig(nodes[n1]["led"], fill="#00ff00")
    canvas.itemconfig(nodes[n2]["led"], fill="#00ff00")
    if is_tapped and tapped_by in nodes and nodes[tapped_by]["type"] == "Eve":
        canvas.itemconfig(nodes[tapped_by]["led"], fill="#00ff00")

    if line_id in connection_value_labels:
        sec = connection_security.get(line_id, {})
        status = sec.get("status", "UNKNOWN")
        prob = sec.get("prob", 0)
        connection_value_labels[line_id].config(
            text=f"{conn_index}. {n1} - {n2} : |{outcome_bit}> | {status} ({prob:.1f}%)",
            fg="green",
        )

    canvas.itemconfig(line_id, fill="red" if is_tapped else "#28a745", width=2 if not is_tapped else 1, dash=())
    if line_id in eve_arrows:
        canvas.itemconfig(eve_arrows[line_id], fill="red" if line_id in eve_arrow_activated else "gray", width=2)

def _simulate_connection_step(backend, conn_index, connection):
    n1, n2, line_id, is_tapped, tapped_by = connection

    canvas.itemconfig(line_id, width=4)
    canvas.itemconfig(line_id, fill="red" if is_tapped else "#00f2ff")
    lbl_status.config(text=f"Adatátvitel: {n1} - {n2}")

    if line_id in eve_arrows:
        canvas.itemconfig(eve_arrows[line_id], fill="red" if is_tapped else "gray", width=2)
        if is_tapped:
            eve_arrow_activated.add(line_id)

    root.update()
    time.sleep(0.5)

    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)

    if is_tapped:
        qc.measure_all()
        root.update()
        time.sleep(0.3)

    qc.measure([0, 1], [0, 1])
    job = backend.run(transpile(qc, backend), shots=1)
    outcome = list(job.result().get_counts().keys())[0]

    connection_ever_active.add(line_id)
    connection_last_key_bits[line_id] = outcome[0]

    _finalize_connection_visuals(line_id, n1, n2, is_tapped, tapped_by, outcome[0], conn_index)
    root.update()
    time.sleep(0.3)

def refresh_connection_value_labels():
    if output_frame is None:
        return

    connection_value_labels.clear()

    for child in output_frame.winfo_children():
        child.destroy()

    if not connections:
        tk.Label(output_frame, text="Kapcsolati állapotok: -", font=("Courier", 10, "bold"), bg="#f0f0f0").pack(anchor="w", padx=10)
        return

    for idx, (n1, n2, line_id, _, _) in enumerate(connections, start=1):
        sec = connection_security.get(line_id, {})
        status = sec.get("status", "UNKNOWN")
        prob = sec.get("prob", 0)
        lbl = tk.Label(
            output_frame,
            text=f"{idx}. {n1} - {n2} : - | {status} ({prob:.1f}%)",
            font=("Courier", 10, "bold"),
            bg="#f0f0f0",
            anchor="w",
        )
        lbl.pack(fill="x", padx=10, anchor="w")
        connection_value_labels[line_id] = lbl

def get_connection_is_tapped(line_id):
    for _, _, lid, is_tapped, _ in connections:
        if lid == line_id:
            return is_tapped
    return False

def get_status_from_qber(qber):
    if qber < 8:
        return "SECURE", "#198754"
    if qber < 18:
        return "SUSPECTED", "#fd7e14"
    return "COMPROMISED", "#dc3545"

def probability_bar(prob):
    slots = 20
    filled = int(round((prob / 100) * slots))
    filled = max(0, min(slots, filled))
    return "[" + ("#" * filled) + ("-" * (slots - filled)) + "]"

def update_connection_security(line_id):
    is_tapped = get_connection_is_tapped(line_id)
    qber = random.uniform(14.0, 30.0) if is_tapped else random.uniform(0.5, 6.0)
    target_prob = min(100.0, (qber / 30.0) * 100.0)

    previous = connection_security.get(line_id, {}).get("prob", 0.0)
    prob = (0.7 * previous) + (0.3 * target_prob)
    status, color = get_status_from_qber(qber)

    connection_security[line_id] = {
        "qber": qber,
        "prob": prob,
        "status": status,
        "color": color,
    }
    return connection_security[line_id]

def move_node_to(n_id, new_x, new_y):
    canvas_w = int(canvas["width"])
    canvas_h = int(canvas["height"])

    cx = max(50, min(canvas_w - 50, new_x))
    cy = max(40, min(canvas_h - 40, new_y))

    canvas.coords(nodes[n_id]["rect"], cx - 50, cy - 40, cx + 50, cy + 40)
    canvas.coords(nodes[n_id]["text"], cx, cy - 25)
    canvas.coords(nodes[n_id]["led"], cx - 10, cy, cx + 10, cy + 20)

    nodes[n_id]["x"] = cx
    nodes[n_id]["y"] = cy
    update_connection_positions()

def deactivate_move_mode(status_text=None, status_color="black"):
    global move_mode, move_selected_node
    move_mode = False
    move_selected_node = None
    btn_move.config(text="MOVE", bg="#ffc107", fg="black")
    clear_node_selection_outline()
    if status_text is not None:
        lbl_status.config(text=status_text, fg=status_color)

def deactivate_bb84_mode(status_text=None, status_color="black"):
    global bb84_mode
    bb84_mode = False
    btn_bb84.config(text="BB84", bg="#17a2b8", fg="white")
    refresh_connection_visuals()
    clear_node_selection_outline()
    if status_text is not None:
        lbl_status.config(text=status_text, fg=status_color)

def get_connection_line_id(n1, n2):
    for a, b, line_id, _, _ in connections:
        if (a == n1 and b == n2) or (a == n2 and b == n1):
            return line_id
    return None

def is_node_in_active_connection(n_id):
    for a, b, line_id, _, _ in connections:
        if line_id in connection_ever_active and (a == n_id or b == n_id):
            return True
    return False

def has_active_connection_between(n1, n2):
    line_id = get_connection_line_id(n1, n2)
    return line_id is not None and line_id in connection_ever_active

def get_or_create_bb84_data(n1, n2):
    line_id = get_connection_line_id(n1, n2)
    if line_id is None:
        return None

    if line_id in bb84_connection_data:
        return bb84_connection_data[line_id]

    key_length = 10
    raw_length = 16

    alice_bits = [random.randint(0, 1) for _ in range(raw_length)]
    alice_bases = [random.choice(["+", "x"]) for _ in range(raw_length)]
    bob_bases = [random.choice(["+", "x"]) for _ in range(raw_length)]

    bob_bits = []
    for i in range(raw_length):
        if alice_bases[i] == bob_bases[i]:
            bob_bits.append(alice_bits[i])
        else:
            bob_bits.append(random.randint(0, 1))

    sifted_positions = [i for i in range(raw_length) if alice_bases[i] == bob_bases[i]]
    sifted_key = [alice_bits[i] for i in sifted_positions][:key_length]

    data = {
        "alice_bits": alice_bits,
        "alice_bases": alice_bases,
        "bob_bases": bob_bases,
        "bob_bits": bob_bits,
        "sifted_positions": sifted_positions,
        "sifted_key": sifted_key,
        "sifted_key_str": "".join(str(b) for b in sifted_key) if sifted_key else "0",
    }
    bb84_connection_data[line_id] = data
    return data

def deactivate_message_mode(status_text=None, status_color="black"):
    global message_mode, message_source, message_target
    message_mode = False
    message_source = None
    message_target = None
    btn_message.config(text="ÜZENET", bg="#6610f2", fg="white")
    clear_node_selection_outline()
    if status_text is not None:
        lbl_status.config(text=status_text, fg=status_color)

def show_message_window(src, dst):
    bb84_data = get_or_create_bb84_data(src, dst)
    key_seed = bb84_data["sifted_key_str"] if bb84_data else "0"
    key_len = max(1, len(key_seed))
    max_value = (2 ** key_len) - 1

    win = tk.Toplevel(root)
    win.title(f"Üzenetküldés: {src} -> {dst}")
    win.geometry("560x420")
    win.configure(bg="#f7f7ff")

    tk.Label(win, text=f"Üzenetküldés aktív kapcsolaton: {src} -> {dst}", font=("Arial", 11, "bold"), bg="#f7f7ff").pack(pady=10)

    conditions = (
        "Feltételek:\n"
        "1) Csak egész szám adható meg.\n"
        f"2) A számnak 0 és {max_value} között kell lennie (beleértve).\n"
        f"   (A kulcs hossza: {key_len} bit, ezért maximum: 2^{key_len}-1 = {max_value})\n"
        "3) A program binárisra bontja, majd kulccsal XOR-olja."
    )
    tk.Label(win, text=conditions, justify="left", bg="#f7f7ff", font=("Arial", 10)).pack(anchor="w", padx=14)

    input_frame = tk.Frame(win, bg="#f7f7ff")
    input_frame.pack(fill="x", padx=14, pady=10)

    tk.Label(input_frame, text=f"Szám (0-{max_value}):", bg="#f7f7ff", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
    entry = tk.Entry(input_frame, width=10, font=("Courier", 11, "bold"))
    entry.pack(side=tk.LEFT, padx=8)

    result_text = tk.Text(win, height=10, width=62, font=("Courier", 10), bg="white")
    result_text.pack(padx=14, pady=10)
    result_text.config(state="disabled")

    def submit_message():
        raw = entry.get().strip()
        try:
            value = int(raw)
        except ValueError:
            messagebox.showwarning("Hiba", "Csak egész számot adhatsz meg!", parent=win)
            return

        if value < 0 or value > max_value:
            messagebox.showwarning("Hiba", f"A számnak 0 és {max_value} között kell lennie!", parent=win)
            return

        msg_bits = format(value, f"0{key_len}b")
        key_bits_for_message = key_seed[:key_len]
        encrypted_bits = "".join("1" if mb != kb else "0" for mb, kb in zip(msg_bits, key_bits_for_message))

        result_text.config(state="normal")
        result_text.delete("1.0", tk.END)
        result_text.insert("1.0", f"Kulcs bitsor      : {key_seed}\n")
        result_text.insert(tk.END, f"Uzenet bitsor     : {msg_bits}\n")
        result_text.insert(tk.END, f"Elkuldott bitsor  : {encrypted_bits}")
        result_text.config(state="disabled")

    tk.Button(win, text="Kuldes", command=submit_message, bg="#0d6efd", fg="white", width=12).pack(pady=6)

def start_message_mode():
    global message_mode, message_source, message_target

    if message_mode:
        deactivate_message_mode(status_text="Üzenet mód kikapcsolva.", status_color="black")
        return

    if not connections or not connection_ever_active:
        messagebox.showinfo("Infó", "Üzenethez legalább egy már aktív kapcsolat kell.")
        return

    if move_mode:
        deactivate_move_mode()
    if Eve_mode:
        deactivate_eve_mode()
    if bb84_mode:
        deactivate_bb84_mode()

    message_mode = True
    message_source = None
    message_target = None
    btn_message.config(text="ÜZENET (AKTÍV)", bg="#4b0082", fg="white")
    clear_node_selection_outline()
    lbl_status.config(text="Üzenet mód: válassz egy gépet, ami már aktív kapcsolatban van!", fg="#4b0082")

def show_bb84_window(n1, n2):
    side_a = f"{nodes[n1]['type'].title()} ({n1})"
    side_b = f"{nodes[n2]['type'].title()} ({n2})"

    def bit_symbol(bit, basis):
        if basis == "+":
            return "-" if bit == 0 else "|"
        return "/" if bit == 0 else "\\"

    bb84_data = get_or_create_bb84_data(n1, n2)
    if bb84_data is None:
        messagebox.showwarning("Hiba", "Ehhez a kapcsolathoz nem találtam BB84 adatot.")
        return

    line_id = get_connection_line_id(n1, n2)
    security = update_connection_security(line_id) if line_id is not None else {"qber": 0.0, "prob": 0.0, "status": "UNKNOWN", "color": "black"}

    alice_bits = bb84_data["alice_bits"]
    alice_bases = bb84_data["alice_bases"]
    bob_bases = bb84_data["bob_bases"]
    bob_bits = bb84_data["bob_bits"]
    sifted_positions = bb84_data["sifted_positions"]
    sifted_key = bb84_data["sifted_key"]
    raw_length = len(alice_bits)

    win = tk.Toplevel(root)
    win.title(f"BB84: {n1} <-> {n2}")
    win.geometry("620x520")
    win.configure(bg="#f6fbff")

    title = tk.Label(win, text=f"BB84 protokoll felépülése ({n1} és {n2})", font=("Arial", 12, "bold"), bg="#f6fbff")
    title.pack(pady=10)

    sec_text = (
        f"QBER: {security['qber']:.2f}% | Állapot: {security['status']} | "
        f"Lehallgatási valószínűség: {security['prob']:.1f}% {probability_bar(security['prob'])}"
    )
    tk.Label(win, text=sec_text, font=("Arial", 10, "bold"), fg=security["color"], bg="#f6fbff").pack(pady=4)

    txt = tk.Text(win, wrap="word", height=24, width=78, font=("Courier", 10), bg="white")
    txt.pack(padx=10, pady=6, fill="both", expand=True)

    lines = []
    lines.append(f"1) {side_a} véletlen biteket és bázisokat választ.")
    lines.append(f"   {side_a} bitek : {' '.join(map(str, alice_bits))}")
    lines.append(f"   {side_a} bázis : {' '.join(alice_bases)}")
    lines.append(f" {side_a} küldött : {' '.join(bit_symbol(alice_bits[i], alice_bases[i]) for i in range(raw_length))}")
    lines.append("")
    lines.append(f"2) {side_b} véletlen bázisokat választ a méréshez.")
    lines.append(f"   {side_b} bázis   : {' '.join(bob_bases)}")
    lines.append(f"   {side_b} mért    : {' '.join(bit_symbol(bob_bits[i], bob_bases[i]) for i in range(raw_length))}")
    lines.append(f"   {side_b} eredmény: {' '.join(map(str, bob_bits))}")
    lines.append("")
    lines.append(f"3) {side_a} és {side_b} nyílt csatornán összehasonlítják a bázisokat (csak a bázist, nem a bitet).")
    lines.append(f"   Egyező pozíciók (0-index): {sifted_positions}")
    lines.append("")
    lines.append(f"4) A közös kulcs {side_a} és {side_b} egyező bázisú pozícióinak bitjeiből áll össze.")
    lines.append(f"   Szűrt kulcs ({len(sifted_key)} bit): {' '.join(map(str, sifted_key)) if sifted_key else '-'}")
    lines.append("")
    lines.append(f"5) {side_a} és {side_b} ellenőrizhet néhány bitet hibaarányra, majd a maradék lesz a titkos kulcs.")

    txt.insert("1.0", "\n".join(lines))
    txt.config(state="disabled")

    refresh_connection_value_labels()

def start_bb84_mode():
    global bb84_mode

    if bb84_mode:
        deactivate_bb84_mode(status_text="BB84 mód kikapcsolva.", status_color="black")
        return

    if not connections:
        messagebox.showinfo("Infó", "Nincs kiépített kapcsolat!")
        return

    available = [idx for idx, conn in enumerate(connections) if not conn[3]]
    if not available:
        messagebox.showinfo("Infó", "Nincs olyan kapcsolat, ami még nem aktív.")
        return

    if move_mode:
        deactivate_move_mode()
    if Eve_mode:
        deactivate_eve_mode()
    if message_mode:
        deactivate_message_mode()

    bb84_mode = True
    btn_bb84.config(text="BB84 (AKTÍV)", bg="#138496", fg="white")
    refresh_connection_visuals()
    lbl_status.config(text="BB84 mód aktív: kattints egy még nem aktív kapcsolatra!", fg="#138496")

def toggle_move_mode():
    global move_mode, move_selected_node

    if move_mode:
        deactivate_move_mode(status_text="Mozgatás kikapcsolva.")
        return

    candidate = second_selection if second_selection is not None else first_selection
    if candidate is None and Eve_mode and active_Eve is not None:
        candidate = active_Eve
    if candidate is None:
        messagebox.showwarning("Hiba", "Mozgatáshoz előbb válassz ki egy gépet (Eve esetén kattints Eve-re, majd MOVE).")
        return

    if Eve_mode:
        deactivate_eve_mode()
    if bb84_mode:
        deactivate_bb84_mode()
    if message_mode:
        deactivate_message_mode()

    move_mode = True
    move_selected_node = candidate
    btn_move.config(text="MOVE (AKTÍV)", bg="#ff9800", fg="white")
    highlight_node(move_selected_node, color="#ff9800")
    lbl_status.config(text=f"Mozgatás aktív: {move_selected_node}. Kattints új helyre!", fg="#b35a00")

def get_node_id_from_item(item_id):
    for tag in canvas.gettags(item_id):
        if tag.startswith("node_"):
            return tag.split("node_", 1)[1]
    return None

def handle_canvas_click_for_move(event):
    if not move_mode or move_selected_node is None:
        return

    current_items = canvas.find_withtag("current")
    if current_items and get_node_id_from_item(current_items[0]) is not None:
        return

    move_node_to(move_selected_node, event.x, event.y)
    lbl_status.config(text=f"{move_selected_node} áthelyezve új pozícióba.", fg="#b35a00")

def get_current_selected_node():
    if move_mode and move_selected_node is not None:
        return move_selected_node
    if second_selection is not None:
        return second_selection
    if first_selection is not None:
        return first_selection
    if Eve_mode and active_Eve is not None:
        return active_Eve
    return None

def delete_selected_node():
    global selected_tap_connection

    target = get_current_selected_node()
    if target is None or target not in nodes:
        messagebox.showwarning("Hiba", "Nincs kiválasztott gép a törléshez!")
        return

    if Eve_mode:
        deactivate_eve_mode()
    if move_mode:
        deactivate_move_mode()
    if bb84_mode:
        deactivate_bb84_mode()
    if message_mode:
        deactivate_message_mode()

    kept_connections = _remove_target_connections(target)
    connections.clear()
    connections.extend(kept_connections)

    canvas.delete(nodes[target]["rect"])
    canvas.delete(nodes[target]["text"])
    canvas.delete(nodes[target]["led"])
    del nodes[target]

    _clear_target_selection(target)
    selected_tap_connection = None
    clear_node_selection_outline()
    refresh_connection_visuals()
    refresh_eve_arrows()
    refresh_connection_value_labels()
    lbl_status.config(text=f"{target} törölve.", fg="black")

def refresh_connection_visuals(active_index=None):
    for i, (n1, n2, line_id, is_tapped, tapped_by) in enumerate(connections):
        if i == active_index:
            canvas.itemconfig(line_id, fill="#ff8800", width=3, dash=())
        elif is_tapped:
            canvas.itemconfig(line_id, fill="red", width=3, dash=())
        elif line_id in connection_ever_active:
            canvas.itemconfig(line_id, fill="#28a745", width=2, dash=())
        else:
            canvas.itemconfig(line_id, fill="gray", width=2, dash=(5, 2))
    refresh_eve_arrows()

def activate_eve_mode(eve_id):
    global Eve_mode, selected_tap_connection, first_selection, second_selection, active_Eve
    Eve_mode = True
    selected_tap_connection = None
    first_selection = None
    second_selection = None
    active_Eve = eve_id

    if bb84_mode:
        deactivate_bb84_mode()

    highlight_node(eve_id, color="#dc3545")

    btn_connection.config(text="LEHALLGATÁS", bg="#dc3545", fg="white")
    refresh_connection_visuals()
    lbl_status.config(text=f"Eve mód aktív ({eve_id}): válassz ki egy kapcsolatot, majd nyomd meg a piros gombot!", fg="red")

def deactivate_eve_mode(status_text=None, status_color="black"):
    global Eve_mode, selected_tap_connection, active_Eve
    Eve_mode = False
    selected_tap_connection = None
    active_Eve = None
    btn_connection.config(text="KAPCSOLAT (+)", bg="#e1e1e1", fg="black")
    refresh_connection_visuals()
    clear_node_selection_outline()

    if status_text is not None:
        lbl_status.config(text=status_text, fg=status_color)

def add_node(node_type="CHARLIE"):
    global node_counter
    node_counter += 1
    n_id = f"N{node_counter}"
    
    if node_type == "ALICE": x, y = 50, 100
    elif node_type == "BOB": x, y = 550, 100
    else: x, y = random.randint(150, 450), random.randint(50, 250)
    
    fill_color = "#ffcccc" if "Eve" in node_type else "#d1d1d1"
    rect = canvas.create_rectangle(x, y, x+100, y+80, fill=fill_color, outline="black", width=2)
    text = canvas.create_text(x+50, y+15, text=f"{node_type}\n({n_id})", font=("Arial", 8, "bold"))
    led = canvas.create_oval(x+40, y+40, x+60, y+60, fill="red")

    for item in (rect, text, led):
        canvas.itemconfig(item, tags=(f"node_{n_id}", "node_item"))

    nodes[n_id] = {
        "rect": rect, "led": led, "text": text, "type": node_type,
        "x": x+50, "y": y+40
    }
    
    for item in (rect, text, led):
        canvas.tag_bind(item, BUTTON_ONE_EVENT, lambda e, id=n_id: select_node(id))
    lbl_status.config(text=f"{n_id} létrehozva.")

def select_node(n_id):
    if message_mode:
        _handle_message_mode_selection(n_id)
        return

    if move_mode:
        deactivate_eve_mode()
        return

    if bb84_mode:
        lbl_status.config(text="BB84 mód aktív: kattints egy még nem aktív kapcsolatra!", fg="#138496")
        return
    
    if nodes[n_id]["type"] == "Eve":
        activate_eve_mode(n_id)
        return

    if Eve_mode:
        lbl_status.config(text="Eve mód aktív: előbb válassz kapcsolatot, majd nyomd meg a piros gombot!", fg="red")
        return

    _handle_default_node_selection(n_id)

def select_connection_for_tap(conn_index):
    global selected_tap_connection

    if conn_index < 0 or conn_index >= len(connections):
        return

    n1, n2, _, _, _ = connections[conn_index]

    if bb84_mode:
        refresh_connection_visuals(active_index=conn_index)
        show_bb84_window(n1, n2)
        deactivate_bb84_mode(status_text=f"BB84 felépülés megjelenítve: {n1}-{n2}", status_color="#138496")
        return

    if not Eve_mode:
        return

    selected_tap_connection = conn_index
    refresh_connection_visuals(active_index=conn_index)
    lbl_status.config(text=f"Kijelölt kapcsolat: {n1}-{n2}. Nyomd meg a piros gombot a lehallgatáshoz!", fg="red")

def start_connection():
    global first_selection, second_selection

    if move_mode:
        messagebox.showwarning("Hiba", "Kapcsold ki a MOVE módot kapcsolat létrehozása előtt!")
        return
    if bb84_mode:
        messagebox.showwarning("Hiba", "Kapcsold ki a BB84 módot kapcsolat létrehozása előtt!")
        return
    if message_mode:
        messagebox.showwarning("Hiba", "Kapcsold ki az ÜZENET módot kapcsolat létrehozása előtt!")
        return

    if Eve_mode:
        if selected_tap_connection is None:
            messagebox.showwarning("Hiba", "Eve módban előbb válassz ki egy kapcsolatot!")
            return

        n1, n2, line_id, _, _ = connections[selected_tap_connection]
        connections[selected_tap_connection] = (n1, n2, line_id, True, active_Eve)
        deactivate_eve_mode(status_text=f"Vonal lehallgatva: {n1}-{n2}", status_color="red")
        refresh_eve_arrows()
        return
    
    if first_selection is None or second_selection is None:
        messagebox.showwarning("Hiba", "Válassz ki két különböző gépet a térképen!")
        return

    if nodes[first_selection]["type"] == "Eve" or nodes[second_selection]["type"] == "Eve":
        messagebox.showerror("Hiba", "Eve-val nem építhető ki biztonságos állandó kapcsolat!")
        first_selection = None
        second_selection = None
        clear_node_selection_outline()
        return

    line = canvas.create_line(nodes[first_selection]["x"], nodes[first_selection]["y"],
                             nodes[second_selection]["x"], nodes[second_selection]["y"], 
                             fill="gray", dash=(5, 2), width=2)
    
    connections.append((first_selection, second_selection, line, False, None))
    conn_index = len(connections) - 1
    canvas.tag_bind(line, BUTTON_ONE_EVENT, lambda e, idx=conn_index: select_connection_for_tap(idx))
    refresh_connection_value_labels()
    lbl_status.config(text=f"Kapcsolat: {first_selection} <-> {second_selection}", fg="green")
    
    clear_node_selection_outline()
    
    first_selection = None
    second_selection = None

def run_network_simulation():
    if not connections:
        messagebox.showinfo("Infó", "Nincs kiépített kapcsolat!")
        return
    
    try:
        backend = Aer.get_backend('qasm_simulator')
        for nid in nodes:
            canvas.itemconfig(nodes[nid]["led"], fill="red")
        root.update()

        for conn_index, connection in enumerate(connections, start=1):
            _simulate_connection_step(backend, conn_index, connection)

        lbl_status.config(text="Hálózati szimuláció befejeződött.")

    except Exception as e:
        messagebox.showerror("Hiba", str(e))

root = tk.Tk()
root.title("Kvantum-Internet Topológia Szimulátor")
root.geometry("800x650")
root.configure(bg="#f0f0f0")

tk.Label(root, text="Dinamikus Kvantum Hálózat Építő", font=("Arial", 14, "bold"), bg="#f0f0f0").pack(pady=10)
canvas = tk.Canvas(root, width=750, height=400, bg="white", highlightthickness=1)
canvas.pack(pady=10)
canvas.bind(BUTTON_ONE_EVENT, handle_canvas_click_for_move, add="+")

btn_frame = tk.Frame(root, bg="#f0f0f0")
btn_frame.pack(pady=10)

tk.Button(btn_frame, text="+ Új Charlie", command=lambda: add_node("CHARLIE"), bg="#005c96", fg="white", width=12).grid(row=0, column=0, padx=5)
tk.Button(btn_frame, text="+ Új Eve", command=lambda: add_node("Eve"), bg="#dc3545", fg="white", width=12).grid(row=0, column=1, padx=5)
btn_connection = tk.Button(btn_frame, text="KAPCSOLAT (+)", command=start_connection, bg="#e1e1e1", width=12)
btn_connection.grid(row=0, column=2, padx=5)
btn_move = tk.Button(btn_frame, text="MOVE", command=toggle_move_mode, bg="#ffc107", width=12)
btn_move.grid(row=0, column=3, padx=5)
tk.Button(btn_frame, text="TÖRLÉS", command=delete_selected_node, bg="#6c757d", fg="white", width=12).grid(row=0, column=4, padx=5)
btn_bb84 = tk.Button(btn_frame, text="BB84", command=start_bb84_mode, bg="#17a2b8", fg="white", width=12)
btn_bb84.grid(row=0, column=5, padx=5)
btn_message = tk.Button(btn_frame, text="ÜZENET", command=start_message_mode, bg="#6610f2", fg="white", width=12)
btn_message.grid(row=0, column=6, padx=5)
tk.Button(btn_frame, text="SZIMULÁCIÓ", command=run_network_simulation, bg="#28a745", fg="white", font=("Arial", 10, "bold"), width=15).grid(row=0, column=7, padx=20)

lbl_status = tk.Label(root, text="Válassz ki két gépet, vagy egy EVÁ-t a lehallgatáshoz!", font=("Arial", 10, "italic"), bg="#f0f0f0")
lbl_status.pack(pady=5)

lbl_output_help = tk.Label(
    root,
    text="Alsó sor jelentése: sorszám. N1 - N2 : |bit> | kapcsolat státusz (lehallgatási valószínűség %)",
    font=("Arial", 9),
    bg="#f0f0f0",
)
lbl_output_help.pack(pady=2)

output_frame = tk.Frame(root, bg="#f0f0f0")
output_frame.pack(fill="x", pady=4)

add_node("ALICE")
add_node("BOB")
refresh_connection_value_labels()
root.mainloop()