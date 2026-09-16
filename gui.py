"""GUI simple: solo gratis sin auth."""
import csv
import json
import threading
from pathlib import Path
from tkinter import ttk, filedialog
import customtkinter as ctk
from playwright.sync_api import sync_playwright

from browser import launch_context
from scrapers import scrape_with_browser, scrape_fast_apis, parse_proxy_line, format_proxy
from validator import validate_proxies

EXPORT_FORMATS = ["ip:port", "protocol://ip:port"]

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def load_countries():
    try:
        with open(Path(__file__).parent / "sources.json", encoding="utf-8") as f:
            return json.load(f).get("countries", ["TODOS"])
    except Exception:
        return ["TODOS", "US", "ES", "MX", "AR", "GB", "DE", "FR", "BR"]


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Proxy Scraper Pro - gratis")
        self.geometry("1080x780")
        self.stop_event = threading.Event()
        self.results = []
        self.raw_all = []

        f = ctk.CTkFrame(self)
        f.pack(fill="x", padx=10, pady=10)
        self.cb_browser = ctk.CTkComboBox(f, values=["Chrome", "Brave", "Edge", "Firefox"], width=120)
        self.cb_browser.set("Chrome")
        self.cb_browser.pack(side="left", padx=5)
        self.var_headless = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(f, text="Navegador oculto", variable=self.var_headless).pack(side="left", padx=5)
        self.vars = {t: ctk.BooleanVar(value=True) for t in ["HTTP", "HTTPS", "SOCKS4", "SOCKS5"]}
        for t, v in self.vars.items():
            ctk.CTkCheckBox(f, text=t, variable=v, width=68).pack(side="left")
        self.var_fast = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(f, text="Valid.Rapida", variable=self.var_fast).pack(side="left", padx=8)

        f2 = ctk.CTkFrame(self)
        f2.pack(fill="x", padx=10)
        ctk.CTkLabel(f2, text="Pais:").pack(side="left", padx=5)
        self.cb_country = ctk.CTkComboBox(f2, values=load_countries(), width=130)
        self.cb_country.set("TODOS")
        self.cb_country.pack(side="left", padx=5)
        ctk.CTkLabel(f2, text="Cant:").pack(side="left", padx=5)
        self.ent_limit = ctk.CTkEntry(f2, width=60)
        self.ent_limit.insert(0, "100")
        self.ent_limit.pack(side="left", padx=5)
        ctk.CTkLabel(f2, text="Anonimato:").pack(side="left", padx=5)
        self.anon_map = {
            "Todos (traer todo)": "all",
            "Transparentes (se ve tu IP - no oculta)": "transparent",
            "Anonimos (oculta tu IP)": "anonymous",
            "Elite (invisible total - recomendado)": "elite",
        }
        self.cb_anon = ctk.CTkComboBox(f2, values=list(self.anon_map.keys()), width=260)
        self.cb_anon.set("Todos (traer todo)")
        self.cb_anon.pack(side="left", padx=5)
        self.btn_go = ctk.CTkButton(f2, text="BUSCAR TODO", command=self.start)
        self.btn_go.pack(side="left", padx=10)
        ctk.CTkButton(f2, text="DETENER", fg_color="#C0392B", hover_color="#922B21",
                      command=self.stop_event.set).pack(side="left")

        self.prog = ctk.CTkProgressBar(self)
        self.prog.pack(fill="x", padx=10, pady=6)
        self.prog.set(0)
        self.lbl = ctk.CTkLabel(self, text="Listo")
        self.lbl.pack()

        cols = ("ip", "port", "type", "country", "anonymity", "latency", "source")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=13)
        widths = {"ip": 130, "port": 70, "type": 80, "country": 80, "anonymity": 90, "latency": 70, "source": 150}
        for c in cols:
            self.tree.heading(c, text=c.upper())
            self.tree.column(c, width=widths.get(c, 110), anchor="center")
        self.tree.pack(fill="both", expand=True, padx=10)

        # --- fila manual simple (sin auth) ---
        f4 = ctk.CTkFrame(self)
        f4.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(f4, text="IP:").pack(side="left", padx=2)
        self.ent_ip = ctk.CTkEntry(f4, width=120, placeholder_text="1.2.3.4")
        self.ent_ip.pack(side="left", padx=2)
        ctk.CTkLabel(f4, text="Puerto:").pack(side="left", padx=2)
        self.ent_port = ctk.CTkEntry(f4, width=60, placeholder_text="8080")
        self.ent_port.pack(side="left", padx=2)
        self.cb_mtype = ctk.CTkComboBox(f4, values=["HTTP", "HTTPS", "SOCKS4", "SOCKS5"], width=100)
        self.cb_mtype.set("HTTP")
        self.cb_mtype.pack(side="left", padx=2)
        ctk.CTkButton(f4, text="Añadir", width=70, command=self.add_manual).pack(side="left", padx=4)
        ctk.CTkButton(f4, text="Importar TXT", width=100, command=self.import_txt).pack(side="left", padx=2)

        f3 = ctk.CTkFrame(self)
        f3.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f3, text="Formato:").pack(side="left", padx=3)
        self.cb_fmt = ctk.CTkComboBox(f3, values=EXPORT_FORMATS, width=240)
        self.cb_fmt.set("ip:port")
        self.cb_fmt.pack(side="left", padx=3)
        ctk.CTkButton(f3, text="Copiar", width=85, command=self.copy).pack(side="left", padx=3)
        ctk.CTkButton(f3, text="Exportar", width=85, command=self.export).pack(side="left", padx=3)
        ctk.CTkButton(f3, text="Mostrar sin validar", width=150, command=self.show_raw).pack(side="left", padx=3)
        ctk.CTkButton(f3, text="Testear", command=self.retest).pack(side="left", padx=3)

        self.logbox = ctk.CTkTextbox(self, height=130)
        self.logbox.pack(fill="x", padx=10, pady=5)
        try:
            nsrc = len(json.load(open(Path(__file__).parent / "sources.json", encoding="utf-8")).get("github_raw", []))
        except Exception:
            nsrc = 0
        self.log(f"V3 listo. {nsrc} GitHub + 8 TXT + 16 webs + Google. Elige PAIS del dropdown y pulsa BUSCAR TODO.")

    def log(self, msg):
        self.logbox.insert("end", msg + "\n")
        self.logbox.see("end")
        print(msg)

    def start(self):
        self.stop_event.clear()
        self.tree.delete(*self.tree.get_children())
        self.results = []
        self.prog.set(0.05)
        threading.Thread(target=self.worker, daemon=True).start()

    def worker(self):
        try:
            wanted = [t for t, v in self.vars.items() if v.get()]
            if not wanted:
                self.log("[!] Marca al menos un tipo.")
                return
            sel_country = self.cb_country.get().strip().upper()
            countries = [] if sel_country in ("", "TODOS", "TODOS ") else [sel_country]
            anon_label = self.cb_anon.get()
            anon = self.anon_map.get(anon_label, "all")
            try:
                limit = max(1, int(self.ent_limit.get() or "100"))
            except ValueError:
                limit = 100
            fast = self.var_fast.get()
            self.log(f"[*] Buscando {wanted} paises={countries or 'TODOS'} anon={anon} limit={limit} fast={fast}")

            # 1. FAST (GitHub + APIs) -> miles
            all_px = scrape_fast_apis(self.log, wanted)
            self.log(f"[**] FAST bruto: {len(all_px)}")
            self.prog.set(0.35)
            self.lbl.configure(text=f"FAST: {len(all_px)} | pasando a navegador...")

            # 2. BROWSER (tablas + google)
            if not self.stop_event.is_set():
                try:
                    with sync_playwright() as p:
                        ctx = launch_context(p, self.cb_browser.get(), self.var_headless.get())
                        bpx = scrape_with_browser(ctx, self.log, self.stop_event, wanted)
                        ctx.close()
                        self.log(f"[**] BROWSER bruto: {len(bpx)}")
                        all_px += bpx
                except Exception as e:
                    self.log(f"[!] Navegador: {e} (sigo con lo ya obtenido)")
            self.prog.set(0.55)
            self.log(f"[**] TOTAL bruto (FAST+BROWSER): {len(all_px)}")
            self.raw_all = list(all_px)

            # 3. Filtros (solo si el proxy trae pais/anon; si trae '--' lo conservamos)
            pre = len(all_px)
            if countries:
                all_px = [x for x in all_px if x.get("country", "").upper() in countries or x.get("country") in ("--", "")]
            if anon != "all":
                all_px = [x for x in all_px if anon in x.get("anonymity", "") or x.get("anonymity") == "unknown"]
            # filtro tipo estricto
            all_px = [x for x in all_px if x.get("type") in wanted]
            self.log(f"[*] Tras filtros: {len(all_px)} (antes {pre})")
            if not all_px:
                self.log("[!] Filtros dejaron 0. Mostrando top sin filtrar.")
                all_px = self.raw_all[:limit*5]

            self.lbl.configure(text=f"Total {len(all_px)} | validando...")
            self.log(f"[*] Sin validar: {len(all_px)}. Validando...")
            vivos = validate_proxies(all_px, self.log, limit=limit, fast=fast)
            self.prog.set(0.95)

            # FALLBACK: si 0 vivos, muestra sin validar para que tengas algo
            if not vivos:
                self.log("[!] 0 vivos con validacion. Muestro SIN VALIDAR para que puedas usar/testear.")
                vivos = all_px[:limit]
                for v in vivos:
                    v["latency"] = -1
            self.results = vivos
            self.prog.set(1.0)
            self.lbl.configure(text=f"OK {len(self.results)} proxies")
            self.log(f"[OK] {len(self.results)} proxies en tabla.")
            for r in self.results:
                self.insert_row(r)
        except Exception as e:
            import traceback
            self.log(f"[ERROR] {e}\n{traceback.format_exc()}")

    def show_raw(self):
        self.tree.delete(*self.tree.get_children())
        rows = (self.raw_all or [])[:500]
        self.results = rows
        for r in rows:
            self.insert_row(r)
        self.log(f"[*] Mostrando {len(rows)} sin validar.")

    def insert_row(self, r):
        self.tree.insert("", "end", values=(
            r.get("ip"), r.get("port"), r.get("type"),
            r.get("country"), r.get("anonymity"), r.get("latency"), r.get("source")))

    def add_manual(self):
        ip = self.ent_ip.get().strip()
        try:
            port = int(self.ent_port.get().strip())
        except Exception:
            self.log("[!] Puerto inválido.")
            return
        px = {"ip": ip, "port": port, "type": self.cb_mtype.get(),
              "username": "", "password": "",
              "country": "--", "anonymity": "unknown", "latency": -1, "source": "manual"}
        # valida formato ip
        import re as _re
        if not _re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
            self.log("[!] IP inválida. Ej: 1.2.3.4")
            return
        self.results = [px] + self.results
        self.raw_all = [px] + self.raw_all
        self.insert_row(px)
        self.log(f"[+] Añadido manual: {format_proxy(px, 'ip:port')}")

    def import_txt(self):
        from tkinter import filedialog as _fd
        path = _fd.askopenfilename(filetypes=[("TXT", "*.txt"), ("Todos", "*.*")])
        if not path:
            return
        n = 0
        try:
            for line in open(path, encoding="utf-8", errors="ignore"):
                px = parse_proxy_line(line, default_type="HTTP", source="import")
                if px:
                    px["username"] = ""
                    px["password"] = ""
                    self.results.append(px)
                    self.raw_all.append(px)
                    self.insert_row(px)
                    n += 1
        except Exception as e:
            self.log(f"[!] Importar: {e}")
        self.log(f"[*] Importados {n} desde {path}. Formato: ip:port o proto://ip:port")

    def _rows(self):
        if self.tree.selection():
            out = []
            for iid in self.tree.selection():
                v = self.tree.item(iid)["values"]
                # cols: ip,port,type,country,anonymity,latency,source
                out.append({"ip": v[0], "port": v[1], "type": v[2],
                            "username": "", "password": "",
                            "country": v[3], "anonymity": v[4], "latency": v[5], "source": v[6]})
            return out
        return self.results

    def copy(self):
        rows = self._rows()
        if not rows:
            return
        fmt = self.cb_fmt.get()
        txt = "\n".join(format_proxy(r, fmt) for r in rows)
        self.clipboard_clear()
        self.clipboard_append(txt)
        self.log(f"[*] Copiado {len(rows)} en formato {fmt}.")

    def export(self):
        rows = self._rows()
        if not rows:
            self.log("[!] Nada que exportar.")
            return
        fmt = self.cb_fmt.get()
        path = filedialog.asksaveasfilename(defaultextension=".txt",
            filetypes=[("TXT", "*.txt"), ("JSON", "*.json"), ("CSV", "*.csv")])
        if not path:
            return
        if path.endswith(".json"):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rows, f, indent=2)
        elif path.endswith(".csv"):
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["ip", "port", "type", "country", "anonymity", "latency", "source"])
                w.writeheader()
                w.writerows([{k: r.get(k, "") for k in ["ip", "port", "type", "country", "anonymity", "latency", "source"]} for r in rows])
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(format_proxy(r, fmt) for r in rows))
        self.log(f"[OK] Guardado {path} ({len(rows)}) formato {fmt}")

    def retest(self):
        sel = self._rows()
        if not sel:
            return
        threading.Thread(
            target=lambda: self.log(f"[Retest] vivos: {len(validate_proxies(sel, self.log, limit=len(sel), fast=self.var_fast.get()))}"),
            daemon=True).start()


def run():
    App().mainloop()
