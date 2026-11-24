#!/usr/bin/env python3
"""speeddisk - cross-platform TUI disk speed test (Linux, WSL, Windows, macOS).

Copyright (c) 2026 Roberto Bissanti <roberto.bissanti@gmail.com>
SPDX-License-Identifier: BSD-3-Clause

Usage: speeddisk [target_dir] [--size GB] [--block MB] [--secs N] [--lang xx]
Keys:  SPACE start/stop  t target  z file size  b block size  d direct I/O
       +/- phase time  l language  q quit
"""
import argparse
import io
import mmap
import sys
import os
import threading
import time
from collections import deque

try:
    import curses
except ImportError:  # Windows senza windows-curses
    sys.exit("curses module missing: on Windows run  pip install windows-curses")

IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
__version__ = "1.0.1"

# ------------------------------------------------------------ I18N ----
LANGS = ["en", "it", "es", "fr", "de"]
STR = {
    "press_start": {"en": "Press SPACE to start", "it": "Premi SPAZIO per avviare",
                    "es": "Pulsa ESPACIO para empezar", "fr": "Appuyez sur ESPACE pour démarrer",
                    "de": "LEERTASTE zum Starten drücken"},
    "error": {"en": "Error", "it": "Errore", "es": "Error", "fr": "Erreur", "de": "Fehler"},
    "stopped": {"en": "Stopped. Press SPACE to restart", "it": "Fermato. Premi SPAZIO per riavviare",
                "es": "Detenido. Pulsa ESPACIO para reiniciar",
                "fr": "Arrêté. Appuyez sur ESPACE pour relancer",
                "de": "Gestoppt. LEERTASTE zum Neustart"},
    "writing": {"en": "Writing...", "it": "Scrittura in corso...", "es": "Escribiendo...",
                "fr": "Écriture en cours...", "de": "Schreiben..."},
    "reading": {"en": "Reading...", "it": "Lettura in corso...", "es": "Leyendo...",
                "fr": "Lecture en cours...", "de": "Lesen..."},
    "stopping": {"en": "Stopping...", "it": "Arresto...", "es": "Deteniendo...",
                 "fr": "Arrêt...", "de": "Wird gestoppt..."},
    "stop_first": {"en": "Stop the test before changing settings",
                   "it": "Ferma il test prima di cambiare impostazioni",
                   "es": "Detén la prueba antes de cambiar ajustes",
                   "fr": "Arrêtez le test avant de modifier les réglages",
                   "de": "Test vor dem Ändern der Einstellungen stoppen"},
    "target_dir": {"en": "Target folder", "it": "Cartella target", "es": "Carpeta destino",
                   "fr": "Dossier cible", "de": "Zielordner"},
    "target_set": {"en": "Target set", "it": "Target impostato", "es": "Destino establecido",
                   "fr": "Cible définie", "de": "Ziel gesetzt"},
    "bad_dir": {"en": "Invalid or read-only folder", "it": "Cartella non valida o non scrivibile",
                "es": "Carpeta no válida o sin escritura", "fr": "Dossier invalide ou non inscriptible",
                "de": "Ungültiger oder schreibgeschützter Ordner"},
    "too_small": {"en": "Window too small", "it": "Finestra troppo piccola",
                  "es": "Ventana demasiado pequeña", "fr": "Fenêtre trop petite",
                  "de": "Fenster zu klein"},
    "device": {"en": "DEVICE", "it": "DISPOSITIVO", "es": "DISPOSITIVO", "fr": "PÉRIPHÉRIQUE",
               "de": "GERÄT"},
    "detecting": {"en": "Detecting device...", "it": "Rilevamento dispositivo in corso...",
                  "es": "Detectando dispositivo...", "fr": "Détection du périphérique...",
                  "de": "Gerät wird erkannt..."},
    "block": {"en": "Block", "it": "Blocco", "es": "Bloque", "fr": "Bloc", "de": "Block"},
    "phase": {"en": "Phase", "it": "Fase", "es": "Fase", "fr": "Phase", "de": "Phase"},
    "peak": {"en": "peak", "it": "picco", "es": "pico", "fr": "pic", "de": "Spitze"},
    "waiting": {"en": "(waiting for data)", "it": "(in attesa dati)", "es": "(esperando datos)",
                "fr": "(en attente de données)", "de": "(warte auf Daten)"},
    "will_it": {"en": "FORMAT SUPPORT", "it": "FORMATI SUPPORTATI", "es": "FORMATOS COMPATIBLES",
                "fr": "FORMATS PRIS EN CHARGE", "de": "UNTERSTÜTZTE FORMATE"},
    "title": {"en": "DISK SPEED TEST", "it": "TEST VELOCITÀ DISCO", "es": "PRUEBA DE VELOCIDAD DE DISCO",
              "fr": "TEST DE VITESSE DU DISQUE", "de": "FESTPLATTEN-GESCHWINDIGKEITSTEST"},
    "write": {"en": "WRITE", "it": "SCRITTURA", "es": "ESCRITURA", "fr": "ÉCRITURE", "de": "SCHREIBEN"},
    "read": {"en": "READ", "it": "LETTURA", "es": "LECTURA", "fr": "LECTURE", "de": "LESEN"},
    "rd_ch": {"en": "R", "it": "L", "es": "L", "fr": "L", "de": "L"},
    "wr_ch": {"en": "W", "it": "S", "es": "E", "fr": "É", "de": "S"},
    "target": {"en": "Target", "it": "Cartella", "es": "Destino", "fr": "Cible", "de": "Ziel"},
    "file": {"en": "File", "it": "File", "es": "Archivo", "fr": "Fichier", "de": "Datei"},
    "best": {"en": "best", "it": "migliore", "es": "mejor", "fr": "meilleur", "de": "bester"},
    "legend": {"en": "✔ read+write   R read only   W write only   ✘ no",
               "it": "✔ lettura+scrittura   L solo lettura   S solo scrittura   ✘ no",
               "es": "✔ lectura+escritura   L solo lectura   E solo escritura   ✘ no",
               "fr": "✔ lecture+écriture   L lecture seule   É écriture seule   ✘ non",
               "de": "✔ Lesen+Schreiben   L nur Lesen   S nur Schreiben   ✘ nein"},
    "mbs_needed": {"en": "MB/s required", "it": "MB/s richiesti", "es": "MB/s necesarios",
                   "fr": "MB/s requis", "de": "MB/s benötigt"},
    "format": {"en": "FORMAT", "it": "FORMATO", "es": "FORMATO", "fr": "FORMAT", "de": "FORMAT"},
    "keys": {"en": " [SPACE] start/stop  [t] target  [z] file  [b] block  [d] direct I/O  [+/-] time  [l] language  [q] quit ",
             "it": " [SPAZIO] avvia/ferma  [t] cartella  [z] file  [b] blocco  [d] I/O diretto  [+/-] durata  [l] lingua  [q] esci ",
             "es": " [ESPACIO] iniciar/parar  [t] destino  [z] archivo  [b] bloque  [d] E/S directa  [+/-] tiempo  [l] idioma  [q] salir ",
             "fr": " [ESPACE] démarrer/arrêter  [t] cible  [z] fichier  [b] bloc  [d] E/S directe  [+/-] durée  [l] langue  [q] quitter ",
             "de": " [LEER] Start/Stopp  [t] Ziel  [z] Datei  [b] Block  [d] Direkt-I/O  [+/-] Dauer  [l] Sprache  [q] Ende "},
    "unknown": {"en": "Unknown", "it": "Sconosciuto", "es": "Desconocido", "fr": "Inconnu",
                "de": "Unbekannt"},
    "disk": {"en": "Disk", "it": "Disco", "es": "Disco", "fr": "Disque", "de": "Laufwerk"},
    "virtual": {"en": "Virtual disk", "it": "Disco virtuale", "es": "Disco virtual",
                "fr": "Disque virtuel", "de": "Virtuelles Laufwerk"},
    "drive": {"en": "Drive", "it": "Unità", "es": "Unidad", "fr": "Lecteur", "de": "Laufwerk"},
    "on": {"en": "on", "it": "su", "es": "en", "fr": "sur", "de": "auf"},
    "host_prob": {"en": "host, probable", "it": "host, probabile", "es": "host, probable",
                  "fr": "hôte, probable", "de": "Host, vermutlich"},
    "note_net": {"en": "Network path: this measures the network, not a local disk.",
                 "it": "Percorso di rete: misura la rete, non un disco locale.",
                 "es": "Ruta de red: mide la red, no un disco local.",
                 "fr": "Chemin réseau : mesure le réseau, pas un disque local.",
                 "de": "Netzwerkpfad: misst das Netzwerk, keine lokale Platte."},
    "note_ram": {"en": "File lives in RAM: this does not measure a disk!",
                 "it": "Il file sta in memoria: non misura un disco!",
                 "es": "El archivo está en RAM: ¡no mide un disco!",
                 "fr": "Le fichier est en RAM : ne mesure pas un disque !",
                 "de": "Datei liegt im RAM: misst keine Platte!"},
    "note_9p": {"en": "WSL 9P access: speed is limited by the Linux↔Windows bridge, not the disk.",
                "it": "Accesso via protocollo 9P di WSL: la velocità è limitata dal bridge Linux↔Windows, non dal disco.",
                "es": "Acceso 9P de WSL: la velocidad la limita el puente Linux↔Windows, no el disco.",
                "fr": "Accès 9P de WSL : la vitesse est limitée par le pont Linux↔Windows, pas le disque.",
                "de": "WSL-9P-Zugriff: Tempo begrenzt durch die Linux↔Windows-Brücke, nicht die Platte."},
    "note_vhdx": {"en": "Virtual disk: Windows cache may inflate results, use large files (z).",
                  "it": "Disco virtuale: la cache di Windows può gonfiare i risultati, usa file grandi (z).",
                  "es": "Disco virtual: la caché de Windows puede inflar resultados, usa archivos grandes (z).",
                  "fr": "Disque virtuel : le cache Windows peut gonfler les résultats, utilisez de gros fichiers (z).",
                  "de": "Virtuelle Platte: Windows-Cache kann Werte verfälschen, große Dateien nutzen (z)."},
    "dev_lbl": {"en": "Device", "it": "Dispositivo", "es": "Dispositivo", "fr": "Périphérique",
                "de": "Gerät"},
    "note_lbl": {"en": "Note", "it": "Nota", "es": "Nota", "fr": "Note", "de": "Hinweis"},
}
LANG = "en"


