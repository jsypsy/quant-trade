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


# ──────────────────────────────────────────────────────────────────────────
# 스윙형 브라켓 백테스트 (정배열 진입 / 손절·익절 청산) — 라이브 전략과 동일 구조
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class CostModel:
    fee_rate: float = 0.00015   # 수수료 (매수·매도 각)
    tax_rate: float = 0.0018    # 거래세 (매도)
    slippage: float = 0.001     # 슬리피지 (매수·매도 각)

    @property
    def round_trip(self) -> float:
        """왕복 총비용(수익률 차감 분율). 기본 ≈ 0.41%."""
        return self.fee_rate * 2 + self.tax_rate + self.slippage * 2


@dataclass
class BracketResult:
    n_trades: int = 0
    win_rate: float = 0.0
    total_return: float = 0.0   # 누적(복리) 순수익률
    avg_win: float = 0.0
    avg_loss: float = 0.0
    mdd: float = 0.0
    total_cost: float = 0.0
    n_tp: int = 0               # 익절 횟수
    n_sl: int = 0               # 손절 횟수

    def line(self) -> str:
        return (
            f"거래 {self.n_trades}회(익절 {self.n_tp}/손절 {self.n_sl}) | "
            f"승률 {self.win_rate*100:.0f}% | 순수익 {self.total_return*100:+.2f}% | "
            f"MDD {self.mdd*100:.1f}% | 평균익 {self.avg_win*100:+.2f}% 평균손 {self.avg_loss*100:+.2f}%"
        )


def backtest_bracket(
    ohlcv: pd.DataFrame,
    *,
    short: int = 3,
    long: int = 10,
    band_pct: float = 0.001,
    take_profit: float = 0.04,
    stop_loss: float = 0.02,
    cost: CostModel | None = None,
) -> BracketResult:
    """정배열(state_entry) 진입 → 익절/손절 청산. 봉 고가/저가로 도달 판정.

    라이브 스윙 전략(exit_on_reversal=False + PositionMonitor 손절/익절)과 동일 구조.
    """
    cost = cost or CostModel()
    ohlcv = ohlcv.reset_index(drop=True)
    strat = GoldenCrossStrategy(
        "BT", short_window=short, long_window=long, bar_type="daily",
        band_pct=band_pct, state_entry=True, exit_on_reversal=False,
    )
    close = ohlcv["close"].to_numpy(dtype=float)
    high = ohlcv["high"].to_numpy(dtype=float)
    low = ohlcv["low"].to_numpy(dtype=float)
    n = len(ohlcv)

    rets: list[float] = []
    reasons: list[str] = []
    in_pos = False
    entry = 0.0

    for i in range(long + 1, n):
        if not in_pos:
            if strat.generate_signals(ohlcv.iloc[: i + 1])["BT"].action == Action.BUY:
                in_pos, entry = True, close[i]
        else:
            tp, sl = entry * (1 + take_profit), entry * (1 - stop_loss)
            if low[i] <= sl:          # 보수적: 손절 우선
                rets.append((sl / entry - 1) - cost.round_trip); reasons.append("손절"); in_pos = False
            elif high[i] >= tp:
                rets.append((tp / entry - 1) - cost.round_trip); reasons.append("익절"); in_pos = False
    if in_pos:
        rets.append((close[n - 1] / entry - 1) - cost.round_trip); reasons.append("장끝")

    if not rets:
        return BracketResult()
    equity = peak = 1.0
    mdd = 0.0
    for r in rets:
        equity *= (1 + r)
        peak = max(peak, equity)
        mdd = min(mdd, equity / peak - 1)
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    return BracketResult(
        n_trades=len(rets),
        win_rate=len(wins) / len(rets),
        total_return=equity - 1,
        avg_win=sum(wins) / len(wins) if wins else 0.0,
        avg_loss=sum(losses) / len(losses) if losses else 0.0,
        mdd=mdd,
        total_cost=cost.round_trip * len(rets),
        n_tp=reasons.count("익절"),
        n_sl=reasons.count("손절"),
    )
