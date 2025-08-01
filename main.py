from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from rooms import router
from game import manager

import asyncio

app = FastAPI()
app.include_router(router)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
async def startup_event():
    async def cleaner_task():
        while True:
            manager.cleanup_finished_rooms()
            await asyncio.sleep(300)  # 5 минут

    async def logger_task():
        while True:
            # manager.print_state()
            await asyncio.sleep(150)  # 2.5 минут

    asyncio.create_task(cleaner_task())
    asyncio.create_task(logger_task())
