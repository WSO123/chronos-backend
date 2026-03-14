from app.core.celery import celery_app
import time

@celery_app.task(name="example_task")
def example_task(word: str):
    time.sleep(5)
    return f"Hello {word}"
