from fastapi import FastAPI


app = FastAPI(title="Role-Bounded GitHub Agent Demo")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
