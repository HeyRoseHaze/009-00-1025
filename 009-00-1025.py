import tkinter as tk
from tkinter import ttk, messagebox
import serial
import time
import threading

#Komendy FLUKE
CMD_TEMP = b'SOUR:SENS:DATA?\r\n'      # odczyt temperatury pieca
CMD_REF = b'MEAS?\r\n'                 # odczyt wzorca
CMD_MA = b'SENS2:DATA?\r\n'            # odczyt wejścia measure mA
CMD_SETPOINT = b'SOUR:SPO?\r\n'        # odczyt setpointu
CMD_BEEP = b'SYST:BEEP:IMM\r\n'        # sygnał dźwiękowy
CMD_HEAT_ON = b'OUTP:STAT 1\r\n'       # włącz grzanie
CMD_HEAT_OFF = b'OUTP:STAT 0\r\n'      # wyłącz grzanie

#Blokada globalna dla portu COM.

#pomocnicze
def zamiana_float(s):
    try:
        return float(s)
    except Exception:
        return None


def wyslij_komende(port, cmd, timeout=1.0):
    with serial_lock:
        try:
            with serial.Serial(port, baudrate=9600, timeout=timeout) as ser:
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                ser.write(cmd)
                time.sleep(0.05)
                resp = ser.readline()
                return resp.decode(errors='ignore').strip()
        except serial.SerialException as e:
            return f"Błąd portu: {e}"
        except Exception as e:
            return f"Błąd: {e}"

#Panel dla jednego COM
class ComPanel:
    def __init__(self, parent, port_name, nazwa_pieca=""):
        self.port = port_name
        self.nazwa_pieca = nazwa_pieca
        tytul = f"{port_name} - {nazwa_pieca}" if nazwa_pieca else port_name
        self.ramka = ttk.LabelFrame(parent, text=tytul, padding=10)

     #Pole wyświetlania
        self.wyswietl = tk.Text(self.ramka, height=6, width=30, font=("Segoe UI", 14), wrap="word")
        self.wyswietl.config(state="disabled")
        self.wyswietl.grid(row=0, column=0, columnspan=3, padx=5, pady=5)

        #Wybór odczytu
        self.tryb = tk.StringVar(value="temp")
        tryb_ramka = ttk.Frame(self.ramka)
        tryb_ramka.grid(row=1, column=0, columnspan=3, sticky="w", padx=5)
        ttk.Radiobutton(tryb_ramka, text="Temperatura pieca", variable=self.tryb, value="temp").pack(anchor="w")
        ttk.Radiobutton(tryb_ramka, text="Temperatura wzorca", variable=self.tryb, value="ref").pack(anchor="w")
        ttk.Radiobutton(tryb_ramka, text="Prąd mA", variable=self.tryb, value="ma").pack(anchor="w")
        ttk.Radiobutton(tryb_ramka, text="Wszystko", variable=self.tryb, value="all").pack(anchor="w")

        #Ustawienie temperatury
        ttk.Label(self.ramka, text="Nowa temperatura [°C]:").grid(row=2, column=0, sticky="e")
        self.entry_temp = ttk.Entry(self.ramka, width=8)
        self.entry_temp.grid(row=2, column=1, sticky="w")
        ttk.Button(self.ramka, text="Ustaw", command=self.set_temp).grid(row=2, column=2)

        #Odczyt setpoint
        ttk.Button(self.ramka, text="Odczytaj setpoint", command=self.read_setpoint).grid(row=3, column=0, columnspan=3, pady=5)

        #Sterowanie grzaniem
        ttk.Button(self.ramka, text="Włącz grzanie", command=lambda: self.ster_grzaniem(True)).grid(row=4, column=0, pady=6)
        ttk.Button(self.ramka, text="Wyłącz grzanie", command=lambda: self.ster_grzaniem(False)).grid(row=4, column=1, pady=6)
        ttk.Button(self.ramka, text="Odczytaj raz", command=self.odczyt_raz).grid(row=4, column=2, pady=6)

        #Status
        self.status_label = ttk.Label(self.ramka, text="", foreground="green")
        self.status_label.grid(row=5, column=0, columnspan=3, pady=2)

    def grid(self, **kwargs):
        self.ramka.grid(**kwargs)


    def update_wyswietl(self, text):
        self.wyswietl.config(state="normal")
        self.wyswietl.delete("1.0", tk.END)
        self.wyswietl.insert(tk.END, text)
        self.wyswietl.config(state="disabled")

    def update_status(self, text, color="green"):
        self.status_label.config(text=text, foreground=color)

    #Odczyt pojedynczy
    def odczyt_raz(self):
        txt = self.read_data(self.tryb.get())
        self.update_wyswietl(txt)
        self.update_status("Odczyt wykonany")

    def read_data(self, tryb):
        out = []
        if tryb in ("temp", "all"):
            r = wyslij_komende(self.port, CMD_TEMP)
            out.append(self.format_odp("Piec", r, "°C"))
        if tryb in ("ref", "all"):
            r = wyslij_komende(self.port, CMD_REF)
            out.append(self.format_odp("Ref", r, "°C"))
        if tryb in ("ma", "all"):
            r = wyslij_komende(self.port, CMD_MA)
            out.append(self.format_odp("mA", r, "mA"))
        return "\n".join(out)

    def format_odp(self, label, resp, unit):
        if "Błąd" in resp:
            return f"{label}: {resp}"
        v = zamiana_float(resp)
        return f"{label}: {v:.2f} {unit}" if v is not None else f"{label}: {resp}"
