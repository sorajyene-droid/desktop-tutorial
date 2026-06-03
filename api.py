"""FastAPI layer exposing the SecuredExchange over HTTP + WebSocket.

Run with:  uvicorn api:app

Auth: POST /login returns a JWT; pass it as `Authorization: Bearer <token>`.
The JWT signing key is read from the TRADING_SECRET_KEY environment variable
(never hard-coded).
"""
from __future__ import annotations

import asyncio
import os
from typing import Dict, List, Optional, Set

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from login_auth import AuthError, InvalidCredentials
from price_limit import OrderRejected
from secured_exchange import SecuredExchange
from trade_auth import TradeAuthError


# ----- WebSocket hub -----------------------------------------------------
class Hub:
    """Per-symbol set of subscribed WebSockets."""

    def __init__(self):
        self._subs: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, symbol: str, ws: WebSocket) -> None:
        async with self._lock:
            self._subs.setdefault(symbol, set()).add(ws)

    async def unsubscribe(self, symbol: str, ws: WebSocket) -> None:
        async with self._lock:
            subs = self._subs.get(symbol)
            if subs:
                subs.discard(ws)
                if not subs:
                    self._subs.pop(symbol, None)

    async def broadcast(self, symbol: str, message: dict) -> None:
        async with self._lock:
            targets = list(self._subs.get(symbol, set()))
        dead = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.unsubscribe(symbol, ws)


# ----- request models ----------------------------------------------------
class RegisterReq(BaseModel):
    email: str
    login_password: str
    trade_password: str


class LoginReq(BaseModel):
    email: str
    login_password: str


class OrderReq(BaseModel):
    trade_password: str
    symbol: str
    side: str
    price: int
    quantity: int


class PriceLimitReq(BaseModel):
    symbol: str
    reference: int
    ratio: float = 0.10
    amount: Optional[int] = None


def _secret_key() -> str:
    key = os.environ.get("TRADING_SECRET_KEY")
    if not key:
        # Do not ship a default secret. Fail loudly instead.
        raise RuntimeError(
            "TRADING_SECRET_KEY environment variable is required. "
            "Example: export TRADING_SECRET_KEY=$(openssl rand -hex 32)"
        )
    return key


def create_app(exchange: Optional[SecuredExchange] = None) -> FastAPI:
    app = FastAPI(title="Order-book Trading System")
    ex = exchange or SecuredExchange(
        secret_key=_secret_key(),
        db_path=os.environ.get("TRADING_DB_PATH"),
    )
    hub = Hub()
    app.state.exchange = ex
    app.state.hub = hub

    def bearer_token(authorization: Optional[str] = Header(None)) -> str:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        return authorization.split(" ", 1)[1].strip()

    def current_user(token: str = Depends(bearer_token)) -> str:
        try:
            return ex.user_from_token(token)
        except InvalidCredentials as e:
            raise HTTPException(status_code=401, detail=str(e))

    # ----- HTTP endpoints ------------------------------------------------
    @app.post("/register")
    def register(req: RegisterReq):
        try:
            email = ex.register(req.email, req.login_password, req.trade_password)
        except AuthError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"email": email}

    @app.post("/login")
    def login(req: LoginReq):
        try:
            token = ex.login_user(req.email, req.login_password)
        except AuthError as e:
            raise HTTPException(status_code=401, detail=str(e))
        return {"token": token}

    @app.post("/order")
    async def order(req: OrderReq, token: str = Depends(bearer_token)):
        try:
            result = ex.place_order(
                token, req.trade_password, req.symbol, req.side, req.price, req.quantity
            )
        except (InvalidCredentials,) as e:
            raise HTTPException(status_code=401, detail=str(e))
        except TradeAuthError as e:
            raise HTTPException(status_code=403, detail=str(e))
        except OrderRejected as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

        # broadcast updated book + any trades to subscribers of this symbol
        await hub.broadcast(
            req.symbol,
            {
                "type": "update",
                "symbol": req.symbol,
                "depth": ex.depth(req.symbol),
                "trades": [t.to_dict() for t in result.trades],
            },
        )
        return result.to_dict()

    @app.get("/depth/{symbol}")
    def depth(symbol: str):
        return ex.depth(symbol)

    @app.get("/chart/{symbol}")
    def chart(symbol: str, timeframe: str = "1d"):
        try:
            return ex.chart(symbol, timeframe)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/portfolio")
    def portfolio(user: str = Depends(current_user)):
        return ex.portfolio(user)

    @app.get("/history/{symbol}")
    def history(symbol: str):
        return {"symbol": symbol, "trades": ex.trade_history(symbol)}

    @app.get("/symbol/{symbol}")
    def symbol_info(symbol: str):
        info = ex.symbol_info(symbol)
        if info is None:
            raise HTTPException(status_code=404, detail="symbol not found")
        return info

    @app.post("/price_limit")
    def price_limit(req: PriceLimitReq, user: str = Depends(current_user)):
        band = ex.set_price_limit(req.symbol, req.reference, ratio=req.ratio, amount=req.amount)
        return {
            "symbol": req.symbol,
            "reference": band.reference,
            "lower": band.lower,
            "upper": band.upper,
        }

    # ----- WebSocket -----------------------------------------------------
    @app.websocket("/ws/{symbol}")
    async def ws_symbol(websocket: WebSocket, symbol: str):
        await websocket.accept()
        await hub.subscribe(symbol, websocket)
        # snapshot on connect
        await websocket.send_json(
            {"type": "snapshot", "symbol": symbol, "depth": ex.depth(symbol)}
        )
        try:
            while True:
                # we don't expect inbound messages; this keeps the socket open
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await hub.unsubscribe(symbol, websocket)

    return app


# module-level app for `uvicorn api:app`
app = None
if os.environ.get("TRADING_SECRET_KEY"):
    app = create_app()