def detect_lang():
    import locale
    cands = [os.environ.get(k, "") for k in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE")]
    try:
        cands.append(locale.getlocale()[0] or "")
    except ValueError:
        pass
    if IS_WIN:
        try:
            import ctypes
            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            cands.insert(0, locale.windows_locale.get(lcid, ""))
        except (OSError, AttributeError):
            pass
    names = {"italian": "it", "spanish": "es", "french": "fr", "german": "de", "english": "en"}
    for c in cands:
        c = c.lower()
        if c[:2] in LANGS:
            return c[:2]
        for n, code in names.items():
            if c.startswith(n):
                return code
    return "en"


def T(key):
    e = STR[key]
    return e.get(LANG) or e["en"]


SIZES_GB = [1, 2, 5, 10]
BLOCKS_MB = [1, 4, 16, 64]
GAUGE_MAX_STEPS = [100, 250, 500, 1000, 2000, 4000, 8000, 16000]

# (format name, approx. MB per frame)
FORMATS = [
    ("HD 1080p  8bit 4:2:2", 4.15),
    ("HD 1080p 10bit 4:2:2", 5.53),
    ("HD 1080p 12bit 4:4:4", 9.33),
    ("2K DCI   10bit 4:4:4", 13.00),
    ("UHD 2160p 10bit 4:2:2", 22.12),
    ("UHD 2160p 12bit 4:4:4", 37.32),
    ("4K DCI   12bit 4:4:4", 39.81),
    ("8K 4320p 10bit 4:2:2", 88.47),
]
FPS = [24, 25, 30, 50, 60, 120]


class Bench:
    def __init__(self, target, size_gb, block_mb, secs, direct):
        self.target = target
        self.size_gb = size_gb
        self.block_mb = block_mb
        self.secs = secs
        self.direct = direct
        self.running = False
        self.phase = "IDLE"
        self.write_mbs = 0.0
        self.read_mbs = 0.0
        self.best_w = 0.0
        self.best_r = 0.0
        self.hist_w = deque(maxlen=400)
        self.hist_r = deque(maxlen=400)
        self.msg = T("press_start")
        self.direct_active = False
        self.thread = None
        self.err = False
        self.device = None
        self.detect()

    def detect(self):
        self.device = None

        def run(t=self.target):
            d = detect_device(t)
            if t == self.target:
                self.device = d
        threading.Thread(target=run, daemon=True).start()

    @property
    def path(self):
        return os.path.join(self.target, ".speeddisk_test.tmp")

    def start(self):
        if self.running:
            return
        self.running = True
        self.err = False
        self.best_w = self.best_r = 0.0
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _open(self, flags):
        if IS_WIN:
            flags |= os.O_BINARY
            if self.direct:
                fd = _win_open_unbuffered(self.path, flags)
                if fd is not None:
                    self.direct_active = True
                    return fd
        elif self.direct and IS_MAC:
            import fcntl
            fd = os.open(self.path, flags, 0o600)
            try:
                fcntl.fcntl(fd, fcntl.F_NOCACHE, 1)
                self.direct_active = True
            except OSError:
                self.direct_active = False
            return fd
        elif self.direct and hasattr(os, "O_DIRECT"):
            try:
                fd = os.open(self.path, flags | os.O_DIRECT, 0o600)
                self.direct_active = True
                return fd
            except OSError:
                pass
        self.direct_active = False
        return os.open(self.path, flags, 0o600)

    def _drop_cache(self, fd):
        try:
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        except (OSError, AttributeError):
            pass

    def _loop(self):
        bs = self.block_mb * 1024 * 1024
        buf = mmap.mmap(-1, bs)  # page-aligned, adatto a O_DIRECT
        buf.write(os.urandom(bs))  # dati non comprimibili
        total = self.size_gb * 1024 ** 3
        try:
            while self.running:
                self._phase_write(buf, bs, total)
                if not self.running:
                    break
                self._phase_read(buf, bs, total)
        except OSError as e:
            self.msg = f"{T('error')}: {e.strerror} ({self.path})"
            self.err = True
        finally:
            self.running = False
            self.phase = "IDLE"
            buf.close()
            try:
                os.unlink(self.path)
            except OSError:
                pass
            if not self.err:
                self.msg = T("stopped")

    def _measure(self, fd, op, bs, total, setter, hist):
        t0 = time.perf_counter()
        last_t, last_b, done, pos = t0, 0, 0, 0
        while self.running and time.perf_counter() - t0 < self.secs:
            if pos >= total:
                pos = 0
                os.lseek(fd, 0, os.SEEK_SET)
            n = op(fd)
            if n <= 0:
                pos = total
                continue
            done += n
            pos += n
            now = time.perf_counter()
            if now - last_t >= 0.25:
                mbs = (done - last_b) / (now - last_t) / 1e6
                setter(mbs)
                hist.append(mbs)
                last_t, last_b = now, done
        return done, time.perf_counter() - t0

    def _phase_write(self, buf, bs, total):
        self.phase = "WRITE"
        self.msg = T("writing")
        fd = self._open(os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
        try:
            def setw(v):
                self.write_mbs = v
            done, el = self._measure(fd, lambda f: os.write(f, buf), bs, total,
                                     setw, self.hist_w)
            os.fsync(fd)
            el2 = el  # fsync incluso solo nell'ultimo campione
            if el2 > 0:
                self.write_mbs = done / el2 / 1e6
                self.best_w = max(self.best_w, self.write_mbs)
            self._drop_cache(fd)
        finally:
            os.close(fd)

    def _phase_read(self, buf, bs, total):
        self.phase = "READ"
        self.msg = T("reading")
        # assicura che il file abbia dati da leggere
        fd = self._open(os.O_RDONLY)
        try:
            self._drop_cache(fd)

            def setr(v):
                self.read_mbs = v
            done, el = self._measure(fd, lambda f: io.FileIO(f, 'rb', closefd=False).readinto(buf), bs,
                                     total, setr, self.hist_r)
            if el > 0:
                self.read_mbs = done / el / 1e6
                self.best_r = max(self.best_r, self.read_mbs)
        finally:
            os.close(fd)


# ------------------------------------------------------ DEVICE INFO ----
import re
import subprocess


def _win_open_unbuffered(path, flags):
    """Apre un file su Windows bypassando la cache (FILE_FLAG_NO_BUFFERING)."""
    import ctypes
    import msvcrt
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                wintypes.HANDLE]
    write = bool(flags & (os.O_WRONLY | os.O_RDWR))
    access = 0x40000000 if write else 0x80000000          # GENERIC_WRITE/READ
    disp = 2 if flags & os.O_CREAT else 3                  # CREATE_ALWAYS/OPEN_EXISTING
    attrs = 0x20000000 | 0x80000000 | 0x08000000           # NO_BUFFERING|WRITE_THROUGH|SEQ
    h = k32.CreateFileW(path, access, 1 | 2, None, disp, attrs, None)
    if h in (None, wintypes.HANDLE(-1).value):
        return None
    return msvcrt.open_osfhandle(h, os.O_BINARY | (os.O_WRONLY if write else os.O_RDONLY))


IS_WSL = "microsoft" in open("/proc/sys/kernel/osrelease").read().lower() \
    if os.path.exists("/proc/sys/kernel/osrelease") else False


def _rd(p):
    try:
        with open(p) as f:
            return f.read().strip()
    except OSError:
        return ""


def find_mount(path):
    """Ritorna (mountpoint, fstype, source, superopts) del mount che contiene path."""
    path = os.path.realpath(path)
    best = ("/", "?", "?", "")
    for line in _rd("/proc/self/mountinfo").splitlines():
        left, _, right = line.partition(" - ")
        mp = left.split()[4].replace("\\040", " ")
        r = right.split()
        if (path == mp or path.startswith(mp.rstrip("/") + "/")) and len(mp) >= len(best[0]):
            best = (mp, r[0], r[1].replace("\\134", "\\"), r[2] if len(r) > 2 else "")
    return best


def linux_disk(source):
    """Info su un block device Linux reale: (tipo, modello, extra)."""
    if not source.startswith("/dev/"):
        return None
    name = os.path.basename(os.path.realpath(source))
    sysd = f"/sys/class/block/{name}"
    if not os.path.exists(sysd):
        return None
    if os.path.exists(sysd + "/partition"):
        name = os.path.basename(os.path.dirname(os.path.realpath(sysd)))
    base = f"/sys/block/{name}"
    devpath = os.path.realpath(base)
    rot = _rd(base + "/queue/rotational") == "1"
    model = " ".join(x for x in (_rd(base + "/device/vendor"), _rd(base + "/device/model")) if x)
    if name.startswith("nvme"):
        kind = "SSD NVMe"
    elif "/usb" in devpath:
        kind = ("HDD" if rot else "Flash/SSD") + " USB"
    elif name.startswith("mmcblk"):
        kind = "SD / eMMC"
    elif "virtual" in model.lower() or "vmbus" in devpath or "virtio" in devpath or name.startswith(("vd", "xvd")):
        kind = "VIRTUAL"
    elif "/ata" in devpath:
        kind = ("HDD" if rot else "SSD") + " SATA"
    else:
        kind = "HDD" if rot else "SSD"
    return kind, model or name, f"/dev/{name}"


def windows_disk(letter):
    """Interroga Windows (da WSL) sul disco fisico che ospita la lettera di unità."""
    ps = (f"$p=Get-Partition -DriveLetter {letter} -EA Stop|Get-Disk;"
          "$d=Get-PhysicalDisk|?{$_.DeviceId -eq $p.Number};"
          "\"$($d.MediaType)|$($d.BusType)|$($d.FriendlyName)\"")
    try:
        out = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive",
                              "-Command", ps], capture_output=True, text=True,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                             timeout=15).stdout.strip().splitlines()
        media, bus, name = (out[-1].split("|") + ["", "", ""])[:3]
    except (OSError, subprocess.SubprocessError, IndexError):
        return None
    media = {"Unspecified": "", "SCM": "SCM"}.get(media, media)
    if bus == "NVMe":
        kind = "SSD NVMe"
    elif bus == "USB":
        kind = f"{media or T('disk')} USB"
    elif bus in ("SD", "MMC"):
        kind = "SD / eMMC"
    else:
        kind = f"{media or T('disk')} {bus}".strip()
    return kind, name or "?", f"{letter}:"


