"""
工具基类和注册机制
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type
from pydantic import BaseModel, Field
import uuid

# 工具注册表
_tool_registry: Dict[str, Type] = {}
_safe_mode_enabled: bool = False
_pending_executions: Dict[str, Dict[str, Any]] = {}


def register_tool(tool_class: Type) -> Type:
    """
    工具注册装饰器
    
    Args:
        tool_class: 工具类
        
    Returns:
        工具类
    """
    if not issubclass(tool_class, BaseTool):
        raise ValueError(f"{tool_class.__name__} 必须继承自 BaseTool")
    
    tool_instance = tool_class()
    tool_name = tool_instance.name
    
    if tool_name in _tool_registry:
        raise ValueError(f"工具 {tool_name} 已注册")
    
    _tool_registry[tool_name] = tool_class
    return tool_class


def get_tool(tool_name: str):
    """
    获取工具实例
    
    Args:
        tool_name: 工具名称
        
    Returns:
        工具实例
    """
    if tool_name not in _tool_registry:
        return None
    return _tool_registry[tool_name]()


def get_all_tools() -> Dict[str, Type]:
    """获取所有已注册的工具"""
    return _tool_registry.copy()


def set_safe_mode(enabled: bool) -> None:
    """设置安全模式"""
    global _safe_mode_enabled
    _safe_mode_enabled = enabled


def is_safe_mode_enabled() -> bool:
    """检查安全模式是否启用"""
    return _safe_mode_enabled


def requires_confirmation(tool_name: str) -> bool:
    """
    检查工具是否需要确认
    
    Args:
        tool_name: 工具名称
        
    Returns:
        是否需要确认
    """
    if not _safe_mode_enabled:
        return False
    
    tool_class = _tool_registry.get(tool_name)
    if not tool_class:
        return False
    
    tool_instance = tool_class()
    return getattr(tool_instance, 'requires_safe_mode_confirmation', False)


def add_pending_execution(execution_id: str, tool_name: str, tool_args: Dict[str, Any]) -> None:
    """添加待确认的执行"""
    _pending_executions[execution_id] = {
        "tool_name": tool_name,
        "tool_args": tool_args
    }


def get_pending_execution(execution_id: str) -> Optional[Dict[str, Any]]:
    """获取待确认的执行"""
    return _pending_executions.get(execution_id)


def remove_pending_execution(execution_id: str) -> None:
    """移除待确认的执行"""
    _pending_executions.pop(execution_id, None)


class ToolParameter(BaseModel):
    """工具参数模型"""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


class ToolSchema(BaseModel):
    """工具 Schema 模型"""
    name: str
    description: str
    parameters: List[ToolParameter]


class BaseTool(ABC):
    """工具基类"""
    
    name: str = ""
    description: str = ""
    requires_safe_mode_confirmation: bool = False
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行工具
        
        Args:
            **kwargs: 工具参数
            
        Returns:
            执行结果字典，必须包含 'success' 字段
        """
        pass
    
    def get_schema(self) -> ToolSchema:
        """
        获取工具的 JSON Schema
        
        Returns:
            ToolSchema 对象
        """
        # 从类型注解中提取参数信息
        import inspect
        sig = inspect.signature(self.execute)
        parameters = []
        
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            
            param_type = "string"
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == float:
                    param_type = "number"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation == list:
                    param_type = "array"
            
            parameters.append(ToolParameter(
                name=param_name,
                type=param_type,
                description=getattr(self, f'_param_{param_name}_desc', ''),
                required=param.default == inspect.Parameter.empty,
                default=param.default if param.default != inspect.Parameter.empty else None
            ))
        
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=parameters
        )


def get_tool_schemas() -> List[Dict[str, Any]]:
    """
    获取所有工具的 JSON Schema（用于 LLM）
    
    Returns:
        Schema 列表
    """
    schemas = []
    for tool_name, tool_class in _tool_registry.items():
        tool_instance = tool_class()
        schema = tool_instance.get_schema()
        # 兼容 Pydantic v1 和 v2
        if hasattr(schema, 'model_dump'):
            # Pydantic v2
            schemas.append(schema.model_dump())
        elif hasattr(schema, 'dict'):
            # Pydantic v1
            schemas.append(schema.dict())
        else:
            # 降级方案：手动转换
            schemas.append({
                "name": schema.name,
                "description": schema.description,
                "parameters": [
                    {
                        "name": param.name,
                        "type": param.type,
                        "description": param.description,
                        "required": param.required,
                        "default": param.default
                    }
                    for param in schema.parameters
                ]
            })
    return schemas


def auto_discover_tools(tools_dir: str = "tools") -> None:
    """
    自动发现并注册工具
    
    Args:
        tools_dir: 工具目录
    """
    import os
    import importlib
    from pathlib import Path
    
    tools_path = Path(tools_dir)
    if not tools_path.exists():
        return
    
    for file_path in tools_path.glob("*.py"):
        if file_path.name == "__init__.py":
            continue
        
        module_name = file_path.stem
        try:
            module = importlib.import_module(f"tools.{module_name}")
            # 模块导入时会自动执行 @register_tool 装饰器
        except Exception as e:
            print(f"⚠️ 导入工具模块 {module_name} 失败: {e}")



