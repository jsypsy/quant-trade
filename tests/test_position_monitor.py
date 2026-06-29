"""PositionMonitor 단위 테스트."""
from datetime import datetime
from zoneinfo import ZoneInfo

from src.portfolio.account import Position
from src.risk.position_monitor import PositionMonitor

_KST = ZoneInfo("Asia/Seoul")

# 테스트용 고정 한도 (settings 와 독립)
MONITOR = PositionMonitor(stop_loss_pct=2.0, take_profit_pct=4.0)

MIDDAY = datetime(2026, 6, 10, 11, 0, tzinfo=_KST)
AFTER_EOD = datetime(2026, 6, 10, 15, 21, tzinfo=_KST)


def make_position(pnl_rate: float, qty: int = 10, orderable_qty: int | None = None) -> Position:
    return Position(
        ticker="005930", name="삼성전자", qty=qty,
        orderable_qty=qty if orderable_qty is None else orderable_qty,
        avg_price=50_000, current_price=int(50_000 * (1 + pnl_rate / 100)),
        current_value=int(50_000 * qty * (1 + pnl_rate / 100)),
        purchase_amount=50_000 * qty,
        pnl=int(50_000 * qty * pnl_rate / 100), pnl_rate=pnl_rate,
    )


# ------------------------------------------------------------------
# 손절 / 익절
# ------------------------------------------------------------------

def test_stop_loss_triggers():
    exits = MONITOR.check([make_position(-2.5)], now=MIDDAY)
    assert len(exits) == 1
    assert exits[0].qty == 10
    assert "손절" in exits[0].reason


def test_stop_loss_exact_boundary():
    exits = MONITOR.check([make_position(-2.0)], now=MIDDAY)
    assert len(exits) == 1 and "손절" in exits[0].reason


def test_take_profit_triggers():
    exits = MONITOR.check([make_position(4.5)], now=MIDDAY)
    assert len(exits) == 1 and "익절" in exits[0].reason


def test_within_band_no_exit():
    assert MONITOR.check([make_position(-1.9)], now=MIDDAY) == []
    assert MONITOR.check([make_position(3.9)], now=MIDDAY) == []
    assert MONITOR.check([make_position(0.0)], now=MIDDAY) == []


# ------------------------------------------------------------------
# 장 마감 청산
# ------------------------------------------------------------------

def test_eod_exits_all_positions():
    positions = [make_position(0.5), make_position(1.2)]
    exits = MONITOR.check(positions, now=AFTER_EOD)
    assert len(exits) == 2
    assert all("장 마감" in e.reason for e in exits)


def test_eod_active_flag():
    assert MONITOR.eod_active(now=AFTER_EOD) is True
    assert MONITOR.eod_active(now=MIDDAY) is False


# ------------------------------------------------------------------
# 주문가능수량
# ------------------------------------------------------------------

def test_uses_orderable_qty():
    exits = MONITOR.check([make_position(-3.0, qty=10, orderable_qty=7)], now=MIDDAY)
    assert exits[0].qty == 7


def test_zero_orderable_skipped():
    assert MONITOR.check([make_position(-5.0, orderable_qty=0)], now=MIDDAY) == []


# ------------------------------------------------------------------
# 장마감 강제청산 OFF (오버나이트 보유 — 스윙)
# ------------------------------------------------------------------

def test_eod_disabled_holds_overnight():
    m = PositionMonitor(stop_loss_pct=2.0, take_profit_pct=4.0, eod_liquidate=False)
    assert m.eod_active(now=AFTER_EOD) is False
    # 장마감 시간이어도 밴드 내(손절/익절 미도달) 종목은 청산 안 함
    assert m.check([make_position(0.5)], now=AFTER_EOD) == []
    # 단, 손절은 장마감이든 아니든 작동
    exits = m.check([make_position(-3.0)], now=AFTER_EOD)
    assert len(exits) == 1 and "손절" in exits[0].reason