def mac_disk(path):
    """macOS: df + diskutil to identify the disk."""
    info = {"kind": T("unknown"), "model": "", "where": path, "note": ""}
    try:
        dev = subprocess.run(["df", path], capture_output=True, text=True,
                             timeout=10).stdout.splitlines()[-1].split()[0]
        out = subprocess.run(["diskutil", "info", dev], capture_output=True, text=True,
                             timeout=15).stdout
    except (OSError, subprocess.SubprocessError, IndexError):
        return info
    if not dev.startswith("/dev/"):
        info.update(where=dev, note=T("note_net"))
        return info
    kv = {}
    for line in out.splitlines():
        k, _, v = line.partition(":")
        kv[k.strip()] = v.strip()
    proto = kv.get("Protocol", "")
    ssd = kv.get("Solid State", "") == "Yes"
    if "PCI" in proto or "NVMe" in proto:
        kind = "SSD NVMe"
    elif proto == "Apple Fabric":
        kind = "SSD Apple"
    elif proto == "Disk Image":
        kind = T("virtual")
    else:
        kind = f"{'SSD' if ssd else 'HDD'} {proto}".strip()
    fs = kv.get("Type (Bundle)") or kv.get("File System Personality", "")
    info.update(kind=kind, model=kv.get("Device / Media Name", ""), where=f"{dev} ({fs})")
    return info


