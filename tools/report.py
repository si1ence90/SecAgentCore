"""
报告生成工具模块
"""

import os
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from core.tools import BaseTool, register_tool
from core.llm import get_model_provider
import markdown  # For Markdown to HTML conversion


@register_tool
class ReportGeneratorTool(BaseTool):
    """报告生成工具"""
    
    name = "report_generator"
    description = "将执行过程中的数据和结果整理成高质量的报告。支持生成 Markdown 和 HTML 格式。可以传入文本内容、执行结果、统计数据等，工具会自动调用 LLM 整理成结构化的报告。"
    requires_safe_mode_confirmation = False
    
    def execute(
        self,
        content: str,
        title: Optional[str] = None,
        output_dir: str = "reports",
        formats: Optional[List[str]] = None,
        include_timestamp: bool = True,
        model_provider: Optional[str] = None,  # 允许指定LLM模型
        llm_temperature: Optional[float] = None  # 允许指定LLM温度
    ) -> Dict[str, Any]:
        """
        生成报告
        
        Args:
            content: 要整理成报告的原始文本内容（例如：执行日志摘要、关键发现、分析结果等）
            title: 报告标题，如果未提供则自动生成
            output_dir: 报告输出目录，默认为 'reports'
            formats: 报告输出格式列表，支持 'markdown', 'html'，默认为 ['markdown', 'html']
            include_timestamp: 是否在报告标题和文件名中包含时间戳，默认为 True
            model_provider: 用于生成报告的LLM模型名称，如果未提供则使用默认配置
            llm_temperature: LLM的温度参数，如果未提供则使用默认配置
            
        Returns:
            包含报告生成结果的字典，包括生成的文件路径
        """
        if formats is None:
            formats = ["markdown", "html"]
        
        # 创建输出目录
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if not title:
                title = f"执行报告_{timestamp}"
            
            # 调用 LLM 整理报告内容
            report_content = self._generate_report_with_llm(content, title, include_timestamp, model_provider, llm_temperature)
            
            # 生成报告文件
            report_files = {}
            
            if "markdown" in formats:
                md_file = self._save_markdown(report_content, title, output_dir, timestamp)
                report_files["markdown"] = str(md_file)
            
            if "html" in formats:
                html_file = self._save_html(report_content, title, output_dir, timestamp)
                report_files["html"] = str(html_file)
            
            return {
                "success": True,
                "title": title,
                "formats": formats,
                "files": report_files,
                "output_dir": output_dir,
                "timestamp": timestamp,
                "result": {
                    "message": f"报告已成功生成：{', '.join(formats)} 格式",
                    "files": report_files
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"生成报告失败: {str(e)}",
                "result": None
            }
    
    def _generate_report_with_llm(
        self,
        content: str,
        title: str,
        include_timestamp: bool,
        llm_model: Optional[str],
        llm_temperature: Optional[float]
    ) -> str:
        """
        使用 LLM 整理报告内容
        """
        # 获取模型提供商（使用默认配置）
        model_provider = get_model_provider()
        
        # 确保模型提供商已初始化
        if not model_provider.current_provider:
            # 从配置中获取默认提供商
            provider_name = model_provider.config.get('llm', {}).get('provider', 'deepseek-chat')
            model_provider.set_provider(provider_name)
        
        # 构建提示词
        timestamp_info = ""
        if include_timestamp:
            timestamp_info = f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        prompt = f"""请将以下内容整理成一份简洁、专业的网络安全执行报告。

报告标题: {title}
{timestamp_info}

原始内容:
{content}

请按照以下要求整理报告:

1. **报告结构（保持简洁）**:
   - 执行摘要（2-3 句话概括主要发现）
   - 关键发现（使用表格或列表展示核心数据）
   - 结论与建议（简要总结和行动建议）

2. **格式要求**:
   - 使用 Markdown 格式
   - 使用清晰的标题层级（#、##）
   - 优先使用表格展示结构化数据
   - 使用列表展示要点
   - 重要信息使用**粗体**强调
   - 避免冗长的描述，保持简洁明了

3. **内容要求**:
   - **保持简洁**: 每个部分控制在合理长度，避免冗余
   - **突出重点**: 优先展示关键数据和重要发现
   - **结构清晰**: 使用表格和列表，而不是长段落
   - **实用建议**: 提供可执行的建议，避免空泛的描述

4. **简洁原则**:
   - 删除重复信息
   - 合并相似内容
   - 使用表格替代长文本描述
   - 每个段落不超过 3-4 句话

请直接输出整理后的报告内容（Markdown 格式），保持简洁专业，不要添加额外的解释或说明。"""
        
        messages = [
            {"role": "system", "content": "你是一个专业的报告撰写助手，擅长将原始数据整理成简洁、结构化、高质量的网络安全报告。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            # 调用 LLM
            report_content, _ = model_provider.chat_completion(
                messages=messages,
                temperature=llm_temperature or model_provider.llm_config.temperature
            )
            return report_content
        except Exception as e:
            print(f"⚠️  LLM 生成报告失败，使用备用方案: {e}")
            # 备用方案：直接将原始内容格式化为 Markdown
            return f"# {title}\n\n## 原始内容\n\n```\n{content}\n```\n\n## 备注\n\nLLM 生成报告失败，此为自动生成的简要报告。"
    
    def _save_markdown(self, content: str, title: str, output_dir: str, timestamp: str) -> Path:
        """
        保存 Markdown 格式报告
        """
        filename = f"{title.replace(' ', '_').replace('/', '_')}_{timestamp}.md"
        file_path = Path(output_dir) / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return file_path
    
    def _save_html(self, content: str, title: str, output_dir: str, timestamp: str) -> Path:
        """
        保存 HTML 格式报告
        """
        html_content = self._markdown_to_html(content, title)
        filename = f"{title.replace(' ', '_').replace('/', '_')}_{timestamp}.html"
        file_path = Path(output_dir) / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return file_path
    
    def _markdown_to_html(self, md_content: str, title: str) -> str:
        """
        将 Markdown 内容转换为 HTML，并添加样式
        """
        html_body = markdown.markdown(md_content, extensions=['fenced_code', 'tables'])
        
        # 简单的 HTML 模板和样式
        html_template = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 20px; background-color: #f4f7f6; }}
        .container {{ max-width: 900px; margin: 20px auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }}
        h1, h2, h3, h4, h5, h6 {{ color: #2c3e50; margin-top: 1.5em; margin-bottom: 0.8em; }}
        h1 {{ font-size: 2.2em; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
        h2 {{ font-size: 1.8em; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
        h3 {{ font-size: 1.4em; }}
        a {{ color: #3498db; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        pre {{ background-color: #ecf0f1; border: 1px solid #ddd; border-left: 4px solid #3498db; padding: 15px; border-radius: 5px; overflow-x: auto; font-family: 'Consolas', 'Monaco', monospace; font-size: 0.9em; }}
        code {{ font-family: 'Consolas', 'Monaco', monospace; background-color: #e0e0e0; padding: 2px 4px; border-radius: 3px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 1em; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
        th {{ background-color: #f0f0f0; font-weight: bold; }}
        ul, ol {{ margin-left: 20px; }}
        blockquote {{ border-left: 4px solid #ccc; margin: 1.5em 0; padding: 0.5em 10px; color: #666; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; text-align: center; font-size: 0.9em; color: #777; }}
    </style>
</head>
<body>
    <div class="container">
        {html_body}
    </div>
    <div class="footer">
        <p>Generated by SecAgent-Core on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
</body>
</html>
"""
        return html_template



