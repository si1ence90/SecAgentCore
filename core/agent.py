"""
Agent 核心引擎 - ReAct 循环实现
"""

import json
import re
import uuid
import os
import time
import traceback
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, ValidationError
from core.llm import get_model_provider
from core.tools import (
    get_tool, get_tool_schemas, auto_discover_tools,
    requires_confirmation, add_pending_execution, remove_pending_execution
)
from core.state import SessionState, AgentStatus, TaskStep
from core.realtime_logger import RealtimeLogger
from core.execution_logger import ExecutionLogger
from core.knowledge_base import get_knowledge_base
import yaml
from datetime import datetime


class AgentResponse(BaseModel):
    """Agent 响应模型"""
    thought: str = Field(..., description="思考过程")
    plan: List[str] = Field(..., description="执行计划")
    action: str = Field(..., description="要执行的动作（工具名称或 'final_answer'）")
    action_input: Dict[str, Any] = Field(..., description="动作参数")


class SecAgent:
    """SecAgent 核心类"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化 Agent
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.model_provider = get_model_provider(config_path)
        
        # 自动发现并注册工具
        auto_discover_tools()
        self.tool_schemas = get_tool_schemas()
        
        # 初始化模型提供商
        default_provider = self.config.get('llm', {}).get('provider', 'deepseek-chat')
        try:
            self.model_provider.set_provider(default_provider)
        except Exception as e:
            print(f"⚠️  初始化模型提供商失败: {e}")
        
        self.session_state: Optional[SessionState] = None
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"⚠️  加载配置失败: {e}")
            return {}
    
    def _build_system_prompt(self, knowledge_content: Optional[str] = None) -> str:
        """构建系统提示词"""
        # 获取工具列表描述（包含参数信息）
        tools_description_parts = []
        available_tool_names = []  # 记录所有可用工具名称
        
        for tool in self.tool_schemas:
            tool_name = tool['name']
            tool_desc = tool['description']
            params = tool.get('parameters', [])
            available_tool_names.append(tool_name)
            
            # 构建工具描述
            tool_info = f"- **{tool_name}**: {tool_desc}"
            if params:
                tool_info += "\n  参数（参数名称必须完全匹配）:"
                for param in params:
                    param_name = param.get('name', 'unknown')
                    param_type = param.get('type', 'string')
                    param_desc = param.get('description', '')
                    required = param.get('required', True)
                    req_text = "必需" if required else "可选"
                    tool_info += f"\n    - **{param_name}** ({param_type}, {req_text}): {param_desc}"
                
                # 列出所有参数名称，强调必须使用这些名称
                param_names = [p.get('name', '') for p in params]
                # 构建参数名称列表字符串（避免在 f-string 中使用反斜杠）
                param_list = ', '.join([f'"{name}"' for name in param_names])
                tool_info += f"\n  ⚠️ 参数名称列表（必须使用这些名称）: {param_list}"
            
            tools_description_parts.append(tool_info)
        
        tools_description = "\n".join(tools_description_parts)
        # 生成工具名称列表（用于强调）
        tools_list_str = ", ".join([f'"{name}"' for name in available_tool_names])
        
        # 知识库内容
        knowledge_section = ""
        if knowledge_content:
            knowledge_section = f"""
## 知识库指导

以下是从知识库中找到的相关指导，请**严格遵循**这些步骤：

{knowledge_content}

**重要**: 如果知识库中提供了任务规划步骤，你必须严格按照这些步骤执行，不要偏离。

---
"""
        
        # 需要确认的操作列表
        require_confirmation_for = self.config.get('agent', {}).get('require_confirmation_for', [])
        confirmation_list = "\n".join([f"- {op}" for op in require_confirmation_for]) if require_confirmation_for else "- 无"
        
        prompt = f"""你是一个专业的网络安全智能体（SecAgent），负责帮助用户执行安全任务。

{knowledge_section}## 你的能力

**⚠️⚠️⚠️ 极其重要：工具使用限制 ⚠️⚠️⚠️**

**你只能使用以下列出的工具，绝对不能使用任何其他工具或系统命令！**

**可用工具列表（仅限这些）：**
{tools_list_str}

你可以使用以下工具：
{tools_description}

**工具使用规则：**
1. **只能使用上述列出的工具**，不能使用任何未列出的工具或系统命令。
2. 如果任务需要执行系统命令（如 `ping`, `nmap`, `curl`, `wget`, `echo`, `cat` 等），必须使用相应的工具（如网络扫描使用 `network_ping` 和 `port_scan`）。
3. 如果工具不存在，请使用最接近的工具或请求人工帮助。
4. **禁止使用 `command`、`execute`、`run`、`system`、`shell` 等不存在的工具。**

