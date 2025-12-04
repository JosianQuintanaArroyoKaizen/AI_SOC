#!/usr/bin/env python3
"""AI-SOC Deployment Assistant

This desktop helper focuses on the CI/CD + CloudFormation deployment flow.
It replaces the old Docker launcher and helps operators:
  * validate local prerequisites (git, aws cli, cfn-lint)
  * lint CloudFormation templates before committing
  * jump into the Getting Started / CI/CD guides quickly
  * open the GitHub Actions dashboard for manual runs
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk
import webbrowser


@dataclass
class PrereqCheck:
    name: str
    commands: list[list[str]]
    required: bool = True


class AISOCDeploymentAssistant:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("AI-SOC Deployment Assistant")
        self.root.geometry("980x720")
        self.root.minsize(860, 620)

        self.base_dir = Path(__file__).parent.resolve()
        os.chdir(self.base_dir)

        self.repo_actions_url = self._detect_actions_url()

        self.prereq_checks: list[PrereqCheck] = [
            PrereqCheck("Git CLI", [["git", "--version"]]),
            PrereqCheck("AWS CLI v2", [["aws", "--version"]]),
            PrereqCheck("Python 3.11+", [["python3", "--version"], ["python", "--version"]]),
            PrereqCheck("cfn-lint", [["cfn-lint", "--version"]], required=False),
            PrereqCheck("cfn-guard", [["cfn-guard", "--version"]], required=False),
        ]

        self._setup_ui()
        self.root.after(400, self.validate_prereqs)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        header = tk.Frame(self.root, bg="#1b2733", height=90)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="AI-SOC CI/CD Deployment Assistant",
            font=("Segoe UI", 22, "bold"),
            fg="white",
            bg="#1b2733"
        ).pack(pady=20)

        content = tk.Frame(self.root, bg="#f5f6f7")
        content.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        status_card = tk.LabelFrame(
            content,
            text="Prerequisite Status",
            font=("Segoe UI", 11, "bold"),
            bg="#f5f6f7",
            padx=10,
            pady=10
        )
        status_card.pack(fill=tk.X)

        columns = ("check", "status", "details")
        self.status_tree = ttk.Treeview(
            status_card,
            columns=columns,
            show="headings",
            height=5
        )
        self.status_tree.heading("check", text="Check")
        self.status_tree.heading("status", text="Status")
        self.status_tree.heading("details", text="Details")
        self.status_tree.column("check", width=200)
        self.status_tree.column("status", width=120, anchor=tk.CENTER)
        self.status_tree.column("details", width=420)
        self.status_tree.pack(fill=tk.X)

        for check in self.prereq_checks:
            self.status_tree.insert("", tk.END, iid=check.name, values=(check.name, "Pending", ""))

        buttons_card = tk.LabelFrame(
            content,
            text="Deployment Shortcuts",
            font=("Segoe UI", 11, "bold"),
            bg="#f5f6f7",
            padx=10,
            pady=10
        )
        buttons_card.pack(fill=tk.X, pady=10)

        button_specs = [
            ("🔄 Validate Prerequisites", self.validate_prereqs),
            ("🧪 Run Template Validation", self.run_template_validation),
            ("📘 Open Getting Started", lambda: self.open_doc("GETTING-STARTED.md")),
            ("⚙️ Open CI/CD Guide", lambda: self.open_doc("CICD_GUIDE.md")),
            ("🚀 Open GitHub Actions", self.open_actions_dashboard),
            ("☁️ Open AWS CloudFormation", self.open_cloudformation_console),
        ]

        for idx, (label, command) in enumerate(button_specs):
            btn = tk.Button(
                buttons_card,
                text=label,
                command=command,
                font=("Segoe UI", 11, "bold"),
                bg="#0b5fff",
                fg="white",
                padx=14,
                pady=10,
                relief=tk.GROOVE,
                cursor="hand2"
            )
            btn.grid(row=idx // 2, column=idx % 2, sticky="ew", padx=6, pady=6)

        buttons_card.grid_columnconfigure(0, weight=1)
        buttons_card.grid_columnconfigure(1, weight=1)

        next_steps = tk.LabelFrame(
            content,
            text="CI/CD Flow (copy/paste checklist)",
            font=("Segoe UI", 11, "bold"),
            bg="#f5f6f7",
            padx=10,
            pady=10
        )
        next_steps.pack(fill=tk.X, pady=10)

        steps_text = (
            "1. Update CloudFormation templates or Lambda code.\n"
            "2. Run template validation (cfn-lint / cfn-guard).\n"
            "3. Commit + push to main/develop, or dispatch the workflow manually.\n"
            "4. Monitor GitHub Actions → deploy-infra / deploy-lambdas / run-tests.\n"
            "5. Confirm stacks reached CREATE_COMPLETE in eu-central-1 CloudFormation.\n"
            "6. Execute Step Functions test run to validate the end-to-end pipeline."
        )
        tk.Label(
            next_steps,
            text=steps_text,
            font=("Consolas", 11),
            justify=tk.LEFT,
            bg="#f5f6f7"
        ).pack(anchor=tk.W)

        log_frame = tk.LabelFrame(
            content,
            text="Activity Log",
            font=("Segoe UI", 11, "bold"),
            bg="#f5f6f7",
            padx=10,
            pady=10
        )
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=12,
            font=("Consolas", 10),
            bg="#111",
            fg="#7CFC00"
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log("Deployment assistant ready. This tool no longer starts Docker; it helps you run the CI/CD pipeline.")

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------
    def log(self, message: str) -> None:
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)

    def _update_status(self, name: str, status: str, details: str) -> None:
        self.status_tree.item(name, values=(name, status, details))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def validate_prereqs(self) -> None:
        thread = threading.Thread(target=self._validate_prereqs_thread, daemon=True)
        thread.start()

    def _validate_prereqs_thread(self) -> None:
        self.log("Running prerequisite checks...")
        for check in self.prereq_checks:
            result, details = self._run_first_available(check.commands)
            if result:
                self._update_status(check.name, "✅", details)
            else:
                status = "⚠️" if not check.required else "❌"
                detail_msg = details or ("Not found" if check.required else "Optional tool not installed")
                self._update_status(check.name, status, detail_msg)
                if check.required:
                    self.log(f"{check.name} missing. Install it before deploying.")

    def run_template_validation(self) -> None:
        thread = threading.Thread(target=self._run_template_validation_thread, daemon=True)
        thread.start()

    def _run_template_validation_thread(self) -> None:
        script_path = self.base_dir / "scripts" / "validate-cfn.sh"
        if script_path.exists():
            cmd = ["bash", str(script_path)]
            self.log("Executing scripts/validate-cfn.sh ...")
        else:
            templates = sorted(Path(self.base_dir / "cloudformation").glob("*.yaml"))
            if not shutil.which("cfn-lint"):
                self.log("cfn-lint not found. Install it or add scripts/validate-cfn.sh for custom validation.")
                return
            cmd = ["cfn-lint", *[str(t) for t in templates]]
            self.log("Running cfn-lint across cloudformation/*.yaml ...")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.base_dir)
            if result.returncode == 0:
                self.log("Template validation passed.")
            else:
                self.log("Template validation reported issues:")
                self.log(result.stdout or result.stderr)
        except FileNotFoundError as exc:
            self.log(f"Failed to run validation command: {exc}")

    def open_doc(self, relative_path: str) -> None:
        target = (self.base_dir / relative_path).resolve()
        if not target.exists():
            messagebox.showerror("File not found", f"Cannot locate {relative_path}.")
            return
        webbrowser.open(target.as_uri())

    def open_actions_dashboard(self) -> None:
        webbrowser.open(self.repo_actions_url)

    def open_cloudformation_console(self) -> None:
        url = "https://eu-central-1.console.aws.amazon.com/cloudformation/home?region=eu-central-1#/stacks"
        webbrowser.open(url)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _run_first_available(self, commands: list[list[str]]) -> tuple[bool, str]:
        for cmd in commands:
            binary = shutil.which(cmd[0])
            if binary is None:
                continue
            full_cmd = [binary, *cmd[1:]]
            try:
                result = subprocess.run(full_cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    output = result.stdout.strip() or result.stderr.strip()
                    return True, output.splitlines()[0] if output else "OK"
            except Exception as exc:  # pragma: no cover (edge case logging)
                return False, f"error: {exc}"
        return False, "binary not in PATH"

    def _detect_actions_url(self) -> str:
        try:
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                capture_output=True,
                text=True,
                cwd=self.base_dir
            )
            remote = result.stdout.strip()
            if remote:
                if remote.startswith("git@"):
                    remote = remote.replace(":", "/").replace("git@", "https://")
                if remote.endswith(".git"):
                    remote = remote[:-4]
                return f"{remote}/actions"
        except Exception:
            pass
        return "https://github.com/zhadyz/AI_SOC/actions"


def main() -> None:
    root = tk.Tk()
    app = AISOCDeploymentAssistant(root)
    if platform.system() == "Windows":
        try:
            root.iconbitmap(default="")
        except tk.TclError:
            pass
    root.mainloop()


if __name__ == "__main__":
    main()
