import customtkinter as ctk
import sqlite3
import json
import pandas as pd
from datetime import datetime
from tkinter import messagebox, filedialog
import os
import time
import threading
import logging
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# ====================== Logging & Config ======================
logging.basicConfig(
    filename='data/taskflow.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

try:
    with open('config.json', 'r') as f:
        CONFIG = json.load(f)
except FileNotFoundError:
    CONFIG = {
        "app_name": "TaskFlow",
        "database_path": "data/tasks.db",
        "default_work_time": 25,
        "colors": {
            "accent": "#6366F1",
            "success": "#22C55E",
            "danger": "#EF4444",
            "warning": "#F59E0B",
            "text": "#E2E8F0",
            "subtle": "#94A3B8"
        }
    }
    os.makedirs("data", exist_ok=True)
    with open('config.json', 'w') as f:
        json.dump(CONFIG, f, indent=4)

ACCENT_COLOR = CONFIG["colors"]["accent"]
SUCCESS_COLOR = CONFIG["colors"]["success"]
DANGER_COLOR = CONFIG["colors"]["danger"]
WARNING_COLOR = CONFIG["colors"]["warning"]

# ====================== Theme Setup ======================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class Task:
    def __init__(self, task_id=None, title="", description="", status="To Do",
                 priority="Medium", due_date=None, labels=None, time_spent=0, subtasks=None):
        self.id = task_id
        self.title = title
        self.description = description
        self.status = status
        self.priority = priority
        self.due_date = due_date
        self.labels = labels or []
        self.time_spent = time_spent
        self.subtasks = subtasks or []
        self.created_at = datetime.now().isoformat()

    def get_priority_color(self):
        return {"High": DANGER_COLOR, "Medium": WARNING_COLOR, "Low": SUCCESS_COLOR}.get(self.priority, "#64748B")

    def to_dict(self):
        return vars(self)


class TaskFlow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{CONFIG['app_name']} • Professional Team Workspace")
        self.geometry("1520x940")
        self.attributes("-fullscreen", True)  # Make fullscreen
        self.bind("<Escape>", lambda e: self.attributes("-fullscreen", False))  # Exit fullscreen with Escape
        self.minsize(1350, 800)
        self.configure(fg_color="#0A0F1C")

        self.tasks = []
        self.current_page = None
        self.running_timers = {}  # task_id: thread

        self.init_database()
        self.load_tasks()

        self.create_sidebar()
        self.create_main_area()
        self.switch_page("Dashboard")

    def init_database(self):
        try:
            os.makedirs("data", exist_ok=True)
            conn = sqlite3.connect(CONFIG["database_path"])
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT,
                    priority TEXT,
                    due_date TEXT,
                    labels TEXT,
                    time_spent INTEGER DEFAULT 0,
                    subtasks TEXT,
                    created_at TEXT
                )
            ''')
            conn.commit()
            conn.close()
            logging.info("Database initialized successfully")
        except Exception as e:
            logging.error(f"Database init failed: {e}")
            messagebox.showerror("Error", f"Database error: {e}")

    def load_tasks(self):
        try:
            self.tasks.clear()
            conn = sqlite3.connect(CONFIG["database_path"])
            for row in conn.execute("SELECT * FROM tasks ORDER BY created_at DESC"):
                task = Task(
                    task_id=row[0], title=row[1], description=row[2] or "",
                    status=row[3], priority=row[4], due_date=row[5],
                    labels=json.loads(row[6]) if row[6] else [],
                    time_spent=row[7],
                    subtasks=json.loads(row[8]) if row[8] else []
                )
                self.tasks.append(task)
            conn.close()
        except Exception as e:
            logging.error(f"Failed to load tasks: {e}")

    def save_task(self, task: Task):
        try:
            conn = sqlite3.connect(CONFIG["database_path"])
            cursor = conn.cursor()
            subtasks_json = json.dumps(task.subtasks)
            labels_json = json.dumps(task.labels)

            if task.id is None:
                cursor.execute('''INSERT INTO tasks 
                    (title, description, status, priority, due_date, labels, time_spent, subtasks, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (task.title, task.description, task.status, task.priority,
                     task.due_date, labels_json, task.time_spent, subtasks_json, task.created_at))
            else:
                cursor.execute('''UPDATE tasks SET title=?, description=?, status=?, priority=?, 
                    due_date=?, labels=?, time_spent=?, subtasks=? WHERE id=?''',
                    (task.title, task.description, task.status, task.priority,
                     task.due_date, labels_json, task.time_spent, subtasks_json, task.id))

            conn.commit()
            conn.close()
            self.load_tasks()
            self.refresh_current_page()
        except Exception as e:
            logging.error(f"Save failed: {e}")
            messagebox.showerror("Error", "Failed to save task.")

    def delete_task(self, task_id):
        if messagebox.askyesno("Confirm", "Delete this task permanently?", icon="warning"):
            try:
                # Stop timer if running
                if task_id in self.running_timers:
                    del self.running_timers[task_id]
                conn = sqlite3.connect(CONFIG["database_path"])
                conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
                conn.commit()
                conn.close()
                self.load_tasks()
                self.refresh_current_page()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # ====================== Sidebar ======================
    def create_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color="#111827")
        sidebar.pack(side="left", fill="y")

        # Header
        header = ctk.CTkFrame(sidebar, fg_color="transparent")
        header.pack(pady=32, padx=28, fill="x")
        ctk.CTkLabel(header, text=CONFIG["app_name"], font=ctk.CTkFont(size=34, weight="bold"),
                     text_color=ACCENT_COLOR).pack(anchor="w")
        ctk.CTkLabel(header, text="Team Workspace", font=ctk.CTkFont(size=13),
                     text_color="#94A3B8").pack(anchor="w", pady=(2,0))

        ctk.CTkFrame(sidebar, height=1, fg_color="#374151").pack(fill="x", padx=28, pady=24)

        # Navigation
        nav = [
            ("🏠  Dashboard", "Dashboard"),
            ("📋  Kanban Board", "Kanban"),
            ("➕  New Task", None),
            ("📊  Analytics", "Analytics"),
            ("⚙️  Settings", "Settings"),
        ]

        for text, page in nav:
            if page:
                btn = ctk.CTkButton(sidebar, text=text, height=52, anchor="w", corner_radius=12,
                                    fg_color="transparent", hover_color="#1F2937",
                                    text_color="#E2E8F0", font=ctk.CTkFont(size=16),
                                    command=lambda p=page: self.switch_page(p))
            else:
                btn = ctk.CTkButton(sidebar, text=text, height=52, anchor="w", corner_radius=12,
                                    fg_color=ACCENT_COLOR, hover_color="#4F46E5",
                                    text_color="white", font=ctk.CTkFont(size=16, weight="bold"),
                                    command=self.open_new_task_form)
            btn.pack(pady=6, padx=24, fill="x")

        # Focus Timer Button
        ctk.CTkButton(sidebar, text="🍅  Start Focus Session", height=58, corner_radius=14,
                      fg_color="#E11D48", hover_color="#BE123C", font=ctk.CTkFont(size=17, weight="bold"),
                      command=self.open_pomodoro).pack(pady=50, padx=24, fill="x")

    def create_main_area(self):
        self.main_area = ctk.CTkFrame(self, fg_color="#0A0F1C")
        self.main_area.pack(side="right", fill="both", expand=True)

    def switch_page(self, page_name):
        if self.current_page:
            self.current_page.destroy()

        pages = {
            "Dashboard": DashboardPage,
            "Kanban": KanbanPage,
            "Analytics": AnalyticsPage,
            "Settings": SettingsPage
        }
        self.current_page = pages[page_name](self.main_area, self)
        self.current_page.pack(fill="both", expand=True, padx=40, pady=40)

    def refresh_current_page(self):
        if self.current_page:
            name = type(self.current_page).__name__.replace("Page", "")
            self.switch_page(name if name != "Kanban" else "Kanban")

    def open_new_task_form(self):
        TaskForm(self, self.save_task)

    def open_task_form(self, task):
        TaskForm(self, self.save_task, task)

    def open_pomodoro(self):
        PomodoroTimer(self, None, self.update_task_time_spent)

    def update_task_time_spent(self, task_id, minutes):
        for task in self.tasks:
            if task.id == task_id:
                task.time_spent += minutes
                self.save_task(task)
                break

    def show_notification(self, title: str, message: str, color=ACCENT_COLOR):
        notif = ctk.CTkToplevel(self)
        notif.title(title)
        notif.geometry("440x190")
        notif.attributes("-topmost", True)
        notif.configure(fg_color="#1F2937")

        ctk.CTkLabel(notif, text=title, font=ctk.CTkFont(size=20, weight="bold"), text_color=color).pack(pady=(25,8))
        ctk.CTkLabel(notif, text=message, font=ctk.CTkFont(size=15), wraplength=400).pack(pady=10, padx=30)
        ctk.CTkButton(notif, text="Close", width=160, command=notif.destroy).pack(pady=15)


