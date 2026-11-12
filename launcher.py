from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import queue
import shutil
import stat
import subprocess
import sys
import threading
import zipfile

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


APP_TITLE = "Excitebike Recompiled Builder"
APP_ID = "ExcitebikeRecomp"


def user_data_directory() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_ID
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_ID
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_ID


def bundled_payload() -> Path | None:
    frozen_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    candidates = [
        frozen_root / "payload" / "payload.zip",
        frozen_root / "payload.zip",
        Path(__file__).resolve().parent / "payload.zip",
    ]
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def safe_extract_payload(archive_path: Path, destination: Path) -> None:
    temporary = destination.parent / (destination.name + ".extracting")
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir(parents=True, exist_ok=True)
    root = temporary.resolve()

    with zipfile.ZipFile(archive_path) as archive:
        for item in archive.infolist():
            relative = PurePosixPath(item.filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise RuntimeError("The bundled build resources contain an unsafe path.")
            target = (temporary / Path(*relative.parts)).resolve()
            if root not in target.parents and target != root:
                raise RuntimeError("The bundled build resources contain an unsafe path.")
        archive.extractall(temporary)

    extracted_project = temporary / "project"
    if not (extracted_project / "CMakeLists.txt").is_file():
        raise RuntimeError("The bundled build resources are incomplete (CMakeLists.txt is missing).")

    if destination.exists():
        shutil.rmtree(destination)
    extracted_project.rename(destination)
    shutil.rmtree(temporary, ignore_errors=True)


def find_tool(search_root: Path, names: tuple[str, ...]) -> Path:
    # The macOS CMake wheel contains a real, relocatable CLI binary here.
    # Prefer it over the generated Python console-script wrapper in bin/.
    if "cmake" in names:
        wheel_binary = search_root / "cmake" / "data" / "bin" / "cmake"
        if wheel_binary.is_file():
            return wheel_binary

    for name in names:
        matches = sorted(search_root.rglob(name))
        for match in matches:
            if match.is_file() and match.parent.name.lower() == "bin":
                return match
        for match in matches:
            if match.is_file():
                return match
    raise FileNotFoundError(
        "A bundled build tool is missing: " + ", ".join(names) +
        ". Re-download the latest platform launcher."
    )


def clear_macos_quarantine(paths: tuple[Path, ...]) -> None:
    """Remove Gatekeeper quarantine only from bundled, checksum-verified build tools."""
    if sys.platform != "darwin":
        return
    xattr = Path("/usr/bin/xattr")
    if not xattr.is_file():
        return
    for path in paths:
        if path.exists():
            subprocess.run(
                [str(xattr), "-dr", "com.apple.quarantine", str(path)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def game_executable(build_root: Path) -> Path:
    candidates = (
        (build_root / "Release" / "ExcitebikeRecomp.exe", build_root / "ExcitebikeRecomp.exe")
        if os.name == "nt"
        else (build_root / "ExcitebikeRecomp",)
    )
    return next((candidate for candidate in candidates if candidate.is_file()), candidates[0])


class ExcitebikeBuilder:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("790x570")
        self.root.minsize(680, 470)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.running = False
        self.rom_path = tk.StringVar()
        self.status = tk.StringVar(value="Choose your own Excitebike .nes ROM to build the game locally.")

        self._build_interface()
        self.root.after(100, self._drain_events)

    def _build_interface(self) -> None:
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill=tk.BOTH, expand=True)

        heading = ttk.Label(outer, text="EXCITEBIKE RECOMPILED", font=("TkDefaultFont", 19, "bold"))
        heading.pack(anchor=tk.W)
        subtitle = ttk.Label(
            outer,
            text="Build a native version using your own ROM. Successful builds are reused on later launches when the ROM and bundled project version match.",
            wraplength=740,
        )
        subtitle.pack(anchor=tk.W, pady=(3, 14))

        rom_frame = ttk.LabelFrame(outer, text="Your ROM", padding=12)
        rom_frame.pack(fill=tk.X, pady=(0, 12))
        rom_row = ttk.Frame(rom_frame)
        rom_row.pack(fill=tk.X)
        ttk.Entry(rom_row, textvariable=self.rom_path).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.browse_button = ttk.Button(rom_row, text="Browse…", command=self._choose_rom)
        self.browse_button.pack(side=tk.LEFT, padx=(8, 0))

        self.build_button = ttk.Button(
            rom_frame, text="Build Excitebike & Play", command=self._start_build
        )
        self.build_button.pack(anchor=tk.W, pady=(10, 0))

        requirements = (
            "Platform compiler requirement: macOS needs Xcode Command Line Tools; "
            "Windows needs Visual Studio 2022 with Desktop development with C++; "
            "Linux needs a C/C++ compiler, Make and the normal desktop graphics/audio development libraries. "
            "CMake, the managed Python runtime, SDL2 source and recompilation sources are bundled."
        )
        note = ttk.Label(outer, text=requirements, wraplength=740, justify=tk.LEFT)
        note.pack(fill=tk.X, pady=(0, 12))

        output_frame = ttk.LabelFrame(outer, text="Build output", padding=8)
        output_frame.pack(fill=tk.BOTH, expand=True)
        self.output = tk.Text(output_frame, height=15, wrap=tk.WORD, state=tk.DISABLED)
        scrollbar = ttk.Scrollbar(output_frame, orient=tk.VERTICAL, command=self.output.yview)
        self.output.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        footer = ttk.Frame(outer)
        footer.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(footer, textvariable=self.status, wraplength=620).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        self.close_button = ttk.Button(footer, text="Close", command=self.root.destroy)
        self.close_button.pack(side=tk.RIGHT)

        self._append(
            "This download is a local-build launcher, not a prebuilt copy of the game.\n"
            "No ROM or ROM-derived game code is included. Your ROM and generated build stay on this computer."
        )

    def _append(self, text: str) -> None:
        self.output.configure(state=tk.NORMAL)
        self.output.insert(tk.END, text)
        if not text.endswith(chr(10)):
            self.output.insert(tk.END, chr(10))
        self.output.see(tk.END)
        self.output.configure(state=tk.DISABLED)

    def _choose_rom(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select your Excitebike ROM",
            filetypes=[("NES ROM files", "*.nes"), ("All files", "*.*")],
        )
        if selected:
            self.rom_path.set(selected)

    def _start_build(self) -> None:
        if self.running:
            return
        rom = Path(self.rom_path.get()).expanduser()
        if not rom.is_file():
            messagebox.showerror(APP_TITLE, "Select an existing .nes ROM first.")
            return
        try:
            with rom.open("rb") as source:
                header = source.read(4)
        except OSError as error:
            messagebox.showerror(APP_TITLE, "Could not read the selected ROM: " + str(error))
            return
        if header != b"NES\x1a":
            messagebox.showerror(
                APP_TITLE,
                "The selected file does not have a valid iNES header. Select a compatible .nes ROM.",
            )
            return

        self.running = True
        self.build_button.configure(state=tk.DISABLED)
        self.browse_button.configure(state=tk.DISABLED)
        self.status.set("Preparing bundled sources and tools…")
        self._append("")
        self._append("Selected ROM: " + str(rom))
        threading.Thread(target=self._build_worker, args=(rom,), daemon=True).start()

    def _emit(self, kind: str, value: object) -> None:
        self.events.put((kind, value))

    def _run_logged(self, command: list[str], environment: dict[str, str], cwd: Path) -> None:
        self._emit("log", "$ " + subprocess.list2cmdline(command))
        process = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            self._emit("log", line.rstrip())
        result = process.wait()
        if result != 0:
            raise RuntimeError(f"Command failed with exit code {result}: {command[0]}")

    def _build_worker(self, rom: Path) -> None:
        try:
            archive = bundled_payload()
            if archive is None:
                raise RuntimeError("The platform package is missing its embedded build resources.")
            data_root = user_data_directory()
            data_root.mkdir(parents=True, exist_ok=True)
            project_root = data_root / "project"
            build_root = data_root / "build"
            digest = sha256_file(archive)
            rom_digest = sha256_file(rom)
            marker = data_root / "payload-sha256.txt"
            old_digest = marker.read_text(encoding="utf-8").strip() if marker.exists() else ""
            if old_digest != digest or not (project_root / "CMakeLists.txt").is_file():
                self._emit("log", "Extracting the bundled compiler, Python runtime and pinned source dependencies…")
                safe_extract_payload(archive, project_root)
                marker.write_text(digest, encoding="utf-8")

            state_path = data_root / "build-state.json"
            try:
                build_state = json.loads(state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                build_state = {}

            game = game_executable(build_root)
            cache_matches = (
                build_state.get("payload_sha256") == digest
                and build_state.get("rom_sha256") == rom_digest
                and game.is_file()
            )
            if cache_matches:
                self._emit(
                    "log",
                    "A matching native build already exists. Skipping CMake configuration and compilation.",
                )
                self._emit("log", "Starting the existing Excitebike build…")
                subprocess.Popen([str(game), str(rom.resolve())], cwd=str(build_root))
                self._emit("done", "reused")
                return

            self._emit(
                "log",
                "No matching completed build was found. Preparing tools and compiling this ROM…",
            )
            tools_root = project_root / ".tools"
            if sys.platform == "darwin":
                self._emit("log", "Clearing Gatekeeper quarantine only from the bundled, checksum-verified developer tools…")
                clear_macos_quarantine((tools_root / "cmake", tools_root / "python", tools_root / "uv"))
            cmake = find_tool(tools_root / "cmake", ("cmake.exe", "cmake"))
            python = find_tool(tools_root / "python", ("python.exe", "python3.12", "python3", "python"))
            if os.name != "nt":
                for executable in (cmake, python):
                    os.chmod(executable, executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

            environment = os.environ.copy()
            tool_paths = [str(cmake.parent), str(python.parent)]
            environment["PATH"] = os.pathsep.join(tool_paths + [environment.get("PATH", "")])
            build_root.mkdir(parents=True, exist_ok=True)

            configure = [
                str(cmake), "-S", str(project_root), "-B", str(build_root),
                "-DCMAKE_BUILD_TYPE=Release",
                "-DNESRECOMP_ROM=" + str(rom.resolve()),
                "-DPython3_EXECUTABLE=" + str(python),
            ]
            if os.name == "nt":
                configure.extend(["-G", "Visual Studio 17 2022", "-A", "x64"])

            self._emit("log", "Configuring the native game build…")
            self._run_logged(configure, environment, project_root)

            jobs = str(max(2, min(4, os.cpu_count() or 4)))
            self._emit("log", "Compiling SDL2, the NES runtime and the generated game code…")
            self._run_logged(
                [str(cmake), "--build", str(build_root), "--config", "Release", "--parallel", jobs],
                environment,
                project_root,
            )

            game = game_executable(build_root)
            if not game.is_file():
                raise RuntimeError("Build completed but the ExcitebikeRecomp executable was not found.")

            new_state = {
                "payload_sha256": digest,
                "rom_sha256": rom_digest,
            }
            temporary_state = state_path.with_suffix(".json.tmp")
            temporary_state.write_text(json.dumps(new_state, indent=2) + "\n", encoding="utf-8")
            temporary_state.replace(state_path)

            self._emit("log", "Build succeeded. Starting Excitebike…")
            subprocess.Popen([str(game), str(rom.resolve())], cwd=str(build_root), env=environment)
            self._emit("done", "success")
        except Exception as error:
            self._emit("log", "ERROR: " + str(error))
            self._emit("done", str(error))

    def _drain_events(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self._append(str(value))
                elif kind == "done":
                    self.running = False
                    self.build_button.configure(state=tk.NORMAL)
                    self.browse_button.configure(state=tk.NORMAL)
                    if value == "success":
                        self.status.set("Build complete. Excitebike has been launched.")
                        self._append("Game launched. Your build and saves remain in the application data folder.")
                    elif value == "reused":
                        self.status.set("Existing build launched. No rebuild was needed.")
                        self._append("The saved native game was reused. Your ROM, build and saves remain on this computer.")
                    else:
                        self.status.set("Build failed. Details are shown above.")
                        self._append("The launcher has not deleted your ROM or previous build.")
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)


def main() -> int:
    root = tk.Tk()
    try:
        ExcitebikeBuilder(root)
    except Exception as error:
        messagebox.showerror(APP_TITLE, str(error))
        return 1
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
