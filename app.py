import json
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "config.json"

BG = "#10131c"
PANEL = "#191f2d"
TEXT = "#edf2ff"
ACCENT = "#7c5cff"
MUTED = "#9aa6bd"

def load_config():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {"games": []}

def save_config(data):
    CONFIG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GAME PRICE WATCHER")
        self.geometry("980x620")
        self.minsize(820, 520)
        self.configure(bg=BG)
        self.data = load_config()
        self._style()
        self._build()
        self.refresh()

    def _style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, foreground=TEXT, fieldbackground=PANEL,
                        rowheight=34, borderwidth=0)
        style.configure("Treeview.Heading", background="#252d40", foreground=TEXT, relief="flat")
        style.map("Treeview", background=[("selected", ACCENT)])
        style.configure("TButton", background=ACCENT, foreground="white", padding=8)
        style.map("TButton", background=[("active", "#927aff")])

    def _build(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=24, pady=(22, 12))
        tk.Label(header, text="GAME PRICE WATCHER", bg=BG, fg=TEXT,
                 font=("Segoe UI", 22, "bold")).pack(anchor="w")
        tk.Label(header, text="Il tuo centro di controllo offerte videogiochi",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 0))

        panel = tk.Frame(self, bg=PANEL, padx=14, pady=14)
        panel.pack(fill="both", expand=True, padx=24, pady=8)
        cols = ("name", "site", "threshold", "status")
        self.tree = ttk.Treeview(panel, columns=cols, show="headings")
        for col, title, width in [
            ("name", "GIOCO", 430), ("site", "NEGOZIO", 190),
            ("threshold", "SOGLIA", 110), ("status", "STATO", 100)
        ]:
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True)

        actions = tk.Frame(self, bg=BG)
        actions.pack(fill="x", padx=24, pady=14)
        ttk.Button(actions, text="+ Aggiungi gioco", command=self.add_game).pack(side="left")
        ttk.Button(actions, text="Modifica selezionato", command=self.edit_game).pack(side="left", padx=8)
        ttk.Button(actions, text="Rimuovi", command=self.remove_game).pack(side="left")
        ttk.Button(actions, text="Apri cartella progetto", command=self.open_folder).pack(side="right")
        tk.Label(self, text="Il controllo cloud continua tramite GitHub Actions anche a PC spento.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=26, pady=(0, 16))

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for i, game in enumerate(self.data.get("games", [])):
            self.tree.insert("", "end", iid=str(i), values=(
                game.get("name", ""), game.get("site", ""),
                f"{float(game.get('threshold', 0)):.2f} €",
                "ATTIVO" if game.get("enabled") else "DA CONFIGURARE"
            ))

    def edit_dialog(self, game=None):
        game = dict(game or {})
        win = tk.Toplevel(self)
        win.title("Gioco monitorato")
        win.configure(bg=BG)
        win.resizable(False, False)
        fields = [
            ("Nome gioco", "name"), ("Negozio", "site"), ("URL pagina prodotto", "url"),
            ("Selettore CSS prezzo", "price_selector"), ("Prezzo massimo (€)", "threshold")
        ]
        entries = {}
        for row, (label, key) in enumerate(fields):
            tk.Label(win, text=label, bg=BG, fg=TEXT, font=("Segoe UI", 10)).grid(
                row=row, column=0, sticky="w", padx=14, pady=7)
            entry = tk.Entry(win, width=58, bg=PANEL, fg=TEXT, insertbackground=TEXT,
                             relief="flat")
            entry.grid(row=row, column=1, padx=14, pady=7)
            entry.insert(0, str(game.get(key, "")))
            entries[key] = entry
        enabled_var = tk.BooleanVar(value=bool(game.get("enabled", False)))
        tk.Checkbutton(win, text="Attiva monitoraggio", variable=enabled_var,
                       bg=BG, fg=TEXT, selectcolor=PANEL, activebackground=BG).grid(
                           row=len(fields), column=1, sticky="w", padx=14, pady=7)

        def save():
            try:
                item = {key: entries[key].get().strip() for _, key in fields}
                item["threshold"] = float(item["threshold"].replace(",", "."))
                item.update({"currency": "EUR", "enabled": enabled_var.get()})
                if not item["name"] or not item["url"]:
                    raise ValueError("Nome e URL sono obbligatori.")
                if not item["price_selector"] and item["enabled"]:
                    raise ValueError("Inserisci il selettore CSS prima di attivare il monitoraggio.")
                if game.get("url"):
                    idx = next((i for i, g in enumerate(self.data["games"]) if g.get("url") == game.get("url")), None)
                    if idx is not None:
                        self.data["games"][idx] = item
                    else:
                        self.data["games"].append(item)
                else:
                    self.data["games"].append(item)
                save_config(self.data)
                self.refresh()
                win.destroy()
            except Exception as exc:
                messagebox.showerror("Dati non validi", str(exc), parent=win)

        ttk.Button(win, text="Salva", command=save).grid(
            row=len(fields)+1, column=1, sticky="e", padx=14, pady=14)

    def add_game(self):
        self.edit_dialog()

    def edit_game(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Seleziona un gioco", "Seleziona prima un gioco.")
            return
        idx = int(selection[0])
        self.edit_dialog(self.data["games"][idx])

    def remove_game(self):
        selection = self.tree.selection()
        if not selection:
            return
        idx = int(selection[0])
        if messagebox.askyesno("Conferma", "Rimuovere il gioco selezionato?"):
            self.data["games"].pop(idx)
            save_config(self.data)
            self.refresh()

    def open_folder(self):
        import os
        os.startfile(BASE)

if __name__ == "__main__":
    App().mainloop()
