from __future__ import annotations

import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk

from pynput import keyboard, mouse

from autoclicker.timing import next_interval


@dataclass(frozen=True)
class ClickSettings:
    x: int
    y: int
    interval: float
    variation: float


class ClickWorker:
    def __init__(self) -> None:
        self._active = threading.Event()
        self._closed = threading.Event()
        self._interrupt = threading.Event()
        self._lock = threading.Lock()
        self._settings = ClickSettings(0, 0, 1, 0)
        self._mouse = mouse.Controller()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    @property
    def active(self) -> bool:
        return self._active.is_set()

    def start(self, settings: ClickSettings) -> None:
        with self._lock:
            self._settings = settings
        self._interrupt.set()
        self._active.set()

    def stop(self) -> None:
        self._active.clear()
        self._interrupt.set()

    def close(self) -> None:
        self._closed.set()
        self._active.set()
        self._interrupt.set()
        self._thread.join(timeout=1)

    def _run(self) -> None:
        while not self._closed.is_set():
            self._active.wait()
            if self._closed.is_set():
                return
            self._interrupt.clear()
            with self._lock:
                settings = self._settings
            delay = next_interval(settings.interval, settings.variation)
            if self._interrupt.wait(delay):
                continue
            if self._active.is_set():
                self._mouse.position = (settings.x, settings.y)
                self._mouse.click(mouse.Button.left)


class AutoClickerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.worker = ClickWorker()
        self.events: queue.SimpleQueue[str | tuple[str, int, int]] = queue.SimpleQueue()
        self.point_listener: mouse.Listener | None = None
        self.hotkey_listener: keyboard.GlobalHotKeys | None = None

        self.x_var = tk.StringVar(value="0")
        self.y_var = tk.StringVar(value="0")
        self.interval_var = tk.StringVar(value="1.00")
        self.variation_var = tk.StringVar(value="15")
        self.hotkey_var = tk.StringVar(value="F8")
        self.status_var = tk.StringVar(value="Stopped")
        self.toggle_var = tk.StringVar(value="Start")

        self._build()
        self._install_hotkey()
        self.root.after(50, self._poll_events)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build(self) -> None:
        self.root.title("AutoClicker")
        self.root.resizable(False, False)
        frame = ttk.Frame(self.root, padding=16)
        frame.grid(sticky="nsew")

        ttk.Label(frame, text="Click position").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(frame, text="X").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(frame, textvariable=self.x_var, width=9).grid(row=1, column=1, padx=6, pady=(6, 0))
        ttk.Label(frame, text="Y").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(frame, textvariable=self.y_var, width=9).grid(row=2, column=1, padx=6, pady=(6, 0))
        ttk.Button(frame, text="Pick point", command=self._pick_point).grid(row=1, column=2, rowspan=2, padx=(8, 0), pady=(6, 0), sticky="ns")

        ttk.Separator(frame).grid(row=3, column=0, columnspan=3, sticky="ew", pady=14)
        ttk.Label(frame, text="Base interval (seconds)").grid(row=4, column=0, columnspan=2, sticky="w")
        ttk.Entry(frame, textvariable=self.interval_var, width=9).grid(row=4, column=2, sticky="e")
        ttk.Label(frame, text="Timing variation (%)").grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Spinbox(frame, from_=0, to=100, textvariable=self.variation_var, width=7).grid(row=5, column=2, sticky="e", pady=(8, 0))
        ttk.Label(frame, text="Toggle hotkey").grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))
        hotkey = ttk.Combobox(frame, textvariable=self.hotkey_var, values=[f"F{i}" for i in range(6, 13)], width=6, state="readonly")
        hotkey.grid(row=6, column=2, sticky="e", pady=(8, 0))
        hotkey.bind("<<ComboboxSelected>>", lambda _event: self._install_hotkey())

        ttk.Separator(frame).grid(row=7, column=0, columnspan=3, sticky="ew", pady=14)
        ttk.Label(frame, textvariable=self.status_var).grid(row=8, column=0, columnspan=2, sticky="w")
        ttk.Button(frame, textvariable=self.toggle_var, command=self.toggle).grid(row=8, column=2, sticky="e")

    def _settings(self) -> ClickSettings | None:
        try:
            settings = ClickSettings(
                x=int(self.x_var.get()),
                y=int(self.y_var.get()),
                interval=float(self.interval_var.get()),
                variation=float(self.variation_var.get()),
            )
            next_interval(settings.interval, settings.variation)
            return settings
        except ValueError as error:
            messagebox.showerror("Invalid settings", str(error) if str(error) else "Coordinates must be whole numbers")
            return None

    def toggle(self) -> None:
        if self.worker.active:
            self.worker.stop()
            self.status_var.set("Stopped")
            self.toggle_var.set("Start")
            return
        settings = self._settings()
        if settings is None:
            return
        self.worker.start(settings)
        self.status_var.set(f"Running at ({settings.x}, {settings.y})")
        self.toggle_var.set("Stop")

    def _pick_point(self) -> None:
        self.worker.stop()
        self.status_var.set("Click anywhere to select a point")
        self.toggle_var.set("Start")
        self.root.withdraw()

        def capture(x: int, y: int, button: mouse.Button, pressed: bool) -> bool | None:
            if pressed:
                self.events.put(("point", x, y))
                return False
            return None

        self.point_listener = mouse.Listener(on_click=capture)
        self.point_listener.start()

    def _install_hotkey(self) -> None:
        if self.hotkey_listener is not None:
            self.hotkey_listener.stop()
        key = f"<{self.hotkey_var.get().lower()}>"
        self.hotkey_listener = keyboard.GlobalHotKeys({key: lambda: self.events.put("toggle")})
        self.hotkey_listener.start()

    def _poll_events(self) -> None:
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if event == "toggle":
                self.toggle()
            elif isinstance(event, tuple) and event[0] == "point":
                self.x_var.set(str(event[1]))
                self.y_var.set(str(event[2]))
                self.status_var.set(f"Selected ({event[1]}, {event[2]})")
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
        self.root.after(50, self._poll_events)

    def close(self) -> None:
        self.worker.close()
        if self.point_listener is not None:
            self.point_listener.stop()
        if self.hotkey_listener is not None:
            self.hotkey_listener.stop()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    AutoClickerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