# ====================== Pages ======================

class DashboardPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app

        ctk.CTkLabel(self, text="Welcome back, Team", font=ctk.CTkFont(size=36, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(self, text="Stay productive today", font=ctk.CTkFont(size=18), text_color="#94A3B8").pack(anchor="w", pady=(4,30))

        # Stats
        frame = ctk.CTkFrame(self, fg_color="#1F2937", corner_radius=20)
        frame.pack(fill="x", pady=20)

        total = len(app.tasks)
        completed = sum(1 for t in app.tasks if t.status == "Done")
        overdue = sum(1 for t in app.tasks if t.due_date and t.due_date < datetime.now().isoformat() and t.status != "Done")

        for i, (label, value, color) in enumerate([
            ("Total Tasks", total, "#CBD5E1"),
            ("Completed", completed, SUCCESS_COLOR),
            ("Overdue", overdue, DANGER_COLOR)
        ]):
            col = ctk.CTkFrame(frame, fg_color="transparent")
            col.pack(side="left", fill="x", expand=True, padx=40, pady=30)
            ctk.CTkLabel(col, text=str(value), font=ctk.CTkFont(size=48, weight="bold"), text_color=color).pack()
            ctk.CTkLabel(col, text=label, font=ctk.CTkFont(size=15), text_color="#94A3B8").pack()


class KanbanPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app

        ctk.CTkLabel(self, text="Project Board", font=ctk.CTkFont(size=30, weight="bold")).pack(anchor="w", pady=(0,24))

        columns_frame = ctk.CTkFrame(self, fg_color="transparent")
        columns_frame.pack(fill="both", expand=True)

        for status in ["To Do", "In Progress", "Done"]:
            col = ctk.CTkFrame(columns_frame, fg_color="#1F2937", corner_radius=20)
            col.pack(side="left", fill="both", expand=True, padx=14)

            ctk.CTkLabel(col, text=status, font=ctk.CTkFont(size=19, weight="bold")).pack(pady=20)

            scroll = ctk.CTkScrollableFrame(col, fg_color="transparent")
            scroll.pack(fill="both", expand=True, padx=16, pady=(0,16))
            setattr(self, f"col_{status.lower().replace(' ', '_')}", scroll)

        self.refresh_kanban()

    def refresh_kanban(self):
        for status in ["To Do", "In Progress", "Done"]:
            scroll = getattr(self, f"col_{status.lower().replace(' ', '_')}")
            for widget in scroll.winfo_children():
                widget.destroy()

        for task in self.app.tasks:
            card = ctk.CTkFrame(getattr(self, f"col_{task.status.lower().replace(' ', '_')}"),
                                fg_color="#334155", corner_radius=16, border_width=1, border_color="#475569")
            card.pack(fill="x", pady=10, padx=8)

            # Priority bar
            ctk.CTkFrame(card, width=6, fg_color=task.get_priority_color()).pack(side="left", fill="y")

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=18, pady=16)

            ctk.CTkLabel(inner, text=task.title, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w")
            if task.due_date:
                ctk.CTkLabel(inner, text=f"Due: {task.due_date[:10]}", font=ctk.CTkFont(size=13),
                             text_color="#94A3B8").pack(anchor="w", pady=4)
            if task.time_spent > 0:
                hours = task.time_spent // 60
                mins = task.time_spent % 60
                time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
                ctk.CTkLabel(inner, text=f"Time: {time_str}", font=ctk.CTkFont(size=13),
                             text_color="#F59E0B").pack(anchor="w", pady=2)

            btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
            btn_frame.pack(fill="x", pady=(12,0))
            ctk.CTkButton(btn_frame, text="Edit", width=80, height=34, corner_radius=8,
                          command=lambda t=task: self.app.open_task_form(t)).pack(side="left")
            if task.status != "Done":
                ctk.CTkButton(btn_frame, text="Mark Done", width=100, height=34, corner_radius=8, fg_color=SUCCESS_COLOR,
                              command=lambda t=task: self.mark_done(t)).pack(side="left", padx=12)
            ctk.CTkButton(btn_frame, text="Delete", width=80, height=34, corner_radius=8, fg_color=DANGER_COLOR,
                          command=lambda tid=task.id: self.app.delete_task(tid)).pack(side="left", padx=12)

            # Timer button
            timer_text = "Stop Timer" if task.id in self.app.running_timers else "Start Timer"
            ctk.CTkButton(btn_frame, text=timer_text, width=100, height=34, corner_radius=8, fg_color=WARNING_COLOR,
                          command=lambda t=task: self.toggle_timer(t)).pack(side="right")

    def mark_done(self, task):
        task.status = "Done"
        self.app.save_task(task)
        self.refresh_kanban()

    def toggle_timer(self, task):
        if task.id in self.app.running_timers:
            self.stop_timer(task.id)
        else:
            self.start_timer(task)
        self.refresh_kanban()

    def start_timer(self, task):
        def timer_thread():
            while task.id in self.app.running_timers:
                time.sleep(60)  # Update every minute
                task.time_spent += 1
                self.app.save_task(task)  # Save periodically

        thread = threading.Thread(target=timer_thread, daemon=True)
        self.app.running_timers[task.id] = thread
        thread.start()

    def stop_timer(self, task_id):
        if task_id in self.app.running_timers:
            del self.app.running_timers[task_id]


class AnalyticsPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app

        ctk.CTkLabel(self, text="Reports & Insights", font=ctk.CTkFont(size=30, weight="bold")).pack(anchor="w", pady=(0,40))

        frame = ctk.CTkFrame(self, fg_color="#1F2937", corner_radius=20)
        frame.pack(pady=20)

        ctk.CTkButton(frame, text="Export as CSV", height=60, width=280, corner_radius=12,
                      font=ctk.CTkFont(size=16), command=self.export_csv).pack(pady=30, padx=40)
        ctk.CTkButton(frame, text="Export Professional PDF", height=60, width=280, corner_radius=12,
                      fg_color=ACCENT_COLOR, font=ctk.CTkFont(size=16), command=self.export_pdf).pack(pady=10, padx=40)

    def get_df(self):
        return pd.DataFrame([t.to_dict() for t in self.app.tasks]) if self.app.tasks else pd.DataFrame()

    def export_csv(self):
        df = self.get_df()
        if df.empty:
            messagebox.showinfo("Info", "No data to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv")
        if path:
            df.to_csv(path, index=False)
            self.app.show_notification("Success", "CSV exported successfully", SUCCESS_COLOR)

    def export_pdf(self):
        df = self.get_df()
        if df.empty:
            messagebox.showinfo("Info", "No data to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".pdf")
        if path:
            try:
                export_weekly_report(df, path)
                self.app.show_notification("Success", "PDF report generated", SUCCESS_COLOR)
            except Exception as e:
                messagebox.showerror("Error", str(e))


def export_weekly_report(tasks_df, filename):
    doc = SimpleDocTemplate(filename, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [Paragraph("TaskFlow • Weekly Report", styles['Title']),
                Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y')}", styles['Normal']),
                Spacer(1, 30)]

    total = len(tasks_df)
    completed = len(tasks_df[tasks_df['status'] == 'Done']) if not tasks_df.empty else 0

    data = [["Metric", "Value"], ["Total Tasks", total], ["Completed", completed],
            ["Completion Rate", f"{(completed/total*100):.1f}%" if total > 0 else "0%"]]

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    elements.append(table)
    doc.build(elements)


class SettingsPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app

        ctk.CTkLabel(self, text="Settings", font=ctk.CTkFont(size=30, weight="bold")).pack(anchor="w", pady=(0,30))

        ctk.CTkLabel(self, text="Appearance Mode", font=ctk.CTkFont(size=18)).pack(anchor="w", pady=(20,8))
        ctk.CTkOptionMenu(self, values=["Dark", "Light", "System"],
                          command=lambda x: ctk.set_appearance_mode(x.lower())).pack(anchor="w")


class TaskForm(ctk.CTkToplevel):
    def __init__(self, parent, save_callback, task=None):
        super().__init__(parent)
        self.title("New Task" if not task else "Edit Task")
        self.geometry("700x820")
        self.configure(fg_color="#1F2937")
        self.save_callback = save_callback
        self.task = task or Task()

        # Create scrollable frame
        self.scrollable_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.build_form()

    def build_form(self):
        ctk.CTkLabel(self.scrollable_frame, text="Task Details", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=30)

        # Title
        ctk.CTkLabel(self.scrollable_frame, text="Title *", font=ctk.CTkFont(size=16)).pack(anchor="w", padx=40, pady=(0,6))
        self.title_entry = ctk.CTkEntry(self.scrollable_frame, height=50, font=ctk.CTkFont(size=15))
        self.title_entry.pack(fill="x", padx=40)
        self.title_entry.insert(0, self.task.title)

        # Description
        ctk.CTkLabel(self.scrollable_frame, text="Description", font=ctk.CTkFont(size=16)).pack(anchor="w", padx=40, pady=(24,6))
        self.desc_entry = ctk.CTkTextbox(self.scrollable_frame, height=140, font=ctk.CTkFont(size=14))
        self.desc_entry.pack(fill="x", padx=40)
        self.desc_entry.insert("0.0", self.task.description)

        # Row: Priority + Status + Due Date
        row = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        row.pack(fill="x", padx=40, pady=30)

        # Priority
        ctk.CTkLabel(row, text="Priority").pack(side="left")
        self.priority_var = ctk.StringVar(value=self.task.priority)
        ctk.CTkOptionMenu(row, values=["High", "Medium", "Low"], variable=self.priority_var).pack(side="left", padx=20)

        # Status
        ctk.CTkLabel(row, text="Status").pack(side="left", padx=(40,0))
        self.status_var = ctk.StringVar(value=self.task.status)
        ctk.CTkOptionMenu(row, values=["To Do", "In Progress", "Done"], variable=self.status_var).pack(side="left", padx=20)

        # Due Date
        ctk.CTkLabel(self.scrollable_frame, text="Due Date (YYYY-MM-DD)", font=ctk.CTkFont(size=15)).pack(anchor="w", padx=40, pady=(10,6))
        self.due_entry = ctk.CTkEntry(self.scrollable_frame, width=220)
        self.due_entry.pack(anchor="w", padx=40)
        if self.task.due_date:
            self.due_entry.insert(0, self.task.due_date[:10])

        # Action Buttons
        btn_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=40, pady=40)
        ctk.CTkButton(btn_frame, text="Save Task", height=56, font=ctk.CTkFont(size=17, weight="bold"),
                      fg_color=ACCENT_COLOR, command=self.save).pack(side="right", padx=(15,0))
        ctk.CTkButton(btn_frame, text="Cancel", height=56, font=ctk.CTkFont(size=17),
                      fg_color="#475569", command=self.destroy).pack(side="right")

    def save(self):
        if not self.title_entry.get().strip():
            messagebox.showerror("Error", "Task title is required.")
            return
        self.task.title = self.title_entry.get().strip()
        self.task.description = self.desc_entry.get("0.0", "end").strip()
        self.task.priority = self.priority_var.get()
        self.task.status = self.status_var.get()
        self.task.due_date = self.due_entry.get().strip() or None

        self.save_callback(self.task)
        self.destroy()


class PomodoroTimer(ctk.CTkToplevel):
    def __init__(self, parent, linked_task=None, time_callback=None):
        super().__init__(parent)
        self.title("Focus Mode")
        self.geometry("480x580")
        self.configure(fg_color="#1F2937")
        self.resizable(False, False)

        self.work_time = CONFIG["default_work_time"] * 60
        self.current_time = self.work_time
        self.is_running = False
        self.time_callback = time_callback
        self.linked_task = linked_task
        self.app = parent

        self.build_ui()

    def build_ui(self):
        ctk.CTkLabel(self, text="Focus Mode", font=ctk.CTkFont(size=28, weight="bold")).pack(pady=40)

        self.timer_label = ctk.CTkLabel(self, text="25:00", font=ctk.CTkFont(size=92, weight="bold"))
        self.timer_label.pack(pady=20)

        self.status_label = ctk.CTkLabel(self, text="Work Session", font=ctk.CTkFont(size=18))
        self.status_label.pack(pady=10)

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(pady=50)

        for text, cmd in [("Start", self.start), ("Pause", self.pause), ("Reset", self.reset)]:
            ctk.CTkButton(controls, text=text, width=130, height=50, font=ctk.CTkFont(size=16),
                          command=cmd).pack(side="left", padx=12)

    def update_display(self):
        m, s = divmod(self.current_time, 60)
        self.timer_label.configure(text=f"{m:02d}:{s:02d}")

    def start(self):
        if not self.is_running:
            self.is_running = True
            threading.Thread(target=self.countdown, daemon=True).start()

    def pause(self):
        self.is_running = False

    def reset(self):
        self.is_running = False
        self.current_time = self.work_time
        self.update_display()

    def countdown(self):
        while self.current_time > 0 and self.is_running:
            time.sleep(1)
            self.current_time -= 1
            self.after(0, self.update_display)

        if self.current_time <= 0:
            self.after(0, self.finish)

    def finish(self):
        self.is_running = False
        self.app.show_notification("Session Complete", "Excellent focus! Take a break.", SUCCESS_COLOR)
        if self.linked_task and self.time_callback:
            self.time_callback(self.linked_task.id, CONFIG["default_work_time"])
        self.reset()


# ====================== Launch ======================
if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    app = TaskFlow()
    app.mainloop()