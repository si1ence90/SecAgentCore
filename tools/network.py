"""
网络工具模块
"""

import socket
import threading
import time
import subprocess
import platform
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional, List
from core.tools import BaseTool, register_tool


@register_tool
class PortScanTool(BaseTool):
    """端口扫描工具"""
    name = "port_scan"
    description = "扫描目标 IP 地址的开放端口。支持指定端口范围或常用端口列表。"
    requires_safe_mode_confirmation = True
    
    def execute(
        self,
        target_ip: str,
        ports: Optional[str] = "common",
        timeout: Optional[float] = 5.0,
        max_threads: Optional[int] = 10
    ) -> Dict[str, Any]:
        """
        扫描目标 IP 的开放端口
        
        Args:
            target_ip: 目标 IP 地址
            ports: 端口范围，如 "80,443,8080" 或 "1-1000" 或 "common"（常用端口）
            timeout: 连接超时时间（秒）
            max_threads: 最大并发线程数（默认 50，避免资源耗尽）
            
        Returns:
            扫描结果字典
        """
        try:
            # 解析端口列表
            port_list = self._parse_ports(ports)
            
            if not port_list:
                return {
                    "success": False,
                    "error": f"无效的端口范围: {ports}",
                    "result": None
                }
            
            # 限制端口数量，避免扫描过多端口导致超时
            if len(port_list) > 10000:
                return {
                    "success": False,
                    "error": f"端口数量过多（{len(port_list)}），请缩小扫描范围（最多支持 10000 个端口）",
                    "result": None
                }
            
            open_ports = []
            closed_ports = []
            
            # 使用线程池扫描端口，避免创建过多线程
            def scan_port(port: int):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(timeout)
                    result = sock.connect_ex((target_ip, port))
                    sock.close()
                    
                    if result == 0:
                        return ("open", port)
                    else:
                        return ("closed", port)
                except Exception:
                    return ("closed", port)
            
            # 使用线程池执行扫描
            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                # 提交所有扫描任务
                future_to_port = {executor.submit(scan_port, port): port for port in port_list}
                
                # 收集结果
                for future in as_completed(future_to_port):
                    try:
                        status, port = future.result()
                        if status == "open":
                            open_ports.append(port)
                        else:
                            closed_ports.append(port)
                    except Exception:
                        closed_ports.append(future_to_port[future])
            
            # 识别常见服务
            service_map = {
                20: "FTP Data",
                21: "FTP",
                22: "SSH",
                23: "Telnet",
                25: "SMTP",
                53: "DNS",
                80: "HTTP",
                110: "POP3",
                143: "IMAP",
                443: "HTTPS",
                445: "SMB",
                3306: "MySQL",
                3389: "RDP",
                5432: "PostgreSQL",
                8080: "HTTP-Proxy",
                8443: "HTTPS-Alt"
            }
            
            open_ports_info = []
            for port in sorted(open_ports):
                service = service_map.get(port, "Unknown")
                open_ports_info.append({
                    "port": port,
                    "service": service,
                    "status": "open"
                })
            
            return {
                "success": True,
                "result": {
                    "target_ip": target_ip,
                    "open_ports": open_ports,
                    "open_ports_info": open_ports_info,
                    "closed_ports_count": len(closed_ports),
                    "scanned_ports_count": len(port_list),
                    "scan_timeout": timeout
                },
                "error": None
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"端口扫描失败: {str(e)}",
                "result": None
            }
    
    def _parse_ports(self, ports: str) -> List[int]:
        """
        解析端口范围字符串
        
        Args:
            ports: 端口范围字符串
            
        Returns:
            端口列表
        """
        port_list = []
        
        if ports == "common":
            # 常用端口
            port_list = [20, 21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 3306, 3389, 5432, 8080, 8443]
        elif "," in ports:
            # 逗号分隔的端口列表
            for port_str in ports.split(","):
                port_str = port_str.strip()
                try:
                    port_list.append(int(port_str))
                except ValueError:
                    continue
        elif "-" in ports:
            # 端口范围
            try:
                start, end = ports.split("-")
                start = int(start.strip())
                end = int(end.strip())
                port_list = list(range(start, end + 1))
            except ValueError:
                return []
        else:
            # 单个端口
            try:
                port_list = [int(ports)]
            except ValueError:
                return []
        
        # 过滤无效端口
        port_list = [p for p in port_list if 1 <= p <= 65535]
        return port_list


