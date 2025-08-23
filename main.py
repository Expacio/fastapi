from typing import Optional

from fastapi import FastAPI

app = FastAPI()


@app.get("/ponger")
async def root():
    return {"message": "Thanks lmao."}

@app.get("/items/{item_id}")
def read_item(item_id: int, q):
    return {"item_id": item_id, "q": q}