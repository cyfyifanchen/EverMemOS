"""
Long job manager implementation.
Long job manager implementation.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from common_utils.datetime_utils import get_now_with_timezone
from core.longjob.interfaces import LongJobInterface, LongJobStatus
from core.di import service, get_beans_by_type
import os


@service(name="long_job_manager", primary=True)
class LongJobManager:
    """
    Long job manager
    Responsible for managing multiple long-running tasks including starting, stopping, and monitoring functions
    """

    def __init__(self):
        """
        Initialize the long job manager
        Read configuration from environment variables
        """
        # Read configuration from environment variables
        self.max_concurrent_jobs = int(os.getenv('LONGJOB_MAX_CONCURRENT_JOBS', '10'))
        self.auto_discover = (
            os.getenv('LONGJOB_AUTO_DISCOVER', 'true').lower() == 'true'
        )
        self.auto_start_mode = os.getenv('LONGJOB_AUTO_START_MODE', 'all').lower()
        self.job_whitelist = self._parse_job_list(
            os.getenv('LONGJOB_JOB_WHITELIST', '')
        )
        self.job_blacklist = self._parse_job_list(
            os.getenv('LONGJOB_JOB_BLACKLIST', '')
        )
        self.startup_timeout = float(os.getenv('LONGJOB_STARTUP_TIMEOUT', '60.0'))
        self.shutdown_timeout = float(os.getenv('LONGJOB_SHUTDOWN_TIMEOUT', '30.0'))
        self.wait_for_current_task = (
            os.getenv('LONGJOB_WAIT_FOR_CURRENT_TASK', 'true').lower() == 'true'
        )
        self.log_level = os.getenv('LONGJOB_LOG_LEVEL', 'INFO')
        self.log_startup_details = (
            os.getenv('LONGJOB_LOG_STARTUP_DETAILS', 'true').lower() == 'true'
        )
        self.log_job_lifecycle = (
            os.getenv('LONGJOB_LOG_JOB_LIFECYCLE', 'true').lower() == 'true'
        )

        self.logger = logging.getLogger(__name__)

        # Set log level
        if hasattr(logging, self.log_level):
            self.logger.setLevel(getattr(logging, self.log_level))

        # Task storage
        self._jobs: Dict[str, LongJobInterface] = {}
        self._job_tasks: Dict[str, asyncio.Task] = {}

        # Manager state
        self._is_shutdown = False
        self._shutdown_event = asyncio.Event()

        # Statistics
        self.stats = {
            'total_jobs_started': 0,
            'total_jobs_stopped': 0,
            'total_jobs_failed': 0,
            'manager_start_time': get_now_with_timezone(),
        }

        self.logger.info(
            "LongJobManager initialized with max_concurrent_jobs=%d",
            self.max_concurrent_jobs,
        )

        # Auto-discovery flag
        self._auto_discovered = False

    def _parse_job_list(self, job_list_str: str) -> List[str]:
        """
        Parse job list string

        Args:
            job_list_str: Comma-separated job ID string

        Returns:
            List[str]: List of job IDs
        """
        if not job_list_str:
            return []
        return [job.strip() for job in job_list_str.split(',') if job.strip()]

    def should_start_job(self, job_id: str) -> bool:
        """
        Determine whether to start the specified job

        Args:
            job_id: Job ID

        Returns:
            bool: Whether to start the job
        """
        if self.auto_start_mode == 'none':
            return False
        elif self.auto_start_mode == 'all':
            return True
        elif self.auto_start_mode == 'whitelist':
            return job_id in self.job_whitelist
        elif self.auto_start_mode == 'blacklist':
            return job_id not in self.job_blacklist
        else:
            return True

    async def add_job(self, job: LongJobInterface) -> bool:
        """
        Add a long-running job to the manager

        Args:
            job: Long-running job instance to add

        Returns:
            bool: Whether the addition was successful
        """
        if self._is_shutdown:
            self.logger.warning(
                "Cannot add job %s: manager is shutting down", job.job_id
            )
            return False

        if job.job_id in self._jobs:
            self.logger.warning("Job %s already exists in manager", job.job_id)
            return False

        if len(self._jobs) >= self.max_concurrent_jobs:
            self.logger.warning(
                "Cannot add job %s: maximum concurrent jobs (%d) reached",
                job.job_id,
                self.max_concurrent_jobs,
            )
            return False

        self._jobs[job.job_id] = job
        self.logger.info("Job %s added to manager", job.job_id)
        return True

    async def discover_and_add_jobs(self) -> Dict[str, bool]:
        """
        Automatically discover and add all LongJobInterface implementations

        Returns:
            Dict[str, bool]: Addition results for each job
        """
        if self._auto_discovered:
            self.logger.info("Jobs already auto-discovered, skipping")
            return {}

        self.logger.info("Starting auto-discovery of LongJobInterface implementations")

        try:
            # Get all LongJobInterface implementations from DI container
            job_implementations = get_beans_by_type(LongJobInterface)

            results = {}
            for job in job_implementations:
                # Skip LongJobManager itself
                if isinstance(job, LongJobManager):
                    continue

                try:
                    success = await self.add_job(job)
                    results[job.job_id] = success
                    if success:
                        self.logger.info(
                            "Auto-discovered and added job: %s", job.job_id
                        )
                    else:
                        self.logger.warning(
                            "Failed to add auto-discovered job: %s", job.job_id
                        )
                except Exception as e:
                    self.logger.error(
                        "Error adding auto-discovered job %s: %s",
                        getattr(job, 'job_id', 'unknown'),
                        str(e),
                    )
                    results[getattr(job, 'job_id', 'unknown')] = False

            self._auto_discovered = True
            self.logger.info(
                "Auto-discovery completed. Found %d job implementations", len(results)
            )
            return results

        except Exception as e:
            self.logger.error(
                "Error during job auto-discovery: %s", str(e), exc_info=True
            )
            return {}

    async def default_start(
        self, auto_discover: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Default startup process: automatically discover and start long-running jobs allowed by environment variable configuration

        Args:
            auto_discover: Whether to automatically discover jobs (None uses environment variable setting)

        Returns:
            Dict[str, Any]: Startup result statistics
        """
        if self.log_startup_details:
            config_info = {
                'max_concurrent_jobs': self.max_concurrent_jobs,
                'auto_discover': self.auto_discover,
                'auto_start_mode': self.auto_start_mode,
                'job_whitelist': self.job_whitelist,
                'job_blacklist': self.job_blacklist,
            }
            self.logger.info(
                "Starting default startup process with config: %s", config_info
            )
        else:
            self.logger.info("Starting default startup process")

        results = {
            'discovered_jobs': {},
            'started_jobs': {},
            'filtered_jobs': {},
            'total_discovered': 0,
            'total_filtered': 0,
            'total_started': 0,
            'errors': [],
        }

        try:
            # Automatically discover jobs
            should_auto_discover = (
                auto_discover if auto_discover is not None else self.auto_discover
            )
            if should_auto_discover:
                discovered = await self.discover_and_add_jobs()
                results['discovered_jobs'] = discovered
                results['total_discovered'] = len(discovered)

            # Filter jobs to start based on environment variable configuration
            jobs_to_start = {}
            for job_id, job in self._jobs.items():
                if self.should_start_job(job_id):
                    jobs_to_start[job_id] = job
                else:
                    results['filtered_jobs'][job_id] = 'excluded_by_config'
                    if self.log_startup_details:
                        self.logger.info("Job %s excluded by configuration", job_id)

            results['total_filtered'] = len(results['filtered_jobs'])

            # Start filtered jobs
            if jobs_to_start:
                started = {}
                for job_id in jobs_to_start:
                    try:
                        success = await self.start_job(job_id)
                        started[job_id] = success
                        if success and self.log_job_lifecycle:
                            self.logger.info("Successfully started job: %s", job_id)
                    except Exception as e:
                        started[job_id] = False
                        error_msg = f"Failed to start job {job_id}: {str(e)}"
                        self.logger.error(error_msg)
                        results['errors'].append(error_msg)

                results['started_jobs'] = started
                results['total_started'] = sum(
                    1 for success in started.values() if success
                )
            else:
                self.logger.warning("No jobs found to start after filtering")

            if self.log_startup_details:
                self.logger.info(
                    "Default startup completed: discovered=%d, filtered=%d, started=%d",
                    results['total_discovered'],
                    results['total_filtered'],
                    results['total_started'],
                )
            else:
                self.logger.info(
                    "Default startup completed: started=%d jobs",
                    results['total_started'],
                )

        except Exception as e:
            error_msg = f"Error during default startup: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            results['errors'].append(error_msg)

        return results

    async def start_job(self, job_id: str) -> bool:
        """
        Start the specified long-running job

        Args:
            job_id: Job ID

        Returns:
            bool: Whether the start was successful
        """
        if self._is_shutdown:
            self.logger.warning("Cannot start job %s: manager is shutting down", job_id)
            return False

        if job_id not in self._jobs:
            self.logger.error("Job %s not found in manager", job_id)
            return False

        job = self._jobs[job_id]

        if job.is_running():
            self.logger.warning("Job %s is already running", job_id)
            return False

        try:
            # Create task and start
            task = asyncio.create_task(self._run_job_with_monitoring(job))
            self._job_tasks[job_id] = task

            self.stats['total_jobs_started'] += 1
            self.logger.info("Job %s started successfully", job_id)
            return True

        except Exception as e:
            self.stats['total_jobs_failed'] += 1
            self.logger.error(
                "Failed to start job %s: %s", job_id, str(e), exc_info=True
            )
            return False

    async def stop_job(
        self, job_id: str, timeout: float = 30.0, wait_for_current_task: bool = True
    ) -> bool:
        """
        Stop the specified long-running job

        Args:
            job_id: Job ID
            timeout: Stop timeout in seconds
            wait_for_current_task: Whether to wait for current task to complete

        Returns:
            bool: Whether the stop was successful
        """
        if job_id not in self._jobs:
            self.logger.error("Job %s not found in manager", job_id)
            return False

        job = self._jobs[job_id]

        if not job.is_running():
            self.logger.warning("Job %s is not running", job_id)
            return True

        try:
            # Stop job (supports graceful shutdown)
            if (
                hasattr(job, 'shutdown')
                and 'wait_for_current_task' in job.shutdown.__code__.co_varnames
            ):
                await asyncio.wait_for(
                    job.shutdown(
                        timeout=timeout, wait_for_current_task=wait_for_current_task
                    ),
                    timeout=timeout + 5.0,  # Allow some extra time
                )
            else:
                await asyncio.wait_for(job.shutdown(), timeout=timeout)

            # Wait for task to complete
            if job_id in self._job_tasks:
                task = self._job_tasks[job_id]
                if not task.done():
                    try:
                        await asyncio.wait_for(task, timeout=5.0)
                    except asyncio.TimeoutError:
                        self.logger.warning(
                            "Task for job %s did not complete, cancelling", job_id
                        )
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

                del self._job_tasks[job_id]

            self.stats['total_jobs_stopped'] += 1
            self.logger.info("Job %s stopped successfully", job_id)
            return True

        except Exception as e:
            self.logger.error(
                "Failed to stop job %s: %s", job_id, str(e), exc_info=True
            )
            return False

    async def remove_job(self, job_id: str) -> bool:
        """
        Remove the specified long-running job from the manager

        Args:
            job_id: Job ID

        Returns:
            bool: Whether the removal was successful
        """
        if job_id not in self._jobs:
            self.logger.error("Job %s not found in manager", job_id)
            return False

        job = self._jobs[job_id]

        # If job is running, stop it first
        if job.is_running():
            success = await self.stop_job(job_id)
            if not success:
                self.logger.error("Failed to stop job %s before removal", job_id)
                return False

        # Remove job
        del self._jobs[job_id]
        self.logger.info("Job %s removed from manager", job_id)
        return True

    async def start_all_jobs(self) -> Dict[str, bool]:
        """
        Start all non-running jobs

        Returns:
            Dict[str, bool]: Start results for each job
        """
        results = {}

        for job_id, job in self._jobs.items():
            if not job.is_running():
                results[job_id] = await self.start_job(job_id)
            else:
                results[job_id] = True  # Already running

        return results

    async def stop_all_jobs(self, timeout: float = 30.0) -> Dict[str, bool]:
        """
        Stop all running jobs

        Args:
            timeout: Stop timeout per job in seconds

        Returns:
            Dict[str, bool]: Stop results for each job
        """
        results = {}

        # Concurrently stop all jobs
        stop_tasks = []
        running_jobs = []

        for job_id, job in self._jobs.items():
            if job.is_running():
                stop_tasks.append(self.stop_job(job_id, timeout))
                running_jobs.append(job_id)
            else:
                results[job_id] = True  # Already stopped

        if stop_tasks:
            stop_results = await asyncio.gather(*stop_tasks, return_exceptions=True)

            for job_id, result in zip(running_jobs, stop_results):
                if isinstance(result, Exception):
                    self.logger.error(
                        "Exception stopping job %s: %s", job_id, str(result)
                    )
                    results[job_id] = False
                else:
                    results[job_id] = result

        return results

    async def shutdown(self, timeout: float = 60.0) -> None:
        """
        Shut down the manager and stop all jobs

        Args:
            timeout: Total shutdown timeout in seconds
        """
        if self._is_shutdown:
            self.logger.warning("Manager is already shutting down")
            return

        self.logger.info("Starting manager shutdown")
        self._is_shutdown = True

        try:
            # Stop all jobs
            await asyncio.wait_for(
                self.stop_all_jobs(timeout=timeout / 2), timeout=timeout
            )

        except asyncio.TimeoutError:
            self.logger.warning(
                "Manager shutdown timeout, some jobs may not have stopped gracefully"
            )

        except Exception as e:
            self.logger.error(
                "Error during manager shutdown: %s", str(e), exc_info=True
            )

        finally:
            # Cancel all remaining tasks
            for job_id, task in self._job_tasks.items():
                if not task.done():
                    self.logger.warning("Cancelling task for job %s", job_id)
                    task.cancel()

            # Wait for all tasks to finish cancellation
            if self._job_tasks:
                await asyncio.gather(*self._job_tasks.values(), return_exceptions=True)

            self._job_tasks.clear()
            self._shutdown_event.set()

            self.logger.info("Manager shutdown completed")

    def get_job_status(self, job_id: str) -> Optional[LongJobStatus]:
        """
        Get the status of the specified job

        Args:
            job_id: Job ID

        Returns:
            Optional[LongJobStatus]: Job status, returns None if job does not exist
        """
        if job_id not in self._jobs:
            return None

        return self._jobs[job_id].get_status()

    def get_all_jobs_status(self) -> Dict[str, LongJobStatus]:
        """
        Get the status of all jobs

        Returns:
            Dict[str, LongJobStatus]: Mapping from job ID to status
        """
        return {job_id: job.get_status() for job_id, job in self._jobs.items()}

    def get_running_jobs(self) -> List[str]:
        """
        Get a list of all running job IDs

        Returns:
            List[str]: List of running job IDs
        """
        return [job_id for job_id, job in self._jobs.items() if job.is_running()]

    def get_job_stats(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for the specified job

        Args:
            job_id: Job ID

        Returns:
            Optional[Dict[str, Any]]: Job statistics, returns None if job does not exist or does not support statistics
        """
        if job_id not in self._jobs:
            return None

        job = self._jobs[job_id]

        # Check if job supports statistics
        if hasattr(job, 'get_stats'):
            return job.get_stats()

        return {
            'job_id': job_id,
            'status': job.get_status().value,
            'is_running': job.is_running(),
        }

    def get_manager_stats(self) -> Dict[str, Any]:
        """
        Get manager statistics

        Returns:
            Dict[str, Any]: Manager statistics
        """
        stats = self.stats.copy()
        stats.update(
            {
                'total_jobs': len(self._jobs),
                'running_jobs': len(self.get_running_jobs()),
                'is_shutdown': self._is_shutdown,
                'uptime': (
                    get_now_with_timezone() - stats['manager_start_time']
                ).total_seconds(),
            }
        )

        return stats

    async def _run_job_with_monitoring(self, job: LongJobInterface) -> None:
        """
        Run job with monitoring

        Args:
            job: Job to run
        """
        job_id = job.job_id

        try:
            self.logger.info("Starting monitoring for job %s", job_id)

            # Start job
            await job.start()

            # Monitor job status until job stops or manager shuts down
            while not self._is_shutdown and job.is_running():
                await asyncio.sleep(1.0)

            # If manager is shutting down, ensure job also stops
            if self._is_shutdown and job.is_running():
                self.logger.info("Shutting down job %s due to manager shutdown", job_id)
                await job.shutdown()

        except Exception as e:
            self.stats['total_jobs_failed'] += 1
            self.logger.error("Job %s failed: %s", job_id, str(e), exc_info=True)

            # Attempt to clean up job
            try:
                if job.is_running():
                    await job.shutdown()
            except Exception as cleanup_error:
                self.logger.error(
                    "Error during cleanup of failed job %s: %s",
                    job_id,
                    str(cleanup_error),
                    exc_info=True,
                )

        finally:
            self.logger.info("Monitoring ended for job %s", job_id)

    def __len__(self) -> int:
        """Return the number of jobs in the manager"""
        return len(self._jobs)

    def __contains__(self, job_id: str) -> bool:
        """Check if job exists in the manager"""
        return job_id in self._jobs
