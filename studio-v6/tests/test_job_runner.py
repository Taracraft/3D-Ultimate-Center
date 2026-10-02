from core.job_runner import BackgroundJobRunner, JobRequest


async def test_background_job_runner_executes_jobs_in_order() -> None:
    runner = BackgroundJobRunner(max_parallel_jobs=1)
    results: list[int] = []

    async def append(value: int) -> None:
        results.append(value)

    await runner.submit(JobRequest("one", lambda: append(1)))
    await runner.submit(JobRequest("two", lambda: append(2)))
    await runner.join()
    await runner.close()

    assert results == [1, 2]