@register_tool
class NetworkPingTool(BaseTool):
    """网络连通性检测工具"""
    name = "network_ping"
    description = "检测目标 IP 地址的网络连通性（使用 ICMP ping）"
    requires_safe_mode_confirmation = True
    
    def execute(
        self,
        target_ip: str,
        timeout: Optional[float] = 3.0,
        count: Optional[int] = 4
    ) -> Dict[str, Any]:
        """
        检测目标 IP 的网络连通性（使用系统 ping 命令）
        
        Args:
            target_ip: 目标 IP 地址或主机名
            timeout: 超时时间（秒，默认 3.0）
            count: ping 次数（默认 4）
            
        Returns:
            连通性检测结果
        """
        try:
            # 根据操作系统选择 ping 命令参数
            system = platform.system().lower()
            
            if system == "windows":
                # Windows ping 命令
                # -n: ping 次数
                # -w: 超时时间（毫秒）
                timeout_ms = int(timeout * 1000)
                cmd = ["ping", "-n", str(count), "-w", str(timeout_ms), target_ip]
            else:
                # Linux/Mac ping 命令
                # -c: ping 次数
                # -W: 超时时间（秒）
                cmd = ["ping", "-c", str(count), "-W", str(timeout), target_ip]
            
            # 执行 ping 命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 5  # 给命令执行额外的时间缓冲
            )
            
            # 解析 ping 结果
            output = result.stdout + result.stderr
            is_reachable = result.returncode == 0
            
            # 提取响应时间信息
            response_times = []
            if is_reachable:
                # Windows: "时间=XXms" 或 "time=XXms"
                # Linux: "time=XX ms" 或 "time=XXms"
                time_pattern = r'time[=<](\d+(?:\.\d+)?)\s*ms'
                matches = re.findall(time_pattern, output, re.IGNORECASE)
                if matches:
                    response_times = [float(m) for m in matches]
            
            # 计算平均响应时间
            avg_response_time = None
            if response_times:
                avg_response_time = round(sum(response_times) / len(response_times), 2)
            
            # 提取丢包率（Windows）
            packet_loss = None
            if system == "windows":
                loss_match = re.search(r'\((\d+)%', output)
                if loss_match:
                    packet_loss = int(loss_match.group(1))
            
            # 提取丢包率（Linux/Mac）
            if system != "windows" and not packet_loss:
                loss_match = re.search(r'(\d+(?:\.\d+)?)% packet loss', output)
                if loss_match:
                    packet_loss = float(loss_match.group(1))
            
            return {
                "success": True,
                "result": {
                    "target_ip": target_ip,
                    "is_reachable": is_reachable,
                    "response_time_ms": avg_response_time,
                    "packet_loss_percent": packet_loss,
                    "ping_count": count,
                    "timeout": timeout
                },
                "error": None
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"ping 命令执行超时",
                "result": {
                    "target_ip": target_ip,
                    "is_reachable": False,
                    "response_time_ms": None,
                    "timeout": timeout
                }
            }
        except FileNotFoundError:
            # 如果系统没有 ping 命令，回退到 TCP 连接测试
            return self._tcp_ping_fallback(target_ip, timeout)
        except Exception as e:
            return {
                "success": False,
                "error": f"网络连通性检测失败: {str(e)}",
                "result": None
            }
    
    def _tcp_ping_fallback(self, target_ip: str, timeout: float) -> Dict[str, Any]:
        """
        TCP 连接测试回退方案（当系统不支持 ping 命令时）
        
        Args:
            target_ip: 目标 IP 地址
            timeout: 超时时间
            
        Returns:
            连通性检测结果
        """
        try:
            # 测试常用端口
            test_ports = [80, 443, 22, 21]
            is_reachable = False
            response_time = None
            
            for port in test_ports:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(timeout)
                    
                    start_time = time.time()
                    result = sock.connect_ex((target_ip, port))
                    end_time = time.time()
                    
                    sock.close()
                    
                    if result == 0:
                        is_reachable = True
                        response_time = (end_time - start_time) * 1000
                        break
                except Exception:
                    continue
            
            return {
                "success": True,
                "result": {
                    "target_ip": target_ip,
                    "is_reachable": is_reachable,
                    "response_time_ms": round(response_time, 2) if response_time else None,
                    "timeout": timeout,
                    "method": "tcp_fallback"
                },
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"TCP 回退测试失败: {str(e)}",
                "result": None
            }

