"""
SecAgent-Core Streamlit Web 界面
注意：需要 64 位 Python 3.10+
"""

import streamlit as st
from core.agent import SecAgent
from core.state import AgentStatus
from core.tools import auto_discover_tools, get_all_tools, set_safe_mode, is_safe_mode_enabled
from core.llm import get_model_provider


# 页面配置
st.set_page_config(
    page_title="SecAgent-Core",
    page_icon="🔒",
    layout="wide"
)

# 初始化
if 'agent' not in st.session_state:
    st.session_state.agent = SecAgent()
    auto_discover_tools()

if 'verbose' not in st.session_state:
    st.session_state.verbose = False


def main():
    """主函数"""
    st.title("🔒 SecAgent-Core - 网络安全智能体")
    
    # 侧边栏
    with st.sidebar:
        st.header("设置")
        
        # 安全模式
        safe_mode = st.checkbox("安全模式", value=is_safe_mode_enabled())
        set_safe_mode(safe_mode)
        
        # LLM 提供商切换
        model_provider = get_model_provider()
        available_providers = model_provider.get_available_providers()
        if available_providers:
            selected_provider = st.selectbox(
                "LLM 提供商",
                available_providers,
                index=available_providers.index(model_provider.current_provider) if model_provider.current_provider in available_providers else 0
            )
            if selected_provider != model_provider.current_provider:
                try:
                    model_provider.set_provider(selected_provider)
                    st.success(f"已切换到: {selected_provider}")
                except Exception as e:
                    st.error(f"切换失败: {e}")
        
        # 详细模式
        st.session_state.verbose = st.checkbox("详细模式", value=st.session_state.verbose)
        
        # 工具列表
        st.header("可用工具")
        tools = get_all_tools()
        for tool_name in tools.keys():
            st.text(f"• {tool_name}")
    
    # 主界面
    agent = st.session_state.agent
    
    # 创建新任务
    if not agent.session_state:
        st.header("创建新任务")
        user_goal = st.text_area("请输入任务描述", height=100)
        
        if st.button("创建任务", type="primary"):
            if user_goal.strip():
                try:
                    agent.create_session(user_goal.strip())
                    st.success("任务已创建！")
                    st.rerun()
                except Exception as e:
                    st.error(f"创建任务失败: {e}")
    else:
        # 显示当前状态
        state = agent.session_state
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("状态", state.status.value)
        with col2:
            st.metric("迭代次数", f"{state.current_iteration}/{state.max_iterations}")
        with col3:
            st.metric("任务步骤", len(state.task_steps))
        
        # Token 统计
        token_usage = state.token_usage
        st.info(f"Token 使用: {token_usage.total_tokens:,} (提示词: {token_usage.prompt_tokens:,}, 完成: {token_usage.completion_tokens:,}, API 调用: {token_usage.api_calls})")
        
        # 任务步骤
        if state.task_steps:
            st.subheader("任务步骤")
            for step in state.task_steps:
                status_icon = "✅" if step.status == "completed" else "⏳" if step.status == "pending" else "❌"
                st.text(f"{status_icon} 步骤 {step.step_id}: {step.description}")
        
        # 操作按钮
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("执行一步"):
                if state.status == AgentStatus.AWAITING_HUMAN_INPUT:
                    st.warning("需要人工输入")
                else:
                    result = agent.step()
                    st.rerun()
        
        with col2:
            if st.button("继续执行"):
                st.info("自动执行中...")
                max_iterations = 50
                iteration = 0
                
                while iteration < max_iterations:
                    if state.status in [AgentStatus.COMPLETED, AgentStatus.ERROR, AgentStatus.MAX_ITERATIONS_REACHED]:
                        break
                    
                    if state.status == AgentStatus.AWAITING_HUMAN_INPUT:
                        break
                    
                    result = agent.step()
                    iteration += 1
                
                st.rerun()
        
        with col3:
            if st.button("查看详细状态"):
                st.json(state.get_summary())
        
        # 人工输入
        if state.status == AgentStatus.AWAITING_HUMAN_INPUT:
            st.warning(f"需要人工输入: {state.human_input_prompt}")
            user_input = st.text_input("请输入")
            if st.button("提交"):
                result = agent.step(user_input)
                st.rerun()
        
        # 详细模式显示
        if st.session_state.verbose:
            st.divider()
            st.subheader("📊 详细执行信息")
            
            # 1. 思考内容
            if state.current_thought:
                with st.expander("💭 Agent 思考", expanded=True):
                    st.write(state.current_thought)
            
            # 2. 任务规划
            if state.current_plan:
                with st.expander("📋 任务规划", expanded=True):
                    for i, plan_item in enumerate(state.current_plan, 1):
                        st.write(f"{i}. {plan_item}")
            
            # 3. 工具选择
            if state.current_action and state.current_action != "final_answer":
                with st.expander("🔧 工具选择", expanded=True):
                    st.write(f"**工具名称:** `{state.current_action}`")
                    if state.current_action_input:
                        st.write("**工具参数:**")
                        st.json(state.current_action_input)
            
            # 4. 执行进度
            if state.task_steps:
                with st.expander("📈 执行进度", expanded=True):
                    completed_count = sum(1 for s in state.task_steps if s.status == "completed")
                    total_count = len(state.task_steps)
                    progress = completed_count / total_count if total_count > 0 else 0
                    st.progress(progress)
                    st.caption(f"已完成 {completed_count}/{total_count} 步骤")
                    
                    for step in state.task_steps:
                        status_icon = "✅" if step.status == "completed" else "⏳" if step.status == "pending" else "❌"
                        status_color = "green" if step.status == "completed" else "orange" if step.status == "pending" else "red"
                        st.markdown(f"{status_icon} **步骤 {step.step_id}:** {step.description}")
                        if step.tool_name:
                            st.caption(f"工具: {step.tool_name}")
                        if step.result:
                            with st.expander(f"查看步骤 {step.step_id} 结果"):
                                if step.result.get("success"):
                                    st.success("执行成功")
                                    if step.result.get("result"):
                                        st.json(step.result["result"])
                                else:
                                    st.error(f"执行失败: {step.result.get('error', '未知错误')}")
            
            # 5. 最近执行结果
            if state.execution_log:
                with st.expander("📤 最近执行结果"):
                    for log_entry in state.execution_log[-5:]:  # 显示最后5条
                        action = log_entry.get("action", "unknown")
                        details = log_entry.get("details", {})
                        st.write(f"**{action}**")
                        if details:
                            if "tool_result" in details:
                                tool_result = details["tool_result"]
                                if tool_result.get("success"):
                                    st.success("✅ 执行成功")
                                    if tool_result.get("result"):
                                        # 格式化显示结果
                                        result_data = tool_result["result"]
                                        if isinstance(result_data, dict):
                                            if "summary" in result_data:
                                                st.json(result_data["summary"])
                                            elif "open_ports" in result_data:
                                                st.write(f"开放端口: {result_data.get('open_ports', [])}")
                                            elif "is_reachable" in result_data:
                                                st.write(f"网络连通性: {'可达' if result_data.get('is_reachable') else '不可达'}")
                                            else:
                                                st.json(result_data)
                                        else:
                                            st.write(str(result_data))
                                else:
                                    st.error(f"❌ 执行失败: {tool_result.get('error', '未知错误')}")
                            elif "token_usage" in details:
                                token_info = details["token_usage"]
                                st.caption(f"Token: {token_info.get('total_tokens', 0):,}")
            
            # 6. 消息历史
            with st.expander("💬 消息历史"):
                for msg in state.messages[-10:]:  # 显示最后10条
                    role_icon = {"system": "⚙️", "user": "👤", "assistant": "🤖", "tool": "🔧"}.get(msg.role, "📝")
                    st.markdown(f"**{role_icon} [{msg.role}]**")
                    content = msg.content
                    if len(content) > 500:
                        st.text(content[:500] + "...")
                    else:
                        st.text(content)


if __name__ == "__main__":
    main()

