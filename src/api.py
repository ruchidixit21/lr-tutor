from fastapi import FastAPI

app = FastAPI(title="LSAT Tutor API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# TODO: Phase 1 — GET /retrieve
# TODO: Phase 2 — POST /generate, POST /score
# TODO: Phase 3 — POST /session, POST /session/{id}/answer, GET /session/{id}/hint
