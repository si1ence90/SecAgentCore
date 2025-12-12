"""
SecAgent-Core 命令行界面
"""

import sys
from core.agent import SecAgent
from core.state import AgentStatus
from core.tools import auto_discover_tools, get_all_tools, set_safe_mode, is_safe_mode_enabled
from core.llm import get_model_provider


class CLIInterface:
    """命令行界面类"""
    
    def __init__(self):
        """初始化 CLI 界面"""
        self.agent = SecAgent()
        self.verbose = True  # 默认开启详细模式
        # 确保工具已发现
        auto_discover_tools()
    
    def show_menu(self):
        """显示主菜单"""
        # 顶部标题
        print("\n🔒 SecAgent-Core - 网络安全智能体")
        print("=" * 50)
        
        # 状态信息栏
        if self.agent.session_state:
            state = self.agent.session_state
            status_icon = {
                "idle": "⏸️",
                "planning": "🧠",
                "executing": "⚙️",
                "reflecting": "💭",
                "awaiting_human_input": "⏳",
                "completed": "✅",
                "error": "❌",
                "max_iterations_reached": "⚠️"
            }.get(state.status.value, "📊")
            
            status_text = f"{status_icon} {state.status.value}"
            print(f"\n📋 状态: {status_text:20s}  🔄 迭代: {state.current_iteration:2d}/{state.max_iterations:2d}  📝 步骤: {len(state.task_steps):2d}")
        else:
            print("\n📋 状态: 无活动会话")
        
        # 设置状态
        safe_mode_status = "✅ 已启用" if is_safe_mode_enabled() else "❌ 已禁用"
        verbose_status = "✅ 已启用" if self.verbose else "❌ 已禁用"
        from core.llm import get_model_provider
        model_provider = get_model_provider()
        current_provider = model_provider.current_provider or "未设置"
        
        print(f"🔐 安全模式: {safe_mode_status:10s}  📊 详细模式: {verbose_status:10s}  🤖 LLM: {current_provider:15s}")
        
        # 主菜单
        print("\n📋 主菜单")
        print("=" * 50)
        
        # 核心功能组
        print("\n【核心功能】")
        print("  1. 创建新任务")
        print("  2. 执行一步")
        print("  3. 继续执行（自动完成）")
        print("  4. 查看状态")
        
        # 设置组
        print("\n【设置选项】")
        print("  5. 切换安全模式")
        print("  6. 查看可用工具")
        print("  7. 切换 LLM 提供商")
        print("  8. 切换详细模式")
        
        # 退出
        print("\n【退出】")
        print("  0. 退出程序")
        
        # 底部提示
        print("\n💡 提示: 输入对应数字选择操作，按 Ctrl+C 可随时退出")
        print("-" * 60)
    
    def create_task(self):
        """创建新任务"""
        print("\n请输入任务描述:")
        user_goal = input("> ").strip()
        
        if not user_goal:
            print("⚠️  任务描述不能为空")
            return
        
        try:
            self.agent.create_session(user_goal)
            print(f"\n✓ 任务已创建: {user_goal}")
            print(f"会话 ID: {self.agent.session_state.session_id[:8]}")
        except Exception as e:
            print(f"❌ 创建任务失败: {e}")
    
    def step(self):
        """执行一步"""
        if not self.agent.session_state:
            print("⚠️  请先创建任务")
            return
        
        if self.agent.session_state.status == AgentStatus.AWAITING_HUMAN_INPUT:
            print(f"\n⚠️  需要人工输入: {self.agent.session_state.human_input_prompt}")
            user_input = input("请输入: ").strip()
            result = self.agent.step(user_input)
        else:
            if self.verbose:
                print("\n🔄 正在执行一步...")
            result = self.agent.step()
        
        self._display_result(result)
    
    def continue_execution(self):
        """继续执行直到完成"""
        if not self.agent.session_state:
            print("⚠️  请先创建任务")
            return
        
        print("\n开始自动执行...")
        max_iterations = 50  # 防止无限循环
        iteration = 0
        
        while iteration < max_iterations:
            if self.agent.session_state.status in [AgentStatus.COMPLETED, AgentStatus.ERROR, AgentStatus.MAX_ITERATIONS_REACHED]:
                break
            
            if self.agent.session_state.status == AgentStatus.AWAITING_HUMAN_INPUT:
                print(f"\n⚠️  需要人工输入: {self.agent.session_state.human_input_prompt}")
                user_input = input("请输入: ").strip()
                result = self.agent.step(user_input)
            else:
                result = self.agent.step()
            
            status = result.get("status", "unknown")
            
            if self.verbose:
                self._display_result(result)
            else:
                if status == "continuing":
                    print(f"✓ 迭代 {self.agent.session_state.current_iteration}: {result.get('message', '')}")
                elif status == "completed":
                    print(f"\n✅ 任务完成: {result.get('message', '')}")
                elif status == "error":
                    print(f"\n❌ 执行出错: {result.get('message', '')}")
                elif status == "awaiting_human_input":
                    print(f"\n⚠️  等待人工输入...")
                    continue
            
            iteration += 1
        
        if iteration >= max_iterations:
            print("\n⚠️  达到最大迭代次数限制")
        
        # 显示最终状态
        self.show_status()
    
    def show_status(self):
        """显示当前状态"""
        if not self.agent.session_state:
            print("⚠️  没有活动会话")
            return
        
        state = self.agent.session_state
        print("\n" + "=" * 60)
        print("当前状态")
        print("=" * 60)
        print(f"会话 ID: {state.session_id[:8]}")
        print(f"状态: {state.status.value}")
        print(f"用户目标: {state.user_goal}")
        print(f"迭代次数: {state.current_iteration}/{state.max_iterations}")
        print(f"任务步骤数: {len(state.task_steps)}")
        print(f"消息数量: {len(state.messages)}")
        
        # Token 统计
        token_usage = state.token_usage
        print(f"\nToken 使用:")
        print(f"  提示词: {token_usage.prompt_tokens:,}")
        print(f"  完成: {token_usage.completion_tokens:,}")
        print(f"  总计: {token_usage.total_tokens:,}")
        print(f"  API 调用: {token_usage.api_calls}")
        
        # 任务步骤
        if state.task_steps:
            print(f"\n任务步骤:")
            for step in state.task_steps:
                status_icon = "✅" if step.status == "completed" else "⏳" if step.status == "pending" else "❌"
                print(f"  {status_icon} 步骤 {step.step_id}: {step.description}")
                if step.tool_name:
                    print(f"     工具: {step.tool_name}")
        
        # 当前执行上下文（详细模式显示更多信息）
        if self.verbose:
            if state.current_thought:
                print(f"\n💭 当前思考:")
                thought_lines = self._wrap_text(state.current_thought, 60)
                for line in thought_lines:
                    print(f"  {line}")
            if state.current_plan:
                print(f"\n📋 当前计划:")
                for i, plan_item in enumerate(state.current_plan, 1):
                    print(f"  {i}. {plan_item}")
            if state.current_action:
                print(f"\n🔧 当前动作: {state.current_action}")
                if state.current_action_input:
                    import json
                    print(f"  参数: {json.dumps(state.current_action_input, ensure_ascii=False)}")
        else:
            # 非详细模式，只显示简要信息
            if state.current_thought:
                print(f"\n当前思考: {state.current_thought[:100]}...")
            if state.current_plan:
                print(f"当前计划: {state.current_plan}")
            if state.current_action:
                print(f"当前动作: {state.current_action}")
        
        print("=" * 60)
    
    def toggle_safe_mode(self):
        """切换安全模式"""
        current = is_safe_mode_enabled()
        set_safe_mode(not current)
        print(f"\n✓ 安全模式: {'已启用' if not current else '已禁用'}")
    
    def show_tools(self):
        """显示可用工具"""
        auto_discover_tools()  # 确保工具已发现
        tools = get_all_tools()
        
        if not tools:
            print("\n⚠️  暂无可用工具")
            return
        
        print("\n" + "=" * 60)
        print("可用工具")
        print("=" * 60)
        
        for tool_name, tool_class in tools.items():
            tool_instance = tool_class()
            print(f"\n工具名称: {tool_name}")
            print(f"描述: {tool_instance.description}")
            print(f"需要安全确认: {'是' if tool_instance.requires_safe_mode_confirmation else '否'}")
        
        print("=" * 60)
    
    def switch_provider(self):
        """切换 LLM 提供商"""
        model_provider = get_model_provider()
        available = model_provider.get_available_providers()
        
        if not available:
            print("⚠️  没有可用的 LLM 提供商")
            return
        
        print("\n可用提供商:")
        for i, provider in enumerate(available, 1):
            current = " (当前)" if provider == model_provider.current_provider else ""
            print(f"{i}. {provider}{current}")
        
        try:
            choice = input("\n请选择 (1-{}): ".format(len(available))).strip()
            idx = int(choice) - 1
            if 0 <= idx < len(available):
                model_provider.set_provider(available[idx])
                print(f"✓ 已切换到: {available[idx]}")
            else:
                print("⚠️  无效选择")
        except ValueError:
            print("⚠️  无效输入")
    
    def toggle_verbose(self):
        """切换详细模式"""
        self.verbose = not self.verbose
        print(f"\n✓ 详细模式: {'已启用' if self.verbose else '已禁用'}")
    
    def _display_result(self, result: dict):
        """显示执行结果（详细模式）"""
        if not self.verbose:
            # 非详细模式，只显示简要信息
            status = result.get("status", "unknown")
            message = result.get("message", "")
            print(f"\n[{status}] {message}")
            return
        
        # 详细模式：友好展示所有信息
        state = self.agent.session_state
        status = result.get("status", "unknown")
        
        print("\n" + "=" * 70)
        print(f"📊 迭代 {state.current_iteration}/{state.max_iterations} - {status.upper()}")
        print("=" * 70)
        
        # 1. 思考内容
        if state.current_thought:
            print("\n💭 Agent 思考:")
            print("-" * 70)
            # 分段显示，每行不超过70字符
            thought_lines = self._wrap_text(state.current_thought, 70)
            for line in thought_lines:
                print(f"  {line}")
        
        # 2. 任务规划
        if state.current_plan:
            print("\n📋 任务规划:")
            print("-" * 70)
            for i, plan_item in enumerate(state.current_plan, 1):
                print(f"  {i}. {plan_item}")
        
        # 3. 工具选择
        if state.current_action and state.current_action != "final_answer":
            print("\n🔧 工具选择:")
            print("-" * 70)
            print(f"  工具名称: {state.current_action}")
            if state.current_action_input:
                print(f"  工具参数:")
                import json
                params_str = json.dumps(state.current_action_input, ensure_ascii=False, indent=4)
                for line in params_str.split('\n'):
                    print(f"    {line}")
        
        # 4. 执行结果
        if "tool_result" in result:
            tool_result = result["tool_result"]
            print("\n📤 执行结果:")
            print("-" * 70)
            if tool_result.get("success"):
                print("  ✅ 执行成功")
                result_data = tool_result.get("result", {})
                if result_data:
                    # 格式化显示结果
                    self._display_tool_result(result_data)
            else:
                print(f"  ❌ 执行失败: {tool_result.get('error', '未知错误')}")
        
        # 5. 执行进度
        if state.task_steps:
            print("\n📈 执行进度:")
            print("-" * 70)
            completed_count = sum(1 for s in state.task_steps if s.status == "completed")
            total_count = len(state.task_steps)
            print(f"  进度: {completed_count}/{total_count} 步骤已完成")
            for step in state.task_steps:
                status_icon = "✅" if step.status == "completed" else "⏳" if step.status == "pending" else "❌"
                status_text = "已完成" if step.status == "completed" else "进行中" if step.status == "executing" else "待执行" if step.status == "pending" else "失败"
                print(f"  {status_icon} 步骤 {step.step_id}: {step.description} [{status_text}]")
                if step.tool_name:
                    print(f"      └─ 工具: {step.tool_name}")
        
        # 6. 状态信息
        print("\n📊 状态信息:")
        print("-" * 70)
        print(f"  当前状态: {state.status.value}")
        print(f"  Token 使用: {state.token_usage.total_tokens:,} (提示词: {state.token_usage.prompt_tokens:,}, 完成: {state.token_usage.completion_tokens:,})")
        
        print("=" * 70)
    
    def _wrap_text(self, text: str, width: int) -> list:
        """文本换行"""
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            if len(current_line) + len(word) + 1 <= width:
                current_line += (word + " ") if current_line else word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return lines
    
    def _display_tool_result(self, result_data: dict):
        """格式化显示工具执行结果"""
        import json
        
        # 如果是字典，尝试格式化显示
        if isinstance(result_data, dict):
            # 特殊处理常见的结果格式
            if "summary" in result_data:
                print("  📝 摘要:")
                for key, value in result_data["summary"].items():
                    print(f"    • {key}: {value}")
            
            if "open_ports" in result_data:
                print(f"  🔍 开放端口: {result_data.get('open_ports', [])}")
                if "open_ports_info" in result_data:
                    print("  📋 端口详情:")
                    for port_info in result_data["open_ports_info"][:10]:  # 只显示前10个
                        print(f"    • 端口 {port_info.get('port')}: {port_info.get('service', 'Unknown')}")
            
            if "is_reachable" in result_data:
                reachable = result_data.get("is_reachable", False)
                icon = "✅" if reachable else "❌"
                print(f"  {icon} 网络连通性: {'可达' if reachable else '不可达'}")
                if reachable and "response_time_ms" in result_data:
                    print(f"    ⏱️  响应时间: {result_data['response_time_ms']} ms")
            
            if "files" in result_data:
                print("  📄 生成的文件:")
                for format_type, file_path in result_data["files"].items():
                    print(f"    • {format_type.upper()}: {file_path}")
            
            # 显示其他重要字段
            important_keys = ["ip_address", "target_ip", "filepath", "title", "message"]
            for key in important_keys:
                if key in result_data and key not in ["summary", "open_ports", "is_reachable", "files"]:
                    value = result_data[key]
                    if isinstance(value, (str, int, float, bool)):
                        print(f"  • {key}: {value}")
            
            # 如果有其他未显示的字段，显示前几个
            displayed_keys = {"summary", "open_ports", "open_ports_info", "is_reachable", "response_time_ms", "files", "ip_address", "target_ip", "filepath", "title", "message"}
            remaining_keys = [k for k in result_data.keys() if k not in displayed_keys and not k.startswith("_")]
            if remaining_keys:
                print(f"  📦 其他信息: {', '.join(remaining_keys[:5])}")
        else:
            # 非字典类型，直接显示
            result_str = str(result_data)
            if len(result_str) > 200:
                print(f"  {result_str[:200]}...")
            else:
                print(f"  {result_str}")
    
    def run(self):
        """运行 CLI 界面"""
        while True:
            self.show_menu()
            try:
                choice = input("\n请选择操作: ").strip()
                
                if choice == "0":
                    print("\n再见！")
                    break
                elif choice == "1":
                    self.create_task()
                elif choice == "2":
                    self.step()
                elif choice == "3":
                    self.continue_execution()
                elif choice == "4":
                    self.show_status()
                elif choice == "5":
                    self.toggle_safe_mode()
                elif choice == "6":
                    self.show_tools()
                elif choice == "7":
                    self.switch_provider()
                elif choice == "8":
                    self.toggle_verbose()
                else:
                    print("⚠️  无效选择，请重试")
            except KeyboardInterrupt:
                print("\n\n再见！")
                break
            except Exception as e:
                print(f"\n❌ 发生错误: {e}")
                import traceback
                traceback.print_exc()


def main():
    """主函数"""
    cli = CLIInterface()
    cli.run()


if __name__ == "__main__":
    main()

