"""RiskGuard 단위 테스트."""
import pytest

from src.risk.guard import RiskContext, RiskGuard
from src.strategy.base import Action, Signal

# 테스트용 고정 한도 (settings 와 독립)
GUARD = RiskGuard(
    max_daily_loss=300_000,
    max_order_amount=1_000_000,
    max_position_pct=0.2,
)

BASE_CTX = RiskContext(
    current_price=50_000,
    portfolio_value=10_000_000,
    daily_pnl=0,
)

BUY  = Signal(Action.BUY,  10, "test")
SELL = Signal(Action.SELL, 10, "test")
HOLD = Signal(Action.HOLD, 0,  "test")


# ------------------------------------------------------------------
# HOLD
# ------------------------------------------------------------------

def test_hold_always_approved():
    d = GUARD.check("A", HOLD, BASE_CTX)
    assert d.approved and d.action == Action.HOLD


# ------------------------------------------------------------------
# 킬스위치
# ------------------------------------------------------------------

def test_kill_switch_blocks_buy():
    ctx = RiskContext(current_price=50_000, portfolio_value=10_000_000, daily_pnl=-300_000)
    d = GUARD.check("A", BUY, ctx)
    assert not d.approved
    assert "킬스위치" in d.reason

def test_kill_switch_allows_sell():
    ctx = RiskContext(current_price=50_000, portfolio_value=10_000_000, daily_pnl=-300_000)
    d = GUARD.check("A", SELL, ctx)
    assert d.approved

def test_kill_switch_below_threshold_allows_buy():
    ctx = RiskContext(current_price=50_000, portfolio_value=10_000_000, daily_pnl=-299_999)
    d = GUARD.check("A", BUY, ctx)
    assert d.approved


# ------------------------------------------------------------------
# 중복 주문 방지
# ------------------------------------------------------------------

def test_duplicate_pending_rejected():
    ctx = RiskContext(
        current_price=50_000, portfolio_value=10_000_000, daily_pnl=0,
        pending_tickers={"A"},
    )
    d = GUARD.check("A", BUY, ctx)
    assert not d.approved
    assert "미체결" in d.reason

def test_different_ticker_not_blocked():
    ctx = RiskContext(
        current_price=50_000, portfolio_value=10_000_000, daily_pnl=0,
        pending_tickers={"B"},
    )
    d = GUARD.check("A", BUY, ctx)
    assert d.approved


# ------------------------------------------------------------------
# 주문 금액 한도
# ------------------------------------------------------------------

def test_order_amount_limit_reduces_qty():
    # max_order_amount=1_000_000, price=50_000 → max qty=20
    # 요청 qty=30 → 20으로 감축
    ctx = RiskContext(current_price=50_000, portfolio_value=100_000_000, daily_pnl=0)
    d = GUARD.check("A", Signal(Action.BUY, 30, "test"), ctx)
    assert d.approved
    assert d.qty == 20

def test_order_amount_limit_exact_boundary():
    # price=50_000, qty=20 → 1_000_000 exactly → 통과
    ctx = RiskContext(current_price=50_000, portfolio_value=100_000_000, daily_pnl=0)
    d = GUARD.check("A", Signal(Action.BUY, 20, "test"), ctx)
    assert d.approved and d.qty == 20


# ------------------------------------------------------------------
# 종목 비중 한도
# ------------------------------------------------------------------

def test_position_pct_limit_reduces_qty():
    # portfolio=10_000_000, max_pct=0.2 → max_position=2_000_000
    # position_value=1_500_000 → room=500_000, price=50_000 → max_by_pct=10
    ctx = RiskContext(
        current_price=50_000, portfolio_value=10_000_000,
        daily_pnl=0, position_value=1_500_000,
    )
    d = GUARD.check("A", Signal(Action.BUY, 20, "test"), ctx)
    assert d.approved
    assert d.qty == 10

def test_position_full_blocks_buy():
    # 비중 이미 꽉 참 → room=0 → qty=0 → 거부
    ctx = RiskContext(
        current_price=50_000, portfolio_value=10_000_000,
        daily_pnl=0, position_value=2_000_000,
    )
    d = GUARD.check("A", BUY, ctx)
    assert not d.approved


# ------------------------------------------------------------------
# kill_switch_active helper
# ------------------------------------------------------------------

def test_kill_switch_active_helper():
    assert GUARD.kill_switch_active(-300_000) is True
    assert GUARD.kill_switch_active(-299_999) is False
    assert GUARD.kill_switch_active(0) is False
