"""
通知工具模块
支持通过多种渠道发送通知消息
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import Dict, Any, Optional, List
from datetime import datetime
from core.tools import BaseTool, register_tool
from dotenv import load_dotenv
import yaml

# 加载环境变量
load_dotenv()


@register_tool
class NotificationTool(BaseTool):
    """通知工具 - 支持多种通知渠道"""
    
    name = "notification"
    description = "发送通知消息到指定用户。支持邮箱、微信、第三方IM、短信等多种通知渠道。消息会自动格式化。"
    requires_safe_mode_confirmation = False
    
    def __init__(self):
        """初始化工具"""
        super().__init__()
        self._load_config()
    
    def _load_config(self):
        """从配置文件加载通知相关配置"""
        try:
            config_path = os.getenv("CONFIG_PATH", "config.yaml")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    notification_config = config.get('tools', {}).get('notification', {})
                    
                    # 邮箱配置
                    email_config = notification_config.get('email', {})
                    self.email_smtp_host = email_config.get('smtp_host') or os.getenv('EMAIL_SMTP_HOST', 'smtp.qq.com')
                    self.email_smtp_port = email_config.get('smtp_port') or int(os.getenv('EMAIL_SMTP_PORT', '587'))
                    self.email_username = email_config.get('username') or os.getenv('EMAIL_USERNAME')
                    self.email_password = email_config.get('password') or os.getenv('EMAIL_PASSWORD')
                    self.email_from = email_config.get('from') or self.email_username
                    self.email_use_tls = email_config.get('use_tls', True)
                    
                    # 微信配置（预留）
                    wechat_config = notification_config.get('wechat', {})
                    self.wechat_app_id = wechat_config.get('app_id') or os.getenv('WECHAT_APP_ID')
                    self.wechat_app_secret = wechat_config.get('app_secret') or os.getenv('WECHAT_APP_SECRET')
                    
                    # 第三方IM配置（预留）
                    im_config = notification_config.get('im', {})
                    self.im_api_url = im_config.get('api_url') or os.getenv('IM_API_URL')
                    self.im_api_key = im_config.get('api_key') or os.getenv('IM_API_KEY')
                    
                    # 短信配置（预留）
                    sms_config = notification_config.get('sms', {})
                    self.sms_api_url = sms_config.get('api_url') or os.getenv('SMS_API_URL')
                    self.sms_api_key = sms_config.get('api_key') or os.getenv('SMS_API_KEY')
        except Exception as e:
            # 如果配置文件不存在或读取失败，使用环境变量
            self.email_smtp_host = os.getenv('EMAIL_SMTP_HOST', 'smtp.qq.com')
            self.email_smtp_port = int(os.getenv('EMAIL_SMTP_PORT', '587'))
            self.email_username = os.getenv('EMAIL_USERNAME')
            self.email_password = os.getenv('EMAIL_PASSWORD')
            self.email_from = os.getenv('EMAIL_FROM') or self.email_username
            self.email_use_tls = os.getenv('EMAIL_USE_TLS', 'true').lower() == 'true'
            
            self.wechat_app_id = os.getenv('WECHAT_APP_ID')
            self.wechat_app_secret = os.getenv('WECHAT_APP_SECRET')
            self.im_api_url = os.getenv('IM_API_URL')
            self.im_api_key = os.getenv('IM_API_KEY')
            self.sms_api_url = os.getenv('SMS_API_URL')
            self.sms_api_key = os.getenv('SMS_API_KEY')
    
    def execute(
        self,
        message: str,
        recipients: List[str],
        channel: str = "email",
        subject: Optional[str] = None,
        format_type: Optional[str] = "text"
    ) -> Dict[str, Any]:
        """
        发送通知消息
        
        Args:
            message: 要发送的消息内容
            recipients: 接收者列表（邮箱地址、微信ID、手机号等，根据channel而定）
            channel: 通知渠道，支持 'email'（邮箱）、'wechat'（微信）、'im'（第三方IM）、'sms'（短信）
            subject: 消息主题（主要用于邮箱）
            format_type: 消息格式，'text'（纯文本）或 'html'（HTML格式）
            
        Returns:
            发送结果字典
        """
        if not message or not recipients:
            return {
                "success": False,
                "error": "消息内容和接收者不能为空",
                "result": None
            }
        
        if channel == "email":
            return self._send_email(message, recipients, subject, format_type)
        elif channel == "wechat":
            return self._send_wechat(message, recipients)
        elif channel == "im":
            return self._send_im(message, recipients)
        elif channel == "sms":
            return self._send_sms(message, recipients)
        else:
            return {
                "success": False,
                "error": f"不支持的通知渠道: {channel}，支持: email, wechat, im, sms",
                "result": None
            }
    
    def _send_email(
        self,
        message: str,
        recipients: List[str],
        subject: Optional[str] = None,
        format_type: str = "text"
    ) -> Dict[str, Any]:
        """
        发送邮箱通知（已实现）
        
        Args:
            message: 消息内容
            recipients: 接收者邮箱地址列表
            subject: 邮件主题
            format_type: 消息格式
            
        Returns:
            发送结果
        """
        try:
            if not self.email_username or not self.email_password:
                return {
                    "success": False,
                    "error": "邮箱配置未设置，请在配置文件或环境变量中设置 EMAIL_USERNAME 和 EMAIL_PASSWORD",
                    "result": None
                }
            
            # 如果没有提供主题，自动生成
            if not subject:
                subject = f"SecAgent 通知 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # 创建邮件对象
            msg = MIMEMultipart('alternative')
            msg['From'] = Header(self.email_from or self.email_username, 'utf-8')
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = Header(subject, 'utf-8')
            
            # 格式化消息内容
            formatted_message = self._format_message(message, format_type)
            
            # 添加消息内容
            if format_type == "html":
                msg.attach(MIMEText(formatted_message, 'html', 'utf-8'))
            else:
                msg.attach(MIMEText(formatted_message, 'plain', 'utf-8'))
            
            # 发送邮件
            with smtplib.SMTP(self.email_smtp_host, self.email_smtp_port) as server:
                if self.email_use_tls:
                    server.starttls()
                server.login(self.email_username, self.email_password)
                server.sendmail(self.email_from or self.email_username, recipients, msg.as_string())
            
            return {
                "success": True,
                "result": {
                    "channel": "email",
                    "recipients": recipients,
                    "subject": subject,
                    "sent_at": datetime.now().isoformat(),
                    "message_length": len(message)
                },
                "error": None
            }
            
        except smtplib.SMTPAuthenticationError:
            return {
                "success": False,
                "error": "邮箱认证失败，请检查用户名和密码",
                "result": None
            }
        except smtplib.SMTPException as e:
            return {
                "success": False,
                "error": f"发送邮件失败: {str(e)}",
                "result": None
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"邮箱发送异常: {str(e)}",
                "result": None
            }
    
    def _send_wechat(self, message: str, recipients: List[str]) -> Dict[str, Any]:
        """
        发送微信通知（接口预留，未实现）
        
        Args:
            message: 消息内容
            recipients: 接收者微信ID列表
            
        Returns:
            发送结果
        """
        # TODO: 实现微信通知功能
        # 可以使用企业微信API、微信公众号API等
        return {
            "success": False,
            "error": "微信通知功能尚未实现，请使用 email 渠道",
            "result": {
                "channel": "wechat",
                "recipients": recipients,
                "message": message,
                "note": "此功能需要配置微信API（企业微信或微信公众号）"
            }
        }
    
    def _send_im(self, message: str, recipients: List[str]) -> Dict[str, Any]:
        """
        发送第三方IM通知（接口预留，未实现）
        
        Args:
            message: 消息内容
            recipients: 接收者ID列表
            
        Returns:
            发送结果
        """
        # TODO: 实现第三方IM通知功能
        # 可以集成钉钉、飞书、Slack、Teams等
        return {
            "success": False,
            "error": "第三方IM通知功能尚未实现，请使用 email 渠道",
            "result": {
                "channel": "im",
                "recipients": recipients,
                "message": message,
                "note": "此功能需要配置第三方IM API（钉钉、飞书、Slack等）"
            }
        }
    
    def _send_sms(self, message: str, recipients: List[str]) -> Dict[str, Any]:
        """
        发送短信通知（接口预留，未实现）
        
        Args:
            message: 消息内容
            recipients: 接收者手机号列表
            
        Returns:
            发送结果
        """
        # TODO: 实现短信通知功能
        # 可以使用阿里云短信、腾讯云短信等
        return {
            "success": False,
            "error": "短信通知功能尚未实现，请使用 email 渠道",
            "result": {
                "channel": "sms",
                "recipients": recipients,
                "message": message,
                "note": "此功能需要配置短信服务API（阿里云、腾讯云等）"
            }
        }
    
    def _format_message(self, message: str, format_type: str = "text") -> str:
        """
        格式化消息内容
        
        Args:
            message: 原始消息
            format_type: 格式类型
            
        Returns:
            格式化后的消息
        """
        if format_type == "html":
            # HTML格式
            html_template = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .header {{
                        background-color: #4CAF50;
                        color: white;
                        padding: 15px;
                        border-radius: 5px 5px 0 0;
                    }}
                    .content {{
                        background-color: #f9f9f9;
                        padding: 20px;
                        border: 1px solid #ddd;
                        border-radius: 0 0 5px 5px;
                    }}
                    .footer {{
                        margin-top: 20px;
                        font-size: 12px;
                        color: #666;
                        text-align: center;
                    }}
                    pre {{
                        background-color: #f4f4f4;
                        padding: 10px;
                        border-radius: 3px;
                        overflow-x: auto;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h2>🔒 SecAgent 通知</h2>
                </div>
                <div class="content">
                    {self._escape_html(message)}
                </div>
                <div class="footer">
                    <p>此消息由 SecAgent-Core 自动发送</p>
                    <p>时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
            </body>
            </html>
            """
            return html_template
        else:
            # 纯文本格式
            text_template = f"""
{'='*60}
🔒 SecAgent 通知
{'='*60}

{message}

{'='*60}
此消息由 SecAgent-Core 自动发送
时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*60}
            """
            return text_template.strip()
    
    def _escape_html(self, text: str) -> str:
        """
        转义HTML特殊字符
        
        Args:
            text: 原始文本
            
        Returns:
            转义后的文本
        """
        import html
        # 将换行符转换为<br>
        text = html.escape(text)
        text = text.replace('\n', '<br>')
        return text


