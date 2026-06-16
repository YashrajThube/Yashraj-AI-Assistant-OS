import uvicorn

from app.core.config import API_HOST, API_PORT
from app.main import app


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=API_HOST, port=API_PORT, reload=False)