def detect_device(path):
    """Ritorna dict con kind, model, where, note."""
    if IS_WIN:
        drv = os.path.splitdrive(os.path.abspath(path))[0]
        info = {"kind": T("unknown"), "model": "", "where": drv or path, "note": ""}
        if len(drv) == 2 and drv[1] == ":":
            w = windows_disk(drv[0].upper())
            if w:
                info.update(kind=w[0], model=w[1], where=f"{T('drive')} {drv.upper()}")
        else:
            info["note"] = T("note_net")
        return info
    if IS_MAC:
        return mac_disk(path)
    mp, fs, src, opts = find_mount(path)
    info = {"kind": T("unknown"), "model": "", "where": f"{mp} ({fs})", "note": ""}
    if fs in ("tmpfs", "ramfs"):
        info.update(kind="RAM (tmpfs)", note=T("note_ram"))
        return info
    if IS_WSL and fs in ("9p", "drvfs", "v9fs"):
        m = re.search(r"path=([A-Za-z]):", opts) or re.match(r"([A-Za-z]):", src) \
            or re.match(r"/mnt/([a-z])$", mp)
        if m:
            w = windows_disk(m.group(1).upper())
            if w:
                info.update(kind=w[0], model=w[1])
            info["where"] = f"Windows {m.group(1).upper()}: via 9P/DrvFs"
        info["note"] = T("note_9p")
        return info
    d = linux_disk(src)
    if IS_WSL and d and d[0] == "VIRTUAL":
        w = windows_disk("C")
        info.update(kind="VHDX WSL" + (f" {T('on')} {w[0]}" if w else ""),
                    model=(w[1] + f" ({T('host_prob')})") if w else d[1],
                    where=f"{d[2]} ext4.vhdx ({fs})",
                    note=T("note_vhdx"))
        return info
    if d:
        info.update(kind=T("virtual") if d[0] == "VIRTUAL" else d[0], model=d[1], where=f"{d[2]} → {mp} ({fs})")
    return info


