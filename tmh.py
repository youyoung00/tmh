#!/usr/bin/env python3
"""
tmh.py - Task Master Helper (Python version)
완전히 tmh.sh와 동일한 동작을 수행하는 Python 구현
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


class TMH:
    def __init__(self):
        # Config from environment variables
        self.tm_bin = os.environ.get('TM_BIN', 'tm')
        if not self._command_exists(self.tm_bin):
            tm_alt = self._command_exists('task-master')
            if tm_alt:
                self.tm_bin = 'task-master'
            else:
                print("task-master CLI not found. Install: npm i -g task-master-ai@latest")
                sys.exit(1)
        
        self.tag = self._get_current_tag()
        self.tm_file = os.environ.get('TM_FILE', '.taskmaster/tasks/tasks.json')
        self.prompt_dir = os.environ.get('PROMPT_DIR', './prompts')
        self.worktree_base = os.environ.get('WORKTREE_BASE', '../ws')
        self.branch_prefix = os.environ.get('BRANCH_PREFIX', 'ws/')
        self.project_root = os.getcwd()  # Current working directory as project root

    def _get_current_tag(self) -> str:
        """Get current active tag from Task Master state or environment"""
        # 1. Check environment variable first
        if 'TAG' in os.environ:
            return os.environ['TAG']
        
        # 2. Try to read from .taskmaster/state.json
        try:
            state_file = '.taskmaster/state.json'
            if os.path.exists(state_file):
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    if 'currentTag' in state:
                        return state['currentTag']
        except Exception:
            pass
        
        # 3. Try to detect from tasks.json structure
        try:
            if os.path.exists('.taskmaster/tasks/tasks.json'):
                with open('.taskmaster/tasks/tasks.json', 'r', encoding='utf-8') as f:
                    tasks_data = json.load(f)
                    # If it has a 'tags' object, use the first available tag
                    if 'tags' in tasks_data:
                        available_tags = list(tasks_data['tags'].keys())
                        if available_tags:
                            return available_tags[0]
                    # Otherwise, look for direct tag keys (excluding 'metadata')
                    else:
                        for key in tasks_data.keys():
                            if key != 'metadata' and isinstance(tasks_data[key], dict) and 'tasks' in tasks_data[key]:
                                return key
        except Exception:
            pass
        
        # 4. Default fallback
        return 'master'

    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        try:
            subprocess.run(['which', command], capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def _load_tasks(self) -> Dict[str, Any]:
        """Load tasks from JSON file"""
        try:
            with open(self.tm_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Tasks file not found: {self.tm_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in tasks file: {e}")
            sys.exit(1)

    def _get_all_tasks(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get all tasks including subtasks (equivalent to jq allTasks function)"""
        tag_data = data.get(self.tag, {})
        parent_tasks = tag_data.get('tasks', [])
        
        all_tasks = []
        for task in parent_tasks:
            all_tasks.append(task)
            subtasks = task.get('subtasks', [])
            all_tasks.extend(subtasks)
        
        return all_tasks

    def _get_status_map(self, all_tasks: List[Dict[str, Any]]) -> Dict[str, str]:
        """Create a mapping of task ID to status"""
        return {str(task['id']): task['status'] for task in all_tasks}

    def jq_ready_ids(self) -> List[str]:
        """Get IDs of tasks that are ready (pending with satisfied dependencies)"""
        data = self._load_tasks()
        all_tasks = self._get_all_tasks(data)
        status_map = self._get_status_map(all_tasks)
        
        ready_ids = []
        for task in all_tasks:
            if task['status'] != 'pending':
                continue
            
            dependencies = task.get('dependencies', [])
            if not dependencies:
                ready_ids.append(str(task['id']))
                continue
            
            # Check if all dependencies are done or in-progress
            deps_satisfied = all(
                status_map.get(str(dep_id), '') in ['done', 'in-progress']
                for dep_id in dependencies
            )
            
            if deps_satisfied:
                ready_ids.append(str(task['id']))
        
        return sorted(ready_ids, key=lambda x: float(x))

    def jq_blocked(self) -> List[Tuple[str, str]]:
        """Get blocked tasks with their blocking dependencies"""
        data = self._load_tasks()
        all_tasks = self._get_all_tasks(data)
        status_map = self._get_status_map(all_tasks)
        
        blocked = []
        for task in all_tasks:
            if task['status'] != 'pending':
                continue
            
            dependencies = task.get('dependencies', [])
            if not dependencies:
                continue
            
            # Check if any dependencies are not done/in-progress
            unsatisfied_deps = [
                str(dep_id) for dep_id in dependencies
                if status_map.get(str(dep_id), '') not in ['done', 'in-progress']
            ]
            
            if unsatisfied_deps:
                blocked.append((str(task['id']), ','.join(unsatisfied_deps)))
        
        return blocked

    def get_title(self, task_id: str) -> str:
        """Get task title by ID"""
        data = self._load_tasks()
        all_tasks = self._get_all_tasks(data)
        
        for task in all_tasks:
            if str(task['id']) == task_id:
                return task['title']
        
        return ""

    def prompt_one(self, task_id: str) -> str:
        """Generate prompt text for a specific task"""
        data = self._load_tasks()
        all_tasks = self._get_all_tasks(data)
        
        for task in all_tasks:
            if str(task['id']) == task_id:
                dependencies = task.get('dependencies', [])
                dep_str = ', '.join(map(str, dependencies))
                
                prompt = f"""You are an implementation agent for Task #{task['id']}
Title: {task['title']}
Status: {task['status']}  Priority: {task.get('priority', 'medium')}
Dependencies: {dep_str}
Description:
{task.get('description', '(none)')}

Implementation Details:
{task.get('details', '(none)')}

Test Strategy:
{task.get('testStrategy', '(none)')}

Deliverables:
- [ ] Code commits / PRs
- [ ] README/Notes
- [ ] Tests per strategy

Instructions:
1. Work contract-first. Do not change external contracts unless stated.
2. If blocked by deps, stub/mocks allowed—note the assumptions.
3. Output incremental patches or code blocks.
4. Ask for missing info explicitly.
5. Keep messages short; show only the diff/command snippets.
"""
                return prompt
        
        return ""

    def slugify(self, text: str) -> str:
        """Convert text to URL-friendly slug"""
        # Replace newlines and carriage returns with spaces
        s = text.replace('\r', ' ').replace('\n', ' ')
        # Convert to lowercase
        s = s.lower()
        # Replace non-alphanumeric characters with hyphens
        s = re.sub(r'[^a-z0-9]+', '-', s)
        # Remove leading and trailing hyphens
        s = s.strip('-')
        
        return s if s else 'task'

    def prompt_all_ready(self, out_dir: Optional[str] = None) -> None:
        """Generate prompt files for all ready tasks"""
        if out_dir is None:
            out_dir = self.prompt_dir
        
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        
        ready_ids = self.jq_ready_ids()
        if not ready_ids:
            print("No ready tasks.")
            return
        
        for task_id in ready_ids:
            prompt_text = self.prompt_one(task_id)
            prompt_file = Path(out_dir) / f"{task_id}.txt"
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(prompt_text)
            print(f"Wrote {prompt_file}")

    def _is_git_repo(self) -> bool:
        """Check if current directory is a git repository"""
        try:
            subprocess.run(['git', 'rev-parse', '--is-inside-work-tree'], 
                          capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def _has_commits(self) -> bool:
        """Check if git repository has at least one commit"""
        try:
            subprocess.run(['git', 'rev-parse', 'HEAD'], 
                          capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def _branch_exists(self, branch_name: str) -> bool:
        """Check if a git branch exists"""
        try:
            subprocess.run(['git', 'show-ref', '--verify', '--quiet', f'refs/heads/{branch_name}'], 
                          capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def _open_vscode_with_terminal(self, path: str) -> None:
        """Open VS Code with terminal automatically"""
        # First open VS Code
        subprocess.run(['code', '-n', path])
        
        # Use AppleScript to open terminal (macOS)
        if sys.platform == 'darwin':
            applescript = '''
            tell application "Visual Studio Code"
                activate
                delay 1
                tell application "System Events"
                    keystroke "`" using {command down}
                end tell
            end tell
            '''
            try:
                subprocess.run(['osascript', '-e', applescript], 
                             capture_output=True, timeout=3)
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                # Fallback to showing instructions
                pass
        
        # For other platforms or if AppleScript fails, we'll show instructions

    def _open_vscode_with_terminal_and_claude(self, path: str, task_id: str) -> None:
        """Open VS Code with terminal and automatically run Claude CLI with --print option for non-interactive execution"""
        prompt_file = f"{self.project_root}/prompts/{task_id}.txt"
        worktree_path = path
        
        try:
            # Open VS Code in new window
            subprocess.run(['code', '-n', path], check=True)
            print(f"✅ VS Code opened for task {task_id}")
            
            # Wait a moment for VS Code to fully load
            time.sleep(3)
            
            # Use AppleScript to open terminal and run Claude CLI with --print option
            applescript = f'''
            tell application "Visual Studio Code"
                activate
                delay 2
                tell application "System Events"
                    -- Open terminal
                    keystroke "`" using {{command down}}
                    delay 1
                    -- Change to worktree directory and run Claude CLI with --print option in one command
                    keystroke "cd {worktree_path} && claude --print --dangerously-skip-permissions < {prompt_file}"
                    delay 0.5
                    -- Press Enter to execute
                    keystroke return
                end tell
            end tell
            '''
            
            subprocess.run(['osascript', '-e', applescript], check=True)
            print(f"✅ Claude CLI started with --print option for task {task_id}")
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to open VS Code or run Claude CLI for task {task_id}: {e}")
            print(f"💡 Manual commands:")
            print(f"   cd {worktree_path}")
            print(f"   claude --print --dangerously-skip-permissions < {prompt_file}")
        except Exception as e:
            print(f"❌ Unexpected error for task {task_id}: {e}")
            print(f"💡 Manual commands:")
            print(f"   cd {worktree_path}")
            print(f"   claude --print --dangerously-skip-permissions < {prompt_file}")

    def worktree_ready(self) -> None:
        """Create git worktrees for all ready tasks"""
        if not self._is_git_repo():
            print("Not a git repo.")
            sys.exit(1)
        
        if not self._has_commits():
            print("Need at least one commit for worktrees.")
            sys.exit(1)
        
        Path(self.worktree_base).mkdir(parents=True, exist_ok=True)
        
        ready_ids = self.jq_ready_ids()
        if not ready_ids:
            print("No ready tasks.")
            return
        
        print(f"The following tasks are ready for worktree creation: {' '.join(ready_ids)}")
        try:
            response = input(f"Proceed with creating worktrees for {len(ready_ids)} tasks? (y/N) ").strip().lower()
            if response not in ['y', 'yes']:
                print("Worktree creation cancelled.")
                return
        except KeyboardInterrupt:
            print("\nWorktree creation cancelled.")
            return
        
        worktree_paths = []
        for task_id in ready_ids:
            title = self.get_title(task_id)
            slug = self.slugify(title)
            branch = f"{self.branch_prefix}{task_id}-{slug}"
            path = f"{self.worktree_base}/{task_id}-{slug}"
            
            if self._branch_exists(branch):
                print(f"Branch {branch} already exists. Skipping.")
                worktree_paths.append(path)
            else:
                try:
                    subprocess.run(['git', 'worktree', 'add', '-b', branch, path, 'HEAD'], 
                                  check=True)
                    print(f"Created worktree {path} (branch {branch})")
                    worktree_paths.append(path)
                except subprocess.CalledProcessError:
                    print(f"WARNING: Failed to create worktree for task {task_id}. Continuing...")
        
        # Open VS Code windows with terminal
        if worktree_paths:
            if self._command_exists('code'):
                print("Opening worktree directories in separate VS Code windows with terminal...")
                for path in worktree_paths:
                    self._open_vscode_with_terminal(path)
                    time.sleep(1)  # Small delay between windows
                
                print("\n💡 만약 터미널이 자동으로 열리지 않았다면:")
                print("  • 키보드 단축키: Ctrl+` (백틱) 또는 Cmd+` (Mac)")
                print("  • 메뉴: View > Terminal")
            else:
                print("VS Code 'code' command not found. Please open directories manually:")
                for path in worktree_paths:
                    print(f"  - {path}")

    def start_ready(self) -> None:
        """Set all ready tasks to in-progress status"""
        ready_ids = self.jq_ready_ids()
        if not ready_ids:
            print("No ready tasks.")
            return
        
        print(f"The following tasks are ready to start: {' '.join(ready_ids)}")
        try:
            response = input(f"Proceed with starting {len(ready_ids)} tasks? (y/N) ").strip().lower()
            if response not in ['y', 'yes']:
                print("Task start cancelled.")
                return
        except KeyboardInterrupt:
            print("\nTask start cancelled.")
            return
        
        print(f"Starting: {' '.join(ready_ids)}")
        for task_id in ready_ids:
            try:
                subprocess.run([self.tm_bin, 'set-status', '--tag', self.tag, 
                               '--id', task_id, '--status', 'in-progress'], check=True)
            except subprocess.CalledProcessError:
                print(f"WARNING: Failed to set status for task {task_id}. Continuing...")

    def kickoff_ready(self) -> None:
        """Complete kickoff: prompts + worktrees + status change"""
        if not self._is_git_repo():
            print("Not a git repo.")
            sys.exit(1)
        
        if not self._has_commits():
            print("Need at least one commit for worktrees.")
            sys.exit(1)
        
        ready_ids = self.jq_ready_ids()
        if not ready_ids:
            print("No ready tasks.")
            return
        
        print(f"The following tasks are ready for kickoff: {' '.join(ready_ids)}")
        try:
            response = input(f"Proceed with kickoff for {len(ready_ids)} tasks? (y/N) ").strip().lower()
            if response not in ['y', 'yes']:
                print("Kickoff cancelled.")
                return
        except KeyboardInterrupt:
            print("\nKickoff cancelled.")
            return
        
        print(f"Ready IDs: {' '.join(ready_ids)}")
        
        # Generate prompts
        Path(self.prompt_dir).mkdir(parents=True, exist_ok=True)
        for task_id in ready_ids:
            prompt_text = self.prompt_one(task_id)
            prompt_file = Path(self.prompt_dir) / f"{task_id}.txt"
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(prompt_text)
            print(f"Wrote {prompt_file}")
        
        # Create worktrees
        Path(self.worktree_base).mkdir(parents=True, exist_ok=True)
        worktree_paths = []
        for task_id in ready_ids:
            title = self.get_title(task_id)
            slug = self.slugify(title)
            branch = f"{self.branch_prefix}{task_id}-{slug}"
            path = f"{self.worktree_base}/{task_id}-{slug}"
            
            if self._branch_exists(branch):
                print(f"Branch {branch} already exists. Skipping.")
                worktree_paths.append(path)
            else:
                try:
                    subprocess.run(['git', 'worktree', 'add', '-b', branch, path, 'HEAD'], 
                                  check=True)
                    print(f"Created worktree {path} (branch {branch})")
                    worktree_paths.append(path)
                except subprocess.CalledProcessError:
                    print(f"WARNING: Failed to create worktree for task {task_id}. Continuing...")
        
        # Set status to in-progress
        for task_id in ready_ids:
            try:
                subprocess.run([self.tm_bin, 'set-status', '--tag', self.tag, 
                               '--id', task_id, '--status', 'in-progress'], check=True)
            except subprocess.CalledProcessError:
                print(f"WARNING: Failed to set status for task {task_id}. Continuing...")
        
        # Open VS Code windows with terminal
        if worktree_paths:
            if self._command_exists('code'):
                print("Opening worktree directories in separate VS Code windows with terminal...")
                for path in worktree_paths:
                    self._open_vscode_with_terminal(path)
                    time.sleep(1)  # Small delay between windows
                
                print("\n💡 만약 터미널이 자동으로 열리지 않았다면:")
                print("  • 키보드 단축키: Ctrl+` (백틱) 또는 Cmd+` (Mac)")
                print("  • 메뉴: View > Terminal")
            else:
                print("VS Code 'code' command not found. Please open directories manually:")
                for path in worktree_paths:
                    print(f"  - {path}")
        
        print("Kickoff complete.")

    def verify_kickoff(self, task_ids: List[str] = None) -> None:
        """Verify kickoff results (worktrees/branches/status)"""
        if not task_ids:
            task_ids = self.jq_ready_ids()
        
        print(f"== Checking worktrees/branches/status for: {' '.join(task_ids)} ==")
        
        for task_id in task_ids:
            title = self.get_title(task_id)
            slug = self.slugify(title)
            branch = f"{self.branch_prefix}{task_id}-{slug}"
            path = f"{self.worktree_base}/{task_id}-{slug}"
            
            # Check directory
            dir_status = "[dir OK]" if Path(path).is_dir() else "[dir MISSING]"
            
            # Check branch
            branch_status = "[branch OK]" if self._branch_exists(branch) else "[branch MISSING]"
            
            # Check task status
            data = self._load_tasks()
            all_tasks = self._get_all_tasks(data)
            task_status = ""
            for task in all_tasks:
                if str(task['id']) == task_id:
                    task_status = task['status']
                    break
            
            status_check = "[status OK]" if task_status == "in-progress" else f"[status {task_status}]"
            
            print(f"Task {task_id}: {dir_status} {branch_status} {status_check}")

    def debug_ready(self) -> None:
        """Debug output for ready task logic"""
        data = self._load_tasks()
        all_tasks = self._get_all_tasks(data)
        status_map = self._get_status_map(all_tasks)
        
        for task in all_tasks:
            if task['status'] != 'pending':
                continue
            
            dependencies = task.get('dependencies', [])
            dep_str = ','.join(map(str, dependencies))
            
            if not dependencies:
                result = "READY"
            else:
                deps_satisfied = all(
                    status_map.get(str(dep_id), '') in ['done', 'in-progress']
                    for dep_id in dependencies
                )
                result = "READY" if deps_satisfied else "BLOCKED"
            
            print(f"id={task['id']} status={task['status']} deps={dep_str} -> {result}")

    def run_tm_command(self, args: List[str]) -> None:
        """Run task-master command with tag"""
        subprocess.run([self.tm_bin] + args + ['--tag', self.tag])

    def usage(self) -> None:
        """Print usage information"""
        print("""
TMH - Task Master Helper

USAGE:
    tmh.py <command> [args...]

COMMANDS:
    ready-ids           Show task IDs that are ready to work on
    blocked             Show tasks that are blocked by dependencies
    start-ready         Set all ready tasks to in-progress
    prompt <id>         Generate prompt for specific task
    prompt-all-ready    Generate prompts for all ready tasks
    worktree-ready      Create git worktrees for ready tasks
    kickoff-ready       Full kickoff: prompts + worktrees + status change
    worktree-ready-claude   Create worktrees + auto-run Claude CLI
    kickoff-ready-claude    FULL AUTOMATION: kickoff + Claude CLI
    claude-prompt <id>  Send task prompt directly to Claude CLI
    claude-ready        Interactive Claude CLI for ready tasks
    generate-scripts    Generate run_claude.sh scripts in each worktree
    generate-review [ids] Generate diff and code review requests
    auto-review [ids]   Generate review + auto-send to Opus
    set <status> <id>   Set task status
    show <id>           Show task details
    next                Show next task to work on
    debug-ready         Debug ready task detection
    verify-kickoff [ids] Verify kickoff setup
    help                Show this help

EXAMPLES:
    tmh.py ready-ids
    tmh.py kickoff-ready-claude    # 🚀 FULL AUTOMATION
    tmh.py worktree-ready-claude   # Worktree + Claude
    tmh.py claude-prompt 3
    tmh.py set done 3 5 7

ENVIRONMENT:
    TM_BIN              Task-master binary (default: tm)
    TAG                 Tag context (auto-detected from .taskmaster/state.json or tasks.json)
    TM_FILE             Tasks file (default: .taskmaster/tasks/tasks.json)
    WORKTREE_BASE       Worktree base directory (default: ../ws)
    BRANCH_PREFIX       Branch prefix (default: ws/)
    PROMPT_DIR          Prompt directory (default: prompts)
    TMH_AUTO_REVIEW     Enable auto Opus review (default: false)

TAG DETECTION:
    TMH automatically detects the current active tag from:
    1. TAG environment variable (if set)
    2. .taskmaster/state.json (currentTag field)
    3. First available tag in tasks.json
    4. Fallback to 'master'
    
    Override with: TAG=your-tag ./tmh.py <command>
        """)

    def main(self) -> None:
        """Main entry point"""
        if len(sys.argv) < 2:
            self.usage()
            return
        
        cmd = sys.argv[1]
        args = sys.argv[2:]
        
        if cmd == 'ready-ids':
            ready_ids = self.jq_ready_ids()
            for task_id in ready_ids:
                print(task_id)
        
        elif cmd == 'blocked':
            blocked = self.jq_blocked()
            for task_id, deps in blocked:
                print(f"{task_id}\tblocked by: {deps}")
        
        elif cmd == 'start-ready':
            self.start_ready()
        
        elif cmd == 'prompt':
            if len(args) != 1:
                print("Usage: tmh.py prompt <id>")
                sys.exit(1)
            print(self.prompt_one(args[0]))
        
        elif cmd == 'prompt-all-ready':
            self.prompt_all_ready()
        
        elif cmd == 'worktree-ready':
            self.worktree_ready()
        
        elif cmd == 'kickoff-ready':
            self.kickoff_ready()
        
        elif cmd == 'kickoff-ready-claude':
            self.kickoff_ready_with_claude()
        
        elif cmd == 'worktree-ready-claude':
            self.worktree_ready_with_claude()
        
        elif cmd == 'debug-ready':
            self.debug_ready()
        
        elif cmd == 'verify-kickoff':
            self.verify_kickoff(args if args else None)
        
        elif cmd == 'set':
            if len(args) < 2:
                print("Usage: tmh.py set <status> <ids...>")
                sys.exit(1)
            status = args[0]
            task_ids = args[1:]
            for task_id in task_ids:
                subprocess.run([self.tm_bin, 'set-status', '--tag', self.tag, 
                               '--id', task_id, '--status', status])
        
        elif cmd == 'show':
            if len(args) != 1:
                print("Usage: tmh.py show <id>")
                sys.exit(1)
            self.run_tm_command(['show', args[0]])
        
        elif cmd == 'next':
            self.run_tm_command(['next'])
        
        elif cmd == 'claude-prompt':
            if len(args) != 1:
                print("Usage: tmh.py claude-prompt <task_id>")
                sys.exit(1)
            self.claude_prompt(args[0])
        
        elif cmd == 'claude-ready':
            self.claude_ready()
        
        elif cmd == 'generate-scripts':
            self.generate_claude_scripts()
        
        elif cmd == 'generate-review':
            task_ids = args if args else None
            if task_ids and len(task_ids) == 1 and ',' in task_ids[0]:
                task_ids = task_ids[0].split(',')
            self.generate_diff_and_review(task_ids)
        
        elif cmd == 'auto-review':
            # Enable auto-review and generate review
            os.environ['TMH_AUTO_REVIEW'] = 'true'
            task_ids = args if args else None
            if task_ids and len(task_ids) == 1 and ',' in task_ids[0]:
                task_ids = task_ids[0].split(',')
            self.generate_diff_and_review(task_ids)
        
        elif cmd in ['help', '-h', '--help']:
            self.usage()
        
        else:
            print(f"Unknown command: {cmd}")
            print()
            self.usage()
            sys.exit(1)

    def claude_prompt(self, task_id: str) -> None:
        """Call claude CLI with specific task prompt"""
        if not self._command_exists('claude'):
            print("Claude CLI not found. Install: https://docs.claude.ai/claude-code")
            return
        
        prompt_text = self.prompt_one(task_id)
        if not prompt_text:
            print(f"No prompt found for task {task_id}")
            return
        
        print(f"Calling Claude CLI for task {task_id}...")
        print("=" * 50)
        
        try:
            # Use subprocess to call claude with the prompt
            result = subprocess.run([
                'claude', 
                '--dangerously-skip-permissions', 
                '--print',
                prompt_text
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                print(result.stdout)
            else:
                print(f"Claude CLI error: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            print("Claude CLI call timed out after 60 seconds")
        except subprocess.CalledProcessError as e:
            print(f"Claude CLI failed: {e}")

    def claude_ready(self) -> None:
        """Call claude CLI for all ready tasks"""
        if not self._command_exists('claude'):
            print("Claude CLI not found. Install: https://docs.claude.ai/claude-code")
            return
        
        ready_ids = self.jq_ready_ids()
        if not ready_ids:
            print("No ready tasks.")
            return
        
        print(f"Found {len(ready_ids)} ready tasks: {' '.join(ready_ids)}")
        try:
            response = input("Which task would you like to send to Claude? (task ID or 'all'): ").strip()
            
            if response.lower() == 'all':
                for task_id in ready_ids:
                    print(f"\n{'='*60}")
                    print(f"TASK {task_id}")
                    print('='*60)
                    self.claude_prompt(task_id)
            elif response in ready_ids:
                self.claude_prompt(response)
            else:
                print(f"Invalid choice. Available tasks: {' '.join(ready_ids)}")
                
        except KeyboardInterrupt:
            print("\nCancelled.")

    def kickoff_ready_with_claude(self) -> None:
        """Complete kickoff with automatic Claude CLI execution"""
        if not self._is_git_repo():
            print("Not a git repo.")
            sys.exit(1)
        
        if not self._has_commits():
            print("Need at least one commit for worktrees.")
            sys.exit(1)
        
        if not self._command_exists('claude'):
            print("⚠️  Claude CLI not found. Install: https://docs.claude.ai/claude-code")
            print("Falling back to regular kickoff...")
            self.kickoff_ready()
            return
        
        ready_ids = self.jq_ready_ids()
        if not ready_ids:
            print("No ready tasks.")
            return
        
        print(f"🚀 The following tasks are ready for FULL AUTOMATION kickoff: {' '.join(ready_ids)}")
        print("This will:")
        print("  1. Generate prompts")
        print("  2. Create worktrees") 
        print("  3. Open VS Code with terminal")
        print("  4. Automatically run Claude CLI with prompts")
        print("  5. Set tasks to in-progress")
        
        try:
            response = input(f"Proceed with FULL AUTOMATION for {len(ready_ids)} tasks? (y/N) ").strip().lower()
            if response not in ['y', 'yes']:
                print("Full automation cancelled.")
                return
        except KeyboardInterrupt:
            print("\nFull automation cancelled.")
            return
        
        print(f"🎯 Ready IDs: {' '.join(ready_ids)}")
        
        # Generate prompts
        Path(self.prompt_dir).mkdir(parents=True, exist_ok=True)
        for task_id in ready_ids:
            prompt_text = self.prompt_one(task_id)
            prompt_file = Path(self.prompt_dir) / f"{task_id}.txt"
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(prompt_text)
            print(f"📝 Wrote {prompt_file}")
        
        # Create worktrees
        Path(self.worktree_base).mkdir(parents=True, exist_ok=True)
        worktree_paths = []
        for task_id in ready_ids:
            title = self.get_title(task_id)
            slug = self.slugify(title)
            branch = f"{self.branch_prefix}{task_id}-{slug}"
            path = f"{self.worktree_base}/{task_id}-{slug}"
            
            if self._branch_exists(branch):
                print(f"⚠️  Branch {branch} already exists. Skipping.")
                worktree_paths.append((path, task_id))
            else:
                try:
                    subprocess.run(['git', 'worktree', 'add', '-b', branch, path, 'HEAD'], 
                                  check=True)
                    print(f"📁 Created worktree {path} (branch {branch})")
                    worktree_paths.append((path, task_id))
                except subprocess.CalledProcessError:
                    print(f"❌ WARNING: Failed to create worktree for task {task_id}. Continuing...")
        
        # Set status to in-progress
        for task_id in ready_ids:
            try:
                subprocess.run([self.tm_bin, 'set-status', '--tag', self.tag, 
                               '--id', task_id, '--status', 'in-progress'], check=True)
            except subprocess.CalledProcessError:
                print(f"⚠️  WARNING: Failed to set status for task {task_id}. Continuing...")
        
        # Open VS Code windows with terminal and Claude CLI
        if worktree_paths:
            print("🖥️  Opening VS Code windows with automatic Claude CLI execution...")
            for path, task_id in worktree_paths:
                print(f"🎯 Processing task {task_id}...")
                self._open_vscode_with_terminal_and_claude(path, task_id)
                time.sleep(2)  # Delay between windows to avoid conflicts
            
            print("\n🎉 FULL AUTOMATION COMPLETE!")
            print("Each VS Code window should now be running Claude CLI automatically.")
            print("\n💡 If automation failed, you can manually run:")
            for _, task_id in worktree_paths:
                main_project_path = os.path.abspath('.')
                print(f"   cat {main_project_path}/prompts/{task_id}.txt | claude --dangerously-skip-permissions --print")
        else:
            print("❌ No worktrees were created successfully.")

    def worktree_ready_with_claude(self) -> None:
        """Create worktrees and automatically run Claude CLI"""
        if not self._is_git_repo():
            print("Not a git repo.")
            sys.exit(1)
        
        if not self._has_commits():
            print("Need at least one commit for worktrees.")
            sys.exit(1)
        
        if not self._command_exists('claude'):
            print("⚠️  Claude CLI not found. Install: https://docs.claude.ai/claude-code")
            print("Falling back to regular worktree creation...")
            self.worktree_ready()
            return
        
        Path(self.worktree_base).mkdir(parents=True, exist_ok=True)
        
        ready_ids = self.jq_ready_ids()
        if not ready_ids:
            print("No ready tasks.")
            return
        
        print(f"🚀 The following tasks are ready for worktree + Claude automation: {' '.join(ready_ids)}")
        try:
            response = input(f"Proceed with creating worktrees + Claude CLI for {len(ready_ids)} tasks? (y/N) ").strip().lower()
            if response not in ['y', 'yes']:
                print("Automation cancelled.")
                return
        except KeyboardInterrupt:
            print("\nAutomation cancelled.")
            return
        
        # Generate prompts first
        Path(self.prompt_dir).mkdir(parents=True, exist_ok=True)
        for task_id in ready_ids:
            prompt_text = self.prompt_one(task_id)
            prompt_file = Path(self.prompt_dir) / f"{task_id}.txt"
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(prompt_text)
            print(f"📝 Wrote {prompt_file}")
        
        worktree_paths = []
        for task_id in ready_ids:
            title = self.get_title(task_id)
            slug = self.slugify(title)
            branch = f"{self.branch_prefix}{task_id}-{slug}"
            path = f"{self.worktree_base}/{task_id}-{slug}"
            
            if self._branch_exists(branch):
                print(f"⚠️  Branch {branch} already exists. Skipping.")
                worktree_paths.append((path, task_id))
            else:
                try:
                    subprocess.run(['git', 'worktree', 'add', '-b', branch, path, 'HEAD'], 
                                  check=True)
                    print(f"📁 Created worktree {path} (branch {branch})")
                    worktree_paths.append((path, task_id))
                except subprocess.CalledProcessError:
                    print(f"❌ WARNING: Failed to create worktree for task {task_id}. Continuing...")
        
        # Open VS Code windows with Claude CLI automation
        if worktree_paths:
            print("🖥️  Opening VS Code windows with automatic Claude CLI execution...")
            for path, task_id in worktree_paths:
                print(f"🎯 Processing task {task_id}...")
                self._open_vscode_with_terminal_and_claude(path, task_id)
                time.sleep(2)  # Delay between windows
            
            print("\n🎉 AUTOMATION COMPLETE!")
            print("Each VS Code window should now be running Claude CLI automatically.")
        else:
            print("❌ No worktrees were created successfully.")

    def run(self) -> None:
        """Main command dispatcher"""
        if len(sys.argv) < 2:
            self.help()
            return
        
        command = sys.argv[1]
        args = sys.argv[2:]
        
        if command == 'ready-ids':
            ids = self.jq_ready_ids()
            for id in ids:
                print(id)
                
        elif command == 'blocked':
            blocked = self.jq_blocked()
            for line in blocked:
                print(line)
                
        elif command == 'start-ready':
            self.start_ready()
            
        elif command == 'prompt':
            if not args:
                print("Usage: ./tmh.py prompt <task_id>")
                return
            prompt = self.prompt_one(args[0])
            if prompt:
                print(prompt)
                
        elif command == 'prompt-all-ready':
            self.prompt_all_ready()
            
        elif command == 'worktree-ready':
            self.worktree_ready()
            
        elif command == 'kickoff-ready':
            self.kickoff_ready()
            
        elif command == 'kickoff-ready-claude':
            self.kickoff_ready_with_claude()
        
        elif command == 'worktree-ready-claude':
            self.worktree_ready_with_claude()
        
        elif command == 'claude-prompt':
            if not args:
                print("Usage: ./tmh.py claude-prompt <task_id>")
                return
            self.claude_prompt(args[0])
            
        elif command == 'claude-ready':
            self.claude_ready()
            
        elif command == 'set':
            if len(args) < 2:
                print("Usage: ./tmh.py set <status> <task_id> [task_id...]")
                return
            status = args[0]
            task_ids = args[1:]
            for task_id in task_ids:
                subprocess.run([self.tm_bin, 'set-status', '--tag', self.tag, 
                               '--id', task_id, '--status', status])
                
        elif command == 'show':
            if not args:
                print("Usage: ./tmh.py show <task_id>")
                return
            subprocess.run([self.tm_bin, 'show', '--tag', self.tag, args[0]])
            
        elif command == 'next':
            subprocess.run([self.tm_bin, 'next', '--tag', self.tag])
            
        elif command == 'debug-ready':
            self.debug_ready()
            
        elif command == 'verify-kickoff':
            task_ids = args if args else self.jq_ready_ids()
            self.verify_kickoff(task_ids)
            
        elif command == 'help':
            self.help()
            
        else:
            print(f"Unknown command: {command}")
            self.help() 

    def generate_claude_scripts(self) -> None:
        """Generate Claude CLI execution scripts for each worktree"""
        ready_ids = self._get_ready_task_ids()
        if not ready_ids:
            print("No ready tasks.")
            return
            
        print(f"🎯 Generating Claude CLI scripts for tasks: {' '.join(ready_ids)}")
        
        for task_id in ready_ids:
            worktree_path = f"{self.worktree_base}/{self._get_branch_name(task_id)[3:]}"  # Remove 'ws/' prefix
            prompt_file = f"../../petlab-parallel/prompts/{task_id}.txt"
            
            # Create script content
            script_content = f"""#!/bin/bash
# Claude CLI execution script for Task {task_id}
# Generated by tmh.py

echo "=== 🚀 Starting Claude CLI for Task {task_id} ==="
echo "📍 Working directory: $(pwd)"
echo "📝 Prompt file: {prompt_file}"
echo ""

# Check if prompt file exists
if [ ! -f "{prompt_file}" ]; then
    echo "❌ Prompt file not found: {prompt_file}"
    exit 1
fi

# Run Claude CLI in foreground
echo "🎯 Executing Claude CLI..."
claude --dangerously-skip-permissions {prompt_file}

echo ""
echo "✅ Claude CLI execution completed for Task {task_id}"
"""
            
            # Write script to worktree
            script_path = f"{worktree_path}/run_claude.sh"
            try:
                with open(script_path, 'w') as f:
                    f.write(script_content)
                os.chmod(script_path, 0o755)  # Make executable
                print(f"📝 Created executable script: {script_path}")
            except Exception as e:
                print(f"❌ Failed to create script for task {task_id}: {e}")

    def generate_diff_and_review(self, task_ids: list = None) -> None:
        """Generate diff for worktrees and request Opus code review"""
        if task_ids is None:
            # Get all in-progress tasks
            tasks_data = self._load_tasks()
            task_ids = []
            for tag_data in tasks_data.get('tags', {}).values():
                for task in tag_data.get('tasks', []):
                    if task.get('status') == 'in-progress':
                        task_ids.append(str(task.get('id')))
        
        if not task_ids:
            print("No in-progress tasks found for review.")
            return
            
        print(f"🔍 Generating diffs and requesting Opus review for tasks: {' '.join(task_ids)}")
        
        # Create review directory
        review_dir = "reviews"
        os.makedirs(review_dir, exist_ok=True)
        
        for task_id in task_ids:
            try:
                worktree_path = f"{self.worktree_base}/{self._get_branch_name(task_id)[3:]}"  # Remove 'ws/' prefix
                branch_name = self._get_branch_name(task_id)
                
                # Generate diff
                diff_cmd = f"git diff main..{branch_name}"
                result = subprocess.run(diff_cmd.split(), capture_output=True, text=True, cwd=worktree_path)
                
                if result.returncode != 0:
                    print(f"❌ Failed to generate diff for task {task_id}: {result.stderr}")
                    continue
                    
                diff_content = result.stdout
                if not diff_content.strip():
                    print(f"⚠️  No changes found for task {task_id}")
                    continue
                
                # Get task details
                task_details = self._get_task_details(task_id)
                task_title = task_details.get('title', f'Task {task_id}')
                task_description = task_details.get('description', 'No description')
                
                # Create review request
                review_request = f"""# Code Review Request - Task {task_id}

## Task Information
- **Title**: {task_title}
- **Description**: {task_description}
- **Branch**: {branch_name}
- **Status**: in-progress

## Review Request
Please review the following changes and provide feedback on:
1. Code quality and best practices
2. Potential bugs or issues
3. Performance considerations
4. Architecture and design patterns
5. Test coverage suggestions

## Changes

```diff
{diff_content}
```

## Questions for Review
1. Does this implementation align with the task requirements?
2. Are there any security concerns?
3. What improvements would you suggest?
4. Should any additional tests be added?

---
*Generated by tmh.py - Task Master Helper*
"""
                
                # Save review request
                review_file = f"{review_dir}/task_{task_id}_review.md"
                with open(review_file, 'w') as f:
                    f.write(review_request)
                
                print(f"📋 Created review request: {review_file}")
                
                # Optional: Automatically send to Claude/Opus for review
                if self._should_auto_review():
                    self._send_to_opus_review(review_request, task_id)
                    
            except Exception as e:
                print(f"❌ Failed to process task {task_id}: {e}")

    def _should_auto_review(self) -> bool:
        """Check if auto-review is enabled"""
        return os.environ.get('TMH_AUTO_REVIEW', 'false').lower() == 'true'

    def _send_to_opus_review(self, review_request: str, task_id: str) -> None:
        """Send review request to Opus via Claude CLI"""
        try:
            print(f"🤖 Sending task {task_id} to Opus for review...")
            
            # Create a temporary file for the review request
            temp_file = f"temp_review_{task_id}.md"
            with open(temp_file, 'w') as f:
                f.write(review_request)
            
            # Send to Claude CLI for review
            review_cmd = f"claude --dangerously-skip-permissions {temp_file}"
            result = subprocess.run(review_cmd.split(), capture_output=True, text=True)
            
            if result.returncode == 0:
                # Save Opus response
                response_file = f"reviews/task_{task_id}_opus_review.md"
                with open(response_file, 'w') as f:
                    f.write(f"# Opus Review for Task {task_id}\n\n")
                    f.write(result.stdout)
                
                print(f"✅ Opus review saved: {response_file}")
            else:
                print(f"❌ Failed to get Opus review: {result.stderr}")
            
            # Clean up temp file
            os.remove(temp_file)
            
        except Exception as e:
            print(f"❌ Error sending to Opus: {e}")

    def _get_ready_task_ids(self) -> list:
        """Get list of ready task IDs (pending tasks with all dependencies completed)"""
        try:
            tasks_data = self._load_tasks()
            
            # Get tasks for current tag
            if 'tags' in tasks_data:
                tag_tasks = tasks_data.get('tags', {}).get(self.tag, {}).get('tasks', [])
            else:
                tag_tasks = tasks_data.get(self.tag, {}).get('tasks', [])
            
            ready_ids = []
            for task in tag_tasks:
                # Skip if not pending
                if task.get('status') != 'pending':
                    continue
                
                # Check if all dependencies are completed
                dependencies = task.get('dependencies', [])
                all_deps_done = True
                
                for dep_id in dependencies:
                    dep_task = self._find_task_by_id(str(dep_id), tag_tasks)
                    if not dep_task or dep_task.get('status') != 'done':
                        all_deps_done = False
                        break
                
                # If all dependencies are done (or no dependencies), task is ready
                if all_deps_done:
                    ready_ids.append(str(task.get('id')))
            
            # Remove duplicates and return
            return list(set(ready_ids))
            
        except Exception as e:
            print(f"Error getting ready tasks: {e}")
            return []

    def _find_task_by_id(self, task_id: str, tasks: list) -> dict:
        """Find a task by ID in a list of tasks"""
        for task in tasks:
            if str(task.get('id')) == task_id:
                return task
        return {}

    def _get_task_details(self, task_id: str) -> dict:
        """Get task details by ID"""
        tasks_data = self._load_tasks()
        # Check if using old format (direct tag) or new format (tags object)
        if 'tags' in tasks_data:
            for tag_data in tasks_data.get('tags', {}).values():
                for task in tag_data.get('tasks', []):
                    if str(task.get('id')) == task_id:
                        return task
        else:
            # Direct format like 'petlab'
            tag_data = tasks_data.get(self.tag, {})
            for task in tag_data.get('tasks', []):
                if str(task.get('id')) == task_id:
                    return task
        return {}

    def _get_branch_name(self, task_id: str) -> str:
        """Generate a branch name for a given task ID"""
        title = self.get_title(task_id)
        slug = self.slugify(title)
        return f"{self.branch_prefix}{task_id}-{slug}"


if __name__ == '__main__':
    tmh = TMH()
    tmh.main() 