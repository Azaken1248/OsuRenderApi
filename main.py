from src.api.app import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    from src.core.config import get_settings
    
    settings = get_settings()

    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
        log_level="info",
    )
