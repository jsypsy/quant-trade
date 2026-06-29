"""이동평균 골든크로스 / 데드크로스 전략.

진입 방식 두 가지:
- 크로스 기반(state_entry=False, 기본): MA(short)가 MA(long)±band 를 "돌파하는 순간"만 신호.
    · 골든크로스 → BUY / 데드크로스 → SELL. 보수적(이미 추세인 종목은 못 잡음).
- 상태 기반(state_entry=True, 공격적): 현재 정배열이면 BUY, 역배열이면 SELL.
    · MA(short) > MA(long)*(1+band) → BUY (이미 오르는 중인 종목도 즉시 진입)
    · MA(short) < MA(long)*(1-band) → SELL

band_pct 는 노이즈 whipsaw 억제용 최소 격차. 0 이면 단순 비교.

qty 는 플레이스홀더(=1). 실제 수량은 risk.guard 에서 포지션/한도 기준으로 결정.
"""
import pandas as pd

from src.strategy.base import Action, Signal, Strategy


class GoldenCrossStrategy(Strategy):
    def __init__(
        self,
        ticker: str,
        short_window: int = 5,
        long_window: int = 20,
        qty: int = 1,
        bar_type: str = "daily",    # "daily" | "minute"
        band_pct: float = 0.0,      # 최소 격차 (0 = 단순 비교)
        state_entry: bool = False,  # True: 정배열/역배열 '상태'로 진입 (크로스 순간 불필요, 공격적)
        exit_on_reversal: bool = True,  # False: 역배열에도 매도 안 함(churn 제거 — 청산은 손절/익절에 위임)
    ) -> None:
        if short_window >= long_window:
            raise ValueError(f"short_window({short_window}) must be < long_window({long_window})")
        self.ticker = ticker
        self.short_window = short_window
        self.long_window = long_window
        self.qty = qty
        self.bar_type = bar_type
        self.band_pct = band_pct
        self.state_entry = state_entry
        self.exit_on_reversal = exit_on_reversal

    def generate_signals(self, ohlcv: pd.DataFrame) -> dict[str, Signal]:
        if len(ohlcv) < self.long_window + 1:
            return {
                self.ticker: Signal(
                    Action.HOLD,
                    0,
                    f"데이터 부족 ({len(ohlcv)}행 < 필요 {self.long_window + 1}행)",
                )
            }

        close = ohlcv["close"]
        ma_s = close.rolling(self.short_window).mean()
        ma_l = close.rolling(self.long_window).mean()

        prev_s, curr_s = ma_s.iloc[-2], ma_s.iloc[-1]
        prev_l, curr_l = ma_l.iloc[-2], ma_l.iloc[-1]

        # 노이즈 억제용 밴드 — 장기 MA 위/아래로 band_pct 만큼 벌어져야 신호 발생
        prev_upper, curr_upper = prev_l * (1 + self.band_pct), curr_l * (1 + self.band_pct)
        prev_lower, curr_lower = prev_l * (1 - self.band_pct), curr_l * (1 - self.band_pct)

        if self.state_entry:
            # 상태 기반(공격적): 크로스 순간이 아니라 현재 정배열/역배열로 판단
            if curr_s > curr_upper:
                action = Action.BUY
                reason = f"정배열 MA{self.short_window}({curr_s:.0f}) > MA{self.long_window}({curr_l:.0f})"
            elif curr_s < curr_lower and self.exit_on_reversal:
                action = Action.SELL
                reason = f"역배열 MA{self.short_window}({curr_s:.0f}) < MA{self.long_window}({curr_l:.0f})"
            else:
                # 역배열이어도 exit_on_reversal=False 면 보유 유지(청산은 손절/익절이 담당)
                reason = f"HOLD — MA{self.short_window}({curr_s:.0f}) / MA{self.long_window}({curr_l:.0f}) (보유유지)"
                action = Action.HOLD
        elif prev_s <= prev_upper and curr_s > curr_upper:
            action = Action.BUY
            reason = f"골든크로스 MA{self.short_window}({curr_s:.0f}) > MA{self.long_window}({curr_l:.0f})"
        elif prev_s >= prev_lower and curr_s < curr_lower:
            action = Action.SELL
            reason = f"데드크로스 MA{self.short_window}({curr_s:.0f}) < MA{self.long_window}({curr_l:.0f})"
        else:
            pos = "위" if curr_s > curr_l else "아래"
            reason = f"HOLD — MA{self.short_window}({curr_s:.0f})이 MA{self.long_window}({curr_l:.0f}) {pos}"
            action = Action.HOLD

        return {self.ticker: Signal(action, self.qty if action != Action.HOLD else 0, reason)}
