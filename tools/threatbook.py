"""
微步在线 IP 威胁情报查询工具
"""

import os
import requests
from typing import Dict, Any, Optional
from core.tools import BaseTool, register_tool
from dotenv import load_dotenv
import socket  # For IP validation

# 加载环境变量
load_dotenv()


@register_tool
class ThreatBookIPQueryTool(BaseTool):
    """微步在线 IP 威胁情报查询工具"""
    
    name = "threatbook_ip_query"
    description = "查询 IP 地址的威胁情报信息，包括地理位置、风险等级、威胁标签等。使用微步在线 (ThreatBook) API。"
    requires_safe_mode_confirmation = False  # 查询操作不需要安全确认
    
    def __init__(self):
        """初始化工具"""
        super().__init__()
        # API 配置
        self.api_endpoint = "https://api.threatbook.cn/v3/scene/ip_reputation"
        # 从环境变量或配置文件中获取 API Key
        self.api_key = os.getenv("THREATBOOK_API_KEY") or os.getenv("THREATBOOK_APIKEY")
        
        if not self.api_key:
            # 如果环境变量中没有，尝试从配置文件读取
            try:
                import yaml
                config_path = os.getenv("CONFIG_PATH", "config.yaml")
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                        threatbook_config = config.get('tools', {}).get('threatbook', {})
                        self.api_key = threatbook_config.get('api_key')
            except Exception:
                pass
    
    def execute(self, ip_address: str) -> Dict[str, Any]:
        """
        查询 IP 地址的威胁情报
        
        Args:
            ip_address: 要查询的 IP 地址
            
        Returns:
            包含威胁情报信息的字典
        """
        # 检查 API Key
        if not self.api_key:
            return {
                "success": False,
                "error": "未配置 ThreatBook API Key。请设置环境变量 THREATBOOK_API_KEY 或在 config.yaml 中配置。",
                "result": None
            }
        
        # 验证 IP 地址格式
        if not self._is_valid_ip(ip_address):
            return {
                "success": False,
                "error": f"无效的 IP 地址格式: {ip_address}",
                "result": None
            }
        
        try:
            # 构建请求参数
            payload = {
                "apikey": self.api_key,
                "resource": ip_address
            }
            
            # 发送 POST 请求
            # 禁用代理以避免代理连接问题
            proxies = {
                "http": None,
                "https": None
            }
            
            response = requests.post(
                self.api_endpoint,
                data=payload,  # 使用 form-data 格式
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
                proxies=proxies
            )
            
            # 检查 HTTP 状态码
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"API 请求失败: HTTP {response.status_code} - {response.text[:200]}",
                    "result": None
                }
            
            # 解析响应
            result_data = response.json()
            
            # 检查 API 响应状态
            if result_data.get("response_code") != 0:
                error_msg = result_data.get("verbose_msg", "未知错误")
                return {
                    "success": False,
                    "error": f"ThreatBook API 错误: {error_msg}",
                    "result": None
                }
            
            # 提取威胁情报数据
            data = result_data.get("data", {})
            
            # 构建结构化的威胁情报信息
            threat_info = {
                "ip_address": ip_address,
                "is_malicious": data.get("is_malicious", False),
                "severity": data.get("severity", "unknown"),  # critical, high, medium, low, info
                "judgments": data.get("judgments", []),  # 威胁标签列表
                "basic": {
                    "location": data.get("basic", {}).get("location", {}),
                    "carrier": data.get("basic", {}).get("carrier", "unknown")
                },
                "raw_data": data  # 保留原始数据以便进一步分析
            }
            
            # 提取地理位置信息
            location = data.get("basic", {}).get("location", {})
            if location:
                threat_info["location"] = {
                    "country": location.get("country", "unknown"),
                    "province": location.get("province", "unknown"),
                    "city": location.get("city", "unknown"),
                    "country_code": location.get("country_code", "unknown")
                }
            else:
                threat_info["location"] = {
                    "country": "unknown",
                    "province": "unknown",
                    "city": "unknown",
                    "country_code": "unknown"
                }
            
            # 提取运营商信息
            carrier = data.get("basic", {}).get("carrier", "unknown")
            threat_info["carrier"] = carrier
            
            # 构建人类可读的摘要
            severity_map = {
                "critical": "严重",
                "high": "高",
                "medium": "中",
                "low": "低",
                "info": "信息",
                "unknown": "未知"
            }
            
            severity_cn = severity_map.get(threat_info["severity"], "未知")
            judgments_str = ", ".join(threat_info["judgments"]) if threat_info["judgments"] else "无"
            location_str = f"{threat_info['location']['country']} - {threat_info['location']['city']}"
            
            threat_info["summary"] = {
                "ip": ip_address,
                "是否恶意": "是" if threat_info["is_malicious"] else "否",
                "风险等级": f"{severity_cn} ({threat_info['severity']})",
                "威胁标签": judgments_str,
                "地理位置": location_str,
                "运营商": carrier
            }
            
            return {
                "success": True,
                "result": threat_info,
                "error": None
            }
            
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "API 请求超时，请稍后重试",
                "result": None
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"网络请求失败: {str(e)}",
                "result": None
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"查询失败: {str(e)}",
                "result": None
            }
    
    def _is_valid_ip(self, ip_address: str) -> bool:
        """
        验证 IP 地址格式
        
        Args:
            ip_address: IP 地址字符串
            
        Returns:
            是否为有效的 IP 地址
        """
        try:
            socket.inet_aton(ip_address)
            return True
        except socket.error:
            return False



