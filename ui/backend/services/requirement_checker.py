"""System requirement checker service."""

import subprocess


class RequirementChecker:
    """Check system requirements for pipeline execution."""

    REQUIREMENTS = [
        {
            "name": "python",
            "command": "python3 --version",
            "min_version": "3.11",
        },
        {
            "name": "docker",
            "command": "docker --version",
        },
        {
            "name": "docker-compose",
            "command": "docker compose version",
        },
        {
            "name": "ralph-pipeline",
            "command": "ralph-pipeline",
        },
        {
            "name": "claude",
            "command": "claude --version",
        },
        {
            "name": "git",
            "command": "git --version",
        },
        {
            "name": "nodejs",
            "command": "node --version",
        },
    ]

    def check_all(self):
        """Check all requirements."""
        results = []
        for req in self.REQUIREMENTS:
            result = self._check_command(req["name"], req["command"])
            results.append(result)
        return results

    def _check_command(self, name, command):
        """Check if a command is available."""
        try:
            result = subprocess.run(
                command.split(),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return {
                    "name": name,
                    "status": "passed",
                    "details": result.stdout.strip(),
                }
            else:
                return {
                    "name": name,
                    "status": "failed",
                    "details": result.stderr.strip(),
                }
        except FileNotFoundError:
            return {
                "name": name,
                "status": "failed",
                "details": f"{name} not found in PATH",
            }
        except subprocess.TimeoutExpired:
            return {
                "name": name,
                "status": "failed",
                "details": "Command timed out",
            }
        except Exception as e:
            return {
                "name": name,
                "status": "failed",
                "details": str(e),
            }
