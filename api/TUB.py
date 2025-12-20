# api/TUB.py
# Launches USER + ADMIN servers together

import multiprocessing
import uvicorn
import os

def run_user_server():
    uvicorn.run(
        "api.api_server:app",
        host="0.0.0.0",
        port=int(os.getenv("USER_PORT", 8000)),
        reload=False,
    )

def run_admin_server():
    uvicorn.run(
        "api.admin_server:app",
        host="0.0.0.0",
        port=int(os.getenv("ADMIN_PORT", 8001)),
        reload=False,
    )

if __name__ == "__main__":
    user = multiprocessing.Process(target=run_user_server)
    admin = multiprocessing.Process(target=run_admin_server)

    user.start()
    admin.start()

    user.join()
    admin.join()
