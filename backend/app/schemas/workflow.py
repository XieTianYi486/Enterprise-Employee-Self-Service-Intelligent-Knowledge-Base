# ============================================================
# OA 办公流程 Pydantic Schema
# 请假 / 报销 / 审批
# ============================================================

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LeaveSubmitRequest(BaseModel):
    """请假申请请求"""
    leave_type: str = Field(..., description="请假类型：年假/事假/病假/调休/婚假")
    start_date: str = Field(..., description="开始日期 yyyy-MM-dd")
    end_date: str = Field(..., description="结束日期 yyyy-MM-dd")
    reason: Optional[str] = Field(default=None, max_length=500, description="请假事由")


class ExpenseSubmitRequest(BaseModel):
    """报销申请请求"""
    expense_type: str = Field(..., description="报销类型：差旅费/办公用品/招待费/交通费/其他")
    amount: float = Field(..., gt=0, description="报销金额（元）")
    expense_date: str = Field(..., description="费用发生日期 yyyy-MM-dd")
    reason: Optional[str] = Field(default=None, max_length=500, description="报销事由")
    attachments: Optional[list[str]] = Field(default=None, description="凭证附件路径列表")


class ApprovalRequest(BaseModel):
    """审批动作请求"""
    action: str = Field(..., description="审批动作：APPROVE=通过 / REJECT=驳回")
    comment: Optional[str] = Field(default=None, max_length=500, description="审批意见")
