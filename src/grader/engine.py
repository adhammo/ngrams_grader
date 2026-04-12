import os
import shutil
import tempfile
import subprocess
import json
from pathlib import Path
from git import Repo, GitCommandError
from google import genai
from google.genai import types

from src.rubric.rubric import LLM_RUBRIC_PROMPT, RUBRIC_STRUCTURE


class GraderEngine:
    def __init__(self, repo_url, api_key=None, log_callback=None):
        self.repo_url = repo_url
        self.api_key = api_key
        self.log_callback = log_callback or (
            lambda msg, level=0: print(f"{'  ' * level}- {msg}")
        )
        self.temp_dir = tempfile.mkdtemp(prefix="grader_")
        self.scores = {
            cat: {crit: 0 for crit in crits} for cat, crits in RUBRIC_STRUCTURE.items()
        }
        self.reasoning = {
            cat: {crit: "" for crit in crits} for cat, crits in RUBRIC_STRUCTURE.items()
        }
        self.ai_detection = None
        self.llm_graded_successfully = False

    def cleanup(self):
        def on_rm_error(func, path, exc_info):
            import stat

            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception:
                pass

        try:
            shutil.rmtree(self.temp_dir, onerror=on_rm_error)
        except Exception as e:
            self.log_callback(f"Failed to cleanup {self.temp_dir}: {e}")

    def log(self, message, level=0):
        self.log_callback(message, level)

    def run_tests(self):
        self.log("Starting Grading Process...", level=0)
        try:
            repo_path = self.clone_repo()
            if repo_path:
                self.setup_execution_environment(repo_path)
                self.evaluate_execution(repo_path)
                self.evaluate_tooling(repo_path)
                self.evaluate_standard_parts(repo_path)
                self.evaluate_code_structure(repo_path)
                if self.api_key:
                    self.evaluate_with_llm(repo_path)
                else:
                    self.log(
                        "No Gemini API key provided. Skipping LLM evaluation for Code Structure, General Coding, and Design Quality.",
                        level=1,
                    )
        except Exception as e:
            self.log(f"An unexpected error occurred during grading: {str(e)}", level=1)
        finally:
            self.cleanup()

        self.log("Grading process completed.", level=0)
        return (
            self.scores,
            self.reasoning,
            self.ai_detection,
            self.llm_graded_successfully,
        )

    def clone_repo(self):
        self.log(f"Cloning repository {self.repo_url} into {self.temp_dir}...", level=1)
        try:
            Repo.clone_from(self.repo_url, self.temp_dir)
            self.log("Repository cloned successfully.", level=2)

            # Award points for a public github repo
            self.scores["Tooling"][
                "Project developed in VS Code and published as a public GitHub repository"
            ] = 2
            return self.temp_dir
        except GitCommandError as e:
            self.log(f"Error cloning repository: {e}", level=2)
            self.reasoning["Tooling"][
                "Project developed in VS Code and published as a public GitHub repository"
            ] = "Failed to clone repository. Is it public?"
            return None

    def setup_execution_environment(self, repo_path):
        self.log("Setting up execution environment from setup folder...", level=1)
        base = Path(repo_path)
        setup_source = Path("setup")
        if setup_source.exists():
            shutil.copytree(setup_source, base, dirs_exist_ok=True)

    def evaluate_tooling(self, repo_path):
        self.log("Evaluating Tooling (Commits, Branches, Anaconda)...", level=1)
        repo = Repo(repo_path)

        # Check anaconda env (Check requirements.txt or environment.yml)
        env_files = ["environment.yml", "requirements.txt"]
        for f in env_files:
            if (Path(repo_path) / f).exists():
                self.scores["Tooling"]["Anaconda environment created and used"] = 3
                break
        else:
            self.reasoning["Tooling"][
                "Anaconda environment created and used"
            ] = "No environment.yml or requirements.txt found."

        # Check commits
        try:
            commits = list(repo.iter_commits("main"))
            commit_count = len(commits)
        except GitCommandError:
            try:
                commits = list(repo.iter_commits("master"))
                commit_count = len(commits)
            except GitCommandError:
                commit_count = 0

        self.log(f"Found {commit_count} commits.", level=2)
        if commit_count >= 10:
            self.scores["Tooling"]["At least 10 commits in the repository"] = 3
        else:
            self.reasoning["Tooling"][
                "At least 10 commits in the repository"
            ] = f"Only {commit_count} commits found out of the required 10."

        # Check branches: git branch -a should have more than just main to imply a merged branch, or we can look at merge commits
        merge_commits = [c for c in commits if len(c.parents) > 1]

        has_multiple_branches = False
        try:
            # check local and remote tracking branches
            all_branches = [b.name for b in repo.branches] + [
                r.name for r in repo.remote().refs
            ]
            unique_branch_names = set([b.split("/")[-1] for b in all_branches])
            has_multiple_branches = (
                len(unique_branch_names) > 2
            )  # e.g. main, HEAD, feature-branch
        except Exception:
            pass

        if len(merge_commits) > 0 or has_multiple_branches:
            self.scores["Tooling"]["At least one branch merged into main"] = 2
        else:
            self.reasoning["Tooling"][
                "At least one branch merged into main"
            ] = "No merge commits found in main branch, and no evidence of multiple branches."

    def evaluate_standard_parts(self, repo_path):
        self.log(
            "Evaluating Standard Parts (README, requirements, .env, .gitignore)...",
            level=1,
        )
        base = Path(repo_path)

        # README.md
        if (base / "README.md").exists() or (base / "readme.md").exists():
            content = (base / "README.md").read_text(errors="ignore").lower()
            if "requirements" in content and "setup" in content and "usage" in content:
                self.scores["Standard Parts"][
                    "Correct and complete README.md with all required sections"
                ] = 5
            else:
                self.scores["Standard Parts"][
                    "Correct and complete README.md with all required sections"
                ] = 3
                self.reasoning["Standard Parts"][
                    "Correct and complete README.md with all required sections"
                ] = "README exists but may lack Requirements, Setup, or Usage sections."
        else:
            self.reasoning["Standard Parts"][
                "Correct and complete README.md with all required sections"
            ] = "README.md not found."

        # requirements.txt
        req_path = base / "requirements.txt"
        if req_path.exists():
            content = req_path.read_text(errors="ignore")
            if "==" in content:
                self.scores["Standard Parts"][
                    "Correct requirements.txt with all libraries pinned"
                ] = 4
            else:
                self.scores["Standard Parts"][
                    "Correct requirements.txt with all libraries pinned"
                ] = 2
                self.reasoning["Standard Parts"][
                    "Correct requirements.txt with all libraries pinned"
                ] = "Libraries are not explicitly pinned using ==."
        else:
            self.reasoning["Standard Parts"][
                "Correct requirements.txt with all libraries pinned"
            ] = "requirements.txt not found."

        # config/.env
        env_path = base / "config" / ".env"
        if env_path.exists():
            content = env_path.read_text(errors="ignore")
            if "TRAIN_RAW_DIR" in content and "MODEL" in content and "TOP_K" in content:
                self.scores["Standard Parts"][
                    "Correct config/.env with all required variables"
                ] = 4
            else:
                self.scores["Standard Parts"][
                    "Correct config/.env with all required variables"
                ] = 2
                self.reasoning["Standard Parts"][
                    "Correct config/.env with all required variables"
                ] = "Missing some required variables like TRAIN_RAW_DIR or TOP_K."
        else:
            self.reasoning["Standard Parts"][
                "Correct config/.env with all required variables"
            ] = "config/.env not found."

        # .gitignore
        gitig_path = base / ".gitignore"
        if gitig_path.exists():
            content = gitig_path.read_text(errors="ignore")
            if "data/" in content and "*.json" in content and "__pycache__" in content:
                self.scores["Standard Parts"][
                    "Correct .gitignore excluding data/, *.json, and __pycache__/"
                ] = 2
            else:
                self.reasoning["Standard Parts"][
                    "Correct .gitignore excluding data/, *.json, and __pycache__/"
                ] = "Missing data/, *.json, or __pycache__ from .gitignore."
        else:
            self.reasoning["Standard Parts"][
                "Correct .gitignore excluding data/, *.json, and __pycache__/"
            ] = ".gitignore not found."

    def evaluate_code_structure(self, repo_path):
        self.log("Evaluating Folder Structure...", level=1)
        base = Path(repo_path)
        required_dirs = [
            "config",
            "data",
            "src",
            "src/data_prep",
            "src/model",
            "src/inference",
            "src/ui",
            "src/evaluation",
        ]
        missing_dirs = []
        for rd in required_dirs:
            if rd.startswith("src/ui") or rd.startswith("src/evaluation"):
                continue  # Optional modules
            if not (base / rd).is_dir():
                missing_dirs.append(rd)

        if not missing_dirs:
            self.scores["Code Structure"][
                "Repository follows the specified folder and file structure exactly"
            ] = 10
        else:
            self.scores["Code Structure"][
                "Repository follows the specified folder and file structure exactly"
            ] = 5
            self.reasoning["Code Structure"][
                "Repository follows the specified folder and file structure exactly"
            ] = f"Missing directories: {', '.join(missing_dirs)}"

        # Manual check for Unit Tests (Extra Credit)
        test_dirs = ["test", "tests", "src/test", "src/tests"]
        found_tests = False
        for td in test_dirs:
            p = base / td
            if p.is_dir() and any(p.glob("*.py")):
                found_tests = True
                self.scores["Extra Credit"][
                    "Unit Tests — per-method tests, all passing"
                ] = 5
                self.reasoning["Extra Credit"][
                    "Unit Tests — per-method tests, all passing"
                ] = f"Unit tests found in /{td} directory."
                break

        if not found_tests:
            self.reasoning["Extra Credit"][
                "Unit Tests — per-method tests, all passing"
            ] = "No /test or /tests directory found containing .py files."

    def evaluate_with_llm(self, repo_path):
        self.log("Extracting source code for LLM evaluation...", level=1)
        base = Path(repo_path)
        code_content = ""

        main_file = base / "main.py"
        if main_file.exists():
            code_content += (
                f"\n--- main.py ---\n{main_file.read_text(errors='ignore')}\n"
            )

        src_dir = base / "src"
        if src_dir.exists():
            for py_file in src_dir.rglob("*.py"):
                code_content += f"\n--- {py_file.relative_to(base)} ---\n{py_file.read_text(errors='ignore')}\n"

        if not code_content:
            self.log("No python code found to evaluate.", level=2)
            return

        self.log("Invoking Gemini LLM...", level=2)
        try:
            client = genai.Client(api_key=self.api_key)
            prompt = LLM_RUBRIC_PROMPT + f"\n\nStudent Source Code:\n{code_content}"
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite-preview",
                # model="gemini-3-flash-preview",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )

            evaluation = json.loads(response.text)
            self.log("LLM Evaluation parsed successfully.", level=2)

            # Apply LLM evaluation to scores
            cats_mapping = [
                "Code Structure",
                "General Coding",
                "Design Quality",
                "Extra Credit",
            ]
            for cat in cats_mapping:
                if cat in evaluation:
                    for crit, data in evaluation[cat].items():
                        if crit in self.scores[cat]:
                            self.scores[cat][crit] = data.get("score", 0)
                            self.reasoning[cat][crit] = data.get("reasoning", "")

            if "AI Detection" in evaluation:
                self.ai_detection = evaluation["AI Detection"]

            self.llm_graded_successfully = True

        except Exception as e:
            self.log(f"LLM Evaluation failed: {e}", level=2)

    def evaluate_execution(self, repo_path):
        self.log("Executing student code (python main.py --step all)...", level=1)
        base = Path(repo_path)
        main_py = base / "main.py"
        if not main_py.exists():
            self.reasoning["Project"][
                "runs end-to-end without errors (python main.py --step all)"
            ] = "main.py not found at repository root."
            return

        try:
            import sys
            import os

            # Create a virtual environment specifically for this project
            self.log("Creating isolated virtual environment...", level=2)
            venv_dir = base / "venv"
            venv_result = subprocess.run(
                [sys.executable, "-m", "venv", str(venv_dir)],
                cwd=str(base),
                capture_output=True,
                text=True,
            )
            if venv_result.returncode != 0:
                self.log(
                    f"Failed to create virtual environment (exit code {venv_result.returncode}).",
                    level=2,
                )
                if venv_result.stderr:
                    self.log(f"STDERR: {venv_result.stderr.strip()}", level=2)

                self.reasoning["Project"][
                    "runs end-to-end without errors (python main.py --step all)"
                ] = f"Failed to create venv: {venv_result.stderr}"
                self.scores["Project"][
                    "runs end-to-end without errors (python main.py --step all)"
                ] = 0
                return
            self.log("Virtual environment created successfully.", level=2)

            # Determine venv python executable
            if os.name == "nt":
                venv_python = str(venv_dir / "Scripts" / "python.exe")
            else:
                venv_python = str(venv_dir / "bin" / "python")

            # Install dependencies if requirements.txt exists
            req_file = base / "requirements.txt"
            if req_file.exists():
                self.log("Installing dependencies into virtual environment...", level=2)
                process = subprocess.Popen(
                    [
                        venv_python,
                        "-m",
                        "pip",
                        "install",
                        "-r",
                        "requirements.txt",
                    ],
                    cwd=str(base),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                )

                if process.stdout:
                    for line in process.stdout:
                        clean_line = line.strip()
                        if clean_line:
                            self.log(clean_line, level=3)

                process.wait(timeout=60)

                if process.returncode != 0:
                    self.log(
                        f"Failed to install dependencies (exit code {process.returncode}).",
                        level=2,
                    )
                    self.reasoning["Project"][
                        "runs end-to-end without errors (python main.py --step all)"
                    ] = "Failed to install requirements.txt. Check log for details."
                    self.scores["Project"][
                        "runs end-to-end without errors (python main.py --step all)"
                    ] = 0
                    return
                self.log("Dependencies installed successfully.", level=2)

            # Use subprocess to run `python main.py --step all`
            test_sentence = "To Sherlock Holmes she is always the"
            self.log(
                f"Running main.py with 60s timeout and test input: '{test_sentence}' and 'quit'",
                level=2,
            )

            try:
                result = subprocess.run(
                    [venv_python, "main.py", "--step", "all"],
                    cwd=str(base),
                    capture_output=True,
                    text=True,
                    input=f"{test_sentence}\nquit\n",
                    timeout=60,
                )
                if result.returncode == 0:
                    self.scores["Project"][
                        "runs end-to-end without errors (python main.py --step all)"
                    ] = 20
                    self.log("Subprocess execution completed successfully.", level=2)
                    self.reasoning["Project"][
                        "runs end-to-end without errors (python main.py --step all)"
                    ] = f"Execution successful. Output:\n{result.stdout.strip()}"
                else:
                    self.log(
                        f"Execution returned non-zero code {result.returncode}.",
                        level=2,
                    )
                    self.reasoning["Project"][
                        "runs end-to-end without errors (python main.py --step all)"
                    ] = f"Runtime error (code {result.returncode}): {result.stderr}"
                    self.scores["Project"][
                        "runs end-to-end without errors (python main.py --step all)"
                    ] = 0

            except subprocess.TimeoutExpired as e:
                # Capture partial output if available
                stdout_val = (
                    e.stdout.decode(errors="ignore")
                    if isinstance(e.stdout, bytes)
                    else (e.stdout or "")
                )
                output_is_blank = not stdout_val.strip()

                if output_is_blank:
                    # Timeout with blank output: Reduce score by 5 (20 -> 15)
                    self.scores["Project"][
                        "runs end-to-end without errors (python main.py --step all)"
                    ] = 15
                    self.reasoning["Project"][
                        "runs end-to-end without errors (python main.py --step all)"
                    ] = "Execution timed out (60.0s) and returned no output."
                    self.log(
                        "Execution timed out with blank output. Score reduced by 5.",
                        level=2,
                    )
                else:
                    # Timeout but has some output: Slight reduction
                    self.scores["Project"][
                        "runs end-to-end without errors (python main.py --step all)"
                    ] = 18
                    self.reasoning["Project"][
                        "runs end-to-end without errors (python main.py --step all)"
                    ] = f"Execution timed out (60.0s) but produced partial output:\n{stdout_val}"
                    self.log("Execution timed out with partial output.", level=2)

        except Exception as e:
            self.log(f"An error occurred during execution setup or run: {e}", level=1)
            self.reasoning["Project"][
                "runs end-to-end without errors (python main.py --step all)"
            ] = f"Evaluation failure: {str(e)}"
            self.scores["Project"][
                "runs end-to-end without errors (python main.py --step all)"
            ] = 0
