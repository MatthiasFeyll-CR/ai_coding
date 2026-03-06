#!/usr/bin/env python3
"""Fix test_configurator_invoker.py: update Popen mocks to subprocess.run mocks."""

filepath = "tests/test_configurator_invoker.py"
with open(filepath, "r") as f:
    content = f.read()

# 1) Fix test_calls_claude_command
content = content.replace(
    "            # Mock Popen to return a process that emits JSON lines\n"
    "            mock_process = MagicMock()\n"
    "            mock_process.stdout = io.StringIO(\n"
    '                json.dumps({"type": "result", "result": "Config generated"}) + "\\n"\n'
    "            )\n"
    "            mock_process.stderr = MagicMock()\n"
    '            mock_process.stderr.read.return_value = ""\n'
    "            mock_process.wait.return_value = None\n"
    "            mock_process.returncode = 0\n"
    "\n"
    "            with patch(\n"
    '                "services.configurator_invoker.subprocess.Popen",\n'
    "                return_value=mock_process,\n"
    "            ) as mock_popen:\n"
    "                result = invoker._invoke_configurator()\n"
    "\n"
    "                mock_popen.assert_called_once()\n"
    "                cmd = mock_popen.call_args[0][0]\n"
    '                assert "claude" in cmd\n'
    '                assert "-p" in cmd\n'
    "                assert result is True",
    "            # Mock subprocess.run to return a successful CompletedProcess\n"
    "            mock_completed = MagicMock()\n"
    "            mock_completed.returncode = 0\n"
    '            mock_completed.stdout = "Config generated"\n'
    '            mock_completed.stderr = ""\n'
    "\n"
    "            with patch(\n"
    '                "services.configurator_invoker.subprocess.run",\n'
    "                return_value=mock_completed,\n"
    "            ) as mock_run:\n"
    "                result = invoker._invoke_configurator()\n"
    "\n"
    "                mock_run.assert_called_once()\n"
    "                cmd = mock_run.call_args[0][0]\n"
    '                assert "claude" in cmd\n'
    '                assert "-p" in cmd\n'
    "                assert result is True",
)

# 2) Fix test_returns_false_on_failure
content = content.replace(
    "            mock_process = MagicMock()\n"
    '            mock_process.stdout = io.StringIO("")\n'
    "            mock_process.stderr = MagicMock()\n"
    '            mock_process.stderr.read.return_value = "Error!"\n'
    "            mock_process.wait.return_value = None\n"
    "            mock_process.returncode = 1\n"
    "\n"
    "            with patch(\n"
    '                "services.configurator_invoker.subprocess.Popen",\n'
    "                return_value=mock_process,\n"
    "            ):\n"
    "                result = invoker._invoke_configurator()\n"
    "                assert result is False",
    "            mock_completed = MagicMock()\n"
    "            mock_completed.returncode = 1\n"
    '            mock_completed.stdout = ""\n'
    '            mock_completed.stderr = "Error!"\n'
    "\n"
    "            with patch(\n"
    '                "services.configurator_invoker.subprocess.run",\n'
    "                return_value=mock_completed,\n"
    "            ):\n"
    "                result = invoker._invoke_configurator()\n"
    "                assert result is False",
)

# 3) Fix test_returns_false_on_file_not_found
content = content.replace(
    "            with patch(\n"
    '                "services.configurator_invoker.subprocess.Popen",\n'
    "                side_effect=FileNotFoundError,\n"
    "            ):\n"
    "                result = invoker._invoke_configurator()\n"
    "                assert result is False",
    "            with patch(\n"
    '                "services.configurator_invoker.subprocess.run",\n'
    "                side_effect=FileNotFoundError,\n"
    "            ):\n"
    "                result = invoker._invoke_configurator()\n"
    "                assert result is False",
)

with open(filepath, "w") as f:
    f.write(content)

# Verify
import subprocess as sp

r1 = sp.run(
    ["grep", "-c", "subprocess.Popen", filepath], capture_output=True, text=True
)
r2 = sp.run(["grep", "-c", "subprocess.run", filepath], capture_output=True, text=True)
print(f"Remaining subprocess.Popen refs: {r1.stdout.strip()}")
print(f"subprocess.run refs: {r2.stdout.strip()}")

r3 = sp.run(["grep", "-n", "subprocess", filepath], capture_output=True, text=True)
print(r3.stdout)
