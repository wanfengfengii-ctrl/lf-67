from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.routes import router

app = FastAPI(title="漕船粮包堆码模拟系统", version="1.0.0")

app.include_router(router, prefix="/api")

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")