#####################################################################################
    #Sterowanie
    def set_temp(self):
        try:
            val = float(self.entry_temp.get().strip())
        except Exception:
            messagebox.showerror("Błąd", f"{self.port}: nieprawidłowa wartość")
            return
        try:
            with serial_lock:
                with serial.Serial(self.port, 9600, timeout=1) as ser:
                    ser.write(f"SOUR:SPO {val}\r\n".encode())
                    time.sleep(0.05)
                    ser.write(CMD_BEEP)
                    self.update_status(f"SET -> {val:.2f} °C")
        except serial.SerialException as e:
            self.update_status(f"Błąd portu: {e}", "red")

    def read_setpoint(self):
        resp = wyslij_komende(self.port, CMD_SETPOINT)
        v = zamiana_float(resp)
        txt = f"Setpoint: {v:.2f} °C" if v is not None else f"Błąd odczytu {resp}"
        self.update_wyswietl(txt)
        self.update_status("Odczyt setpointu OK" if "Błąd" not in resp else "Błąd odczytu",
                           "green" if "Błąd" not in resp else "red")

    def ster_grzaniem(self, on):
        try:
            with serial_lock:
                with serial.Serial(self.port, 9600, timeout=1) as ser:
                    ser.write(CMD_HEAT_ON if on else CMD_HEAT_OFF)
                    time.sleep(0.05)
                    ser.write(CMD_BEEP)
            self.update_status("Grzanie ON" if on else "Grzanie OFF", "green" if on else "red")
        except serial.SerialException as e:
            self.update_status(f"Błąd portu: {e}", "red")

###############################################################

#Główna aplikacja
class App:
    def __init__(self, root):
        self.root = root
        root.title("Sterowanie temperaturą")

        main = ttk.Frame(root, padding=8)
        main.pack(fill="both", expand=True)

        #Panele COM
        self.panels = []
        konfiguracja = [
            ("COM1", "Piec Fluke 9142 MID"),
            ("COM2", "Piec Fluke 9144"),
            ("COM3", "Piec Fluke 9142"),
        ]
        for i, (port, nazwa) in enumerate(konfiguracja):
            panel = ComPanel(main, port, nazwa)
            panel.grid(row=0, column=i, padx=6, pady=6, sticky="n")
            self.panels.append(panel)

        #Kontrolki główne
        ctrl_ramka = ttk.Frame(root, padding=6)
        ctrl_ramka.pack(fill="x")

        self.cont_flag = False
        self.btn_toggle = ttk.Button(ctrl_ramka, text="▶ Start odczytu ciągłego", command=self.toggle_continuous)
        self.btn_toggle.grid(row=0, column=0, padx=6, pady=6)

        #Status box
        self.status_box = tk.Text(root, height=3, wrap="word", font=("Segoe UI", 10))
        self.status_box.pack(fill="x", padx=8, pady=6)
        self.status_box.config(state="disabled")

        self.read_thread = None

    def append_status(self, txt):
        self.status_box.config(state="normal")
        self.status_box.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {txt}\n")
        self.status_box.see(tk.END)
        self.status_box.config(state="disabled")

    def toggle_continuous(self):
        if not self.cont_flag:
            self.cont_flag = True
            self.btn_toggle.config(text="■ Zatrzymaj odczyt")
            self.append_status("Ciągły odczyt uruchomiony.")
            self.read_thread = threading.Thread(target=self._continuous_loop, daemon=True)
            self.read_thread.start()
        else:
            self.cont_flag = False
            self.btn_toggle.config(text="▶ Start odczytu ciągłego")
            self.append_status("Ciągły odczyt zatrzymany.")

    def _continuous_loop(self):
        interval = 2.0
        while self.cont_flag:
            start = time.time()
            for panel in self.panels:
                threading.Thread(
                    target=lambda p=panel: self._update_panel(p),
                    daemon=True
                ).start()
            self.root.after(0, self.append_status, "Pobrano dane ze wszystkich portów.")
            elapsed = time.time() - start
            time.sleep(max(0, interval - elapsed))

    def _update_panel(self, panel):
        try:
            txt = panel.read_data(panel.tryb.get())
        except Exception as e:
            txt = f"Błąd: {e}"
        self.root.after(0, panel.update_wyswietl, txt)

#____________________________________________
#START
if __name__ == "__main__":
    root = tk.Tk()
    from tkinter import font

    default_font = font.nametofont("TkDefaultFont")
    default_font.configure(size=12)
    text_font = font.nametofont("TkTextFont")
    text_font.configure(size=12)

    app = App(root)
    root.geometry("1300x650")
    root.mainloop()
