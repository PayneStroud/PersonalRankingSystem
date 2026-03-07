import csv
import json
import os
import tkinter as tk
import customtkinter as ctk
from copy import deepcopy
from datetime import datetime
from tkinter import filedialog, messagebox, simpledialog

DIMS = ["Appearance", "Personality", "Compatibility"]
DEFAULT_WEIGHTS = {"Appearance": 0.25, "Personality": 0.25, "Compatibility": 0.5}


class RankingSystem:
    def __init__(self):
        self.nodes = {}
        self.details = {}
        self.rankings = {dim: [] for dim in DIMS}
        self.confidence = {}
        self.comparisons = set()
        self.weights = DEFAULT_WEIGHTS.copy()
        self.snapshots = []

    def _new_node(self):
        return {"Appearance": 5.0, "Personality": 5.0, "Compatibility": 5.0, "Overall": 5.0}

    def _new_conf(self):
        return {dim: 0 for dim in DIMS}

    def _new_details(self):
        return {"notes": "", "tags": "", "photo": ""}

    def _ensure_node_maps(self, name):
        if name not in self.confidence or not isinstance(self.confidence[name], dict):
            self.confidence[name] = self._new_conf()
        else:
            for dim in DIMS:
                self.confidence[name].setdefault(dim, 0)
        self.details.setdefault(name, self._new_details())

    def add_node(self, name, ask_func):
        clean = (name or "").strip()
        if not clean or clean in self.nodes:
            return False

        self.nodes[clean] = self._new_node()
        self.confidence[clean] = self._new_conf()
        self.details[clean] = self._new_details()

        for dim in DIMS:
            if not self.rankings[dim]:
                self.rankings[dim] = [[clean]]
            elif len(self.nodes) > 1:
                self.insert_node_ranked(clean, dim, ask_func)

        self.rebalance_ratings()
        return True

    def insert_node_ranked(self, name, dim, ask_func):
        ranking = self.rankings[dim]
        if not ranking:
            self.rankings[dim] = [[name]]
            return

        low, high = 0, len(ranking)
        while low < high:
            mid = (low + high) // 2
            compare_to = ranking[mid][0]
            result = ask_func(f"For {dim}, is '{name}' better than '{compare_to}'?")

            if result == "yes":
                self.record_comparison(name, compare_to, dims=[dim], mark_pair=False)
                high = mid
            elif result == "no":
                self.record_comparison(name, compare_to, dims=[dim], mark_pair=False)
                low = mid + 1
            else:
                self.record_comparison(name, compare_to, dims=[dim], mark_pair=False)
                ranking[mid].append(name)
                return

        ranking.insert(low, [name])

    def _find_group_index(self, dim, name):
        for idx, group in enumerate(self.rankings.get(dim, [])):
            if name in group:
                return idx
        return None

    def record_comparison(self, a, b, dims=None, mark_pair=True):
        if a not in self.nodes or b not in self.nodes or a == b:
            return

        dims = dims or DIMS
        self._ensure_node_maps(a)
        self._ensure_node_maps(b)
        for dim in dims:
            self.confidence[a][dim] += 1
            self.confidence[b][dim] += 1

        if mark_pair:
            self.comparisons.add(tuple(sorted([a, b])))

    def move_winner_above_loser(self, winner, loser, dims=None, mark_pair=False):
        if winner == loser or winner not in self.nodes or loser not in self.nodes:
            return False

        changed = False
        dims = dims or DIMS

        for dim in dims:
            ranking = self.rankings.get(dim, [])
            if not ranking:
                continue

            winner_idx = self._find_group_index(dim, winner)
            loser_idx = self._find_group_index(dim, loser)
            if winner_idx is None or loser_idx is None:
                continue
            if winner_idx < loser_idx:
                continue

            ranking[winner_idx].remove(winner)
            if not ranking[winner_idx]:
                ranking.pop(winner_idx)

            loser_idx = self._find_group_index(dim, loser)
            if loser_idx is None:
                continue
            ranking.insert(loser_idx, [winner])
            changed = True

        self.record_comparison(winner, loser, dims=dims, mark_pair=mark_pair)
        if changed:
            self.rebalance_ratings()
        return changed

    def delete_node(self, name):
        if name not in self.nodes:
            return False

        del self.nodes[name]
        self.confidence.pop(name, None)
        self.details.pop(name, None)

        for dim in DIMS:
            self.rankings[dim] = [[n for n in group if n != name] for group in self.rankings[dim]]
            self.rankings[dim] = [group for group in self.rankings[dim] if group]

        self.comparisons = {pair for pair in self.comparisons if name not in pair}
        self.rebalance_ratings()
        return True

    def set_weights(self, appearance, personality, compatibility):
        raw = {
            "Appearance": float(appearance),
            "Personality": float(personality),
            "Compatibility": float(compatibility),
        }
        total = sum(raw.values())
        if total <= 0:
            raise ValueError("Weights must sum to a positive number.")
        self.weights = {k: v / total for k, v in raw.items()}
        self.rebalance_ratings()

    def rebalance_ratings(self):
        for dim in DIMS:
            ranking = self.rankings.get(dim, [])
            n_groups = len(ranking)
            if n_groups == 0:
                continue
            if n_groups == 1:
                for node in ranking[0]:
                    self.nodes[node][dim] = 5.0
                continue

            for idx, group in enumerate(ranking):
                ratio = idx / (n_groups - 1)
                rating = 10.0 - ratio * 10.0
                for node in group:
                    self.nodes[node][dim] = rating

        for node in self.nodes:
            self._ensure_node_maps(node)
            self.nodes[node]["Overall"] = sum(self.weights[dim] * self.nodes[node][dim] for dim in DIMS)

    def get_confidence(self, name, dim=None):
        if name not in self.nodes:
            return 0

        self._ensure_node_maps(name)
        max_possible = max(1, len(self.nodes) - 1)

        if dim in DIMS:
            return min(100, int((self.confidence[name][dim] / max_possible) * 100))

        return int(sum(self.get_confidence(name, d) for d in DIMS) / len(DIMS))

    def sorted_nodes(self, sort_key="Overall", reverse=True):
        if sort_key == "Name":
            return sorted(self.nodes.items(), key=lambda x: x[0].lower())
        if sort_key == "Confidence":
            return sorted(self.nodes.items(), key=lambda x: self.get_confidence(x[0]), reverse=reverse)
        if sort_key in DIMS + ["Overall"]:
            return sorted(self.nodes.items(), key=lambda x: x[1][sort_key], reverse=reverse)
        return sorted(self.nodes.items(), key=lambda x: x[1]["Overall"], reverse=True)

    def suggest_comparison(self):
        nodes = list(self.nodes.keys())
        best_pair = None
        best_score = float("inf")

        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a, b = nodes[i], nodes[j]
                pair = tuple(sorted([a, b]))
                if pair in self.comparisons:
                    continue

                score_diff = abs(self.nodes[a]["Overall"] - self.nodes[b]["Overall"])
                uncertainty = (100 - self.get_confidence(a)) + (100 - self.get_confidence(b))
                score = score_diff + uncertainty * 0.05
                if score < best_score:
                    best_score = score
                    best_pair = (a, b)

        return best_pair

    def needs_review_pairs(self, limit=15):
        names = list(self.nodes.keys())
        rows = []
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                diff = abs(self.nodes[a]["Overall"] - self.nodes[b]["Overall"])
                conf_a = self.get_confidence(a)
                conf_b = self.get_confidence(b)
                low_conf = (200 - (conf_a + conf_b)) / 2
                closeness = max(0.0, 10.0 - diff)
                review_score = low_conf * 0.7 + closeness * 3.0
                rows.append((review_score, a, b, diff, conf_a, conf_b))

        rows.sort(key=lambda x: x[0], reverse=True)
        return rows[:limit]

    def add_snapshot(self, reason):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        top = [
            {"name": name, "overall": round(data["Overall"], 2)}
            for name, data in self.sorted_nodes("Overall", reverse=True)[:10]
        ]
        self.snapshots.append({"timestamp": timestamp, "reason": reason, "top": top})
        self.snapshots = self.snapshots[-200:]

    def save_to_file(self, filename):
        payload = {
            "version": 2,
            "nodes": self.nodes,
            "details": self.details,
            "rankings": self.rankings,
            "confidence": self.confidence,
            "comparisons": [list(pair) for pair in self.comparisons],
            "weights": self.weights,
            "snapshots": self.snapshots,
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def load_from_file(self, filename):
        if not os.path.exists(filename):
            return False

        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.nodes = {name: {k: float(v) for k, v in stats.items()} for name, stats in data.get("nodes", {}).items()}
        self.rankings = data.get("rankings", {dim: [] for dim in DIMS})
        self.comparisons = set(tuple(sorted(pair)) for pair in data.get("comparisons", []))
        self.weights = data.get("weights", DEFAULT_WEIGHTS.copy())
        self.snapshots = data.get("snapshots", [])

        raw_conf = data.get("confidence", {})
        self.confidence = {}
        for name in self.nodes:
            val = raw_conf.get(name, self._new_conf())
            if isinstance(val, dict):
                self.confidence[name] = {dim: int(val.get(dim, 0)) for dim in DIMS}
            else:
                self.confidence[name] = {dim: int(val) for dim in DIMS}

        raw_details = data.get("details", {})
        self.details = {}
        for name in self.nodes:
            d = raw_details.get(name, {})
            self.details[name] = {
                "notes": str(d.get("notes", "")),
                "tags": str(d.get("tags", "")),
                "photo": str(d.get("photo", "")),
            }

        for dim in DIMS:
            self.rankings.setdefault(dim, [])

        self.rebalance_ratings()
        return True

    def export_csv(self, filename):
        fields = [
            "Name",
            "Appearance",
            "Personality",
            "Compatibility",
            "Overall",
            "ConfidenceOverall",
            "ConfidenceAppearance",
            "ConfidencePersonality",
            "ConfidenceCompatibility",
            "Tags",
            "Notes",
            "Photo",
        ]
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for name, data in self.sorted_nodes("Overall", reverse=True):
                details = self.details.get(name, self._new_details())
                writer.writerow(
                    {
                        "Name": name,
                        "Appearance": f"{data['Appearance']:.2f}",
                        "Personality": f"{data['Personality']:.2f}",
                        "Compatibility": f"{data['Compatibility']:.2f}",
                        "Overall": f"{data['Overall']:.2f}",
                        "ConfidenceOverall": self.get_confidence(name),
                        "ConfidenceAppearance": self.get_confidence(name, "Appearance"),
                        "ConfidencePersonality": self.get_confidence(name, "Personality"),
                        "ConfidenceCompatibility": self.get_confidence(name, "Compatibility"),
                        "Tags": details.get("tags", ""),
                        "Notes": details.get("notes", ""),
                        "Photo": details.get("photo", ""),
                    }
                )

    def import_csv(self, filename):
        if not os.path.exists(filename):
            return 0

        with open(filename, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        if not rows:
            return 0

        self.nodes = {}
        self.details = {}
        self.confidence = {}
        self.comparisons = set()

        for row in rows:
            name = (row.get("Name") or "").strip()
            if not name:
                continue
            self.nodes[name] = self._new_node()
            self.nodes[name]["Appearance"] = float(row.get("Appearance") or 5.0)
            self.nodes[name]["Personality"] = float(row.get("Personality") or 5.0)
            self.nodes[name]["Compatibility"] = float(row.get("Compatibility") or 5.0)
            self.confidence[name] = {
                "Appearance": int(float(row.get("ConfidenceAppearance") or 0)),
                "Personality": int(float(row.get("ConfidencePersonality") or 0)),
                "Compatibility": int(float(row.get("ConfidenceCompatibility") or 0)),
            }
            self.details[name] = {
                "tags": (row.get("Tags") or "").strip(),
                "notes": row.get("Notes") or "",
                "photo": (row.get("Photo") or "").strip(),
            }

        for dim in DIMS:
            ranked = sorted(self.nodes.keys(), key=lambda n: self.nodes[n][dim], reverse=True)
            groups = []
            last_score = None
            for name in ranked:
                score = self.nodes[name][dim]
                if last_score is None or abs(score - last_score) > 1e-9:
                    groups.append([name])
                    last_score = score
                else:
                    groups[-1].append(name)
            self.rankings[dim] = groups

        self.rebalance_ratings()
        return len(self.nodes)

    def export_state(self):
        return {
            "nodes": deepcopy(self.nodes),
            "details": deepcopy(self.details),
            "rankings": deepcopy(self.rankings),
            "confidence": deepcopy(self.confidence),
            "comparisons": deepcopy(self.comparisons),
            "weights": deepcopy(self.weights),
            "snapshots": deepcopy(self.snapshots),
        }

    def import_state(self, state):
        self.nodes = deepcopy(state["nodes"])
        self.details = deepcopy(state.get("details", {}))
        self.rankings = deepcopy(state["rankings"])
        self.confidence = deepcopy(state["confidence"])
        self.comparisons = deepcopy(state["comparisons"])
        self.weights = deepcopy(state.get("weights", DEFAULT_WEIGHTS.copy()))
        self.snapshots = deepcopy(state.get("snapshots", []))
        self.rebalance_ratings()


class PersonalRankingApp:
    def __init__(self, root):
        ctk.set_default_color_theme("blue")
        ctk.set_appearance_mode("system")

        self.root = root
        self.root.title("Personal Ranking System 2.0")

        self.palette = {
            "app_bg": ("#edf2f7", "#0b1220"),
            "panel": ("#ffffff", "#111827"),
            "panel_alt": ("#f8fafc", "#1f2937"),
            "text": ("#0f172a", "#e5e7eb"),
            "muted": ("#475569", "#9ca3af"),
            "accent": ("#2563eb", "#3b82f6"),
            "accent_soft": ("#dbeafe", "#1e3a8a"),
            "danger": ("#ef4444", "#ef4444"),
            "danger_hover": ("#dc2626", "#dc2626"),
            "status": ("#e2e8f0", "#111827"),
        }
        self.root.configure(fg_color=self.palette["app_bg"])

        self.sys = RankingSystem()
        self.current_file = None
        self.undo_stack = []
        self.redo_stack = []
        self.max_undo = 120

        self.config_path = os.path.expanduser("~/.personal_ranking_system_config.json")
        self.recovery_path = os.path.expanduser("~/Documents/personal_ranking_recovery.json")
        self.auto_save_enabled = True
        self.recent_files = []
        self.load_config()

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh())
        self.sort_var = tk.StringVar(value="Overall")
        self.min_conf_var = tk.IntVar(value=0)
        self.status_var = tk.StringVar(value="Ready")
        self.summary_var = tk.StringVar(value="No file loaded")

        self.main = ctk.CTkFrame(self.root, fg_color="transparent")
        self.main.pack(fill="both", expand=True, padx=16, pady=14)

        self.header = ctk.CTkFrame(self.main, fg_color=("#0f172a", "#020617"), corner_radius=14)
        self.header.pack(fill="x", pady=(0, 12))

        title_row = ctk.CTkFrame(self.header, fg_color="transparent")
        title_row.pack(fill="x", padx=16, pady=(14, 8))

        ctk.CTkLabel(
            title_row,
            text="Personal Ranking Dashboard",
            font=ctk.CTkFont(family="SF Pro Display", size=22, weight="bold"),
            text_color="#f8fafc",
        ).pack(side="left")

        self.appearance_var = tk.StringVar(value="System")
        appearance = ctk.CTkSegmentedButton(
            title_row,
            values=["Light", "Dark", "System"],
            variable=self.appearance_var,
            command=self.set_appearance,
            font=ctk.CTkFont(family="SF Pro Text", size=12, weight="bold"),
        )
        appearance.pack(side="right")
        ctk.CTkLabel(
            title_row,
            text="Payne Stroud",
            text_color="#cbd5e1",
            font=ctk.CTkFont(family="SF Pro Text", size=12, weight="bold"),
        ).pack(side="right", padx=(0, 12))

        ctk.CTkLabel(
            self.header,
            text="A modern workspace for ranking people across key dimensions with confidence.",
            text_color="#cbd5e1",
            font=ctk.CTkFont(family="SF Pro Text", size=13),
        ).pack(anchor="w", padx=16, pady=(0, 14))

        self.body = ctk.CTkFrame(self.main, fg_color="transparent")
        self.body.pack(fill="both", expand=True)
        self.body.grid_columnconfigure(0, weight=0)
        self.body.grid_columnconfigure(1, weight=1)
        self.body.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self.body, fg_color=self.palette["panel"], corner_radius=14, width=340)
        self.sidebar.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self.sidebar.grid_propagate(False)

        sections = ctk.CTkScrollableFrame(
            self.sidebar,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=self.palette["accent"],
            scrollbar_button_hover_color=("#1d4ed8", "#1d4ed8"),
        )
        sections.pack(fill="both", expand=True, padx=10, pady=10)

        self.make_toolbar_section(
            sections,
            "Data",
            [
                ("Open File", self.load),
                ("Open Recent", self.load_recent),
                ("Save", self.save_current),
                ("Save As", self.save_as),
                ("Import CSV", self.import_csv),
                ("Export CSV", self.export_csv),
            ],
        ).pack(fill="x", pady=(0, 8))

        self.make_toolbar_section(
            sections,
            "Manage",
            [
                ("Snapshots", self.show_snapshots),
            ],
        ).pack(fill="x", pady=(0, 8))

        self.make_toolbar_section(
            sections,
            "Tools",
            [
                ("Undo", self.undo),
                ("Redo", self.redo),
                ("Scoring Weights", self.open_settings),
            ],
        ).pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            sections,
            textvariable=self.summary_var,
            text_color=self.palette["muted"],
            font=ctk.CTkFont(family="SF Pro Text", size=12),
            justify="left",
            wraplength=280,
            anchor="w",
        ).pack(fill="x", padx=2, pady=(0, 10))

        self.right_pane = ctk.CTkFrame(self.body, fg_color="transparent")
        self.right_pane.grid(row=0, column=1, sticky="nsew")
        self.right_pane.grid_rowconfigure(2, weight=1)
        self.right_pane.grid_columnconfigure(0, weight=1)

        self.filter_card = ctk.CTkFrame(self.right_pane, fg_color=self.palette["panel"], corner_radius=12)
        self.filter_card.grid(row=0, column=0, sticky="ew")
        self.filter_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.filter_card, text="Search", text_color=self.palette["muted"], font=ctk.CTkFont(family="SF Pro Text", size=12, weight="bold")).grid(row=0, column=0, padx=(12, 6), pady=10, sticky="w")
        self.search_entry = ctk.CTkEntry(self.filter_card, textvariable=self.search_var, height=32, corner_radius=9, font=ctk.CTkFont(family="SF Pro Text", size=12), placeholder_text="Type a name...")
        self.search_entry.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="ew")

        ctk.CTkLabel(self.filter_card, text="Sort", text_color=self.palette["muted"], font=ctk.CTkFont(family="SF Pro Text", size=12, weight="bold")).grid(row=0, column=2, padx=(0, 6), pady=10)
        self.sort_menu = ctk.CTkOptionMenu(
            self.filter_card,
            variable=self.sort_var,
            values=["Overall", "Name", "Appearance", "Personality", "Compatibility", "Confidence"],
            command=lambda *_: self.refresh(),
            width=150,
            height=32,
            corner_radius=9,
            font=ctk.CTkFont(family="SF Pro Text", size=12),
            dropdown_font=ctk.CTkFont(family="SF Pro Text", size=12),
        )
        self.sort_menu.grid(row=0, column=3, padx=(0, 10), pady=10)

        ctk.CTkLabel(self.filter_card, text="Min Confidence", text_color=self.palette["muted"], font=ctk.CTkFont(family="SF Pro Text", size=12, weight="bold")).grid(row=0, column=4, padx=(0, 8), pady=10)
        self.conf_slider = ctk.CTkSlider(self.filter_card, from_=0, to=100, variable=self.min_conf_var, command=self.on_conf_change, width=160)
        self.conf_slider.grid(row=0, column=5, padx=(0, 6), pady=10)
        self.conf_label = ctk.CTkLabel(self.filter_card, text="0%", text_color=self.palette["muted"], width=42, font=ctk.CTkFont(family="SF Pro Text", size=12, weight="bold"))
        self.conf_label.grid(row=0, column=6, padx=(0, 12), pady=10)

        self.compare_bar = ctk.CTkFrame(self.right_pane, fg_color=self.palette["panel"], corner_radius=12)
        self.compare_bar.grid(row=1, column=0, sticky="ew", pady=(8, 8))
        ctk.CTkLabel(
            self.compare_bar,
            text="Compare Actions",
            text_color=self.palette["muted"],
            font=ctk.CTkFont(family="SF Pro Text", size=12, weight="bold"),
        ).pack(side="left", padx=(12, 10), pady=8)
        ctk.CTkButton(
            self.compare_bar,
            text="+ Add Person",
            command=self.add_node,
            height=32,
            corner_radius=10,
            width=132,
            fg_color=self.palette["accent"],
            hover_color=("#1d4ed8", "#1d4ed8"),
            text_color="#ffffff",
            font=ctk.CTkFont(family="SF Pro Text", size=12, weight="bold"),
        ).pack(side="left", padx=(0, 8), pady=8)
        ctk.CTkButton(self.compare_bar, text="Compare Manually", command=self.manual_compare, height=30, corner_radius=9, width=150).pack(side="left", padx=4, pady=8)
        ctk.CTkButton(self.compare_bar, text="Suggested Compare", command=self.suggest_compare, height=30, corner_radius=9, width=150).pack(side="left", padx=4, pady=8)
        ctk.CTkButton(self.compare_bar, text="Review Queue", command=self.show_needs_review, height=30, corner_radius=9, width=130).pack(side="left", padx=4, pady=8)

        self.content = ctk.CTkScrollableFrame(
            self.right_pane,
            fg_color=self.palette["panel_alt"],
            corner_radius=14,
            border_width=1,
            border_color=("#dbe3ed", "#2d3748"),
            label_text="Ranked List",
            label_font=ctk.CTkFont(family="SF Pro Text", size=13, weight="bold"),
            label_text_color=self.palette["muted"],
        )
        self.content.grid(row=2, column=0, sticky="nsew")
        self.setup_smooth_scrolling()

        self.status_bar = ctk.CTkFrame(self.right_pane, fg_color=self.palette["status"], corner_radius=10)
        self.status_bar.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ctk.CTkLabel(
            self.status_bar,
            textvariable=self.status_var,
            text_color=self.palette["text"],
            font=ctk.CTkFont(family="SF Pro Text", size=12),
            anchor="w",
        ).pack(fill="x", padx=12, pady=8)

        self.set_initial_window_geometry()
        self.root.after(40, self.ensure_window_visible)
        self.bind_shortcuts()
        self.try_recover_backup()
        self.refresh()

    def set_initial_window_geometry(self):
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(1380, max(1080, screen_w - 140))
        height = min(920, max(740, screen_h - 140))
        x = max(20, (screen_w - width) // 2)
        y = max(20, (screen_h - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(1020, 680)

    def ensure_window_visible(self):
        try:
            if self.root.state() == "iconic":
                self.root.state("normal")
        except tk.TclError:
            pass
        self.root.lift()
        self.root.focus_force()

    def set_appearance(self, mode):
        mapping = {"Light": "light", "Dark": "dark", "System": "system"}
        ctk.set_appearance_mode(mapping.get(mode, "system"))

    def bind_shortcuts(self):
        for seq in ["<Command-n>", "<Control-n>"]:
            self.root.bind(seq, lambda e: self.add_node())
        for seq in ["<Command-r>", "<Control-r>"]:
            self.root.bind(seq, lambda e: self.suggest_compare())
        for seq in ["<Command-s>", "<Control-s>"]:
            self.root.bind(seq, lambda e: self.save_current())
        for seq in ["<Command-S>", "<Control-S>"]:
            self.root.bind(seq, lambda e: self.save_as())
        for seq in ["<Command-o>", "<Control-o>"]:
            self.root.bind(seq, lambda e: self.load())
        for seq in ["<Command-z>", "<Control-z>"]:
            self.root.bind(seq, lambda e: self.undo())
        for seq in ["<Command-y>", "<Control-y>"]:
            self.root.bind(seq, lambda e: self.redo())
        for seq in ["<Command-f>", "<Control-f>"]:
            self.root.bind(seq, lambda e: self.focus_search())

    def focus_search(self):
        self.search_entry.focus_set()
        self.search_entry.select_range(0, tk.END)

    def make_toolbar_section(self, parent, title, actions):
        section = ctk.CTkFrame(parent, fg_color=self.palette["panel_alt"], corner_radius=12, border_width=1, border_color=("#cdd8e6", "#314155"))
        ctk.CTkLabel(
            section,
            text=title,
            text_color=self.palette["accent"],
            font=ctk.CTkFont(family="SF Pro Text", size=13, weight="bold"),
        ).pack(anchor="w", padx=12, pady=(10, 6))

        for label, action in actions:
            self.make_action_button(section, label, action).pack(fill="x", padx=10, pady=3)
        return section

    def make_action_button(self, parent, text, command):
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            height=32,
            corner_radius=10,
            fg_color=self.palette["accent_soft"],
            hover_color=("#bfdbfe", "#1d4ed8"),
            text_color=self.palette["accent"],
            font=ctk.CTkFont(family="SF Pro Text", size=12, weight="bold"),
            anchor="w",
        )

    def on_conf_change(self, value):
        self.conf_label.configure(text=f"{int(float(value))}%")
        self.refresh()

    def setup_smooth_scrolling(self):
        self._list_canvas = getattr(self.content, "_parent_canvas", None)
        if self._list_canvas is None:
            return
        self.root.bind_all("<MouseWheel>", self.on_list_mousewheel, add="+")
        self.root.bind_all("<Button-4>", self.on_list_mousewheel, add="+")
        self.root.bind_all("<Button-5>", self.on_list_mousewheel, add="+")

    def widget_in_list_area(self, widget):
        current = widget
        list_canvas = getattr(self, "_list_canvas", None)
        while current is not None:
            if current == self.content or current == list_canvas:
                return True
            current = getattr(current, "master", None)
        return False

    def on_list_mousewheel(self, event):
        if not self.widget_in_list_area(event.widget):
            return
        if not getattr(self, "_list_canvas", None):
            return

        if getattr(event, "num", None) == 4:
            self._list_canvas.yview_scroll(-2, "units")
            return
        if getattr(event, "num", None) == 5:
            self._list_canvas.yview_scroll(2, "units")
            return

        delta = getattr(event, "delta", 0)
        if delta == 0:
            return
        steps = int(-delta / 120)
        if steps == 0:
            steps = -1 if delta > 0 else 1
        self._list_canvas.yview_scroll(steps, "units")

    def gradient_color_readable(self, rating):
        rating = max(0.0, min(10.0, float(rating)))
        if rating <= 5:
            ratio = rating / 5.0
            r = 255
            g = int(130 + 125 * ratio)
            b = 0
        else:
            ratio = (rating - 5.0) / 5.0
            r = int(255 * (1 - ratio) * 0.7)
            g = int(255 * (1 - 0.2 * ratio))
            b = 0
        return f"#{r:02x}{g:02x}{b:02x}"

    def resolve_name(self, text):
        if not text:
            return None
        raw = text.strip()
        if raw in self.sys.nodes:
            return raw
        low = raw.lower()
        for name in self.sys.nodes:
            if name.lower() == low:
                return name
        return None

    def refresh(self):
        for w in self.content.winfo_children():
            w.destroy()

        search = self.search_var.get().strip().lower()
        min_conf = int(self.min_conf_var.get())

        rows = self.sys.sorted_nodes(self.sort_var.get(), reverse=True)
        if self.sort_var.get() == "Name":
            rows = self.sys.sorted_nodes("Name", reverse=False)

        shown = 0
        for name, data in rows:
            if search and search not in name.lower():
                continue

            conf_overall = self.sys.get_confidence(name)
            if conf_overall < min_conf:
                continue

            shown += 1

            card = ctk.CTkFrame(
                self.content,
                fg_color=self.palette["panel"],
                corner_radius=12,
                border_width=1,
                border_color=("#d7dee9", "#2d3748"),
            )
            card.pack(fill="x", padx=8, pady=4)
            card.grid_columnconfigure(1, weight=1)

            left = ctk.CTkFrame(card, fg_color="transparent")
            left.grid(row=0, column=0, padx=(10, 8), pady=8, sticky="nw")
            badge_color = self.gradient_color_readable(data["Overall"])
            ctk.CTkLabel(
                left,
                text=f"{data['Overall']:.1f}",
                width=48,
                height=48,
                corner_radius=24,
                fg_color=badge_color,
                text_color="#0b0f18",
                font=ctk.CTkFont(family="SF Pro Display", size=14, weight="bold"),
            ).pack()

            mid = ctk.CTkFrame(card, fg_color="transparent")
            mid.grid(row=0, column=1, sticky="nsew", padx=6, pady=7)

            head = ctk.CTkFrame(mid, fg_color="transparent")
            head.pack(fill="x")
            ctk.CTkLabel(
                head,
                text=name,
                text_color=self.palette["text"],
                font=ctk.CTkFont(family="SF Pro Display", size=15, weight="bold"),
                anchor="w",
            ).pack(side="left")

            ctk.CTkButton(
                head,
                text="Remove",
                command=lambda n=name: self.delete_node(n),
                width=88,
                height=27,
                corner_radius=8,
                fg_color=self.palette["danger"],
                hover_color=self.palette["danger_hover"],
                text_color="#ffffff",
                font=ctk.CTkFont(family="SF Pro Text", size=11, weight="bold"),
            ).pack(side="right")

            for dim in DIMS:
                row = ctk.CTkFrame(mid, fg_color="transparent")
                row.pack(fill="x", pady=(4, 0))

                ctk.CTkLabel(
                    row,
                    text=dim,
                    width=110,
                    anchor="w",
                    text_color=self.palette["text"],
                    font=ctk.CTkFont(family="SF Pro Text", size=11, weight="bold"),
                ).pack(side="left")

                bar = ctk.CTkProgressBar(
                    row,
                    height=9,
                    corner_radius=8,
                    fg_color=("#e5e7eb", "#263244"),
                    progress_color=self.gradient_color_readable(data[dim]),
                )
                bar.pack(side="left", fill="x", expand=True, padx=(0, 12))
                bar.set(max(0.0, min(1.0, data[dim] / 10.0)))

                conf_dim = self.sys.get_confidence(name, dim)
                ctk.CTkLabel(
                    row,
                    text=f"{data[dim]:.1f} ({conf_dim}%)",
                    width=100,
                    anchor="e",
                    text_color=self.palette["muted"],
                    font=ctk.CTkFont(family="SF Pro Text", size=11),
                ).pack(side="right")

            ctk.CTkLabel(
                mid,
                text=f"Overall confidence: {conf_overall}%",
                text_color=self.palette["muted"],
                font=ctk.CTkFont(family="SF Pro Text", size=11),
                anchor="w",
            ).pack(fill="x", pady=(6, 0))

        current = self.current_file if self.current_file else "Unsaved session"
        self.summary_var.set(current)
        self.status_var.set(f"Showing {shown} node(s)  |  Auto-save: {'On' if self.auto_save_enabled else 'Off'}")

    def center_popup(self, dlg):
        dlg.update_idletasks()
        w, h = dlg.winfo_width(), dlg.winfo_height()
        ws, hs = self.root.winfo_width(), self.root.winfo_height()
        x = self.root.winfo_x() + (ws // 2) - (w // 2)
        y = self.root.winfo_y() + (hs // 2) - (h // 2)
        dlg.geometry(f"+{x}+{y}")

    def ask_three_option(self, question):
        dlg = ctk.CTkToplevel(self.root)
        dlg.title("Comparison")
        dlg.transient(self.root)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text=question, justify="left", font=ctk.CTkFont(family="SF Pro Text", size=14, weight="bold"), wraplength=540).pack(padx=18, pady=(16, 12))
        result = {"choice": None}

        buttons = ctk.CTkFrame(dlg, fg_color="transparent")
        buttons.pack(padx=12, pady=(0, 14), fill="x")

        def choose(opt):
            result["choice"] = opt
            dlg.destroy()

        ctk.CTkButton(buttons, text="Yes", command=lambda: choose("yes"), height=34, corner_radius=10).pack(side="left", padx=5, expand=True, fill="x")
        ctk.CTkButton(buttons, text="No", command=lambda: choose("no"), height=34, corner_radius=10).pack(side="left", padx=5, expand=True, fill="x")
        ctk.CTkButton(buttons, text="Equal / Don't know", command=lambda: choose("equal"), height=34, corner_radius=10).pack(side="left", padx=5, expand=True, fill="x")

        self.center_popup(dlg)
        self.root.wait_window(dlg)
        return result["choice"]

    def ask_pair_choice(self, a, b, prompt):
        dlg = ctk.CTkToplevel(self.root)
        dlg.title("Suggested Comparison")
        dlg.transient(self.root)
        dlg.grab_set()
        result = {"choice": None}

        ctk.CTkLabel(dlg, text=prompt, font=ctk.CTkFont(family="SF Pro Display", size=16, weight="bold")).pack(padx=18, pady=(14, 6))
        ctk.CTkLabel(dlg, text=f"{a}  vs  {b}", text_color=self.palette["muted"], font=ctk.CTkFont(family="SF Pro Text", size=13)).pack(padx=18, pady=(0, 10))

        box = ctk.CTkFrame(dlg, fg_color="transparent")
        box.pack(fill="x", padx=14, pady=(0, 12))

        def choose(opt):
            result["choice"] = opt
            dlg.destroy()

        ctk.CTkButton(box, text=a, command=lambda: choose("a"), height=36, corner_radius=10).pack(fill="x", pady=3)
        ctk.CTkButton(box, text=b, command=lambda: choose("b"), height=36, corner_radius=10).pack(fill="x", pady=3)
        ctk.CTkButton(box, text="Equal / Skip", command=lambda: choose("equal"), height=34, corner_radius=10, fg_color=("#64748b", "#334155"), hover_color=("#475569", "#475569")).pack(fill="x", pady=3)

        self.center_popup(dlg)
        self.root.wait_window(dlg)
        return result["choice"]

    def prompt_manual_compare(self):
        dlg = ctk.CTkToplevel(self.root)
        dlg.title("Manual Compare")
        dlg.transient(self.root)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="Manual Comparison", font=ctk.CTkFont(family="SF Pro Display", size=16, weight="bold")).grid(row=0, column=0, columnspan=2, padx=16, pady=(14, 8), sticky="w")

        better_var = tk.StringVar()
        worse_var = tk.StringVar()
        dim_var = tk.StringVar(value="All")

        ctk.CTkLabel(dlg, text="Better").grid(row=1, column=0, padx=(16, 8), pady=6, sticky="e")
        ctk.CTkEntry(dlg, textvariable=better_var, width=280, height=34, corner_radius=8).grid(row=1, column=1, padx=(0, 16), pady=6, sticky="ew")

        ctk.CTkLabel(dlg, text="Worse").grid(row=2, column=0, padx=(16, 8), pady=6, sticky="e")
        ctk.CTkEntry(dlg, textvariable=worse_var, width=280, height=34, corner_radius=8).grid(row=2, column=1, padx=(0, 16), pady=6, sticky="ew")

        ctk.CTkLabel(dlg, text="Dimension").grid(row=3, column=0, padx=(16, 8), pady=6, sticky="e")
        ctk.CTkOptionMenu(dlg, variable=dim_var, values=["All", *DIMS], width=220, height=34, corner_radius=8).grid(row=3, column=1, padx=(0, 16), pady=6, sticky="w")

        result = {"ok": False}

        def submit():
            result["ok"] = True
            dlg.destroy()

        btns = ctk.CTkFrame(dlg, fg_color="transparent")
        btns.grid(row=4, column=0, columnspan=2, padx=16, pady=12, sticky="e")
        ctk.CTkButton(btns, text="Cancel", command=dlg.destroy, width=110, fg_color=("#64748b", "#334155"), hover_color=("#475569", "#475569")).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btns, text="Apply", command=submit, width=110).pack(side="right")

        self.center_popup(dlg)
        self.root.wait_window(dlg)

        if not result["ok"]:
            return None
        return better_var.get().strip(), worse_var.get().strip(), dim_var.get().strip()

    def push_undo(self, reason):
        self.undo_stack.append({"reason": reason, "state": self.sys.export_state()})
        self.undo_stack = self.undo_stack[-self.max_undo :]
        self.redo_stack.clear()

    def commit_change(self, reason, save=True):
        self.sys.add_snapshot(reason)
        self.write_recovery_backup()
        if save:
            self.auto_save_current()
        self.refresh()

    def undo(self):
        if not self.undo_stack:
            self.status_var.set("Nothing to undo.")
            return
        self.redo_stack.append({"state": self.sys.export_state()})
        item = self.undo_stack.pop()
        self.sys.import_state(item["state"])
        self.auto_save_current()
        self.refresh()
        self.status_var.set(f"Undid: {item['reason']}")

    def redo(self):
        if not self.redo_stack:
            self.status_var.set("Nothing to redo.")
            return
        self.undo_stack.append({"reason": "redo", "state": self.sys.export_state()})
        item = self.redo_stack.pop()
        self.sys.import_state(item["state"])
        self.auto_save_current()
        self.refresh()
        self.status_var.set("Redid action.")

    def add_node(self):
        name = simpledialog.askstring("Add Node", "Enter new node name:")
        if not name:
            return
        clean = name.strip()
        if clean in self.sys.nodes:
            messagebox.showerror("Error", "Node already exists.")
            return
        self.push_undo("add node")
        created = self.sys.add_node(clean, self.ask_three_option)
        if created:
            self.commit_change(f"Add {clean}")

    def delete_node(self, name):
        if not messagebox.askyesno("Delete Node", f"Delete '{name}'?"):
            return
        self.push_undo("delete node")
        self.sys.delete_node(name)
        self.commit_change(f"Delete {name}")

    def manual_compare(self):
        payload = self.prompt_manual_compare()
        if not payload:
            return

        better_raw, worse_raw, dim_choice = payload
        better = self.resolve_name(better_raw)
        worse = self.resolve_name(worse_raw)
        if better is None or worse is None:
            messagebox.showerror("Error", "Both names must exist.")
            return
        if better == worse:
            messagebox.showerror("Error", "Names must be different.")
            return

        dims = DIMS if dim_choice == "All" else [dim_choice]
        mark_pair = dim_choice == "All"

        self.push_undo("manual compare")
        self.sys.move_winner_above_loser(better, worse, dims=dims, mark_pair=mark_pair)
        self.commit_change(f"Manual compare {better}>{worse} ({dim_choice})")

    def compare_pair_by_dimension(self, a, b, title_prefix):
        decisions = {}
        for dim in DIMS:
            choice = self.ask_pair_choice(a, b, f"{title_prefix}: {dim}")
            if not choice:
                return None
            decisions[dim] = choice
        return decisions

    def apply_dimension_decisions(self, a, b, decisions):
        for dim, result in decisions.items():
            if result == "a":
                self.sys.move_winner_above_loser(a, b, dims=[dim], mark_pair=False)
            elif result == "b":
                self.sys.move_winner_above_loser(b, a, dims=[dim], mark_pair=False)
            else:
                self.sys.record_comparison(a, b, dims=[dim], mark_pair=False)
        self.sys.comparisons.add(tuple(sorted([a, b])))

    def suggest_compare(self):
        pair = self.sys.suggest_comparison()
        if not pair:
            messagebox.showinfo("Done", "No useful un-compared pairs left.")
            return

        a, b = pair
        decisions = self.compare_pair_by_dimension(a, b, "Who is better")
        if not decisions:
            return

        self.push_undo("suggest compare")
        self.apply_dimension_decisions(a, b, decisions)
        self.commit_change(f"Suggest compare by dimension: {a} vs {b}")

    def show_needs_review(self):
        pairs = self.sys.needs_review_pairs(limit=20)
        if not pairs:
            messagebox.showinfo("Needs Review", "Not enough nodes to build a review queue.")
            return

        dlg = ctk.CTkToplevel(self.root)
        dlg.title("Needs Review Queue")
        dlg.transient(self.root)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="Top pairs to review", font=ctk.CTkFont(family="SF Pro Display", size=16, weight="bold")).pack(anchor="w", padx=14, pady=(12, 8))

        txt = ctk.CTkTextbox(dlg, width=780, height=360, corner_radius=10)
        txt.pack(padx=14, pady=(0, 10), fill="both", expand=True)
        txt.insert("end", "Top pairs to review (low confidence or close overall scores):\n\n")
        for idx, (score, a, b, diff, conf_a, conf_b) in enumerate(pairs, start=1):
            txt.insert(
                "end",
                f"{idx:02d}. {a} vs {b} | diff={diff:.2f} | conf={conf_a}%/{conf_b}% | priority={score:.1f}\n",
            )
        txt.configure(state="disabled")

        def compare_top():
            dlg.destroy()
            first = pairs[0]
            a, b = first[1], first[2]
            decisions = self.compare_pair_by_dimension(a, b, "Review pair")
            if not decisions:
                return
            self.push_undo("review compare")
            self.apply_dimension_decisions(a, b, decisions)
            self.commit_change("Needs review compare")

        btns = ctk.CTkFrame(dlg, fg_color="transparent")
        btns.pack(fill="x", padx=14, pady=(0, 12))
        ctk.CTkButton(btns, text="Close", width=120, command=dlg.destroy, fg_color=("#64748b", "#334155"), hover_color=("#475569", "#475569")).pack(side="right")
        ctk.CTkButton(btns, text="Compare Top Pair", width=160, command=compare_top).pack(side="right", padx=(0, 8))

        self.center_popup(dlg)

    def open_settings(self):
        dlg = ctk.CTkToplevel(self.root)
        dlg.title("Settings")
        dlg.transient(self.root)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="Scoring Weights", font=ctk.CTkFont(family="SF Pro Display", size=16, weight="bold")).grid(row=0, column=0, columnspan=2, padx=16, pady=(14, 10), sticky="w")

        app_var = tk.StringVar(value=str(round(self.sys.weights["Appearance"], 4)))
        per_var = tk.StringVar(value=str(round(self.sys.weights["Personality"], 4)))
        com_var = tk.StringVar(value=str(round(self.sys.weights["Compatibility"], 4)))

        ctk.CTkLabel(dlg, text="Appearance").grid(row=1, column=0, sticky="e", padx=(16, 8), pady=5)
        ctk.CTkEntry(dlg, textvariable=app_var, width=150).grid(row=1, column=1, sticky="w", padx=(0, 16), pady=5)
        ctk.CTkLabel(dlg, text="Personality").grid(row=2, column=0, sticky="e", padx=(16, 8), pady=5)
        ctk.CTkEntry(dlg, textvariable=per_var, width=150).grid(row=2, column=1, sticky="w", padx=(0, 16), pady=5)
        ctk.CTkLabel(dlg, text="Compatibility").grid(row=3, column=0, sticky="e", padx=(16, 8), pady=5)
        ctk.CTkEntry(dlg, textvariable=com_var, width=150).grid(row=3, column=1, sticky="w", padx=(0, 16), pady=5)

        autosave_var = tk.BooleanVar(value=self.auto_save_enabled)
        ctk.CTkCheckBox(dlg, text="Enable auto-save to current file", variable=autosave_var).grid(row=4, column=0, columnspan=2, padx=16, pady=(10, 6), sticky="w")

        def apply_settings():
            try:
                self.push_undo("change weights")
                self.sys.set_weights(float(app_var.get()), float(per_var.get()), float(com_var.get()))
                self.auto_save_enabled = bool(autosave_var.get())
                self.save_config()
                self.commit_change("Update settings")
                dlg.destroy()
            except Exception as exc:
                messagebox.showerror("Settings Error", str(exc))

        btns = ctk.CTkFrame(dlg, fg_color="transparent")
        btns.grid(row=5, column=0, columnspan=2, sticky="e", padx=16, pady=12)
        ctk.CTkButton(btns, text="Cancel", command=dlg.destroy, width=110, fg_color=("#64748b", "#334155"), hover_color=("#475569", "#475569")).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btns, text="Save", command=apply_settings, width=110).pack(side="right")

        self.center_popup(dlg)

    def show_snapshots(self):
        if not self.sys.snapshots:
            messagebox.showinfo("Snapshots", "No snapshots yet.")
            return

        dlg = ctk.CTkToplevel(self.root)
        dlg.title("Ranking Snapshots")
        dlg.transient(self.root)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="Snapshots", font=ctk.CTkFont(family="SF Pro Display", size=16, weight="bold")).pack(anchor="w", padx=14, pady=(12, 8))

        txt = ctk.CTkTextbox(dlg, width=780, height=400, corner_radius=10)
        txt.pack(padx=14, pady=(0, 10), fill="both", expand=True)

        for snap in reversed(self.sys.snapshots[-80:]):
            txt.insert("end", f"[{snap['timestamp']}] {snap['reason']}\n")
            top = ", ".join([f"{row['name']} ({row['overall']:.2f})" for row in snap.get("top", [])[:5]])
            txt.insert("end", f"Top: {top}\n\n")

        txt.configure(state="disabled")
        ctk.CTkButton(dlg, text="Close", command=dlg.destroy, width=120).pack(pady=(0, 12))
        self.center_popup(dlg)

    def save_current(self):
        if self.current_file:
            self.sys.save_to_file(self.current_file)
            self.update_recent_files(self.current_file)
            self.status_var.set(f"Saved: {self.current_file}")
            return
        self.save_as()

    def save_as(self):
        filename = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if not filename:
            return
        self.current_file = filename
        self.sys.save_to_file(filename)
        self.update_recent_files(filename)
        self.status_var.set(f"Saved: {filename}")

    def load(self):
        filename = filedialog.askopenfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if not filename:
            return
        ok = self.sys.load_from_file(filename)
        if ok:
            self.current_file = filename
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.update_recent_files(filename)
            self.refresh()
            self.status_var.set(f"Loaded: {filename}")
            messagebox.showinfo("Loaded", f"Loaded rankings from {filename}")

    def load_recent(self):
        if not self.recent_files:
            messagebox.showinfo("Recent Files", "No recent files saved yet.")
            return

        for path in self.recent_files:
            if os.path.exists(path):
                ok = self.sys.load_from_file(path)
                if ok:
                    self.current_file = path
                    self.refresh()
                    self.status_var.set(f"Loaded recent: {path}")
                    return

        messagebox.showerror("Recent Files", "No recent file path is currently valid.")

    def import_csv(self):
        filename = filedialog.askopenfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not filename:
            return
        self.push_undo("import csv")
        count = self.sys.import_csv(filename)
        self.commit_change(f"Import CSV ({count} nodes)", save=False)
        messagebox.showinfo("Import CSV", f"Imported {count} node(s) from {filename}")

    def export_csv(self):
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not filename:
            return
        self.sys.export_csv(filename)
        self.status_var.set(f"CSV exported: {filename}")

    def auto_save_current(self):
        if self.auto_save_enabled and self.current_file:
            try:
                self.sys.save_to_file(self.current_file)
                self.update_recent_files(self.current_file)
            except Exception:
                pass

    def write_recovery_backup(self):
        try:
            target = self.recovery_path
            if self.current_file:
                base, _ = os.path.splitext(self.current_file)
                target = f"{base}.recovery.json"
            self.sys.save_to_file(target)
        except Exception:
            pass

    def try_recover_backup(self):
        if os.path.exists(self.recovery_path) and not self.sys.nodes:
            if messagebox.askyesno("Recovery", f"Recovery file found. Load it now?\n\n{self.recovery_path}"):
                ok = self.sys.load_from_file(self.recovery_path)
                if ok:
                    self.status_var.set(f"Recovered from {self.recovery_path}")

    def load_config(self):
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self.auto_save_enabled = bool(cfg.get("auto_save_enabled", True))
            self.recent_files = [p for p in cfg.get("recent_files", []) if isinstance(p, str)]
        except Exception:
            self.auto_save_enabled = True
            self.recent_files = []

    def save_config(self):
        payload = {
            "auto_save_enabled": self.auto_save_enabled,
            "recent_files": self.recent_files[:10],
        }
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception:
            pass

    def update_recent_files(self, filename):
        if not filename:
            return
        self.recent_files = [p for p in self.recent_files if p != filename]
        self.recent_files.insert(0, filename)
        self.recent_files = self.recent_files[:10]
        self.save_config()


root = ctk.CTk()
app = PersonalRankingApp(root)
root.mainloop()
