# Agentic Service Buyer

This workspace now contains:

- A redesigned HTML/CSS/JS frontend for the autonomous buyer dashboard
- A Python backend in `backend/app.py`
- Gemini-ready intent generation endpoint
- Algorand-style service registry, spend policy, confirmation flow, and persistent receipt log

## Run locally

1. Make sure Python 3.10+ is installed and available on your PATH.
2. Copy `.env.example` to `.env` and fill in your values.
3. Export the variables in your shell or load them with your preferred tool.
4. Start the backend:

```powershell
python backend/app.py
```

5. Open `http://127.0.0.1:8000/` once the backend is running.

## What is implemented

- Service registry cards with pricing, payment addresses, and settlement metadata
- Spend cap policy enforcement before payment
- Simulated Algorand payment confirmation timeline
- Persistent receipts stored in `backend/storage.json`
- Gemini buyer brief generation through `POST /api/gemini/brief`
- Config surface for Algod, Indexer, payment wallet, and Pinata gateway

## Notes

- The backend uses Python standard library only, so it does not require Flask or FastAPI.
- Purchases are currently simulated to match the hackathon flow in your brief; swap the confirmation and payment sections with real Algorand SDK logic when you connect this UI into your AlgoKit workspace.
- Your current shell does not expose `python`, so the server could not be run from this environment yet.
