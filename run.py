import uvicorn
import os
import sys

# Ensure current working directory is on python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.config import settings

def main():
    print(f"Starting Urja Meter Ops Gateway API on http://{settings.host}:{settings.port}")
    print(f"  • Interactive Swagger Docs: http://localhost:{settings.port}/docs")
    print(f"  • Scalar Reference Docs:   http://localhost:{settings.port}/scalar")
    print(f"  • ReDoc Documentation:     http://localhost:{settings.port}/redoc")
    print(f"  • Modern Web Client UI:    http://localhost:{settings.port}/ui")
    print(f"  • OpenAPI Specification:   http://localhost:{settings.port}/openapi.json")

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )

if __name__ == "__main__":
    main()
