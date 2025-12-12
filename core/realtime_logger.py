"""
实时日志记录器
"""

import os
import threading
from typing import Optional
from datetime import datetime
from pathlib import Path


class RealtimeLogger:
    """实时日志记录器"""
    
    def __init__(self, session_id: str, logs_dir: str = "logs"):
        """
        初始化实时日志记录器
        
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
        log_filename = f"realtime_{self.session_id[:8]}_{timestamp}.log"
        self.log_file = Path(self.logs_dir) / log_filename
        
        try:
            self.file_handle = open(self.log_file, 'a', encoding='utf-8')
            self._write_header()
        except Exception as e:
            print(f"⚠️  无法创建实时日志文件: {e}")
            self.file_handle = None
    
    def _write_header(self) -> None:
        """写入日志头部"""
        if self.file_handle:
            header = f"""
{'=' * 80}
SecAgent-Core 实时日志
会话 ID: {self.session_id}
开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'=' * 80}

"""
            self.file_handle.write(header)
            self.file_handle.flush()
    
    def log(self, level: str, message: str, details: Optional[dict] = None) -> None:
        """
        写入日志
        
        Args:
            level: 日志级别
            message: 日志消息
            details: 详细信息
        """
        if not self.file_handle:
            return
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with self.lock:
            log_line = f"[{timestamp}] [{level}] {message}\n"
            if details:
                details_str = "\n".join([f"  {k}: {v}" for k, v in details.items()])
                log_line += f"{details_str}\n"
            log_line += "\n"
            
            try:
                self.file_handle.write(log_line)
                self.file_handle.flush()
            except Exception as e:
                print(f"⚠️  写入日志失败: {e}")
    
    def log_status_change(self, old_status: str, new_status: str) -> None:
        """记录状态变化"""
        self.log("INFO", f"状态变化: {old_status} -> {new_status}")
    
    def log_iteration_start(self, iteration: int, max_iterations: int) -> None:
        """记录迭代开始"""
        self.log("INFO", f"开始迭代 {iteration}/{max_iterations}")
    
    def log_llm_call(self, iteration: int, token_usage: dict) -> None:
        """记录 LLM 调用"""
        self.log("INFO", f"LLM 调用 (迭代 {iteration})", {
            "prompt_tokens": token_usage.get("prompt_tokens", 0),
            "completion_tokens": token_usage.get("completion_tokens", 0),
            "total_tokens": token_usage.get("total_tokens", 0)
        })
    
    def log_tool_execution(self, tool_name: str, args: dict, result: dict) -> None:
        """记录工具执行"""
        self.log("INFO", f"工具执行: {tool_name}", {
            "参数": str(args),
            "成功": result.get("success", False),
            "结果": str(result.get("result", ""))[:200] if result.get("result") else "N/A"
        })
    
    def log_task_step(self, step_id: int, description: str, status: str) -> None:
        """记录任务步骤"""
        self.log("INFO", f"任务步骤 {step_id}: {description}", {"状态": status})
    
    def log_task_complete(self, summary: dict) -> None:
        """记录任务完成"""
        self.log("INFO", "任务完成", summary)
    
    def log_human_input_request(self, prompt: str) -> None:
        """记录人工输入请求"""
        self.log("INFO", "请求人工输入", {"提示": prompt})
    
    def log_warning(self, message: str) -> None:
        """记录警告"""
        self.log("WARNING", message)
    
    def log_error(self, message: str, error: Optional[Exception] = None) -> None:
        """记录错误"""
        error_details = {"错误": str(error)} if error else {}
        self.log("ERROR", message, error_details)
    
    def close(self) -> None:
        """关闭日志文件"""
        if self.file_handle:
            try:
                footer = f"""
{'=' * 80}
实时日志结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'=' * 80}
"""
                self.file_handle.write(footer)
                self.file_handle.close()
                print(f"✓ 实时日志已保存: {self.log_file}")
            except Exception as e:
                print(f"⚠️  关闭实时日志文件失败: {e}")
            finally:
                self.file_handle = None
    
    def get_log_path(self) -> Optional[str]:
        """获取日志文件路径"""
        return str(self.log_file) if self.log_file else None



