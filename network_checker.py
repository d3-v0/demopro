#!/usr/bin/env python3
"""Network Checker - simple network diagnostic GUI for Linux/Ubuntu."""

import json
import platform
import re
import socket
import subprocess
import threading
import time
import urllib.request
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path


def run(cmd, timeout=8):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, check=False)
        return p.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return ""


def default_interface():
    m = re.search(r"default via \S+ dev (\S+)",
                  run(["ip", "route", "show", "default"]))
    return m.group(1) if m else ""


def gateway():
    m = re.search(r"default via (\S+)",
                  run(["ip", "route", "show", "default"]))
    return m.group(1) if m else ""


def local_ip(interface=""):
    if interface:
        out = run(["ip", "-4", "addr", "show", "dev", interface])
        m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)/", out)
        if m:
            return m.group(1)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return ""


def mac(interface):
    try:
        return Path(f"/sys/class/net/{interface}/address").read_text().strip()
    except OSError:
        return ""


def dns_servers():
    try:
        text = Path("/etc/resolv.conf").read_text(errors="replace")
        return re.findall(r"^\s*nameserver\s+(\S+)", text, re.M)
    except OSError:
        return []


def dns_test():
    try:
        start = time.perf_counter()
        socket.gethostbyname("www.google.com")
        return True, round((time.perf_counter() - start) * 1000, 2)
    except (socket.gaierror, OSError):
        return False, None


