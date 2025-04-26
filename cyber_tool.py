import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, simpledialog # Added simpledialog
import subprocess
import tempfile
import os
import threading
import sys
import json # For saving/loading script configurations

# --- Configuration ---
# Store paths to your PowerShell scripts here.
# You can add more scripts by adding entries to this dictionary.
# It's recommended to keep the scripts in a subfolder (e.g., 'scripts')
SCRIPT_CONFIG_FILE = 'scripts_config.json'
DEFAULT_SCRIPTS = {
    "Get Network Info": "scripts/get_network_info.ps1",
    "Check Common Ports (localhost)": "scripts/check_common_ports.ps1",
    # Add more default scripts here if desired
}

class CyberToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Simple Cyber Tool Runner")
        # Make window slightly larger
        self.root.geometry("800x600")

        # Load script paths
        self.script_paths = self.load_script_config()

        # --- GUI Setup ---
        # Frame for buttons
        self.button_frame = tk.Frame(root, pady=10) # Store frame reference
        self.button_frame.pack(fill=tk.X)

        # Add Script Button
        add_button = tk.Button(self.button_frame, text="Add Script", command=self.add_script, padx=5, pady=2)
        add_button.pack(side=tk.LEFT, padx=10)

        # Report Area
        self.report_area = scrolledtext.ScrolledText(
            root, wrap=tk.WORD, state=tk.DISABLED, height=25, width=90,
            font=("Consolas", 10) # Use a monospaced font for reports
        )
        self.report_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Create buttons for each script
        self.create_script_buttons(self.button_frame)

        # Status Bar (Optional)
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = tk.Label(root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.update_report("Application started. Add scripts or click buttons to run tasks.\n"
                           "Note: Running scripts will request Administrator privileges (UAC prompt) on Windows.")

    def load_script_config(self):
        """Loads script configurations from a JSON file."""
        try:
            if os.path.exists(SCRIPT_CONFIG_FILE):
                with open(SCRIPT_CONFIG_FILE, 'r', encoding='utf-8') as f: # Specify encoding
                    return json.load(f)
            else:
                # Create default config if not found
                self.save_script_config(DEFAULT_SCRIPTS)
                # Ensure the 'scripts' directory exists
                if not os.path.exists('scripts'):
                    try:
                        os.makedirs('scripts')
                        self.update_report("Created 'scripts' directory for PowerShell files.")
                    except OSError as e:
                         self.update_report(f"Error creating 'scripts' directory: {e}")
                         messagebox.showerror("Directory Error", f"Could not create 'scripts' directory:\n{e}")

                return DEFAULT_SCRIPTS
        except json.JSONDecodeError as e:
            messagebox.showerror("Config Load Error", f"Error decoding {SCRIPT_CONFIG_FILE}:\n{e}\n\nPlease check the file format. Loading defaults.")
            return DEFAULT_SCRIPTS
        except Exception as e:
            messagebox.showerror("Config Load Error", f"Failed to load {SCRIPT_CONFIG_FILE}:\n{e}")
            return DEFAULT_SCRIPTS # Return default on error

    def save_script_config(self, config_data):
        """Saves script configurations to a JSON file."""
        try:
            with open(SCRIPT_CONFIG_FILE, 'w', encoding='utf-8') as f: # Specify encoding
                json.dump(config_data, f, indent=4)
        except Exception as e:
            messagebox.showerror("Config Save Error", f"Failed to save {SCRIPT_CONFIG_FILE}:\n{e}")

    def create_script_buttons(self, parent_frame):
        """Dynamically creates buttons based on the loaded script config."""
         # Clear existing buttons first (if any)
        for widget in parent_frame.winfo_children():
            # Keep the 'Add Script' button
            if isinstance(widget, tk.Button) and widget.cget('text') != "Add Script":
                widget.destroy()

        # Create buttons for loaded scripts
        for script_name, script_path in self.script_paths.items():
            # Use lambda to capture the correct script_name and script_path for each button
            button = tk.Button(
                parent_frame,
                text=script_name,
                command=lambda name=script_name, path=script_path: self.run_script_thread(name, path),
                padx=5, pady=2
            )
            button.pack(side=tk.LEFT, padx=5)

    def add_script(self):
        """Allows user to add a new script via file dialog."""
        script_path = filedialog.askopenfilename(
            title="Select PowerShell Script",
            filetypes=[("PowerShell Scripts", "*.ps1"), ("All Files", "*.*")]
        )
        if not script_path:
            return # User cancelled

        # Ask for a friendly name for the button
        script_name = simpledialog.askstring("Script Name", "Enter a name for this script button:")
        if not script_name:
            script_name = os.path.basename(script_path) # Default to filename if empty

        if script_name in self.script_paths:
            if not messagebox.askyesno("Overwrite?", f"A script named '{script_name}' already exists. Overwrite?"):
                return

        self.script_paths[script_name] = script_path
        self.save_script_config(self.script_paths)
        self.create_script_buttons(self.button_frame) # Recreate buttons in the button_frame
        self.update_report(f"Added script: '{script_name}' -> {script_path}")

    def run_script_thread(self, script_name, script_path):
        """Runs the script execution in a separate thread to keep GUI responsive."""
        # Disable buttons while running? (Optional - consider disabling specific button)
        self.status_var.set(f"Running '{script_name}'...")
        thread = threading.Thread(target=self._execute_powershell_elevated, args=(script_name, script_path), daemon=True)
        thread.start()

    def _execute_powershell_elevated(self, script_name, script_path):
        """Handles the logic to execute a PowerShell script with elevation."""
        self.update_report(f"\n--- Starting '{script_name}' ---")

        # --- Pre-checks ---
        if not os.path.exists(script_path):
            self.update_report(f"Error: Script not found at '{os.path.abspath(script_path)}'")
            # No messagebox here, report area is sufficient
            self.status_var.set(f"Error: '{script_name}' script not found.")
            return

        # Check if running on Windows before attempting elevation
        if sys.platform != "win32":
            self.update_report(f"Info: Running on non-Windows platform ({sys.platform}). Cannot elevate.")
            self.update_report("Attempting to run script without elevation...")
            self.status_var.set(f"Running '{script_name}' (no elevation)...")
            self._execute_powershell_basic(script_name, script_path) # Fallback for non-windows
            return
        # --- End Pre-checks ---

        output_file_path = None
        process = None # Define process variable
        try:
            # Create a temporary file to capture output from the elevated script
            # Use delete=False so we can manually delete it after reading
            with tempfile.NamedTemporaryFile(suffix=".txt", prefix=f"cybertool_{script_name}_", mode="w", delete=False, encoding='utf-8') as temp_f:
                 output_file_path = temp_f.name

            # Resolve the absolute path for the script
            abs_script_path = os.path.abspath(script_path)
            abs_output_file_path = os.path.abspath(output_file_path)

            # Construct the PowerShell command block to be run elevated.
            # This block executes the target script and redirects *all* output streams (*>&)
            # to the temporary file. Using $ErrorActionPreference = 'Continue' to capture errors.
            # Added try/catch within PowerShell for better error capture to the file.
            inner_command = (
                f"$ErrorActionPreference = 'Stop'; " # Stop on terminating errors
                f"try {{ & '{abs_script_path}' *>&1 | Out-File -Encoding utf8 -FilePath '{abs_output_file_path}'; $exitCode = $LASTEXITCODE }} "
                f"catch {{ Write-Output ('Error in script execution: ' + $_.Exception.Message); Write-Output $_.ScriptStackTrace | Out-File -Encoding utf8 -Append -FilePath '{abs_output_file_path}'; $exitCode = 1 }} "
                f"exit $exitCode"
            )

            # Escape single quotes within the inner command for the outer PowerShell command string
            quoted_inner_command = inner_command.replace("'", "''")

            # Command to launch an initial PowerShell process, which then uses Start-Process
            # to launch the *actual* script elevated (-Verb RunAs).
            # -Wait ensures the initial process waits for the elevated one to complete.
            # Using -WindowStyle Hidden to try and hide the elevated PowerShell window.
            command = [
                "powershell.exe",
                "-ExecutionPolicy", "Bypass", # Policy for the launcher process
                "-Command", f"Start-Process powershell.exe -ArgumentList '-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command \"{quoted_inner_command}\"' -Verb RunAs -Wait -WindowStyle Hidden"
            ]

            self.update_report(f"Executing (elevated): {abs_script_path}")
            self.update_report("Requesting Administrator privileges (UAC)...")

            # Execute the command. This triggers UAC.
            # creationflags=subprocess.CREATE_NO_WINDOW attempts to hide the initial PowerShell window.
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False, # Don't raise exception on non-zero exit code for the launcher
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                encoding='utf-8', # Specify encoding for captured output
                errors='ignore'   # Ignore decoding errors for launcher output
            )

            # Check the return code of the *launcher* process.
            if process.returncode != 0:
                 error_message = f"Error launching elevated process for '{script_name}'.\n"
                 error_message += f"Launcher Return Code: {process.returncode}\n"
                 # Display stdout/stderr only if they contain useful info
                 if process.stderr and process.stderr.strip():
                     error_message += f"Launcher STDERR:\n{process.stderr.strip()}\n"
                 if process.stdout and process.stdout.strip():
                    error_message += f"Launcher STDOUT:\n{process.stdout.strip()}\n"
                 self.update_report(f"Error: Failed to start elevated process. UAC denied or other launcher error. Check details.")
                 self.update_report(error_message) # Show details in report area
                 self.status_var.set(f"Error: '{script_name}' launch failed.")
                 # Try to read the temp file anyway
                 self.read_and_display_output(script_name, output_file_path)
                 return # Stop further processing

            # If launcher succeeded (return code 0), the elevated script *should* have run.
            self.update_report(f"'{script_name}' elevated process finished. Reading results...")
            self.read_and_display_output(script_name, output_file_path)
            self.status_var.set(f"'{script_name}' completed.")


        except FileNotFoundError:
             self.update_report("Error: 'powershell.exe' not found. Is PowerShell installed and in your system's PATH?")
             # No messagebox here, report area is sufficient
             self.status_var.set("Error: PowerShell not found.")
        except Exception as e:
            self.update_report(f"An unexpected error occurred during elevation attempt for '{script_name}': {e}")
            import traceback
            self.update_report(f"Traceback:\n{traceback.format_exc()}")
            # No messagebox here, report area is sufficient
            self.status_var.set(f"Error: '{script_name}' failed unexpectedly.")
        finally:
            # Clean up the temporary file
            if output_file_path and os.path.exists(output_file_path):
                try:
                    os.remove(output_file_path)
                    # self.update_report(f"Cleaned up temp file: {output_file_path}") # Optional debug message
                except Exception as e:
                    self.update_report(f"Warning: Could not delete temporary file '{output_file_path}': {e}")
            # Re-enable buttons? (If you disabled them)
            if sys.platform == "win32": # Only reset status if it was a windows execution attempt
                 self.status_var.set("Ready") # Reset status bar


    def _execute_powershell_basic(self, script_name, script_path):
        """Executes a PowerShell script directly without elevation (for non-Windows or fallback)."""
        output_file_path = None
        try:
            # Create a temporary file to capture output
            with tempfile.NamedTemporaryFile(suffix=".txt", prefix=f"cybertool_{script_name}_", mode="w", delete=False, encoding='utf-8') as temp_f:
                output_file_path = temp_f.name

            abs_script_path = os.path.abspath(script_path)
            abs_output_file_path = os.path.abspath(output_file_path)

            # Command to run PowerShell directly
            command = [
                "powershell.exe" if sys.platform == "win32" else "pwsh", # Use pwsh for Linux/Mac if installed
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy", "Bypass",
                "-Command",
                f"& '{abs_script_path}' *>&1 | Out-File -Encoding utf8 -FilePath '{abs_output_file_path}'; exit $LASTEXITCODE"
            ]

            self.update_report(f"Executing (non-elevated): {abs_script_path}")

            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                encoding='utf-8',
                errors='ignore'
            )

            if process.returncode != 0:
                self.update_report(f"Warning: Non-elevated script '{script_name}' exited with code {process.returncode}.")
                if process.stderr and process.stderr.strip():
                    self.update_report(f"STDERR:\n{process.stderr.strip()}")
                # Still try to read the output file as it might contain partial results or errors

            self.read_and_display_output(script_name, output_file_path)
            self.status_var.set(f"'{script_name}' completed (non-elevated).")

        except FileNotFoundError:
             cmd_name = "powershell.exe" if sys.platform == "win32" else "pwsh"
             self.update_report(f"Error: '{cmd_name}' not found. Is PowerShell installed and in your system's PATH?")
             self.status_var.set(f"Error: {cmd_name} not found.")
        except Exception as e:
            self.update_report(f"An unexpected error occurred during non-elevated execution of '{script_name}': {e}")
            import traceback
            self.update_report(f"Traceback:\n{traceback.format_exc()}")
            self.status_var.set(f"Error: '{script_name}' failed unexpectedly.")
        finally:
            # Clean up the temporary file
            if output_file_path and os.path.exists(output_file_path):
                try:
                    os.remove(output_file_path)
                except Exception as e:
                    self.update_report(f"Warning: Could not delete temporary file '{output_file_path}': {e}")
            self.status_var.set("Ready") # Reset status bar


    def read_and_display_output(self, script_name, file_path):
        """Reads the content of the output file and displays it in the report area."""
        output_content = f"--- Results for {script_name} ---\n"
        try:
            if file_path and os.path.exists(file_path):
                 if os.path.getsize(file_path) > 0:
                    # Try reading with UTF-8, fallback to latin-1 if needed
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            script_output = f.read()
                    except UnicodeDecodeError:
                         self.update_report(f"Warning: Could not decode output file {os.path.basename(file_path)} as UTF-8, trying latin-1.")
                         with open(file_path, 'r', encoding='latin-1') as f:
                            script_output = f.read()
                    output_content += script_output
                 else:
                     output_content += "(Script produced no output)"
            else:
                 output_content += "(Output file not found or not created - script might have failed early)"

        except Exception as e:
            output_content += f"\nError reading output file '{os.path.basename(file_path)}': {e}"
            # No messagebox here, report area is sufficient

        output_content += "\n--- End of Results ---"
        self.update_report(output_content)


    def update_report(self, message):
        """Safely updates the report_area GUI element from any thread."""
        def _update():
            if self.report_area.winfo_exists(): # Check if widget still exists
                self.report_area.config(state=tk.NORMAL)
                self.report_area.insert(tk.END, message + "\n")
                self.report_area.see(tk.END) # Scroll to the end
                self.report_area.config(state=tk.DISABLED)
        # Schedule the GUI update to run in the main Tkinter thread
        if self.root.winfo_exists(): # Check if root window still exists
            self.root.after(0, _update)

# --- Main execution ---
if __name__ == "__main__":
    # Check if display is available (important for Codespaces/SSH)
    try:
        # Try to create the root window. This might fail if there's no display.
        root = tk.Tk()
        # Check if a display name is set (basic check)
        # On Linux/Codespaces, this often needs to be forwarded (e.g., via X11 forwarding)
        # or a virtual framebuffer (like Xvfb) needs to be running.
        if sys.platform != "win32" and not os.environ.get('DISPLAY'):
             print("Warning: DISPLAY environment variable not set. GUI might not appear.")
             print("If running in Codespaces or SSH, ensure X11 forwarding is enabled or use a virtual framebuffer (Xvfb).")

        app = CyberToolApp(root)
        root.mainloop()
    except tk.TclError as e:
        print(f"Error initializing Tkinter GUI: {e}")
        print("This usually means a graphical display environment is not available.")
        print("If running in a headless environment (like Codespaces without forwarding), the GUI cannot be shown.")
        # Exit gracefully if GUI cannot be created
        sys.exit(1)