## 工作流程（ReAct 循环）
1. **思考（Think）**: 分析用户目标，理解任务需求
2. **规划（Plan）**: 将复杂任务拆解为可执行的步骤列表
3. **行动（Act）**: 选择合适的工具并执行当前步骤
4. **观察（Observe）**: 分析工具执行结果
5. **反思（Reflect）**: 判断是否完成任务，是否需要继续

## 重要安全规则
在执行以下操作前，**必须**进行自我反思并请求人工确认：
{confirmation_list}

## 输出格式要求（严格遵循 - 这是最重要的规则）

**⚠️ 警告：如果你不按照以下 JSON 格式输出，系统将无法解析你的响应，任务将失败！**

**你必须只输出一个有效的 JSON 对象，格式如下（不要添加任何其他文本、Markdown、代码块、解释或说明）：**

{{
    "thought": "你的思考过程，分析当前情况和任务需求",
    "plan": ["步骤1", "步骤2", "步骤3"],
    "action": "工具名称 或 'final_answer'",
    "action_input": {{"参数名": "参数值"}}
}}

### 字段说明：

- **thought** (必需): 字符串，描述你的思考过程，分析当前情况和下一步要做什么
- **plan** (必需): 字符串数组，包含完整的任务执行计划，列出所有需要执行的步骤。如果是单步任务，可以只包含当前步骤
- **action** (必需): 字符串，要执行的动作：
  - 如果是工具调用，使用工具名称（如 {tools_list_str}）
  - 如果任务完成，使用 "final_answer"
- **action_input** (必需): 对象/字典，包含动作的参数：
  - 工具调用时，包含工具所需的参数（参数名称必须完全匹配，例如 `target_ip` 而不是 `ip`）
  - 任务完成时，包含 {{"answer": "最终答案文本"}}

### ⚠️ 严格禁止的行为：

1. **禁止输出 Markdown 格式**（如 # 标题、```代码块等）
2. **禁止输出解释性文字**（如"我将为您执行..."、"以下是详细步骤..."等）
3. **禁止输出代码块标记**（如 ```json 或 ```）
4. **禁止输出任何非 JSON 内容**
5. **禁止使用未在"可用工具列表"中列出的工具名称**

### ✅ 正确的输出方式：

**只输出一行 JSON，例如：**
{{"thought": "用户想要扫描主机，我需要先检查连通性，然后扫描端口", "plan": ["检查网络连通性", "扫描开放端口", "生成报告"], "action": "network_ping", "action_input": {{"target_ip": "127.0.0.1", "port": 80}}}}

### 重要提示：

1. **只输出 JSON 对象，不要添加任何其他内容**
2. **确保 JSON 格式完全正确，可以被直接解析**
3. **plan 字段必须是一个字符串数组，即使只有一个步骤也要用数组格式**
4. **如果任务需要多步执行，plan 应该包含所有步骤；如果当前是第一步，后续步骤可以基于当前情况规划**

