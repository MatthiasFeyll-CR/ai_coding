"""Milestone FSM runner — drives one milestone through its phases.

Uses the `transitions` library for state machine management.
"""

from __future__ import annotations

from pathlib import Path

from transitions import Machine

from ralph_pipeline.ai.claude import ClaudeRunner
from ralph_pipeline.config import MilestoneConfig, PipelineConfig
from ralph_pipeline.git_ops import GitOps
from ralph_pipeline.infra.regression import RegressionAnalyzer
from ralph_pipeline.infra.test_infra import TestInfraManager
from ralph_pipeline.infra.test_runner import TestRunner
from ralph_pipeline.log import PipelineLogger
from ralph_pipeline.phases.prd_generation import run_prd_generation
from ralph_pipeline.phases.qa_review import run_qa_review
from ralph_pipeline.phases.ralph_execution import run_ralph_execution
from ralph_pipeline.phases.reconciliation import MergeError, run_reconciliation
from ralph_pipeline.state import PipelineState
from ralph_pipeline.usage import EventLogger


class MilestoneRunner:
    """FSM for executing one milestone through all pipeline phases.

    States: pending → prd_generation → ralph_execution → qa_review →
            reconciliation → complete | failed

    The reconciliation phase now includes the merge operation (previously
    a separate phase).  In a linear single-agent pipeline the merge is
    trivial and needs no post-merge verification.

    On resume, the FSM starts in the saved state and continues from there.
    """

    states = [
        "pending",
        "prd_generation",
        "ralph_execution",
        "qa_review",
        "reconciliation",
        "complete",
        "failed",
    ]

    transitions = [
        {
            "trigger": "start",
            "source": "pending",
            "dest": "prd_generation",
            "after": "_on_phase_start",
        },
        {
            "trigger": "prd_done",
            "source": "prd_generation",
            "dest": "ralph_execution",
            "after": "_on_phase_start",
        },
        {
            "trigger": "ralph_done",
            "source": "ralph_execution",
            "dest": "qa_review",
            "after": "_on_phase_start",
        },
        {
            "trigger": "qa_passed",
            "source": "qa_review",
            "dest": "reconciliation",
            "after": "_on_phase_start",
        },
        {
            "trigger": "qa_needs_fix",
            "source": "qa_review",
            "dest": "ralph_execution",
            "after": "_on_bugfix",
        },
        {
            "trigger": "reconciled",
            "source": "reconciliation",
            "dest": "complete",
            "after": "_on_complete",
        },
        {
            "trigger": "fail",
            "source": "*",
            "dest": "failed",
            "after": "_on_fail",
        },
    ]

    def __init__(
        self,
        milestone: MilestoneConfig,
        config: PipelineConfig,
        pipeline_state: PipelineState,
        state_file: Path,
        claude: ClaudeRunner,
        git: GitOps,
        test_runner: TestRunner,
        infra: TestInfraManager,
        regression_analyzer: RegressionAnalyzer,
        plogger: PipelineLogger,
        event_logger: EventLogger,
        project_root: Path,
    ):
        self.milestone = milestone
        self.config = config
        self.pipeline_state = pipeline_state
        self.state_file = state_file
        self.claude = claude
        self.git = git
        self.test_runner = test_runner
        self.infra = infra
        self.regression_analyzer = regression_analyzer
        self.plogger = plogger
        self.event_logger = event_logger
        self.project_root = project_root
        self._failure_reason: str = ""

        # Resume: start FSM from saved phase
        ms_state = pipeline_state.milestones[milestone.id]
        initial = ms_state.phase if ms_state.phase != "pending" else "pending"

        self.machine = Machine(
            model=self,
            states=self.states,
            transitions=self.transitions,
            initial=initial,
        )

    def _on_phase_start(self) -> None:
        """Called after each state transition — persist new state for resume."""
        self.plogger.info(f"M{self.milestone.id}: transitioning to next phase")
        self._persist_state()

    def _on_bugfix(self) -> None:
        """Increment bugfix cycle counter."""
        ms = self.pipeline_state.milestones[self.milestone.id]
        ms.bugfix_cycle += 1
        self.plogger.info(f"M{self.milestone.id}: QA bugfix cycle {ms.bugfix_cycle}")
        self._persist_state()

    def _on_complete(self) -> None:
        """Mark milestone complete."""
        self.plogger.success(f"M{self.milestone.id} ({self.milestone.slug}) COMPLETE")
        self.pipeline_state.update_phase(self.milestone.id, "complete")
        self.pipeline_state.save(self.state_file)
        self.event_logger.emit(
            "milestone_complete",
            milestone=self.milestone.id,
        )

    def _on_fail(self) -> None:
        """Log failure, persist state for resume."""
        self.plogger.error(f"M{self.milestone.id} FAILED: {self._failure_reason}")
        self.pipeline_state.update_phase(self.milestone.id, "failed")
        self.pipeline_state.save(self.state_file)
        self.event_logger.emit(
            "milestone_failed",
            milestone=self.milestone.id,
            data={"reason": self._failure_reason},
        )

    def _persist_state(self) -> None:
        """Save current FSM state to disk."""
        self.pipeline_state.update_phase(self.milestone.id, self.state)
        self.pipeline_state.save(self.state_file)

    def execute(self) -> bool:
        """Drive the FSM from current state to completion or failure.

        Returns True if milestone completed, False if failed.
        """
        # If pending, trigger start
        if self.state == "pending":
            self.start()

        while self.state not in ("complete", "failed"):
            try:
                self._execute_current_phase()
            except Exception as e:
                self._failure_reason = str(e)
                self.fail()
                return False

        return self.state == "complete"

    def _execute_current_phase(self) -> None:
        """Dispatch to the correct phase module based on current FSM state."""
        handlers = {
            "prd_generation": self._run_prd_generation,
            "ralph_execution": self._run_ralph_execution,
            "qa_review": self._run_qa_review,
            "reconciliation": self._run_reconciliation,
        }
        handler = handlers.get(self.state)
        if handler:
            handler()

    def _run_prd_generation(self) -> None:
        """Phase 1: Generate PRD."""
        self.event_logger.emit(
            "phase_start", milestone=self.milestone.id, data={"phase": "prd_generation"}
        )
        run_prd_generation(
            milestone=self.milestone,
            config=self.config,
            claude=self.claude,
            plogger=self.plogger,
            project_root=self.project_root,
            pipeline_state=self.pipeline_state,
        )
        self.event_logger.emit(
            "phase_end", milestone=self.milestone.id, data={"phase": "prd_generation"}
        )
        self.prd_done()

    def _run_ralph_execution(self) -> None:
        """Phase 2: Run Ralph agent."""
        self.event_logger.emit(
            "phase_start",
            milestone=self.milestone.id,
            data={"phase": "ralph_execution"},
        )
        run_ralph_execution(
            milestone=self.milestone,
            config=self.config,
            git=self.git,
            plogger=self.plogger,
            project_root=self.project_root,
            claude=self.claude,
            event_logger=self.event_logger,
        )
        self.event_logger.emit(
            "phase_end", milestone=self.milestone.id, data={"phase": "ralph_execution"}
        )
        self.ralph_done()

    def _run_qa_review(self) -> None:
        """Phase 3: QA review with bugfix cycles."""
        self.event_logger.emit(
            "phase_start", milestone=self.milestone.id, data={"phase": "qa_review"}
        )
        passed = run_qa_review(
            milestone=self.milestone,
            config=self.config,
            claude=self.claude,
            test_runner=self.test_runner,
            git=self.git,
            plogger=self.plogger,
            project_root=self.project_root,
            event_logger=self.event_logger,
        )
        self.event_logger.emit(
            "phase_end",
            milestone=self.milestone.id,
            data={"phase": "qa_review", "passed": passed},
        )
        if passed:
            self.qa_passed()
        else:
            self._failure_reason = (
                f"QA failed after {self.config.qa.max_bugfix_cycles} bugfix cycles"
            )
            self.fail()

    def _run_reconciliation(self) -> None:
        """Phase 4: Merge feature branch + spec reconciliation."""
        self.event_logger.emit(
            "phase_start", milestone=self.milestone.id, data={"phase": "reconciliation"}
        )
        try:
            recon_success = run_reconciliation(
                milestone=self.milestone,
                config=self.config,
                state=self.pipeline_state,
                claude=self.claude,
                regression_analyzer=self.regression_analyzer,
                git=self.git,
                plogger=self.plogger,
                project_root=self.project_root,
                state_file=self.state_file,
            )
        except MergeError as e:
            self._failure_reason = str(e)
            self.event_logger.emit(
                "phase_end",
                milestone=self.milestone.id,
                data={"phase": "reconciliation", "error": str(e)},
            )
            self.fail()
            return

        # Record reconciliation outcome in state
        ms = self.pipeline_state.milestones[self.milestone.id]
        ms.reconciliation_status = "success" if recon_success else "failed"
        self.pipeline_state.save(self.state_file)

        if not recon_success:
            self.plogger.warning(
                f"Reconciliation debt: M{self.milestone.id} specs not updated. "
                f"Total unreconciled milestones: "
                f"{self.pipeline_state.reconciliation_debt()}"
            )

        self.event_logger.emit(
            "phase_end",
            milestone=self.milestone.id,
            data={
                "phase": "reconciliation",
                "reconciliation_success": recon_success,
            },
        )
        self.reconciled()




