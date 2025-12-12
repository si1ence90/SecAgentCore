"""
执行日志记录器 - 详细记录所有执行细节
"""

import os
import json
import threading
import traceback
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path


class ExecutionLogger:
    """执行日志记录器 - 详细记录所有执行细节"""
    
    def __init__(self, session_id: str, logs_dir: str = "logs"):
        """
        初始化执行日志记录器
        
        Args:
            session_id: 会话 ID
            logs_dir: 日志目录
        """
        self.session_id = session_id
        self.logs_dir = logs_dir
        self.log_file: Optional[Path] = None
        self.file_handle = None
        self.lock = threading.Lock()
        self._initialize_log_file()
    
    def _initialize_log_file(self) -> None:
        """初始化日志文件"""
        os.makedirs(self.logs_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"execution_{self.session_id[:8]}_{timestamp}.log"
        self.log_file = Path(self.logs_dir) / log_filename
        
        try:
            self.file_handle = open(self.log_file, 'a', encoding='utf-8')
            self._write_header()
        except Exception as e:
            print(f"⚠️  无法创建执行日志文件: {e}")
            self.file_handle = None
    
    def _write_header(self) -> None:
        """写入日志头部"""
        if self.file_handle:
            header = f"""
{'=' * 100}
SecAgent-Core 执行日志（详细版）
会话 ID: {self.session_id}
开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'=' * 100}

本日志记录 Agent 的完整执行过程，包括：
- 状态变化
- LLM 输入输出（完整文本）
- 工具执行详情
- 任务步骤变化
- 执行进展（思考、计划、动作）
- 对话历史快照
- 错误信息

{'=' * 100}

"""
            self.file_handle.write(header)
            self.file_handle.flush()
    
    def _write_log_entry(self, entry_type: str, data: Dict[str, Any]) -> None:
        """
        写入日志条目
        
        Args:
            entry_type: 日志条目类型
            data: 日志数据
        """
        if not self.file_handle:
            return
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
        with self.lock:
            log_entry = {
                "timestamp": timestamp,
                "type": entry_type,
                "data": data
            }
            try:
                json_str = json.dumps(log_entry, ensure_ascii=False, indent=2)
                self.file_handle.write(f"{json_str}\n")
                self.file_handle.write("-" * 100 + "\n\n")
                self.file_handle.flush()
            except Exception as e:
                print(f"⚠️  写入执行日志失败: {e}")
    
    def log_session_start(self, user_goal: str, config: Dict[str, Any]) -> None:
        """记录会话开始"""
        self._write_log_entry("SESSION_START", {
            "user_goal": user_goal,
            "config": config,
            "session_id": self.session_id
        })
    
    def log_state_change(self, old_status: str, new_status: str, context: Optional[Dict[str, Any]] = None) -> None:
        """记录状态变化"""
        self._write_log_entry("STATE_CHANGE", {
            "old_status": old_status,
            "new_status": new_status,
            "context": context or {}
        })
    
    def log_iteration_start(self, iteration: int, max_iterations: int) -> None:
        """记录迭代开始"""
        self._write_log_entry("ITERATION_START", {
            "iteration": iteration,
            "max_iterations": max_iterations,
            "progress": f"{iteration}/{max_iterations}"
        })
    
    def log_llm_request(self, messages: List[Dict[str, str]], model: str, temperature: Optional[float] = None) -> None:
        """记录 LLM 请求（输入），包含完整消息内容"""
        total_content_length = sum(len(msg.get("content", "")) for msg in messages)
        
        # 记录每条消息的完整内容
        full_messages_details = []
        for idx, msg in enumerate(messages):
            full_messages_details.append({
                "index": idx,
                "role": msg.get("role", "unknown"),
                "content": msg.get("content", ""),
                "content_length": len(msg.get("content", ""))
            })
        
        self._write_log_entry("LLM_REQUEST", {
            "model": model,
            "temperature": temperature,
            "messages_count": len(messages),
            "total_content_length": total_content_length,
            "messages": full_messages_details
        })
    
    def log_llm_response(self, response: str, token_usage: Dict[str, int], model: str) -> None:
        """记录 LLM 响应（输出），包含完整响应内容"""
        self._write_log_entry("LLM_RESPONSE", {
            "model": model,
            "response_length": len(response),
            "response": response,  # 完整响应
            "token_usage": token_usage
        })
    
    def log_agent_parsed_response(self, parsed: Dict[str, Any], raw_response: str) -> None:
        """记录 Agent 解析后的响应，包含完整的原始响应"""
        self._write_log_entry("AGENT_PARSED_RESPONSE", {
            "parsed": parsed,
            "raw_response": raw_response  # 完整原始响应
        })
    
    def log_execution_progress(
        self,
        iteration: int,
        thought: str,
        plan: List[str],
        action: str,
        action_input: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录 Agent 的执行进展（思考、计划、动作）"""
        self._write_log_entry("EXECUTION_PROGRESS", {
            "iteration": iteration,
            "thought": thought,
            "plan": plan,
            "action": action,
            "action_input": action_input,
            "context": context or {}
        })
    
    def log_conversation_history(self, messages: List[Dict[str, Any]]) -> None:
        """记录完整的对话历史快照"""
        self._write_log_entry("CONVERSATION_HISTORY", {
            "messages_count": len(messages),
            "messages": messages  # 完整的消息列表
        })
    
    def log_task_steps_snapshot(self, task_steps: List[Dict[str, Any]]) -> None:
        """记录任务步骤的快照"""
        self._write_log_entry("TASK_STEPS_SNAPSHOT", {
            "steps_count": len(task_steps),
            "steps": task_steps  # 完整的任务步骤列表
        })
    
    def log_tool_execution_start(self, tool_name: str, tool_args: Dict[str, Any]) -> None:
        """记录工具执行开始"""
        self._write_log_entry("TOOL_EXECUTION_START", {
            "tool_name": tool_name,
            "tool_args": tool_args
        })
    
    def log_tool_execution_result(
        self,
        tool_name: str,
        result: Dict[str, Any],
        execution_time: Optional[float] = None
    ) -> None:
        """记录工具执行结果"""
        self._write_log_entry("TOOL_EXECUTION_RESULT", {
            "tool_name": tool_name,
            "result": result,
            "execution_time_seconds": execution_time
        })
    
    def log_task_step_update(
        self,
        step_id: int,
        description: str,
        status: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录任务步骤更新"""
        self._write_log_entry("TASK_STEP_UPDATE", {
            "step_id": step_id,
            "description": description,
            "status": status,
            "details": details or {}
        })
    
    def log_human_input_request(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> None:
        """记录人工输入请求"""
        self._write_log_entry("HUMAN_INPUT_REQUEST", {
            "prompt": prompt,
            "context": context or {}
        })
    
    def log_human_input_received(self, input_text: str) -> None:
        """记录收到人工输入"""
        self._write_log_entry("HUMAN_INPUT_RECEIVED", {
            "input": input_text,
            "input_length": len(input_text)
        })
    
    def log_error(
        self,
        error_type: str,
        error_message: str,
        traceback_str: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录错误"""
        self._write_log_entry("ERROR", {
            "error_type": error_type,
            "error_message": error_message,
            "traceback": traceback_str,
            "context": context or {}
        })
    
    def log_warning(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """记录警告"""
        self._write_log_entry("WARNING", {
            "message": message,
            "context": context or {}
        })
    
    def log_knowledge_base_search(self, query: str, results: List[Dict[str, Any]]) -> None:
        """记录知识库搜索"""
        self._write_log_entry("KNOWLEDGE_BASE_SEARCH", {
            "query": query,
            "results_count": len(results),
            "results": results
        })
    
    def log_session_complete(self, summary: Dict[str, Any]) -> None:
        """记录会话完成"""
        self._write_log_entry("SESSION_COMPLETE", {
            "summary": summary
        })
        self.close()
    
    def log_custom(self, event_type: str, data: Dict[str, Any]) -> None:
        """记录自定义事件"""
        self._write_log_entry(event_type, data)
    
    def close(self) -> None:
        """关闭日志文件"""
        if self.file_handle:
            try:
                footer = f"""
{'=' * 100}
执行日志结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'=' * 100}
"""
                self.file_handle.write(footer)
                self.file_handle.close()
                print(f"✓ 执行日志已保存: {self.log_file}")
            except Exception as e:
                print(f"⚠️  关闭执行日志文件失败: {e}")
            finally:
                self.file_handle = None
    
    def get_log_path(self) -> Optional[str]:
        """获取日志文件路径"""
        return str(self.log_file) if self.log_file else None



