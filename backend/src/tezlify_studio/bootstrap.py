import uvicorn
from tezlify_studio.infrastructure.configuration.settings import settings

def start_server():
    print(f"🚀 Starting {settings.app_name} on http://{settings.host}:{settings.backend_port}")
    uvicorn.run(
        "tezlify_studio.presentation.api.app:app",
        host=settings.host,
        port=settings.backend_port,
        reload=settings.debug,
        log_level="info",
    )

if __name__ == "__main__":
    start_server()
