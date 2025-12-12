"""
会话状态管理模块
"""

from enum import Enum
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from core.realtime_logger import RealtimeLogger
    from core.execution_logger import ExecutionLogger


class AgentStatus(Enum):
    """Agent 状态枚举"""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    AWAITING_HUMAN_INPUT = "awaiting_human_input"
    COMPLETED = "completed"
    ERROR = "error"
    MAX_ITERATIONS_REACHED = "max_iterations_reached"


class Message(BaseModel):
    """消息模型"""
    role: str  # system, user, assistant, tool
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None


class TaskStep(BaseModel):
    """任务步骤模型"""
    step_id: int
    description: str
    status: str = "pending"  # pending, executing, completed, failed
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class TokenUsage(BaseModel):
    """Token 使用统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_calls: int = 0
    
    def add_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        """添加 token 使用"""
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += prompt_tokens + completion_tokens
        self.api_calls += 1


class SessionState(BaseModel):
    """会话状态模型"""
    session_id: str
    status: AgentStatus = AgentStatus.IDLE
    user_goal: Optional[str] = None
    messages: List[Message] = Field(default_factory=list)
    task_steps: List[TaskStep] = Field(default_factory=list)
    execution_log: List[Dict[str, Any]] = Field(default_factory=list)
    current_iteration: int = 0
    max_iterations: int = 20
    human_input_required: bool = False
    human_input_prompt: Optional[str] = None
    # 安全模式确认相关
    pending_tool_execution_id: Optional[str] = None
    pending_tool_name: Optional[str] = None
    pending_tool_args: Optional[Dict[str, Any]] = None
    # Token 统计
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    # 当前执行上下文（用于显示详细状态）
    current_thought: Optional[str] = None
    current_plan: List[str] = Field(default_factory=list)
    current_action: Optional[str] = None
    current_action_input: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        """Pydantic 配置"""
        # 允许额外字段（用于存储实时日志记录器等私有属性）
        extra = 'allow'
    
    def __init__(self, **data):
        """初始化，设置实时日志记录器和执行日志记录器为 None"""
        super().__init__(**data)
        # 使用 object.__setattr__ 绕过 Pydantic 的验证
        object.__setattr__(self, '_realtime_logger', None)
        object.__setattr__(self, '_execution_logger', None)
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """添加消息"""
        self.messages.append(Message(role=role, content=content, metadata=metadata))
        self.updated_at = datetime.now()
    
    def add_task_step(self, description: str) -> TaskStep:
        """添加任务步骤"""
        step_id = len(self.task_steps) + 1
        step = TaskStep(step_id=step_id, description=description)
        self.task_steps.append(step)
        self.updated_at = datetime.now()
        return step
    
    def update_task_step(
        self,
        step_id: int,
        status: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        tool_name: Optional[str] = None,
        tool_args: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> None:
        """更新任务步骤"""
        for step in self.task_steps:
            if step.step_id == step_id:
                if status:
                    step.status = status
                if result is not None:
                    step.result = result
                if tool_name:
                    step.tool_name = tool_name
                if tool_args:
                    step.tool_args = tool_args
                if error:
                    step.error = error
                self.updated_at = datetime.now()
                break
    
    def add_execution_log(self, action: str, details: Optional[Dict[str, Any]] = None) -> None:
        """添加执行日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details or {}
        }
        self.execution_log.append(log_entry)
        self.updated_at = datetime.now()
    
    def request_human_input(self, prompt: str) -> None:
        """请求人工输入"""
        self.human_input_required = True
        self.human_input_prompt = prompt
        self.status = AgentStatus.AWAITING_HUMAN_INPUT
        self.updated_at = datetime.now()
    
    def clear_human_input(self) -> None:
        """清除人工输入请求"""
        self.human_input_required = False
        self.human_input_prompt = None
        self.updated_at = datetime.now()
    
    def set_pending_tool_execution(self, execution_id: str, tool_name: str, tool_args: Dict[str, Any]) -> None:
        """设置待确认的工具执行"""
        self.pending_tool_execution_id = execution_id
        self.pending_tool_name = tool_name
        self.pending_tool_args = tool_args
    
    def clear_pending_tool_execution(self) -> None:
        """清除待确认的工具执行"""
        self.pending_tool_execution_id = None
        self.pending_tool_name = None
        self.pending_tool_args = None
    
    def set_status(self, status: AgentStatus) -> None:
        """设置 Agent 状态"""
        old_status = self.status.value if self.status else "unknown"
        self.status = status
        self.updated_at = datetime.now()
        # 记录状态变化到实时日志
        if hasattr(self, '_realtime_logger') and self._realtime_logger:
            self._realtime_logger.log_status_change(old_status, status.value)
        # 记录状态变化到执行日志
        if hasattr(self, '_execution_logger') and self._execution_logger:
            self._execution_logger.log_state_change(old_status, status.value, {"iteration": self.current_iteration})
    
    def get_summary(self) -> Dict[str, Any]:
        """获取会话摘要"""
        return {
            "session_id": self.session_id,
            "user_goal": self.user_goal,
            "status": self.status.value,
            "iterations": self.current_iteration,
            "max_iterations": self.max_iterations,
            "task_steps_count": len(self.task_steps),
            "messages_count": len(self.messages),
            "token_usage": {
                "prompt_tokens": self.token_usage.prompt_tokens,
                "completion_tokens": self.token_usage.completion_tokens,
                "total_tokens": self.token_usage.total_tokens,
                "api_calls": self.token_usage.api_calls
            },
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

