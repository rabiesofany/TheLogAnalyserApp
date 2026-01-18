"""Script to run the API server."""

import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))

    print(f"Starting PLC Error Classification API on {host}:{port}")
    print(f"API Documentation: http://{host}:{port}/docs")

    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=True
    )
