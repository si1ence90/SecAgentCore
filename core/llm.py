"""
LLM 交互模块
支持 DeepSeek 和 Qwen 等兼容 OpenAI API 的模型
"""

import os
import time
from typing import Optional, Dict, Any, List, Tuple
from openai import OpenAI
from openai import APIError, APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
from pydantic import BaseModel, Field
import yaml
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class LLMConfig(BaseModel):
    """LLM 配置模型"""
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096


class ModelProvider:
    """模型提供商类，支持切换不同的 LLM"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        初始化模型提供商
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.client: Optional[OpenAI] = None
        self.llm_config: Optional[LLMConfig] = None
        self.current_provider: Optional[str] = None
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"⚠️ 加载配置失败: {e}")
            return {}
    
    def _resolve_env_vars(self, value: Any) -> Any:
        """解析环境变量引用"""
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            return os.getenv(env_var, value)
        return value
    
    def set_provider(self, provider_name: str) -> None:
        """
        设置 LLM 提供商
        
        Args:
            provider_name: 提供商名称（如 'deepseek-chat', 'qwen-max'）
        """
        llm_config_dict = self.config.get('llm', {}).get(provider_name, {})
        if not llm_config_dict:
            raise ValueError(f"未找到提供商配置: {provider_name}")
        
        # 解析环境变量
        api_key = self._resolve_env_vars(llm_config_dict.get('api_key', ''))
        base_url = self._resolve_env_vars(llm_config_dict.get('base_url', ''))
        model = llm_config_dict.get('model', provider_name)
        temperature = llm_config_dict.get('temperature', 0.7)
        max_tokens = llm_config_dict.get('max_tokens', 4096)
        
        if not api_key:
            raise ValueError(f"提供商 {provider_name} 的 API Key 未配置")
        
        self.llm_config = LLMConfig(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        self.current_provider = provider_name
        print(f"✓ 已切换到提供商: {provider_name} (模型: {model})")
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ) -> Tuple[str, Dict[str, int]]:
        """
        发送聊天请求并返回响应和 token 使用情况（带自动重试）
        
        Args:
            messages: 消息列表
            temperature: 温度参数（可选）
            max_tokens: 最大 token 数（可选）
            max_retries: 最大重试次数（默认 3）
            retry_delay: 初始重试延迟（秒，默认 1.0，使用指数退避）
            
        Returns:
            (响应文本, token 使用信息)
        """
        if self.client is None or self.llm_config is None:
            raise RuntimeError("请先调用 set_provider() 设置提供商")
        
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.llm_config.model,
                    messages=messages,
                    temperature=temperature or self.llm_config.temperature,
                    max_tokens=max_tokens or self.llm_config.max_tokens
                )
                
                # 提取 token 使用情况
                token_info = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
                
                return response.choices[0].message.content, token_info
                
            except (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError) as e:
                # 可重试的错误类型
                last_exception = e
                if attempt < max_retries:
                    # 指数退避：延迟时间 = 初始延迟 * 2^尝试次数
                    delay = retry_delay * (2 ** attempt)
                    error_type = type(e).__name__
                    print(f"⚠️  LLM 调用失败 ({error_type})，{delay:.1f} 秒后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(delay)
                else:
                    # 最后一次尝试也失败
                    break
                    
            except APIError as e:
                # 检查是否是 5xx 服务器错误（可重试）
                if hasattr(e, 'status_code') and e.status_code and 500 <= e.status_code < 600:
                    last_exception = e
                    if attempt < max_retries:
                        delay = retry_delay * (2 ** attempt)
                        print(f"⚠️  LLM 服务器错误 ({e.status_code})，{delay:.1f} 秒后重试 ({attempt + 1}/{max_retries})...")
                        time.sleep(delay)
                    else:
                        break
                else:
                    # 4xx 客户端错误，不重试
                    raise RuntimeError(f"LLM 调用失败: {str(e)}")
                    
            except Exception as e:
                # 其他未知错误，不重试
                raise RuntimeError(f"LLM 调用失败: {str(e)}")
        
        # 所有重试都失败
        raise RuntimeError(f"LLM 调用失败（已重试 {max_retries} 次）: {str(last_exception)}")
    
    def get_available_providers(self) -> List[str]:
        """获取可用的提供商列表"""
        llm_config = self.config.get('llm', {})
        providers = []
        for key in llm_config.keys():
            if key != 'provider' and isinstance(llm_config[key], dict):
                providers.append(key)
        return providers


# 全局模型提供商实例
_model_provider: Optional[ModelProvider] = None


def get_model_provider(config_path: str = "config.yaml") -> ModelProvider:
    """
    获取全局模型提供商实例（单例模式）
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        ModelProvider 实例
    """
    global _model_provider
    if _model_provider is None:
        _model_provider = ModelProvider(config_path)
    return _model_provider

