from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

import pandas as pd


class Action(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class Signal:
    action: Action
    qty: int
    reason: str


class Strategy(ABC):
    @abstractmethod
    def generate_signals(self, market_data: pd.DataFrame) -> dict[str, Signal]:
        """종목코드 -> Signal(action=BUY/SELL/HOLD, qty, reason) 매핑 반환"""