def internet_test():
    for url in ("https://www.google.com/generate_204",
                "https://1.1.1.1/"):
        try:
            start = time.perf_counter()
            req = urllib.request.Request(
                url, headers={"User-Agent": "NetworkChecker/1.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                r.read(1)
            return True, round((time.perf_counter() - start) * 1000, 2)
        except Exception:
            pass
    return False, None


def ping(host):
    if platform.system().lower() == "windows":
        cmd = ["ping", "-n", "1", "-w", "3000", host]
    else:
        cmd = ["ping", "-c", "1", "-W", "3", host]

    out = run(cmd, timeout=5)
    m = re.search(r"time[=<]\s*([\d.]+)\s*ms", out, re.I)
    return round(float(m.group(1)), 2) if m else None


def public_ip():
    for url in ("https://api.ipify.org", "https://ipv4.icanhazip.com"):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "NetworkChecker/1.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                ip = r.read().decode().strip()
            if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", ip):
                return ip
        except Exception:
            pass
    return ""


def download_test():
    url = "https://speed.cloudflare.com/__down?bytes=5000000"
    try:
        start = time.perf_counter()
        req = urllib.request.Request(
            url, headers={"User-Agent": "NetworkChecker/1.0"})
        total = 0
        with urllib.request.urlopen(req, timeout=15) as r:
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                total += len(chunk)
        elapsed = time.perf_counter() - start
        return round(total * 8 / elapsed / 1_000_000, 2) if total and elapsed else None
    except Exception:
        return None


def collect():
    iface = default_interface()
    gw = gateway()
    d = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "interface": iface,
        "mac": mac(iface) if iface else "",
        "local_ip": local_ip(iface),
        "gateway": gw,
        "dns_servers": dns_servers(),
        "public_ip": "",
        "internet": False,
        "internet_latency_ms": None,
        "dns_ok": False,
        "dns_latency_ms": None,
        "gateway_ping_ms": ping(gw) if gw else None,
        "google_ping_ms": ping("8.8.8.8"),
        "cloudflare_ping_ms": ping("1.1.1.1"),
        "download_mbps": None,
    }

    d["dns_ok"], d["dns_latency_ms"] = dns_test()
    d["internet"], d["internet_latency_ms"] = internet_test()

    if d["internet"]:
        d["public_ip"] = public_ip()
        d["download_mbps"] = download_test()

    return d


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Network Checker")
        self.root.geometry("700x650")
        self.root.minsize(620, 560)
        self.data = {}
        self.running = False
        self.vars = {}
        self.build()

    def build(self):
        ttk.Label(self.root, text="NETWORK CHECKER",
                  font=("TkDefaultFont", 20, "bold")).pack(pady=(18, 4))
        ttk.Label(self.root, text="Network diagnostic tool for Linux / Ubuntu").pack()

        self.status = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status,
                  font=("TkDefaultFont", 12, "bold")).pack(pady=12)

        info = ttk.LabelFrame(self.root, text="Network Information", padding=12)
        info.pack(fill="x", padx=18, pady=5)

        fields = [
            ("Interface", "interface"), ("MAC Address", "mac"),
            ("Local IP", "local_ip"), ("Gateway", "gateway"),
            ("Public IP", "public_ip"), ("DNS Servers", "dns_servers")
        ]
        for row, (label, key) in enumerate(fields):
            ttk.Label(info, text=label + ":").grid(row=row, column=0,
                                                   sticky="w", padx=(0, 18), pady=4)
            self.vars[key] = tk.StringVar(value="-")
            ttk.Label(info, textvariable=self.vars[key]).grid(
                row=row, column=1, sticky="w", pady=4)

        tests = ttk.LabelFrame(self.root, text="Connectivity Tests", padding=12)
        tests.pack(fill="x", padx=18, pady=5)

        fields = [
            ("Gateway ping", "gateway_ping_ms"),
            ("Google DNS ping", "google_ping_ms"),
            ("Cloudflare ping", "cloudflare_ping_ms"),
            ("DNS resolution", "dns_result"),
            ("Internet", "internet_result")
        ]
        for row, (label, key) in enumerate(fields):
            ttk.Label(tests, text=label + ":").grid(
                row=row, column=0, sticky="w", padx=(0, 18), pady=4)
            self.vars[key] = tk.StringVar(value="-")
            ttk.Label(tests, textvariable=self.vars[key]).grid(
                row=row, column=1, sticky="w", pady=4)

        speed = ttk.LabelFrame(self.root, text="Speed Test", padding=12)
        speed.pack(fill="x", padx=18, pady=5)
        ttk.Label(speed, text="Download:").grid(row=0, column=0, sticky="w")
        self.vars["download"] = tk.StringVar(value="-")
        ttk.Label(speed, textvariable=self.vars["download"]).grid(
            row=0, column=1, sticky="w", padx=18)
        ttk.Label(speed, text="Approximate test using a 5 MB download.").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))

        buttons = ttk.Frame(self.root)
        buttons.pack(pady=12)
        self.check_btn = ttk.Button(buttons, text="CHECK NETWORK",
                                    command=self.start)
        self.check_btn.pack(side="left", padx=5)
        self.export_btn = ttk.Button(buttons, text="EXPORT JSON",
                                     command=self.export, state="disabled")
        self.export_btn.pack(side="left", padx=5)

        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
        self.progress.pack(fill="x", padx=18, pady=(0, 8))

        self.log = tk.Text(self.root, height=7, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, padx=18, pady=(0, 15))

    def log_write(self, text):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def start(self):
        if self.running:
            return
        self.running = True
        self.check_btn.config(state="disabled")
        self.export_btn.config(state="disabled")
        self.progress.start(10)
        self.status.set("Checking network...")
        self.log_write("\n--- Network check started ---")
        threading.Thread(target=self.worker, daemon=True).start()

    def worker(self):
        try:
            data = collect()
            self.root.after(0, lambda: self.finish(data))
        except Exception as e:
            self.root.after(0, lambda: self.error(str(e)))

    @staticmethod
    def fmt(value):
        return f"{value} ms" if value is not None else "Failed"

    def finish(self, d):
        self.data = d
        self.running = False
        self.progress.stop()
        self.check_btn.config(state="normal")
        self.export_btn.config(state="normal")

        self.vars["interface"].set(d["interface"] or "Unknown")
        self.vars["mac"].set(d["mac"] or "Unknown")
        self.vars["local_ip"].set(d["local_ip"] or "Unknown")
        self.vars["gateway"].set(d["gateway"] or "Unknown")
        self.vars["public_ip"].set(d["public_ip"] or "Unknown")
        self.vars["dns_servers"].set(", ".join(d["dns_servers"]) or "Unknown")

        for key in ("gateway_ping_ms", "google_ping_ms", "cloudflare_ping_ms"):
            self.vars[key].set(self.fmt(d[key]))

        self.vars["dns_result"].set(
            f"OK ({d['dns_latency_ms']} ms)" if d["dns_ok"] else "FAILED")
        self.vars["internet_result"].set(
            f"OK ({d['internet_latency_ms']} ms)" if d["internet"] else "FAILED")
        self.vars["download"].set(
            f"{d['download_mbps']} Mbps" if d["download_mbps"] is not None else "Not available")

        self.status.set("● Connected" if d["internet"] else "● Disconnected")
        self.log_write("Internet: " + ("OK" if d["internet"] else "FAILED"))
        self.log_write("Gateway ping: " + self.fmt(d["gateway_ping_ms"]))
        self.log_write("Google ping: " + self.fmt(d["google_ping_ms"]))
        self.log_write("Cloudflare ping: " + self.fmt(d["cloudflare_ping_ms"]))
        self.log_write("DNS: " + ("OK" if d["dns_ok"] else "FAILED"))
        if d["download_mbps"] is not None:
            self.log_write(f"Download: {d['download_mbps']} Mbps")
        self.log_write("--- Check completed ---")

    def error(self, text):
        self.running = False
        self.progress.stop()
        self.check_btn.config(state="normal")
        self.status.set("Error")
        self.log_write("ERROR: " + text)
        messagebox.showerror("Network Checker", text)

    def export(self):
        if not self.data:
            return
        filename = filedialog.asksaveasfilename(
            title="Save network report",
            defaultextension=".json",
            initialfile="network_report.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not filename:
            return
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Network Checker", f"Report saved:\n{filename}")
        except OSError as e:
            messagebox.showerror("Network Checker", str(e))


def main():
    root = tk.Tk()
    try:
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
