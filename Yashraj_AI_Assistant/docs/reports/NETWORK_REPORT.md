# Network Report

Date: 2026-06-13

Validated local ports

- Backend: `127.0.0.1:5000` or alternate debug port `5001/5002`
- Frontend: `localhost:5173`

Proxy and API configuration

- Frontend Vite proxy forwards `/api` requests to `http://127.0.0.1:5000` by default.
- `VITE_API_BASE_URL` can override the API base if needed.

Known issue observed during investigation

- Port 5000 was already occupied by another backend process at one point, which can cause frontend requests to fail and display the generic fallback.

Recommended fix if the issue reappears

1. Stop the old backend process.
2. Restart the backend on the expected port.
3. Confirm the frontend proxy or `VITE_API_BASE_URL` is pointing at the same backend host/port.
