"""
知识库管理模块
"""

import os
import re
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path


class KnowledgeBase:
    """知识库管理器"""
    
    def __init__(self, knowledge_dir: str = "knowledge_base"):
        """
        初始化知识库
        
        Args:
            knowledge_dir: 知识库目录
        """
        self.knowledge_dir = Path(knowledge_dir)
        self.knowledge_files: List[Dict[str, Any]] = []
        self._load_knowledge_files()
    
    def _load_knowledge_files(self) -> None:
        """加载知识库文件"""
        if not self.knowledge_dir.exists():
            self.knowledge_dir.mkdir(parents=True, exist_ok=True)
            return
        
        for file_path in self.knowledge_dir.glob("*.txt"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # 解析知识库文件
                knowledge_entry = {
                    "file": file_path.name,
                    "path": str(file_path),
                    "content": content,
                    "scenario": self._extract_field(content, "场景"),
                    "applicable_tasks": self._extract_applicable_tasks(content),
                    "planning_steps": self._extract_planning_steps(content)
                }
                
                self.knowledge_files.append(knowledge_entry)
            except Exception as e:
                print(f"⚠️  加载知识库文件 {file_path} 失败: {e}")
    
    def _extract_field(self, content: str, field_name: str) -> Optional[str]:
        """提取字段值"""
        pattern = rf"{field_name}[:：]\s*(.+?)(?=\n\n|\n适用任务|$)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None
    
    def _extract_applicable_tasks(self, content: str) -> List[str]:
        """提取适用任务列表"""
        pattern = r"适用任务[:：]\s*\n((?:- .+\n?)+)"
        match = re.search(pattern, content)
        if match:
            tasks_text = match.group(1)
            tasks = re.findall(r"- (.+)", tasks_text)
            return [task.strip() for task in tasks]
        return []
    
    def _extract_planning_steps(self, content: str) -> str:
        """提取任务规划步骤"""
        pattern = r"任务规划步骤[:：]\s*\n((?:.+\n?)+?)(?=\n工具使用指南|$)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""
    
    def search(self, query: str, top_k: int = 1) -> List[Dict[str, Any]]:
        """
        搜索相关知识库
        
        Args:
            query: 查询文本
            top_k: 返回前 k 个结果
            
        Returns:
            相关知识库条目列表
        """
        query_lower = query.lower()
        results = []
        
        for entry in self.knowledge_files:
            score = 0.0
            
            # 检查场景匹配
            if entry["scenario"]:
                scenario_lower = entry["scenario"].lower()
                if any(keyword in scenario_lower for keyword in query_lower.split()):
                    score += 0.3
            
            # 检查适用任务匹配
            for task in entry["applicable_tasks"]:
                task_lower = task.lower()
                # 计算关键词匹配度
                query_keywords = set(query_lower.split())
                task_keywords = set(task_lower.split())
                if query_keywords & task_keywords:
                    score += 0.5 / len(entry["applicable_tasks"])
            
            # 检查内容匹配
            content_lower = entry["content"].lower()
            for keyword in query_lower.split():
                if keyword in content_lower:
                    score += 0.1
            
            if score > 0.3:  # 相关性阈值
                results.append({
                    "entry": entry,
                    "score": score
                })
        
        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return results[:top_k]
    
    def get_knowledge_for_task(self, task_description: str) -> Optional[str]:
        """
        获取任务相关的知识库内容
        
        Args:
            task_description: 任务描述
            
        Returns:
            知识库内容（如果找到相关条目）
        """
        results = self.search(task_description, top_k=1)
        
        if results and results[0]["score"] > 0.3:
            entry = results[0]["entry"]
            return entry["content"]
        
        return None
    
    def get_all_knowledge(self) -> List[Dict[str, Any]]:
        """获取所有知识库条目"""
        return [
            {
                "file": entry["file"],
                "scenario": entry["scenario"],
                "applicable_tasks": entry["applicable_tasks"]
            }
            for entry in self.knowledge_files
        ]


# 全局知识库实例
_knowledge_base: Optional[KnowledgeBase] = None


def get_knowledge_base(knowledge_dir: str = "knowledge_base") -> KnowledgeBase:
    """
    获取全局知识库实例（单例模式）
    
    Args:
        knowledge_dir: 知识库目录
        
    Returns:
        KnowledgeBase 实例
    """
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase(knowledge_dir)
    return _knowledge_base



