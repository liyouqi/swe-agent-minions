import os
from dotenv import load_dotenv
from openai import OpenAI

import re
import shlex
import subprocess

from rich.console import Console
from rich.panel import Panel


# 1.load env and configure client
load_dotenv()

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url=os.environ.get("OPENAI_BASE_URL"),
)

console = Console()

MAX_STEPS = 15 # maximum steps to prevent infinite loops
MODEL_NAME = os.environ.get("MODEL_NAME")
WORKSPACE_ROOT = os.path.realpath(os.getcwd())
SANDBOX_ROOT = os.path.realpath(os.path.join(WORKSPACE_ROOT, "sandbox"))

# 2. The brain. Core prompt to guide the agent's behavior
SYSTEM_PROMPT = """You are a top-tier AI developer programming assistant, running in a Linux environment. 
The only way you can interact with is outputting Bash commands. I will excute the commands you provide and return the 
results (stdout and stderr) to you. 

[Core Principles]
1. Each response must include your thought process and **only one** code block wrapped with ```bash and ```.
2. You can use cat to read files, sed/awk/python -c to modify files, pytest/python to run tests.
3. Your working directory is the current host directory. Please prioritize entering the ./sandbox directory for operations.
4. When you think the goal has been fully achieved (e.g., tests passed), please output ```bash\nexit\n``` to end the task.

[Output Format Requirements]
Thoughts: [Write down your reasoning process]
```bash
[The one or set of terminal commands you want to execute]
```"""

# 3 Fence. Security of parsing and safety.
def is_safe_command(command: str) -> bool:
    """Lightweight safety checks for experiment use, with common bypasses blocked."""
    if not command.strip():
        return False

    if ".." in command or "~" in command:
        return False

    # Block command substitution to reduce shell-injection style bypasses.
    if "$ (" in command or "$(" in command or "`" in command:
        return False

    # Keep policy moderate: dangerous/system/interactive/network-heavy commands are denied.
    forbidden_cmds = {
        "rm", "dd", "mkfs", "shutdown", "reboot", "init",
        "useradd", "groupadd", "passwd", "chown", "chgrp",
        "telnet", "nc", "netcat", "nmap", "tcpdump", "wireshark", "iptables", "ufw",
        "vim", "nano", "top", "htop", "ping"
    }

    # Validate each command segment to prevent bypass via "cmd1 && cmd2".
    segments = re.split(r"\s*(?:&&|\|\||;|\n|\|)\s*", command.strip())
    for segment in segments:
        if not segment:
            continue
        try:
            tokens = shlex.split(segment)
        except ValueError:
            return False
        if not tokens:
            continue

        base_cmd = tokens[0].lower()
        if base_cmd in forbidden_cmds:
            return False

        # Lightweight path guard: reject explicit absolute paths outside ./sandbox when sandbox exists.
        for token in tokens[1:]:
            if token.startswith("-") or "=" in token:
                continue
            if token.startswith("/"):
                if os.path.isdir(SANDBOX_ROOT) and not os.path.realpath(token).startswith(SANDBOX_ROOT):
                    return False

    return True

def parse_llm_output(text: str):
    """lastly, extract the bash code block and do security checks"""
    pattern = r"`{3}(?:bash|sh)?\s*(.*?)`{3}"
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)

    if not matches:
        return None,  "Parse error: No bash code block found. Please output the correct bash code block."

        # robustness
    command = matches[-1].strip() # take the last code block, which is likely the most recent command

    if command.lower() == "exit":
        return "exit", "SUCCESS"
    
    if not is_safe_command(command):
        return None, f"[Security intercepted] The command `{command}` is not allowed due to security policies. Please provide a different command."
    
    return command, "Parsed successfully"

# 4. Physical executor. 
def execute_command(command: str) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=WORKSPACE_ROOT,
        )
        return result.stdout if result.returncode == 0 else result.stderr
    except subprocess.TimeoutExpired:
        return "[Error timeout] The command took too long to execute and was terminated."
    except Exception as e:
        return f"[Error system] {str(e)}"



#5. Agent loop Controller
def run_agent(goal: str):
    conversation = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"The goal is: {goal}"}
    ]

    console.print(Panel(f"[bold green] New Task Started: {goal} [/bold green] {goal} \nuse", border_style="green"))
    recent_errors = []

    for step in range(1, MAX_STEPS + 1):
        console.print(f"\n[bold dim]--- Iteration {step}/{MAX_STEPS} ---[/bold dim]")
        
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=conversation,
                temperature=0.2
            )
            llm_text = response.choices[0].message.content
        except Exception as e:
            console.print(f"[bold red]API call failed: {e}[/bold red]")
            break
            
        thought_text = re.sub(r"\x60{3}.*?\x60{3}", "", llm_text, flags=re.DOTALL).strip()
        if thought_text:
            console.print(Panel(thought_text, title="🧠 [bold blue]AI Thought[/]", border_style="blue"))
            
        command, parse_msg = parse_llm_output(llm_text)
        conversation.append({"role": "assistant", "content": llm_text})
        
        if command == "exit":
            console.print(Panel("🎉 [bold green]Task Completed Successfully![/]", border_style="green"))
            break
            
        if not command: 
            console.print(Panel(parse_msg, title="⚠️ [bold yellow]Parsing/Security Warning[/]", border_style="yellow"))
            conversation.append({"role": "user", "content": parse_msg})
            continue
            
        console.print(Panel(command, title="⚡ [bold yellow]Action to Execute[/]", border_style="yellow"))
        
        observation = execute_command(command)
        obs_color = "red" if "Error" in observation or "Exception" in observation else "green"
        
        display_obs = observation[:1000] + ("...\n(truncated)" if len(observation) > 1000 else "")
        if not display_obs.strip(): display_obs = "[empty output]"
            
        console.print(Panel(display_obs, title="🌍 [bold]Terminal Observation[/]", border_style=obs_color))
        
        if obs_color == "red":
            recent_errors.append(observation)
            if len(recent_errors) >= 3 and recent_errors[-1] == recent_errors[-2] == recent_errors[-3]:
                intervention = "[System Intervention] You've triggered the same error 3 times in a row! Please change your approach immediately."
                console.print(f"\n[bold magenta]{intervention}[/bold magenta]")
                observation += f"\n\n{intervention}"
                recent_errors.clear()
        else:
            recent_errors.clear()

        conversation.append({
            "role": "user",
            "content": f"Command output:\n{observation}\n\nPlease continue with the next step based on this. If the task is completed, please output \x60\x60\x60bash\nexit\n\x60\x60\x60"
        })
    else:
        console.print(Panel(f"❌ Reached maximum steps, terminating forcefully.", border_style="red"))


    
#   6. Entry point
if __name__ == "__main__":
    print("Starting the AI agent...")
    task = "Please navigate to the sandbox/tc_01 directory and find the buggy math_ops.py. It's a division function that lacks a check for division by zero. Please fix it so that running python test_math.py will pass the tests."
    run_agent(task)