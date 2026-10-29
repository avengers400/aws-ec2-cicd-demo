
from fastapi import FastAPI

app = FastAPI(
    title="AWS EC2 CI/CD Demo",
    version="1.0.0",
)


@app.get("/")
def home():
    return {
        "application": "AWS EC2 CI/CD Demo",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/api/info")
def info():
    return {
        "platform": "AWS",
        "deployment": "GitHub Actions",
        "image_registry": "Amazon ECR",
        "container": "Docker",
    }
