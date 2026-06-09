"""이동평균 골든크로스 백테스트 엔진.

look-ahead bias 방지:
  날짜 T의 시그널 산출 시 data[0:T+1] 만 사용한다.
  매매 체결 가격은 시그널 발생 당일의 종가(close)로 가정한다.

수수료 기본값 (국내):
  매수: 0.015%  매도: 0.015% + 증권거래세 0.20% = 0.215%
  합계: ~0.23%

성과 지표:
  - 총 수익률 (%)
  - 최대 낙폭 (MDD, %)
  - 샤프 비율 (일별 수익률 × √252, 무위험이자율 0%)
  - 승률 (%)
  - 총 거래 횟수
"""
import math
from dataclasses import dataclass, field

import pandas as pd

from src.strategy.base import Action
from src.strategy.golden_cross import GoldenCrossStrategy


@dataclass
class Trade:
    date: str
    side: str       # "BUY" | "SELL" | "SELL(강제)"
    price: float
    qty: int
    fee: float
    pnl: float = 0.0  # SELL 시 실현 손익


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series)
    initial_capital: float = 0.0
    final_capital: float = 0.0

    @property
    def total_return_pct(self) -> float:
        if self.initial_capital == 0:
            return 0.0
        return (self.final_capital / self.initial_capital - 1) * 100

    @property
    def max_drawdown_pct(self) -> float:
        if self.equity_curve.empty:
            return 0.0
        peak = self.equity_curve.cummax()
        drawdown = (self.equity_curve - peak) / peak * 100
        return float(drawdown.min())

    @property
    def sharpe_ratio(self) -> float:
        if len(self.equity_curve) < 2:
            return 0.0
        daily_ret = self.equity_curve.pct_change().dropna()
        std = daily_ret.std()
        if std == 0:
            return 0.0
        return float(daily_ret.mean() / std * math.sqrt(252))

    @property
    def win_rate_pct(self) -> float:
        sells = [t for t in self.trades if "SELL" in t.side]
        if not sells:
            return 0.0
        wins = sum(1 for t in sells if t.pnl > 0)
        return wins / len(sells) * 100

    @property
    def trade_count(self) -> int:
        return len([t for t in self.trades if "SELL" in t.side])


class BacktestEngine:
    def __init__(
        self,
        strategy: GoldenCrossStrategy,
        buy_fee_rate: float = 0.00015,   # 0.015%
        sell_fee_rate: float = 0.00215,  # 0.015% + 증권거래세 0.20%
    ) -> None:
        self._strategy = strategy
        self._buy_fee = buy_fee_rate
        self._sell_fee = sell_fee_rate

    def run(self, ohlcv: pd.DataFrame, initial_capital: float = 10_000_000) -> BacktestResult:
        """ohlcv: date, open, high, low, close, volume 컬럼. 오름차순 정렬 필요."""
        if ohlcv.empty:
            return BacktestResult(initial_capital=initial_capital, final_capital=initial_capital)

        ohlcv = ohlcv.reset_index(drop=True)
        cash = initial_capital
        position_qty = 0
        entry_price = 0.0
        trades: list[Trade] = []
        equity: list[float] = []

        for i in range(len(ohlcv)):
            row = ohlcv.iloc[i]
            price = float(row["close"])
            date_val = row["date"]
            date = str(date_val.date() if hasattr(date_val, "date") else date_val)

            # look-ahead bias 방지 — 현재 행까지만 전달
            signals = self._strategy.generate_signals(ohlcv.iloc[: i + 1])
            signal = signals.get(self._strategy.ticker)

            if signal and signal.action == Action.BUY and position_qty == 0:
                qty = int(cash / (price * (1 + self._buy_fee)))
                if qty > 0:
                    fee = price * qty * self._buy_fee
                    cash -= price * qty + fee
                    position_qty = qty
                    entry_price = price
                    trades.append(Trade(date=date, side="BUY", price=price, qty=qty, fee=fee))

            elif signal and signal.action == Action.SELL and position_qty > 0:
                fee = price * position_qty * self._sell_fee
                proceeds = price * position_qty - fee
                pnl = proceeds - entry_price * position_qty
                cash += proceeds
                trades.append(Trade(date=date, side="SELL", price=price, qty=position_qty, fee=fee, pnl=pnl))
                position_qty = 0
                entry_price = 0.0

            equity.append(cash + position_qty * price)

        # 미청산 포지션은 마지막 종가로 강제 청산
        if position_qty > 0:
            final_price = float(ohlcv.iloc[-1]["close"])
            fee = final_price * position_qty * self._sell_fee
            proceeds = final_price * position_qty - fee
            pnl = proceeds - entry_price * position_qty
            last_date_val = ohlcv.iloc[-1]["date"]
            last_date = str(last_date_val.date() if hasattr(last_date_val, "date") else last_date_val)
            trades.append(Trade(date=last_date, side="SELL(강제)", price=final_price, qty=position_qty, fee=fee, pnl=pnl))
            cash += proceeds
            equity[-1] = cash

        equity_series = pd.Series(equity, index=ohlcv["date"])
        return BacktestResult(
            trades=trades,
            equity_curve=equity_series,
            initial_capital=initial_capital,
            final_capital=cash,
        )
