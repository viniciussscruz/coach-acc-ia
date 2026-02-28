from __future__ import annotations

from collections import deque
import math
import queue
import threading
import time
import tkinter as tk
from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class OverlayPayload:
    status: str = "starting"
    provider: str = "-"
    lap: int = 0
    sector: int = 0
    speed_kmh: float = 0.0
    throttle: float = 0.0
    brake: float = 0.0
    steer: float = 0.0
    steering_angle_deg: float = 0.0
    spline: float = 0.0
    latest_hint: str = "Sem nova dica"
    hint_level: str = "info"
    baseline_label: str = "session_best"
    track_name: str = "-"
    track_length_m: float = 0.0
    fuel_l: Optional[float] = None
    fuel_estimated_laps: Optional[float] = None
    laps_remaining: Optional[int] = None
    fuel_will_finish: Optional[bool] = None
    road_temp_c: Optional[float] = None
    air_temp_c: Optional[float] = None
    traction_loss_rear: bool = False
    tires: dict[str, dict[str, float | None]] = field(default_factory=dict)
    updated_at: float = field(default_factory=time.time)


class CoachOverlayWindow:
    """Top-most windows overlay for quick in-race guidance and tire status."""

    def __init__(self, x: int, y: int, width: int, height: int) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self._queue: queue.Queue[OverlayPayload] = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_ui, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self.push(OverlayPayload(status="stopped"))

    def push(self, payload: OverlayPayload) -> None:
        if not self._running:
            return
        self._queue.put(payload)

    def _run_ui(self) -> None:
        try:
            root = tk.Tk()
        except Exception:  # noqa: BLE001
            self._running = False
            return

        main_min_w = max(540, min(self.width, 760))
        main_min_h = max(300, min(self.height, 420))
        main_size = {"w": max(self.width, main_min_w), "h": max(self.height, main_min_h)}

        tire_min_w = 360
        tire_min_h = 242
        tire_size = {"w": tire_min_w, "h": tire_min_h}

        root.title("AI Coach Overlay")
        root.geometry(f"{main_size['w']}x{main_size['h']}+{self.x}+{self.y}")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.90)
        root.configure(bg="#101418")

        frame = tk.Frame(root, bg="#101418", highlightthickness=2, highlightbackground="#304050")
        frame.pack(fill="both", expand=True)

        title_var = tk.StringVar(value="AI Driving Coach")
        move_btn_var = tk.StringVar(value="Mover")
        tire_btn_var = tk.StringVar(value="Pneus")
        alpha_var = tk.DoubleVar(value=90.0)
        meta_var = tk.StringVar(value="")
        metrics_var = tk.StringVar(value="")
        hint_var = tk.StringVar(value="Sem nova dica")
        footer_var = tk.StringVar(value="")

        drag_enabled = {"value": False}
        tire_visible = {"value": False}
        tire_drag_enabled = {"value": False}
        tire_manual_position = {"value": False}
        drag_start = {"x": 0, "y": 0}
        tire_drag_start = {"x": 0, "y": 0}
        resize_start = {"x": 0, "y": 0, "w": main_size["w"], "h": main_size["h"]}
        tire_resize_start = {"x": 0, "y": 0, "w": tire_size["w"], "h": tire_size["h"]}

        topbar = tk.Frame(frame, bg="#101418")
        title = tk.Label(topbar, textvariable=title_var, bg="#101418", fg="#8ad4ff", font=("Segoe UI", 12, "bold"))
        alpha_scale = tk.Scale(
            topbar,
            from_=55,
            to=100,
            orient="horizontal",
            showvalue=0,
            variable=alpha_var,
            length=96,
            sliderlength=12,
            bg="#101418",
            fg="#9db3d4",
            highlightthickness=0,
            troughcolor="#22344f",
            activebackground="#2e496d",
            bd=0,
        )
        tire_btn = tk.Button(
            topbar,
            textvariable=tire_btn_var,
            bg="#22344f",
            fg="#d9e7ff",
            activebackground="#2e496d",
            activeforeground="#ffffff",
            relief="flat",
            padx=10,
            pady=2,
            font=("Segoe UI", 9, "bold"),
        )
        move_btn = tk.Button(
            topbar,
            textvariable=move_btn_var,
            bg="#22344f",
            fg="#d9e7ff",
            activebackground="#2e496d",
            activeforeground="#ffffff",
            relief="flat",
            padx=10,
            pady=2,
            font=("Segoe UI", 9, "bold"),
        )

        meta = tk.Label(frame, textvariable=meta_var, bg="#101418", fg="#d0d7de", font=("Segoe UI", 10))
        metrics = tk.Label(frame, textvariable=metrics_var, bg="#101418", fg="#e6edf3", font=("Segoe UI", 12, "bold"))
        hint = tk.Label(
            frame,
            textvariable=hint_var,
            bg="#101418",
            fg="#f6bd60",
            font=("Segoe UI", 11, "bold"),
            anchor="w",
            justify="left",
            wraplength=main_size["w"] - 16,
        )
        pedals = tk.Canvas(
            frame,
            bg="#0b0f13",
            highlightthickness=1,
            highlightbackground="#304050",
            height=96,
        )
        footer = tk.Label(frame, textvariable=footer_var, bg="#101418", fg="#96a6b4", font=("Segoe UI", 9))

        throttle_history: deque[float] = deque(maxlen=160)
        brake_history: deque[float] = deque(maxlen=160)
        steer_history: deque[float] = deque(maxlen=160)

        topbar.pack(fill="x", padx=8, pady=(6, 0))
        title.pack(side="left", anchor="w")
        move_btn.pack(side="right", anchor="e")
        tire_btn.pack(side="right", anchor="e", padx=(0, 6))
        alpha_scale.pack(side="right", anchor="e", padx=(0, 8))
        meta.pack(anchor="w", padx=8, pady=(2, 0))
        metrics.pack(anchor="w", padx=8, pady=(6, 0))
        hint.pack(fill="x", padx=8, pady=(6, 0))
        pedals.pack(fill="x", padx=8, pady=(8, 0))
        footer.pack(anchor="w", padx=8, pady=(6, 6))
        resize_grip = tk.Label(
            frame,
            text="◢",
            bg="#101418",
            fg="#8aa7d6",
            font=("Segoe UI", 9, "bold"),
            cursor="size_nw_se",
        )
        resize_grip.place(relx=1.0, rely=1.0, anchor="se", x=-4, y=-4)

        tire_window = tk.Toplevel(root)
        tire_window.withdraw()
        tire_window.overrideredirect(True)
        tire_window.attributes("-topmost", True)
        tire_window.attributes("-alpha", 0.92)
        tire_window.configure(bg="#101418")
        tire_window.geometry(f"{tire_size['w']}x{tire_size['h']}+{self.x + main_size['w'] + 14}+{self.y}")

        tire_frame = tk.Frame(tire_window, bg="#101418", highlightthickness=2, highlightbackground="#304050")
        tire_frame.pack(fill="both", expand=True)
        tire_topbar = tk.Frame(tire_frame, bg="#101418")
        tire_title = tk.Label(
            tire_topbar,
            text="Status De Pneus E Freios",
            bg="#101418",
            fg="#8ad4ff",
            font=("Segoe UI", 11, "bold"),
        )
        tire_alpha_var = tk.DoubleVar(value=92.0)
        tire_alpha_scale = tk.Scale(
            tire_topbar,
            from_=55,
            to=100,
            orient="horizontal",
            showvalue=0,
            variable=tire_alpha_var,
            length=90,
            sliderlength=12,
            bg="#101418",
            fg="#9db3d4",
            highlightthickness=0,
            troughcolor="#22344f",
            activebackground="#2e496d",
            bd=0,
        )
        tire_move_btn_var = tk.StringVar(value="Mover")
        tire_move_btn = tk.Button(
            tire_topbar,
            textvariable=tire_move_btn_var,
            bg="#22344f",
            fg="#d9e7ff",
            activebackground="#2e496d",
            activeforeground="#ffffff",
            relief="flat",
            padx=10,
            pady=2,
            font=("Segoe UI", 9, "bold"),
        )
        tire_topbar.pack(fill="x", padx=8, pady=(6, 2))
        tire_title.pack(side="left", anchor="w")
        tire_move_btn.pack(side="right", anchor="e")
        tire_alpha_scale.pack(side="right", anchor="e", padx=(0, 8))

        tire_env_var = tk.StringVar(value="Pista -C | Ar -C | Tracao traseira: -")
        tk.Label(tire_frame, textvariable=tire_env_var, bg="#101418", fg="#d0d7de", font=("Segoe UI", 9)).pack(
            anchor="w", padx=8, pady=(0, 6)
        )

        tire_row_vars: dict[str, tk.StringVar] = {
            "FL": tk.StringVar(value="FL  P:-  T:-  B:-"),
            "FR": tk.StringVar(value="FR  P:-  T:-  B:-"),
            "RL": tk.StringVar(value="RL  P:-  T:-  B:-"),
            "RR": tk.StringVar(value="RR  P:-  T:-  B:-"),
        }
        tire_row_labels: dict[str, tk.Label] = {}
        for code in ("FL", "FR", "RL", "RR"):
            label = tk.Label(
                tire_frame,
                textvariable=tire_row_vars[code],
                bg="#101418",
                fg="#d8e3f3",
                font=("Consolas", 10, "bold"),
                anchor="w",
            )
            label.pack(fill="x", padx=8, pady=(0, 4))
            tire_row_labels[code] = label
        tire_resize_grip = tk.Label(
            tire_frame,
            text="◢",
            bg="#101418",
            fg="#8aa7d6",
            font=("Segoe UI", 9, "bold"),
            cursor="size_nw_se",
        )
        tire_resize_grip.place(relx=1.0, rely=1.0, anchor="se", x=-4, y=-4)

        def _fmt_num(value: float | int | None, digits: int = 1) -> str:
            if value is None:
                return "-"
            return f"{float(value):.{digits}f}"

        def _fmt_bool(value: bool | None) -> str:
            if value is None:
                return "-"
            return "SIM" if value else "NAO"

        def _temp_color(temp_value: float | None) -> str:
            if temp_value is None:
                return "#d8e3f3"
            if temp_value < 72.0:
                return "#7fb6ff"
            if temp_value > 102.0:
                return "#ff9d7f"
            return "#7de3a9"

        def _place_tire_window(nx: int | None = None, ny: int | None = None) -> None:
            base_x = root.winfo_x() if nx is None else nx
            base_y = root.winfo_y() if ny is None else ny
            tire_window.geometry(f"{tire_size['w']}x{tire_size['h']}+{base_x + main_size['w'] + 14}+{base_y}")

        def _apply_main_size(new_w: int, new_h: int) -> None:
            screen_w = root.winfo_screenwidth()
            screen_h = root.winfo_screenheight()
            main_size["w"] = max(main_min_w, min(new_w, screen_w - 8))
            main_size["h"] = max(main_min_h, min(new_h, screen_h - 8))
            x = root.winfo_x()
            y = root.winfo_y()
            root.geometry(f"{main_size['w']}x{main_size['h']}+{x}+{y}")
            hint.configure(wraplength=max(180, main_size["w"] - 16))
            if tire_visible["value"] and not tire_manual_position["value"]:
                _place_tire_window(x, y)

        def _apply_tire_size(new_w: int, new_h: int) -> None:
            screen_w = tire_window.winfo_screenwidth()
            screen_h = tire_window.winfo_screenheight()
            tire_size["w"] = max(tire_min_w, min(new_w, screen_w - 8))
            tire_size["h"] = max(tire_min_h, min(new_h, screen_h - 8))
            x = tire_window.winfo_x()
            y = tire_window.winfo_y()
            tire_window.geometry(f"{tire_size['w']}x{tire_size['h']}+{x}+{y}")

        def _set_drag_enabled(enabled: bool) -> None:
            drag_enabled["value"] = enabled
            if enabled:
                move_btn_var.set("Travar")
                footer_var.set("Modo mover ativo: arraste a janela e clique Travar.")
                frame.configure(highlightbackground="#f6bd60")
            else:
                move_btn_var.set("Mover")
                frame.configure(highlightbackground="#304050")

        def _toggle_drag() -> None:
            _set_drag_enabled(not drag_enabled["value"])

        def _toggle_tire_window() -> None:
            tire_visible["value"] = not tire_visible["value"]
            if tire_visible["value"]:
                if not tire_manual_position["value"]:
                    _place_tire_window()
                tire_window.deiconify()
                tire_btn_var.set("Pneus ON")
            else:
                tire_window.withdraw()
                tire_btn_var.set("Pneus")

        def _start_drag(event: tk.Event) -> None:
            if not drag_enabled["value"]:
                return
            drag_start["x"] = event.x_root - root.winfo_x()
            drag_start["y"] = event.y_root - root.winfo_y()

        def _on_drag(event: tk.Event) -> None:
            if not drag_enabled["value"]:
                return
            nx = event.x_root - drag_start["x"]
            ny = event.y_root - drag_start["y"]
            root.geometry(f"{main_size['w']}x{main_size['h']}+{nx}+{ny}")
            if tire_visible["value"] and not tire_manual_position["value"]:
                _place_tire_window(nx, ny)

        def _set_tire_drag_enabled(enabled: bool) -> None:
            tire_drag_enabled["value"] = enabled
            if enabled:
                tire_move_btn_var.set("Travar")
                tire_frame.configure(highlightbackground="#f6bd60")
            else:
                tire_move_btn_var.set("Mover")
                tire_frame.configure(highlightbackground="#304050")

        def _toggle_tire_drag() -> None:
            _set_tire_drag_enabled(not tire_drag_enabled["value"])

        def _start_tire_drag(event: tk.Event) -> None:
            if not tire_drag_enabled["value"]:
                return
            tire_drag_start["x"] = event.x_root - tire_window.winfo_x()
            tire_drag_start["y"] = event.y_root - tire_window.winfo_y()

        def _on_tire_drag(event: tk.Event) -> None:
            if not tire_drag_enabled["value"]:
                return
            nx = event.x_root - tire_drag_start["x"]
            ny = event.y_root - tire_drag_start["y"]
            tire_window.geometry(f"{tire_size['w']}x{tire_size['h']}+{nx}+{ny}")
            tire_manual_position["value"] = True

        def _start_resize(event: tk.Event) -> None:
            resize_start["x"] = event.x_root
            resize_start["y"] = event.y_root
            resize_start["w"] = main_size["w"]
            resize_start["h"] = main_size["h"]

        def _on_resize(event: tk.Event) -> None:
            delta_x = event.x_root - resize_start["x"]
            delta_y = event.y_root - resize_start["y"]
            _apply_main_size(resize_start["w"] + delta_x, resize_start["h"] + delta_y)

        def _start_tire_resize(event: tk.Event) -> None:
            tire_resize_start["x"] = event.x_root
            tire_resize_start["y"] = event.y_root
            tire_resize_start["w"] = tire_size["w"]
            tire_resize_start["h"] = tire_size["h"]
            tire_manual_position["value"] = True

        def _on_tire_resize(event: tk.Event) -> None:
            delta_x = event.x_root - tire_resize_start["x"]
            delta_y = event.y_root - tire_resize_start["y"]
            _apply_tire_size(tire_resize_start["w"] + delta_x, tire_resize_start["h"] + delta_y)

        move_btn.configure(command=_toggle_drag)
        tire_btn.configure(command=_toggle_tire_window)
        tire_move_btn.configure(command=_toggle_tire_drag)
        for widget in (topbar, title, frame):
            widget.bind("<ButtonPress-1>", _start_drag)
            widget.bind("<B1-Motion>", _on_drag)
        for widget in (tire_topbar, tire_title, tire_frame):
            widget.bind("<ButtonPress-1>", _start_tire_drag)
            widget.bind("<B1-Motion>", _on_tire_drag)
        resize_grip.bind("<ButtonPress-1>", _start_resize)
        resize_grip.bind("<B1-Motion>", _on_resize)
        tire_resize_grip.bind("<ButtonPress-1>", _start_tire_resize)
        tire_resize_grip.bind("<B1-Motion>", _on_tire_resize)

        def _on_main_alpha(_value: str) -> None:
            root.attributes("-alpha", max(0.55, min(1.0, alpha_var.get() / 100.0)))

        def _on_tire_alpha(_value: str) -> None:
            tire_window.attributes("-alpha", max(0.55, min(1.0, tire_alpha_var.get() / 100.0)))

        alpha_scale.configure(command=_on_main_alpha)
        tire_alpha_scale.configure(command=_on_tire_alpha)

        def _draw_pedals(throttle: float, brake: float, steer_deg: float) -> None:
            pedals.delete("all")
            width = max(120, pedals.winfo_width())
            height = max(70, pedals.winfo_height())
            left = 8
            right = width - 8
            dial_w = 114
            graph_right = max(left + 140, right - dial_w - 8)
            bar_w = max(120, graph_right - left)
            bar_h = 10
            max_steer_deg = 180.0
            steer_deg_clamped = max(-max_steer_deg, min(max_steer_deg, steer_deg))

            pedals.create_rectangle(left, 8, left + bar_w, 8 + bar_h, fill="#1f2a36", outline="")
            pedals.create_rectangle(left, 24, left + bar_w, 24 + bar_h, fill="#1f2a36", outline="")
            pedals.create_rectangle(left, 8, left + int(bar_w * throttle), 8 + bar_h, fill="#00c27a", outline="")
            pedals.create_rectangle(left, 24, left + int(bar_w * brake), 24 + bar_h, fill="#ff5c5c", outline="")
            pedals.create_text(left, 5, anchor="w", text=f"THR {throttle*100:3.0f}%", fill="#9ddfc6", font=("Segoe UI", 8, "bold"))
            pedals.create_text(left, 21, anchor="w", text=f"BRK {brake*100:3.0f}%", fill="#ffb2b2", font=("Segoe UI", 8, "bold"))
            pedals.create_text(left + bar_w - 2, 5, anchor="e", text=f"STR {steer_deg:+6.1f} deg", fill="#a7d0ff", font=("Segoe UI", 8, "bold"))

            plot_top = 42
            plot_bottom = height - 8
            plot_h = max(8, plot_bottom - plot_top)
            pedals.create_rectangle(left, plot_top, left + bar_w, plot_bottom, outline="#2b3a4d", fill="#111820")
            y_mid = plot_top + (plot_h * 0.5)
            pedals.create_line(left, y_mid, left + bar_w, y_mid, fill="#304257", width=1)
            if len(throttle_history) >= 2:
                step = bar_w / float(max(1, len(throttle_history) - 1))
                thr_points: list[float] = []
                brk_points: list[float] = []
                str_points: list[float] = []
                for idx, (thr, brk, str_deg) in enumerate(zip(throttle_history, brake_history, steer_history)):
                    x = left + idx * step
                    y_thr = plot_bottom - (thr * plot_h)
                    y_brk = plot_bottom - (brk * plot_h)
                    str_norm = max(-1.0, min(1.0, str_deg / max_steer_deg))
                    y_str = y_mid - (str_norm * (plot_h * 0.5 - 1))
                    thr_points.extend((x, y_thr))
                    brk_points.extend((x, y_brk))
                    str_points.extend((x, y_str))
                pedals.create_line(*thr_points, fill="#00d084", width=1.8, smooth=True)
                pedals.create_line(*brk_points, fill="#ff6b6b", width=1.8, smooth=True)
                pedals.create_line(*str_points, fill="#6ea8ff", width=1.8, smooth=True)

            dial_left = graph_right + 10
            dial_right = right
            cx = dial_left + ((dial_right - dial_left) * 0.5)
            cy = (height * 0.53)
            radius = max(16, min((dial_right - dial_left) * 0.45, height * 0.33))
            pedals.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline="#3a4f73", width=2)
            pedals.create_line(cx - radius, cy, cx + radius, cy, fill="#24354d", width=1)
            pedals.create_line(cx, cy - radius, cx, cy + radius, fill="#24354d", width=1)
            ratio = steer_deg_clamped / max_steer_deg
            angle_rad = math.radians(-90.0 + ratio * 120.0)
            nx = cx + math.cos(angle_rad) * (radius - 4)
            ny = cy + math.sin(angle_rad) * (radius - 4)
            pedals.create_line(cx, cy, nx, ny, fill="#8ec5ff", width=3)
            pedals.create_text(cx, cy + radius + 10, text="Volante", fill="#9db3d4", font=("Segoe UI", 8, "bold"))

        def apply_payload(payload: OverlayPayload) -> None:
            fuel_text = f"{_fmt_num(payload.fuel_l, 1)}L"
            est_laps_text = _fmt_num(payload.fuel_estimated_laps, 2)
            laps_left_text = "-" if payload.laps_remaining is None else str(int(payload.laps_remaining))

            title_var.set(f"AI Driving Coach | {payload.status.upper()}")
            meta_var.set(
                f"provider={payload.provider} baseline={payload.baseline_label} "
                f"track={payload.track_name} ({payload.track_length_m:.0f}m) "
                f"fuel={fuel_text} est={est_laps_text}L left={laps_left_text}"
            )
            metrics_var.set(
                f"L{payload.lap:02d} S{payload.sector or 0} | "
                f"{payload.speed_kmh:5.1f} km/h | THR {payload.throttle*100:3.0f}% | BRK {payload.brake*100:3.0f}% "
                f"| STR {payload.steering_angle_deg:+6.1f} deg"
            )
            hint_var.set(payload.latest_hint)
            level_color = {"info": "#8ad4ff", "warn": "#f6bd60", "critical": "#f28482"}.get(payload.hint_level, "#8ad4ff")
            hint.configure(fg=level_color)

            throttle_history.append(max(0.0, min(1.0, payload.throttle)))
            brake_history.append(max(0.0, min(1.0, payload.brake)))
            steer_history.append(payload.steering_angle_deg)
            _draw_pedals(payload.throttle, payload.brake, payload.steering_angle_deg)

            traction_text = "PATINANDO" if payload.traction_loss_rear else "OK"
            tire_env_var.set(
                f"Pista {_fmt_num(payload.road_temp_c, 1)}C | Ar {_fmt_num(payload.air_temp_c, 1)}C | "
                f"Tracao traseira: {traction_text}"
            )
            for code in ("FL", "FR", "RL", "RR"):
                data = payload.tires.get(code, {})
                pressure = _fmt_num(data.get("pressure"), 2)
                temp = _fmt_num(data.get("temp"), 1)
                brake_temp = _fmt_num(data.get("brake_temp"), 0)
                slip = data.get("slip_ratio")
                slip_str = f" | slip {float(slip):+.2f}" if slip is not None else ""
                tire_row_vars[code].set(f"{code}  P:{pressure} psi  T:{temp}C  B:{brake_temp}C{slip_str}")
                tire_row_labels[code].configure(fg=_temp_color(data.get("temp")))

            if not drag_enabled["value"]:
                footer_var.set(
                    f"spline={payload.spline:.4f} fuel_ok={_fmt_bool(payload.fuel_will_finish)} "
                    f"updated={time.strftime('%H:%M:%S', time.localtime(payload.updated_at))}"
                )

        def tick() -> None:
            if not self._running:
                try:
                    tire_window.destroy()
                except Exception:  # noqa: BLE001
                    pass
                root.destroy()
                return

            last_payload: Optional[OverlayPayload] = None
            while True:
                try:
                    last_payload = self._queue.get_nowait()
                except queue.Empty:
                    break
            if last_payload is not None:
                apply_payload(last_payload)
            root.after(80, tick)

        root.after(80, tick)
        root.mainloop()