现在开始工作，**只输出一行纯 JSON，不要任何其他内容**。"""
        return prompt
    
    def create_session(self, user_goal: str) -> SessionState:
        """创建新的会话"""
        session_id = str(uuid.uuid4())
        self.session_state = SessionState(
            session_id=session_id,
            user_goal=user_goal,
            max_iterations=self.config.get('agent', {}).get('max_iterations', 20)
        )
        
        # 初始化实时日志记录器
        object.__setattr__(self.session_state, '_realtime_logger', RealtimeLogger(session_id))
        self.session_state._realtime_logger.log("INFO", "会话创建", {
            "用户目标": user_goal,
            "最大迭代次数": self.session_state.max_iterations
        })
        
        # 初始化执行日志记录器
        object.__setattr__(self.session_state, '_execution_logger', ExecutionLogger(session_id))
        self.session_state._execution_logger.log_session_start(
            user_goal,
            {
                "max_iterations": self.session_state.max_iterations,
                "llm_provider": self.model_provider.current_provider if hasattr(self.model_provider, 'current_provider') else "unknown"
            }
        )
        
        # 搜索知识库
        knowledge_base = get_knowledge_base()
        knowledge_content = knowledge_base.get_knowledge_for_task(user_goal)
        
        if knowledge_content:
            self.session_state._realtime_logger.log("INFO", "找到相关知识库", {
                "相关性": "高",
                "知识库内容长度": len(knowledge_content)
            })
            # 记录知识库搜索结果
            search_results = knowledge_base.search(user_goal, top_k=1)
            self.session_state._execution_logger.log_knowledge_base_search(user_goal, search_results)
            # 重新构建包含知识库内容的系统提示词
            system_prompt = self._build_system_prompt(knowledge_content)
        else:
            self.session_state._realtime_logger.log("INFO", "未找到相关知识库，使用默认规划")
            self.session_state._execution_logger.log_knowledge_base_search(user_goal, [])
            system_prompt = self._build_system_prompt()
        
        # 添加系统消息和用户目标
        self.session_state.add_message("system", system_prompt)
        self.session_state.add_message("user", user_goal)
        
        return self.session_state
    
    def _parse_agent_response(self, response: str) -> AgentResponse:
        """解析 Agent 响应"""
        # 尝试多种方式提取 JSON
        json_str = None
        
        # 方法1: 尝试直接解析
        try:
            parsed = json.loads(response.strip())
            return AgentResponse(**parsed)
        except:
            pass
        
        # 方法2: 提取代码块中的 JSON
        code_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        matches = re.findall(code_block_pattern, response, re.DOTALL)
        if matches:
            try:
                parsed = json.loads(matches[0])
                return AgentResponse(**parsed)
            except:
                pass
        
        # 方法3: 提取第一个完整的 JSON 对象
        brace_count = 0
        start_idx = -1
        for i, char in enumerate(response):
            if char == '{':
                if start_idx == -1:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx != -1:
                    json_str = response[start_idx:i+1]
                    break
        
        if json_str:
            try:
                parsed = json.loads(json_str)
                return AgentResponse(**parsed)
            except:
                pass
        
        # 方法4: 简单匹配
        simple_match = re.search(r'\{[^{}]*"thought"[^{}]*"plan"[^{}]*"action"[^{}]*"action_input"[^{}]*\}', response, re.DOTALL)
        if simple_match:
            try:
                parsed = json.loads(simple_match.group(0))
                return AgentResponse(**parsed)
            except:
                pass
        
        # 如果所有方法都失败，抛出异常
        raise ValueError(f"无法解析 Agent 响应: {response[:200]}")
    
    def _check_requires_confirmation(self, action: str, action_input: Dict[str, Any]) -> bool:
        """检查操作是否需要人工确认"""
        # 默认关闭人机协同，除非配置明确开启
        if not self.config.get('agent', {}).get('enable_human_in_the_loop', False):
            return False
        
        require_confirmation_for = self.config.get('agent', {}).get('require_confirmation_for', [])
        
        # 检查操作描述中是否包含需要确认的关键词
        action_str = f"{action} {json.dumps(action_input)}".lower()
        for keyword in require_confirmation_for:
            if keyword.lower() in action_str:
                return True
        
        return False
    
    def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具"""
        tool = get_tool(tool_name)
        if not tool:
            return {
                "success": False,
                "error": f"工具 {tool_name} 不存在",
                "result": None
            }
        
        try:
            result = tool.execute(**tool_args)
            return result
        except TypeError as e:
            error_msg = str(e)
            # 检查是否是参数错误
            if "missing" in error_msg.lower() or "required" in error_msg.lower():
                # 提取缺少的参数名
                param_match = re.search(r'缺少必需参数[：:]\s*(\w+)', error_msg)
                if not param_match:
                    param_match = re.search(r'missing.*?argument[:\s]+[\'"]?(\w+)', error_msg, re.IGNORECASE)
                if param_match:
                    required_param = param_match.group(1)
                    return {
                        "success": False,
                        "error": f"缺少必需参数: {required_param}",
                        "result": None
                    }
            return {
                "success": False,
                "error": f"工具执行失败: {error_msg}",
                "result": None
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"工具执行出错: {str(e)}",
                "result": None
            }
    
    def step(self, human_input: Optional[str] = None) -> Dict[str, Any]:
        """执行一步 ReAct 循环"""
        if self.session_state is None:
            raise RuntimeError("请先创建会话")
        
        # 处理人工输入
        if human_input:
            self.session_state.add_message("user", human_input)
            self.session_state.clear_human_input()
            self.session_state._execution_logger.log_human_input_received(human_input)
        
        # 检查迭代次数限制
        if self.session_state.current_iteration >= self.session_state.max_iterations:
            error_msg = "已达到最大迭代次数"
            self.session_state.set_status(AgentStatus.MAX_ITERATIONS_REACHED)
            self.session_state.add_message("system", error_msg)
            
            if self.session_state._realtime_logger:
                self.session_state._realtime_logger.log_warning("已达到最大迭代次数限制")
                summary = self.session_state.get_summary()
                self.session_state._realtime_logger.log_task_complete(summary)
                self.session_state._realtime_logger.close()
            
            if self.session_state._execution_logger:
                summary = self.session_state.get_summary()
                self.session_state._execution_logger.log_warning("已达到最大迭代次数限制", {"summary": summary})
                self.session_state._execution_logger.log_session_complete(summary)
            
            self._save_session_log()
            return {
                "status": "max_iterations_reached",
                "message": "已达到最大迭代次数",
                "session_state": self.session_state
            }
        
        # 增加迭代次数
        self.session_state.current_iteration += 1
        self.session_state.set_status(AgentStatus.PLANNING)
        
        # 构建消息历史（排除 system 和 tool 消息，转换为 user 消息）
        messages = []
        for msg in self.session_state.messages:
            if msg.role == "system":
                # 只在第一条消息时包含 system 消息
                if len(messages) == 0:
                    messages.append({"role": "system", "content": msg.content})
            elif msg.role == "tool":
                # 将 tool 消息转换为 user 消息
                messages.append({"role": "user", "content": f"[工具执行结果] {msg.content}"})
            else:
                messages.append({"role": msg.role, "content": msg.content})
        
        # 记录对话历史和任务步骤快照
        if self.session_state._execution_logger:
            self.session_state._execution_logger.log_conversation_history(messages)
            task_steps_snapshot = [
                {
                    "step_id": step.step_id,
                    "description": step.description,
                    "status": step.status,
                    "tool_name": step.tool_name,
                    "result": step.result
                }
                for step in self.session_state.task_steps
            ]
            self.session_state._execution_logger.log_task_steps_snapshot(task_steps_snapshot)
        
        # 添加格式提醒（如果用户输入暗示需要修复格式）
        format_reminder = {
            "role": "system",
            "content": "⚠️⚠️⚠️ 重要提醒：\n1. 你必须只输出一个有效的 JSON 对象，格式：{\"thought\": \"...\", \"plan\": [...], \"action\": \"...\", \"action_input\": {...}}\n2. action 字段必须是以下工具名称之一：" + ", ".join([f'"{t["name"]}"' for t in self.tool_schemas]) + "，或 \"final_answer\"\n3. 绝对禁止使用任何其他工具名称！\n4. 不要输出任何 Markdown、代码块、解释文字或其他内容，只输出纯 JSON！"
        }
        messages_with_reminder = messages + [format_reminder]
        
        # 记录迭代开始
        if self.session_state._realtime_logger:
            self.session_state._realtime_logger.log_iteration_start(
                self.session_state.current_iteration,
                self.session_state.max_iterations
            )
        if self.session_state._execution_logger:
            self.session_state._execution_logger.log_iteration_start(
                self.session_state.current_iteration,
                self.session_state.max_iterations
            )
        
        try:
            # 记录 LLM 调用开始
            if self.session_state._realtime_logger:
                self.session_state._realtime_logger.log("INFO", "正在调用 LLM 进行思考和规划...")
            
            # 获取模型配置信息
            model_name = self.model_provider.llm_config.model if self.model_provider.llm_config else "unknown"
            temperature = self.model_provider.llm_config.temperature if self.model_provider.llm_config else None
            
            # 记录 LLM 请求（输入）到执行日志
            if self.session_state._execution_logger:
                self.session_state._execution_logger.log_llm_request(messages_with_reminder, model_name, temperature)
            
            llm_response, token_info = self.model_provider.chat_completion(messages_with_reminder)
            self.session_state.add_message("assistant", llm_response)
            
            # 记录 token 使用
            self.session_state.token_usage.add_usage(
                token_info["prompt_tokens"],
                token_info["completion_tokens"]
            )
            
            # 记录到执行日志
            self.session_state.add_execution_log("llm_call", {
                "iteration": self.session_state.current_iteration,
                "token_usage": token_info
            })
            
            # 记录到实时日志
            if self.session_state._realtime_logger:
                self.session_state._realtime_logger.log_llm_call(
                    self.session_state.current_iteration,
                    token_info
                )
            
            # 记录 LLM 响应（输出）到执行日志
            if self.session_state._execution_logger:
                self.session_state._execution_logger.log_llm_response(llm_response, token_info, model_name)
            
            # 解析响应（使用 Pydantic 验证）
            try:
                parsed_response = self._parse_agent_response(llm_response)
            except ValueError as e:
                # 尝试自动修复常见问题
                try:
                    # 尝试修复 plan 字段（如果是字符串，转换为列表）
                    temp_parsed = json.loads(re.search(r'\{.*\}', llm_response, re.DOTALL).group(0))
                    if isinstance(temp_parsed.get('plan'), str):
                        temp_parsed['plan'] = [temp_parsed['plan']]
                    if 'action_input' not in temp_parsed:
                        temp_parsed['action_input'] = {}
                    parsed_response = AgentResponse(**temp_parsed)
                except:
                    # 如果自动修复失败，请求人工介入
                    prompt = f"Agent 输出格式错误，无法解析。原始响应: {llm_response[:500]}... 错误: {str(e)}。请提供指导或修正。"
                    self.session_state.request_human_input(prompt)
                    
                    # 记录错误到执行日志
                    if self.session_state._execution_logger:
                        self.session_state._execution_logger.log_error(
                            "ValueError", str(e), traceback_str=traceback.format_exc(),
                            context={"llm_response": llm_response[:1000]}
                        )
                    
                    return {
                        "status": "awaiting_human_input",
                        "message": prompt,
                        "session_state": self.session_state
                    }
            
            # 记录 Agent 解析后的响应
            if self.session_state._execution_logger:
                self.session_state._execution_logger.log_agent_parsed_response(parsed_response.dict(), llm_response)
            
            # 提取字段
            thought = parsed_response.thought
            plan = parsed_response.plan
            action = parsed_response.action
            action_input = parsed_response.action_input
            
            # 更新当前执行上下文
            self.session_state.current_thought = thought
            self.session_state.current_plan = plan
            self.session_state.current_action = action
            self.session_state.current_action_input = action_input
            
            # 记录思考过程和计划
            self.session_state.add_execution_log("think", {
                "thought": thought,
                "plan": plan,
                "action": action
            })
            
            # 记录执行进展到执行日志
            if self.session_state._execution_logger:
                self.session_state._execution_logger.log_execution_progress(
                    iteration=self.session_state.current_iteration,
                    thought=thought,
                    plan=plan,
                    action=action,
                    action_input=action_input,
                    context={
                        "task_steps_count": len(self.session_state.task_steps),
                        "messages_count": len(self.session_state.messages),
                        "status": self.session_state.status.value
                    }
                )
            
            # 如果有新的计划，更新任务步骤
            if plan and len(plan) > len(self.session_state.task_steps):
                for i, step_desc in enumerate(plan[len(self.session_state.task_steps):], start=len(self.session_state.task_steps) + 1):
                    step = self.session_state.add_task_step(step_desc)
                    # 记录到实时日志
                    if self.session_state._realtime_logger:
                        self.session_state._realtime_logger.log_task_step(
                            step.step_id, step_desc, "pending"
                        )
                    # 记录到执行日志
                    if self.session_state._execution_logger:
                        self.session_state._execution_logger.log_task_step_update(
                            step.step_id, step_desc, "pending"
                        )
            
            # 如果是最终答案，完成任务
            if action == "final_answer":
                self.session_state.set_status(AgentStatus.COMPLETED)
                answer = action_input.get("answer", "任务完成")
                self.session_state.add_message("assistant", answer)
                
                # 记录任务完成到实时日志
                if self.session_state._realtime_logger:
                    summary = self.session_state.get_summary()
                    self.session_state._realtime_logger.log_task_complete(summary)
                    self.session_state._realtime_logger.close()
                
                # 记录任务完成到执行日志
                if self.session_state._execution_logger:
                    summary = self.session_state.get_summary()
                    self.session_state._execution_logger.log_session_complete(summary)
                
                # 生成最终日志文件
                self._save_session_log()
                
                return {
                    "status": "completed",
                    "message": answer,
                    "session_state": self.session_state
                }
            
            # 检查是否需要人工确认（包括安全模式确认）
            if self._check_requires_confirmation(action, action_input):
                prompt = f"即将执行操作: {action}，参数: {json.dumps(action_input, ensure_ascii=False)}。是否继续？"
                if self.session_state._realtime_logger:
                    self.session_state._realtime_logger.log_human_input_request(prompt)
                if self.session_state._execution_logger:
                    self.session_state._execution_logger.log_human_input_request(prompt, {
                        "action": action,
                        "action_input": action_input
                    })
                self.session_state.request_human_input(prompt)
                return {
                    "status": "awaiting_human_input",
                    "message": prompt,
                    "session_state": self.session_state
                }
            
            # 检查安全模式确认（仅在安全模式启用时）
            if requires_confirmation(action):
                # 如果启用了人机协同，才需要确认
                if self.config.get('agent', {}).get('enable_human_in_the_loop', False):
                    execution_id = str(uuid.uuid4())
                    add_pending_execution(execution_id, action, action_input)
                    self.session_state.set_pending_tool_execution(execution_id, action, action_input)
                    prompt = f"⚠️ 安全模式已启用\n\n工具: **{action}**\n参数: {json.dumps(action_input, ensure_ascii=False, indent=2)}\n\n此操作涉及网络扫描或文件写入，需要您的确认。"
                    if self.session_state._realtime_logger:
                        self.session_state._realtime_logger.log_human_input_request(prompt)
                    if self.session_state._execution_logger:
                        self.session_state._execution_logger.log_human_input_request(prompt, {
                            "action": action,
                            "action_input": action_input,
                            "safe_mode": True
                        })
                    self.session_state.request_human_input(prompt)
                    return {
                        "status": "awaiting_human_input",
                        "message": prompt,
                        "session_state": self.session_state,
                        "requires_safe_mode_confirmation": True
                    }
                # 如果未启用人机协同，直接执行（记录日志但不暂停）
                else:
                    if self.session_state._execution_logger:
                        self.session_state._execution_logger.log_custom("SAFE_MODE_SKIPPED", {
                            "action": action,
                            "action_input": action_input,
                            "reason": "人机协同已关闭，自动执行"
                        })
            
            # 执行工具
            self.session_state.set_status(AgentStatus.EXECUTING)
            
            # 记录工具执行开始
            if self.session_state._realtime_logger:
                self.session_state._realtime_logger.log("INFO", f"开始执行工具: {action}", {
                    "参数": str(action_input)
                })
            if self.session_state._execution_logger:
                self.session_state._execution_logger.log_tool_execution_start(action, action_input)
            
            # 记录执行开始时间
            tool_start_time = time.time()
            tool_result = self._execute_tool(action, action_input)
            tool_execution_time = time.time() - tool_start_time
            
            # 检查工具执行是否成功
            if not tool_result.get("success", False):
                error_msg = tool_result.get("error", "未知错误")
                
                # 如果参数名称错误，尝试自动修复
                if "缺少必需参数" in error_msg or "missing" in error_msg.lower():
                    # 提取需要的参数名
                    param_match = re.search(r'缺少必需参数[：:]\s*(\w+)', error_msg)
                    if not param_match:
                        param_match = re.search(r'missing.*?argument[:\s]+[\'"]?(\w+)', error_msg, re.IGNORECASE)
                    
                    if param_match:
                        required_param = param_match.group(1)
                        # 尝试从现有参数中推断并修复
                        corrected_input = action_input.copy()
                        
                        # 常见的参数名称映射
                        param_mappings = {
                            "target_ip": ["target", "ip", "host", "hostname", "address"],
                            "ip_address": ["ip", "address", "target_ip", "target", "ips"],  # 威胁情报工具参数
                            "ports": ["port", "port_range"],
                            "filepath": ["file", "path", "filename"],
                            "content": ["text", "data", "message"]
                        }
                        
                        # 查找可能的参数映射
                        for correct_param, possible_names in param_mappings.items():
                            if required_param == correct_param:
                                # 查找可能的错误参数名
                                found = False
                                for wrong_name in possible_names:
                                    if wrong_name in action_input:
                                        value = action_input[wrong_name]
                                        
                                        # 特殊处理：如果 wrong_name 是 "ips" 且值是列表，提取第一个 IP
                                        if wrong_name == "ips" and isinstance(value, list) and len(value) > 0:
                                            # 从列表中提取第一个 IP
                                            corrected_input[correct_param] = value[0]
                                            # 保留原始 ips 列表，以便后续处理
                                            if "original_ips" not in corrected_input:
                                                corrected_input["original_ips"] = value[1:]  # 存储剩余的 IP
                                            else:
                                                corrected_input["original_ips"].extend(value[1:])
                                            found = True
                                            break
                                        elif wrong_name != "ips":  # 避免将 "ips" 作为一个普通参数直接复制
                                            # 修复参数名
                                            corrected_input[correct_param] = action_input[wrong_name]
                                            if wrong_name != correct_param:
                                                corrected_input.pop(wrong_name, None)
                                            found = True
                                            break
                                if found:
                                    break
                        
                        # 如果修复了参数，重新执行
                        if corrected_input != action_input:
                            if self.session_state._realtime_logger:
                                self.session_state._realtime_logger.log("INFO", f"自动修复参数：{action_input} -> {corrected_input}")
                            if self.session_state._execution_logger:
                                self.session_state._execution_logger.log_warning(
                                    f"参数名称错误，自动修复",
                                    {"original_input": action_input, "corrected_input": corrected_input, "required_param": required_param}
                                )
                            
                            # 更新当前动作输入
                            self.session_state.current_action_input = corrected_input
                            
                            # 重新执行工具
                            tool_result = self._execute_tool(action, corrected_input)
                            
                            # 如果修复后成功，更新任务步骤并继续执行
                            if tool_result.get("success", False):
                                tool_result_str = json.dumps(tool_result, ensure_ascii=False, indent=2)
                                self.session_state.add_message("tool", f"工具 {action} 执行结果:\n{tool_result_str}")
                                self.session_state.add_execution_log("tool_execution", {
                                    "tool": action,
                                    "args": corrected_input,
                                    "result": tool_result,
                                    "auto_fixed_params": True
                                })
                                
                                # 记录工具执行结果到实时日志
                                if self.session_state._realtime_logger:
                                    self.session_state._realtime_logger.log_tool_execution(
                                        action, corrected_input, tool_result
                                    )
                                
                                # 记录工具执行结果到执行日志
                                if self.session_state._execution_logger:
                                    self.session_state._execution_logger.log_tool_execution_result(
                                        action, tool_result, tool_execution_time
                                    )
                                
                                # 更新任务步骤状态
                                if self.session_state.task_steps:
                                    last_step = self.session_state.task_steps[-1]
                                    if last_step.tool_name == action or (not last_step.tool_name and len(self.session_state.task_steps) > 0):
                                        self.session_state.update_task_step(
                                            last_step.step_id,
                                            status="completed",
                                            result=tool_result,
                                            tool_name=action,
                                            tool_args=corrected_input
                                        )
                                        self.session_state._execution_logger.log_task_step_update(
                                            last_step.step_id,
                                            last_step.description,
                                            "completed",
                                            {
                                                "tool_result": tool_result,
                                                "execution_time": tool_execution_time,
                                                "tool_name": action,
                                                "tool_args": corrected_input
                                            }
                                        )
                                
                                # 继续下一步（跳过后续错误处理）
                                self.session_state.set_status(AgentStatus.REFLECTING)
                                return {
                                    "status": "continuing",
                                    "message": f"已执行 {action}（参数已自动修复），继续下一步",
                                    "session_state": self.session_state,
                                    "tool_result": tool_result
                                }
                            else:
                                # 修复后仍然失败，继续错误处理流程
                                error_msg = tool_result.get("error", "未知错误")
                
                # 如果工具不存在，尝试自动修复
                if "不存在" in error_msg or "not found" in error_msg.lower():
                    # 尝试推断正确的工具
                    corrected_action = None
                    corrected_input = action_input.copy()
                    
                    # 根据错误信息和任务目标推断工具
                    if "command" in action.lower() or "ping" in str(action_input).lower():
                        # 如果是网络连通性检查
                        if "ping" in str(action_input).lower() or "127.0.0.1" in str(action_input):
                            corrected_action = "network_ping"
                            # 提取 IP 地址
                            ip_match = re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', str(action_input))
                            if ip_match:
                                corrected_input = {"target_ip": ip_match.group(0), "port": 80, "timeout": 3.0}
                    elif "nmap" in str(action_input).lower() or "scan" in action.lower():
                        # 如果是端口扫描
                        corrected_action = "port_scan"
                        # 提取 IP 地址
                        ip_match = re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', str(action_input))
                        if ip_match:
                            corrected_input = {"target_ip": ip_match.group(0), "ports": "common"}
                    
                    # 如果推断出正确的工具，自动修复并重试
                    if corrected_action and get_tool(corrected_action):
                        if self.session_state._realtime_logger:
                            self.session_state._realtime_logger.log("INFO", f"自动修复：将工具 {action} 替换为 {corrected_action}")
                        if self.session_state._execution_logger:
                            self.session_state._execution_logger.log_warning(
                                f"工具 {action} 不存在，自动修复为 {corrected_action}",
                                {"original_action": action, "corrected_action": corrected_action, "corrected_input": corrected_input}
                            )
                        
                        # 更新当前动作
                        self.session_state.current_action = corrected_action
                        self.session_state.current_action_input = corrected_input
                        
                        # 重新执行工具
                        tool_result = self._execute_tool(corrected_action, corrected_input)
                        tool_result_str = json.dumps(tool_result, ensure_ascii=False, indent=2)
                        self.session_state.add_message("tool", f"工具 {corrected_action} 执行结果:\n{tool_result_str}")
                        self.session_state.add_execution_log("tool_execution", {
                            "tool": corrected_action,
                            "args": corrected_input,
                            "result": tool_result,
                            "auto_fixed": True
                        })
                        
                        # 如果修复后仍然失败，请求人工介入
                        if not tool_result.get("success", False):
                            prompt = f"工具执行失败（已尝试自动修复）: {tool_result.get('error', '未知错误')}。请提供指导或修正。"
                            self.session_state.request_human_input(prompt)
                            return {
                                "status": "awaiting_human_input",
                                "message": prompt,
                                "session_state": self.session_state
                            }
                    else:
                        # 无法自动修复，请求人工介入
                        available_tools = [t['name'] for t in self.tool_schemas]
                        prompt = f"工具 '{action}' 不存在。可用工具: {', '.join(available_tools)}。请使用正确的工具名称。"
                        self.session_state.request_human_input(prompt)
                        # 记录错误到执行日志
                        if self.session_state._execution_logger:
                            self.session_state._execution_logger.log_error(
                                "ToolNotFoundError", error_msg,
                                context={"tool_name": action, "tool_args": action_input, "available_tools": available_tools}
                            )
                        return {
                            "status": "awaiting_human_input",
                            "message": prompt,
                            "session_state": self.session_state
                        }
                else:
                    # 其他类型的错误，请求人工介入
                    prompt = f"工具执行失败: {error_msg}。请提供指导或修正。"
                    self.session_state.request_human_input(prompt)
                    # 记录错误到执行日志
                    if self.session_state._execution_logger:
                        self.session_state._execution_logger.log_error(
                            "ToolExecutionError", error_msg,
                            context={"tool_name": action, "tool_args": action_input, "tool_result": tool_result}
                        )
                    return {
                        "status": "awaiting_human_input",
                        "message": prompt,
                        "session_state": self.session_state
                    }
            
            # 工具执行成功，记录结果
            tool_result_str = json.dumps(tool_result, ensure_ascii=False, indent=2)
            self.session_state.add_message("tool", f"工具 {action} 执行结果:\n{tool_result_str}")
            self.session_state.add_execution_log("tool_execution", {
                "tool": action,
                "args": action_input,
                "result": tool_result
            })
            
            # 记录到实时日志
            if self.session_state._realtime_logger:
                self.session_state._realtime_logger.log_tool_execution(
                    action, action_input, tool_result
                )
            # 记录到执行日志
            if self.session_state._execution_logger:
                self.session_state._execution_logger.log_tool_execution_result(
                    action, tool_result, tool_execution_time
                )
                # 更新任务步骤状态
                if self.session_state.task_steps:
                    last_step = self.session_state.task_steps[-1]
                    if last_step.tool_name == action or (not last_step.tool_name and len(self.session_state.task_steps) > 0):
                        # 更新最后一个步骤的状态
                        self.session_state.update_task_step(
                            last_step.step_id,
                            status="completed" if tool_result.get("success") else "failed",
                            result=tool_result,
                            tool_name=action,
                            tool_args=action_input
                        )
                        self.session_state._execution_logger.log_task_step_update(
                            last_step.step_id,
                            last_step.description,
                            "completed" if tool_result.get("success") else "failed",
                            {
                                "tool_result": tool_result,
                                "execution_time": tool_execution_time,
                                "tool_name": action,
                                "tool_args": action_input
                            }
                        )
            
            # 继续下一步
            self.session_state.set_status(AgentStatus.REFLECTING)
            return {
                "status": "continuing",
                "message": f"已执行 {action}，继续下一步",
                "session_state": self.session_state,
                "tool_result": tool_result
            }
            
        except Exception as e:
            error_msg = f"Agent 执行出错: {str(e)}"
            self.session_state.set_status(AgentStatus.ERROR)
            self.session_state.add_message("system", error_msg)
            
            # 记录错误到实时日志
            if self.session_state._realtime_logger:
                self.session_state._realtime_logger.log_error(error_msg, e)
                self.session_state._realtime_logger.close()
            
            # 记录错误到执行日志
            if self.session_state._execution_logger:
                self.session_state._execution_logger.log_error(
                    type(e).__name__, error_msg, traceback_str=traceback.format_exc(),
                    context={"current_iteration": self.session_state.current_iteration}
                )
                self.session_state._execution_logger.log_session_complete(self.session_state.get_summary())
            
            # 保存错误日志
            self._save_session_log()
            return {
                "status": "error",
                "message": error_msg,
                "session_state": self.session_state
            }
    
    def _save_session_log(self) -> str:
        """
        保存会话的最终日志
        
        Returns:
            日志文件路径
        """
        if self.session_state is None:
            return ""
        
        os.makedirs("logs", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"session_{self.session_state.session_id[:8]}_{timestamp}.log"
        log_file_path = os.path.join("logs", log_filename)
        
        try:
            summary = self.session_state.get_summary()
            
            with open(log_file_path, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("SecAgent-Core 会话执行日志\n")
                f.write("=" * 80 + "\n\n")
                
                f.write("【会话摘要】\n")
                for key, value in summary.items():
                    if key == "token_usage":
                        f.write(f"Token 使用统计:\n")
                        for k, v in value.items():
                            f.write(f"  {k}: {v}\n")
                    else:
                        f.write(f"{key}: {value}\n")
                f.write("\n")
                
                f.write("【执行统计】\n")
                f.write(f"迭代次数: {self.session_state.current_iteration}/{self.session_state.max_iterations}\n")
                f.write(f"任务步骤数: {len(self.session_state.task_steps)}\n")
                f.write(f"消息数量: {len(self.session_state.messages)}\n")
                f.write("\n")
                
                f.write("【任务步骤】\n")
                for step in self.session_state.task_steps:
                    status_icon = "✅" if step.status == "completed" else "⏳" if step.status == "pending" else "❌"
                    f.write(f"{status_icon} 步骤 {step.step_id}: {step.description}\n")
                    if step.tool_name:
                        f.write(f"   工具: {step.tool_name}\n")
                f.write("\n")
                
                f.write("【执行日志】\n")
                for log_entry in self.session_state.execution_log:
                    timestamp = log_entry.get("timestamp", "N/A")
                    action = log_entry.get("action", "unknown")
                    details = log_entry.get("details", {})
                    f.write(f"[{timestamp}] {action}\n")
                    if details:
                        for k, v in details.items():
                            if k == "token_usage":
                                f.write(f"  Token: {v.get('prompt_tokens', 0)} + {v.get('completion_tokens', 0)} = {v.get('total_tokens', 0)}\n")
                            elif k == "iteration":
                                f.write(f"  iteration: {v}\n")
                            else:
                                f.write(f"  {k}: {v}\n")
                    f.write("\n")
            
            print(f"✓ 会话日志已保存: {log_file_path}")
            
            # 确保执行日志在会话结束时关闭
            if hasattr(self.session_state, '_execution_logger') and self.session_state._execution_logger:
                # 如果还没有通过 log_session_complete 关闭，则在这里关闭
                if self.session_state._execution_logger.file_handle:
                    self.session_state._execution_logger.close()
            
            return log_file_path
        except Exception as e:
            print(f"⚠️  保存会话日志失败: {e}")
            return ""
  