# ---------------------------------------------------------------- UI ----
BARS = " ▁▂▃▄▅▆▇█"


def gauge_max(v):
    for s in GAUGE_MAX_STEPS:
        if v <= s * 0.9:
            return s
    return GAUGE_MAX_STEPS[-1]


def put(win, y, x, s, attr=0):
    h, w = win.getmaxyx()
    if 0 <= y < h and 0 <= x < w:
        try:
            win.addstr(y, x, s[: w - x], attr)
        except curses.error:
            pass


def box(win, y, x, hh, ww, title="", attr=0):
    put(win, y, x, "╭" + "─" * (ww - 2) + "╮", attr)
    for i in range(1, hh - 1):
        put(win, y + i, x, "│", attr)
        put(win, y + i, x + ww - 1, "│", attr)
    put(win, y + hh - 1, x, "╰" + "─" * (ww - 2) + "╯", attr)
    if title:
        put(win, y, x + 2, f" {title} ", attr | curses.A_BOLD)


def chart(win, y, x, hh, ww, hist, color):
    """Grafico ad area multi-riga, scala sul massimo visibile."""
    data = list(hist)[-ww:]
    if not data:
        put(win, y + hh // 2, x + max(0, (ww - len(T("waiting"))) // 2), T("waiting"), curses.A_DIM)
        return
    vmax = max(data) * 1.1 or 1
    vmin = min(data)
    for col, v in enumerate(data):
        eighths = int(v / vmax * hh * 8)
        for r in range(hh):
            lvl = eighths - (hh - 1 - r) * 8
            if lvl > 0:
                put(win, y + r, x + col, BARS[min(8, lvl)], color)
    put(win, y, x, f"▲{vmax:.0f}", curses.A_DIM)
    put(win, y + hh - 1, x, f"min {vmin:.0f}", curses.A_DIM)


def draw_gauge(win, y, x, hh, w, label, active, val, best, hist, color):
    box(win, y, x, hh, w, ("● " if active else "") + label, color)
    ix, iw = x + 2, w - 4
    vmax = gauge_max(max(best, val, 1))
    big = f"{val:8.1f} MB/s"
    put(win, y + 1, ix + iw - len(big), big, curses.A_BOLD | color)
    put(win, y + 1, ix, f"{T('peak')} {best:.1f}", curses.A_DIM)
    fill = int(min(1.0, val / vmax) * iw)
    put(win, y + 2, ix, "█" * fill, color)
    put(win, y + 2, ix + fill, "░" * (iw - fill), curses.A_DIM)
    put(win, y + 3, ix, "0", curses.A_DIM)
    put(win, y + 3, ix + iw - len(str(vmax)), str(vmax), curses.A_DIM)
    put(win, y + 4, x + 1, "┄" * (w - 2), curses.A_DIM)
    chart(win, y + 5, ix, hh - 6, iw, hist, color)


def draw(scr, b):
    scr.erase()
    h, w = scr.getmaxyx()
    if h < 30 or w < 80:
        put(scr, 0, 0, f"{T('too_small')} ({w}x{h}, min 80x30)")
        scr.refresh()
        return
    G, R, Y, C = (curses.color_pair(i) for i in (1, 2, 3, 4))
    title = f" ◉ {T('title')} "
    put(scr, 0, (w - len(title)) // 2, title, curses.A_REVERSE | curses.A_BOLD)

    # riquadro dispositivo
    d = b.device
    box(scr, 1, 0, 5, w, T("device"), C)
    if d is None:
        put(scr, 2, 2, T("detecting"), curses.A_DIM)
    else:
        put(scr, 2, 2, f"{d['kind']}", Y | curses.A_BOLD | curses.A_REVERSE)
        put(scr, 2, 4 + len(d["kind"]), f"{d['model']}   [{d['where']}]", curses.A_BOLD)
        if d["note"]:
            put(scr, 4, 2, "⚠ " + d["note"], Y)
    io = "buffered"
    if b.direct:
        io = ("F_NOCACHE" if IS_MAC else "NO_BUFFERING" if IS_WIN else "O_DIRECT") if (b.direct_active or b.phase == "IDLE") else "buffered+fadvise"
    put(scr, 3, 2, f"{T('target')}: {b.target}   {T('file')}: {b.size_gb} GB   {T('block')}: {b.block_mb} MB"
        f"   {T('phase')}: {b.secs}s   I/O: {io}   [{LANG}]", C)

    # misuratori con grafico
    tbl_h = len(FORMATS) + 4
    gy = 6
    gh = h - gy - tbl_h - 2
    gw = w // 2
    draw_gauge(scr, gy, 0, gh, gw, T("write"), b.phase == "WRITE",
               b.write_mbs, b.best_w, b.hist_w, R)
    draw_gauge(scr, gy, gw, gh, w - gw, T("read"), b.phase == "READ",
               b.read_mbs, b.best_r, b.hist_r, G)

    # tabella formati
    ty = gy + gh
    box(scr, ty, 0, tbl_h, w, T("will_it"))
    two = w >= 2 + 24 + 6 * len(FPS) + 6 + 6 * len(FPS) + 2
    rx = 26 + 6 * len(FPS) + 6
    put(scr, ty + 1, 2, T("legend"),
        curses.A_DIM)
    if two:
        put(scr, ty + 1, rx, T("mbs_needed"), curses.A_DIM)
    hdr = f"{T('format'):24}" + "".join(f"{f:>6}" for f in FPS)
    put(scr, ty + 2, 2, hdr, curses.A_UNDERLINE)
    if two:
        put(scr, ty + 2, rx, "".join(f"{f:>6}" for f in FPS), curses.A_UNDERLINE)
    wv = b.best_w or b.write_mbs
    rv = b.best_r or b.read_mbs
    for i, (name, mbf) in enumerate(FORMATS):
        row = ty + 3 + i
        put(scr, row, 2, f"{name:24}")
        x = 26
        for fps in FPS:
            need = mbf * fps
            ok_w, ok_r = wv >= need, rv >= need
            if ok_w and ok_r:
                put(scr, row, x, f"{'✔':>6}", G | curses.A_BOLD)
            elif ok_r:
                put(scr, row, x, f"{T('rd_ch'):>6}", Y)
            elif ok_w:
                put(scr, row, x, f"{T('wr_ch'):>6}", Y)
            else:
                put(scr, row, x, f"{'✘':>6}", R | curses.A_DIM)
            x += 6
        if two:
            put(scr, row, rx, "".join(f"{mbf * f:6.0f}" for f in FPS), curses.A_DIM)

    put(scr, h - 2, 1, b.msg, Y)
    keys = T("keys")
    put(scr, h - 1, 0, keys.ljust(w - 1), curses.A_REVERSE)
    scr.refresh()


def prompt(scr, text, default):
    h, w = scr.getmaxyx()
    curses.echo()
    curses.curs_set(1)
    scr.move(h - 2, 1)
    scr.clrtoeol()
    scr.addstr(h - 2, 1, f"{text} [{default}]: ")
    scr.nodelay(False)
    s = scr.getstr(h - 2, len(text) + len(default) + 6, 200).decode().strip()
    curses.noecho()
    curses.curs_set(0)
    scr.nodelay(True)
    return s or default


def cycle(lst, v):
    return lst[(lst.index(v) + 1) % len(lst)] if v in lst else lst[0]


def main(scr, args):
    global LANG
    curses.curs_set(0)
    curses.start_color()
    try:
        curses.use_default_colors()
    except curses.error:
        pass
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_RED, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_CYAN, -1)
    scr.nodelay(True)
    b = Bench(os.path.abspath(args.target), args.size, args.block, args.secs,
              not args.no_direct)
    if args.start:
        b.start()
    while True:
        draw(scr, b)
        k = scr.getch()
        if k == curses.KEY_RESIZE and hasattr(curses, "resize_term"):
            curses.resize_term(0, 0)
            continue
        if k == -1:
            time.sleep(0.1)
            continue
        c = chr(k) if 0 <= k < 256 else ""
        if c in "qQ":
            b.stop()
            if b.thread:
                b.thread.join(timeout=b.secs + 5)
            break
        if c in " sS":
            if b.running:
                b.stop()
                b.msg = T("stopping")
            else:
                b.start()
        elif b.running:
            b.msg = T("stop_first")
        elif c == "t":
            t = os.path.abspath(os.path.expanduser(prompt(scr, T("target_dir"), b.target)))
            if os.path.isdir(t) and os.access(t, os.W_OK):
                b.target = t
                b.detect()
                b.msg = T("target_set")
            else:
                b.msg = f"{T('bad_dir')}: {t}"
        elif c == "l":
            LANG = cycle(LANGS, LANG)
            b.msg = T("press_start")
            b.detect()
        elif c == "z":
            b.size_gb = cycle(SIZES_GB, b.size_gb)
        elif c == "b":
            b.block_mb = cycle(BLOCKS_MB, b.block_mb)
        elif c == "d":
            b.direct = not b.direct
        elif c == "+":
            b.secs = min(60, b.secs + 1)
        elif c == "-":
            b.secs = max(2, b.secs - 1)


def headless(args):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    b = Bench(os.path.abspath(args.target), args.size, args.block, args.secs,
              not args.no_direct)
    b.start()
    time.sleep(args.secs * 2 * args.cycles + 0.5)
    b.stop()
    b.thread.join()
    d = detect_device(b.target)
    print(f"{T('dev_lbl')}: {d['kind']} - {d['model']} [{d['where']}]")
    if d["note"]:
        print(f"{T('note_lbl')}:", d["note"])
    print(f"{T('target')}: {b.target}  direct I/O: {b.direct_active}")
    print(f"{T('write')} {T('best')}: {b.best_w:.1f} MB/s   {T('read')} {T('best')}: {b.best_r:.1f} MB/s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="speeddisk",
                                 description="Cross-platform TUI disk speed test")
    ap.add_argument("target", nargs="?", default=".", help="folder to test (default: .)")
    ap.add_argument("--size", type=int, default=1, choices=SIZES_GB, help="test file size in GB")
    ap.add_argument("--block", type=int, default=4, choices=BLOCKS_MB, help="I/O block size in MB")
    ap.add_argument("--secs", type=int, default=5, help="seconds per write/read phase")
    ap.add_argument("--no-direct", action="store_true", help="disable direct (uncached) I/O")
    ap.add_argument("--headless", action="store_true", help="no TUI, print results and exit")
    ap.add_argument("--cycles", type=int, default=1, help="write+read cycles in headless mode")
    ap.add_argument("--start", action="store_true", help="start the test immediately")
    ap.add_argument("--lang", choices=LANGS, help="UI language (default: system)")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    a = ap.parse_args()
    LANG = a.lang or detect_lang()
    if not os.path.isdir(a.target):
        ap.error(f"folder not found: {a.target}")
    if a.headless:
        headless(a)
    else:
        curses.wrapper(main, a)
