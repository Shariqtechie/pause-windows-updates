import os
import sys
import ctypes
import json
import winreg
from datetime import datetime, timedelta, timezone
import tkinter as tk
from tkinter import ttk, messagebox
import threading

# Registry Path
REG_PATH = r"SOFTWARE\Microsoft\WindowsUpdate\UX\Settings"

# Keys of Interest
REG_KEYS = [
    "PauseUpdatesExpiryTime",
    "PauseFeatureUpdatesStartTime",
    "PauseFeatureUpdatesEndTime",
    "PauseQualityUpdatesStartTime",
    "PauseQualityUpdatesEndTime",
    "PauseUpdatesRequestedUntilTime"  # Extra reliability key in newer Windows 11 builds
]

def is_admin():
    """Check if the script is running with administrative privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def run_as_admin():
    """Relaunch the script with admin elevation."""
    # Need to quote the path in case there are spaces
    script = os.path.abspath(sys.argv[0])
    params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}" {params}', None, 1
        )
        sys.exit(0)
    except Exception as e:
        messagebox.showerror(
            "Elevation Failed",
            f"This utility requires Administrator privileges to edit Windows Update Registry keys.\n\nError: {e}"
        )
        sys.exit(1)

class PauseManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Windows Update Pause Manager v1.0")
        self.root.geometry("480x600")
        self.root.resizable(False, False)
        
        # Configure overall themes and styles
        self.style = ttk.Style()
        self.style.theme_use('vista') # Use native windows engine
        
        # Set Colors
        self.bg_color = "#f3f3f3"
        self.card_bg = "#ffffff"
        self.accent_color = "#0078d4" # Win11 Blue
        self.danger_color = "#e81123"
        self.text_color = "#202020"
        self.muted_text = "#5f5f5f"
        
        self.root.configure(bg=self.bg_color)
        
        # Grid weights
        self.root.columnconfigure(0, weight=1)
        
        # Setup UI Variables
        self.pause_state_var = tk.StringVar(value="Checking...")
        self.pause_until_var = tk.StringVar(value="-")
        self.status_var = tk.StringVar(value="Ready")
        self.selected_duration = tk.StringVar(value="1 Year")
        
        self.build_ui()
        self.refresh_data()

    def build_ui(self):
        # Header Panel
        header_frame = tk.Frame(self.root, bg=self.accent_color, padx=20, pady=20)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.columnconfigure(0, weight=1)
        
        header_title = tk.Label(
            header_frame, 
            text="Windows Update Pause Manager", 
            font=("Segoe UI", 16, "bold"), 
            fg="white", 
            bg=self.accent_color
        )
        header_title.grid(row=0, column=0, sticky="w")
        
        header_sub = tk.Label(
            header_frame, 
            text="Set arbitrary future pause expiration dates instantly", 
            font=("Segoe UI", 9), 
            fg="#e1f0fc", 
            bg=self.accent_color
        )
        header_sub.grid(row=1, column=0, sticky="w")

        # Container for main layout (with margins)
        main_frame = tk.Frame(self.root, bg=self.bg_color, padx=20, pady=20)
        main_frame.grid(row=1, column=0, sticky="nsew")
        main_frame.columnconfigure(0, weight=1)
        
        # Card 1: Current Status Card
        status_card = tk.LabelFrame(
            main_frame, 
            text=" Current Configuration ", 
            font=("Segoe UI", 10, "bold"), 
            bg=self.card_bg, 
            fg=self.accent_color,
            padx=15, 
            pady=15,
            bd=1,
            relief="solid"
        )
        status_card.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        status_card.columnconfigure(1, weight=1)
        
        # Labels inside card
        lbl_state_title = tk.Label(status_card, text="Pause State:", font=("Segoe UI", 10, "bold"), bg=self.card_bg, fg=self.muted_text)
        lbl_state_title.grid(row=0, column=0, sticky="w", pady=5)
        
        self.lbl_state_val = tk.Label(
            status_card, 
            textvariable=self.pause_state_var, 
            font=("Segoe UI", 11, "bold"), 
            bg=self.card_bg, 
            fg=self.text_color
        )
        self.lbl_state_val.grid(row=0, column=1, sticky="w", padx=10, pady=5)
        
        lbl_until_title = tk.Label(status_card, text="Pause Expiry:", font=("Segoe UI", 10, "bold"), bg=self.card_bg, fg=self.muted_text)
        lbl_until_title.grid(row=1, column=0, sticky="w", pady=5)
        
        lbl_until_val = tk.Label(
            status_card, 
            textvariable=self.pause_until_var, 
            font=("Segoe UI", 10), 
            bg=self.card_bg, 
            fg=self.text_color
        )
        lbl_until_val.grid(row=1, column=1, sticky="w", padx=10, pady=5)
        
        # Refresh Button inline with card
        self.btn_refresh = tk.Button(
            status_card, 
            text=" ↻ Refresh ", 
            command=self.refresh_data, 
            font=("Segoe UI", 9), 
            bg="#f0f0f0", 
            fg=self.text_color,
            activebackground="#e0e0e0", 
            relief="groove", 
            bd=1, 
            padx=5, 
            pady=2
        )
        self.btn_refresh.grid(row=2, column=1, sticky="e", pady=(10, 0))

        # Card 2: Configuration / Action Panel
        action_card = tk.LabelFrame(
            main_frame, 
            text=" Update Settings ", 
            font=("Segoe UI", 10, "bold"), 
            bg=self.card_bg, 
            fg=self.accent_color,
            padx=15, 
            pady=15,
            bd=1,
            relief="solid"
        )
        action_card.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        action_card.columnconfigure(0, weight=1)
        
        lbl_duration = tk.Label(
            action_card, 
            text="Choose New Pause Duration:", 
            font=("Segoe UI", 10, "bold"), 
            bg=self.card_bg, 
            fg=self.text_color
        )
        lbl_duration.grid(row=0, column=0, sticky="w", pady=(0, 10))
        
        # Combobox Selection
        durations = ["7 Days", "30 Days", "90 Days", "1 Year", "3 Years", "5 Years", "Resume Updates (Clear Pause)"]
        self.combo_durations = ttk.Combobox(
            action_card, 
            textvariable=self.selected_duration, 
            values=durations, 
            state="readonly", 
            font=("Segoe UI", 10)
        )
        self.combo_durations.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        self.combo_durations.bind("<<ComboboxSelected>>", self.on_duration_changed)
        
        # Custom Date Picker Frame (Hidden by default, triggered if custom supported)
        self.custom_frame = tk.Frame(action_card, bg=self.card_bg)
        self.custom_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self.custom_frame.grid_remove() # hidden Initially
        
        lbl_custom_desc = tk.Label(
            self.custom_frame, 
            text="Custom Expiry Date (YYYY-MM-DD):", 
            font=("Segoe UI", 9), 
            bg=self.card_bg, 
            fg=self.muted_text
        )
        lbl_custom_desc.pack(anchor="w")
        
        self.entry_custom_date = ttk.Entry(self.custom_frame, font=("Segoe UI", 10))
        self.entry_custom_date.pack(fill="x", pady=5)
        self.entry_custom_date.insert(0, (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d"))

        # Primary Apply Button
        self.btn_apply = tk.Button(
            action_card, 
            text="Apply Changes", 
            font=("Segoe UI", 11, "bold"), 
            bg=self.accent_color, 
            fg="white",
            activebackground="#005a9e", 
            activeforeground="white",
            relief="flat", 
            bd=0, 
            pady=8,
            command=self.apply_changes_threaded
        )
        self.btn_apply.grid(row=3, column=0, sticky="ew", pady=(5, 5))
        
        # Status / Feedback bar
        feedback_frame = tk.Frame(self.root, bg="#e1e1e1", height=30, padx=15)
        feedback_frame.grid(row=2, column=0, sticky="ews")
        feedback_frame.columnconfigure(0, weight=1)
        
        self.lbl_status = tk.Label(
            feedback_frame, 
            textvariable=self.status_var, 
            font=("Segoe UI", 9, "italic"), 
            bg="#e1e1e1", 
            fg=self.muted_text
        )
        self.lbl_status.grid(row=0, column=0, sticky="w", pady=4)
        
        self.spinner_label = tk.Label(feedback_frame, text="", font=("Segoe UI", 9), bg="#e1e1e1", fg=self.accent_color)
        self.spinner_label.grid(row=0, column=1, sticky="e", pady=4)

    def on_duration_changed(self, event=None):
        selection = self.selected_duration.get()
        if "Custom" in selection:
            self.custom_frame.grid()
        else:
            self.custom_frame.grid_remove()

    def set_loading(self, loading, status_text=""):
        """Toggles interface interactive state & shows mock/live indicators."""
        if loading:
            self.status_var.set(status_text)
            self.spinner_label.config(text="⏳ Processing...")
            self.btn_apply.config(state="disabled", bg="#cccccc")
            self.btn_refresh.config(state="disabled")
            self.combo_durations.config(state="disabled")
        else:
            self.status_var.set(status_text if status_text else "Ready")
            self.spinner_label.config(text="")
            self.btn_apply.config(state="normal", bg=self.accent_color)
            self.btn_refresh.config(state="normal")
            self.combo_durations.config(state="readonly")

    def refresh_data(self):
        """Reads registry keys directly and loads active details."""
        self.set_loading(True, "Reading Registry Configuration...")
        
        def task():
            registry_data = {}
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_PATH, 0, winreg.KEY_READ) as key:
                    for val_name in REG_KEYS:
                        try:
                            val, _ = winreg.QueryValueEx(key, val_name)
                            registry_data[val_name] = val
                        except FileNotFoundError:
                            registry_data[val_name] = None
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Read Error", f"Could not read Windows Update Registry settings.\n\nError: {e}"))
            
            self.root.after(0, lambda: self.update_ui_state(registry_data))

        threading.Thread(target=task, daemon=True).start()

    def update_ui_state(self, reg_data):
        """Converts raw registry ISO dates to friendly system strings."""
        expiry_val = reg_data.get("PauseUpdatesExpiryTime")
        
        if expiry_val:
            # Parse ISO 8601 Timestamp: YYYY-MM-DDTHH:MM:SSZ
            try:
                # Remove Z and convert
                clean_ts = expiry_val.replace("Z", "")
                dt = datetime.fromisoformat(clean_ts)
                formatted_date = dt.strftime("%d %b %Y @ %H:%M:%S (UTC)")
                
                self.pause_state_var.set("Paused")
                self.lbl_state_val.config(fg="#107c41") # Green
                self.pause_until_var.set(formatted_date)
            except Exception:
                self.pause_state_var.set("Unknown / Corrupted")
                self.lbl_state_val.config(fg=self.danger_color)
                self.pause_until_var.set(str(expiry_val))
        else:
            self.pause_state_var.set("Not Paused / Resumed")
            self.lbl_state_val.config(fg=self.danger_color) # Red
            self.pause_until_var.set("-")
            
        self.set_loading(False, "Ready")

    def apply_changes_threaded(self):
        """Dispatches backup and save processes on a background thread."""
        self.set_loading(True, "Preparing Backup...")
        threading.Thread(target=self.apply_changes, daemon=True).start()

    def apply_changes(self):
        # 1. Back Up Current Key Values First
        backup_dict = {}
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_PATH, 0, winreg.KEY_READ) as key:
                for val_name in REG_KEYS:
                    try:
                        val, val_type = winreg.QueryValueEx(key, val_name)
                        backup_dict[val_name] = {"value": val, "type": val_type}
                    except FileNotFoundError:
                        backup_dict[val_name] = None
        except Exception as e:
            self.root.after(0, lambda: messagebox.showwarning("Backup Notice", f"Unable to fetch all original registry states for backup.\nContinuing anyway.\nError: {e}"))

        # Save Backup file locally
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"wua_pause_backup_{timestamp}.json"
        try:
            with open(backup_filename, "w") as bf:
                json.dump(backup_dict, bf, indent=2)
            self.root.after(0, lambda: self.status_var.set(f"Backup created: {backup_filename}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showwarning("Backup Save Failure", f"Backup JSON could not be written locally.\nError: {e}"))

        # 2. Determine Action
        selection = self.selected_duration.get()
        
        if "Resume Updates" in selection:
            # We must delete or nullify those registry configurations
            self.perform_resume()
        else:
            self.perform_pause(selection)

    def perform_resume(self):
        """Cleans out Registry values to resume normal Windows Update cycles."""
        self.root.after(0, lambda: self.status_var.set("Deleting registry pause values..."))
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
                for val_name in REG_KEYS:
                    try:
                        winreg.DeleteValue(key, val_name)
                    except FileNotFoundError:
                        pass # Key wasn't present anyway
            
            self.root.after(0, lambda: messagebox.showinfo("Success", "Windows Update pause values cleared successfully!\n\nOpen Settings → Windows Update to confirm updates are resumed."))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Write Error", f"Failed to modify Registry.\n\nError: {e}"))
        
        self.refresh_data()

    def perform_pause(self, selection):
        """Calculates future target dates and formats them to registry specifications."""
        now_utc = datetime.now(timezone.utc)
        
        if "7 Days" in selection:
            expiry_dt = now_utc + timedelta(days=7)
        elif "30 Days" in selection:
            expiry_dt = now_utc + timedelta(days=30)
        elif "90 Days" in selection:
            expiry_dt = now_utc + timedelta(days=90)
        elif "1 Year" in selection:
            expiry_dt = now_utc + timedelta(days=365)
        elif "3 Years" in selection:
            expiry_dt = now_utc + timedelta(days=365 * 3)
        elif "5 Years" in selection:
            expiry_dt = now_utc + timedelta(days=365 * 5)
        else:
            # Custom Expiry
            custom_str = self.entry_custom_date.get().strip()
            try:
                expiry_dt = datetime.strptime(custom_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if expiry_dt <= now_utc:
                    raise ValueError("Target date must be in the future.")
            except Exception as ex:
                self.root.after(0, lambda: messagebox.showerror("Invalid Date", f"Please input a valid future date formatted as YYYY-MM-DD.\n\nError: {ex}"))
                self.root.after(0, lambda: self.set_loading(False, "Error state"))
                return

        # Format timestamps correctly (e.g., 2029-06-16T07:56:22Z)
        start_time_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        expiry_time_iso = expiry_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        updates_to_write = {
            "PauseUpdatesExpiryTime": expiry_time_iso,
            "PauseFeatureUpdatesStartTime": start_time_iso,
            "PauseFeatureUpdatesEndTime": expiry_time_iso,
            "PauseQualityUpdatesStartTime": start_time_iso,
            "PauseQualityUpdatesEndTime": expiry_time_iso,
            "PauseUpdatesRequestedUntilTime": expiry_time_iso
        }

        self.root.after(0, lambda: self.status_var.set("Applying registry payload..."))
        
        try:
            # Create or open key for writing
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
                for k, v in updates_to_write.items():
                    winreg.SetValueEx(key, k, 0, winreg.REG_SZ, v)
                    
            self.root.after(0, lambda: messagebox.showinfo(
                "Success", 
                f"Registry Values Updated!\n\nWindows Update Pause extended to: {expiry_time_iso}\n\nPlease check Windows Update in Settings to confirm changes."
            ))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Write Failure", f"Failed to apply pause configurations.\n\nError: {e}"))

        self.refresh_data()


if __name__ == "__main__":
    # Ensure tool runs with elevated privileges
    if not is_admin():
        run_as_admin()
    else:
        root = tk.Tk()
        app = PauseManagerApp(root)
        root.mainloop()
