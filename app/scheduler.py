from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.jobs.my_job import my_job


scheduler = AsyncIOScheduler()


def start_scheduler():
    scheduler.add_job(
        my_job,
        trigger="interval",
        minutes=10,
        id="my_job",
        replace_existing=True,
    )

    scheduler.start()


def stop_scheduler():
    scheduler.shutdown()