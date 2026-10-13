import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from config.settings import settings
from src.agent.workflow import NewsAnalysisWorkflow
from src.utils.logger import logger


class AgentScheduler:
    """
    Manages continuous background scheduling and execution of the news analysis workflow.
    """

    def __init__(
        self,
        workflow: Optional[NewsAnalysisWorkflow] = None,
        interval_seconds: Optional[int] = None
    ):
        self.workflow = workflow or NewsAnalysisWorkflow()
        self.interval_seconds = interval_seconds or settings.FETCH_INTERVAL_SECONDS or 300
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.total_runs: int = 0
        self.last_run_time: Optional[datetime] = None
        self.last_error: Optional[str] = None

    async def run_single_iteration(self) -> Dict[str, Any]:
        """
        Execute a single end-to-end iteration of the agent workflow.
        """
        self.total_runs += 1
        self.last_run_time = datetime.now(timezone.utc)
        logger.info(f"AgentScheduler starting run #{self.total_runs} at {self.last_run_time.isoformat()}")

        try:
            final_state = await self.workflow.run()
            verdicts_count = len(final_state.get("verdicts", {}))
            articles_count = len(final_state.get("new_articles", []))
            logger.info(f"Run #{self.total_runs} completed successfully: {articles_count} new articles, {verdicts_count} verdicts.")
            return final_state
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Error during scheduled run #{self.total_runs}: {e}")
            return {"errors": [str(e)]}

    async def _loop(self):
        """
        Internal continuous polling loop.
        """
        logger.info(f"Starting continuous agent scheduler loop with interval: {self.interval_seconds}s")
        while self.is_running:
            await self.run_single_iteration()
            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break

    def start(self):
        """
        Start the background polling loop as an asyncio Task.
        """
        if self.is_running:
            logger.warning("AgentScheduler is already running.")
            return

        self.is_running = True
        self._task = asyncio.create_task(self._loop())

    def stop(self):
        """
        Gracefully stop the background scheduler task.
        """
        if not self.is_running:
            return

        self.is_running = False
        if self._task:
            self._task.cancel()
        logger.info("AgentScheduler stopped.")

    def get_status(self) -> Dict[str, Any]:
        """
        Return operational telemetry and health status.
        """
        return {
            "is_running": self.is_running,
            "total_runs": self.total_runs,
            "last_run_time": self.last_run_time.isoformat() if self.last_run_time else None,
            "interval_seconds": self.interval_seconds,
            "last_error": self.last_error
        }
