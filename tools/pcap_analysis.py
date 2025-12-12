"""
PCAP 网络流量分析与查询工具
支持解析 .cap 和 .pcap 文件，并提供类似 SQL/Pandas 的查询功能
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import pandas as pd
from core.tools import BaseTool, register_tool

try:
    from scapy.all import rdpcap, IP, TCP, UDP, ICMP, ARP, DNS, Raw
    from scapy.layers.inet import Ether
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False

try:
    import pandasql as psql
    PANDASQL_AVAILABLE = True
except ImportError:
    PANDASQL_AVAILABLE = False


@register_tool
class PCAPAnalysisTool(BaseTool):
    """PCAP 网络流量分析与查询工具"""
    
    name = "pcap_analysis"
    description = """分析PCAP网络流量文件（.cap或.pcap格式），解析数据包并转换为结构化数据。
支持使用类似SQL或Pandas的语法进行灵活查询，可以按协议、IP地址、端口、时间等条件过滤数据包。
支持导出查询结果为CSV、JSON、Excel等格式。

主要功能：
1. 解析PCAP文件，提取数据包的详细信息（IP、端口、协议、时间戳等）
2. 支持Pandas查询语法（如：protocol == 'TCP' and src_ip == '192.168.1.1'）
3. 支持SQL查询语法（如：SELECT * FROM df WHERE protocol = 'TCP'）
4. 支持基础过滤参数（protocols、src_ip、dst_ip、src_port、dst_port）
5. 提供统计信息（协议分布、Top IP、Top端口等）
6. 支持导出为CSV、JSON、Excel格式

参数说明：
- pcap_file (必需): PCAP文件路径
- query (可选): 查询语句，支持Pandas或SQL语法
- query_type (可选): 'pandas'（默认）或'sql'
- export_format (可选): 'csv'、'json'、'excel'
- export_path (可选): 导出文件路径
- limit (可选): 限制返回结果数量
- protocols (可选): 协议过滤列表，如['TCP', 'UDP']
- src_ip/dst_ip (可选): IP地址过滤
- src_port/dst_port (可选): 端口过滤

使用示例：
- 基本分析: {"pcap_file": "capture.pcap"}
- Pandas查询: {"pcap_file": "capture.pcap", "query": "protocol == 'TCP'", "query_type": "pandas"}
- SQL查询: {"pcap_file": "capture.pcap", "query": "SELECT * FROM df WHERE src_ip = '192.168.1.1'", "query_type": "sql"}
- 基础过滤: {"pcap_file": "capture.pcap", "protocols": ["TCP"], "src_ip": "192.168.1.1"}
- 导出结果: {"pcap_file": "capture.pcap", "query": "protocol == 'TCP'", "export_format": "csv"}"""
    requires_safe_mode_confirmation = False
    
    def __init__(self):
        """初始化工具"""
        super().__init__()
    
    def execute(
        self,
        pcap_file: str,
        query: Optional[str] = None,
        query_type: str = "pandas",
        export_format: Optional[str] = None,
        export_path: Optional[str] = None,
        limit: Optional[int] = None,
        protocols: Optional[List[str]] = None,
        src_ip: Optional[str] = None,
        dst_ip: Optional[str] = None,
        src_port: Optional[int] = None,
        dst_port: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        分析PCAP文件并执行查询
        
        Args:
            pcap_file: PCAP文件路径（支持.cap和.pcap格式）
            query: 查询语句。如果query_type为'pandas'，使用pandas query语法（如"src_ip == '192.168.1.1' and protocol == 'TCP'"）；
                   如果query_type为'sql'，使用SQL语法（如"SELECT * FROM packets WHERE src_ip = '192.168.1.1' AND protocol = 'TCP'"）
            query_type: 查询类型，'pandas'（默认）或'sql'
            export_format: 导出格式，'csv'、'json'、'excel'或None（不导出）
            export_path: 导出文件路径（如果未指定，自动生成）
            limit: 限制返回结果数量
            protocols: 协议过滤列表，如['TCP', 'UDP', 'ICMP']
            src_ip: 源IP地址过滤
            dst_ip: 目标IP地址过滤
            src_port: 源端口过滤
            dst_port: 目标端口过滤
            
        Returns:
            分析结果字典，包含数据包统计信息、查询结果等
        """
        try:
            # 检查scapy是否可用
            if not SCAPY_AVAILABLE:
                return {
                    "success": False,
                    "error": "scapy 库未安装。请运行: pip install scapy\n如果安装失败，可以尝试: pip install scapy[basic]",
                    "result": None
                }
            
            # 检查文件是否存在
            pcap_path = Path(pcap_file)
            if not pcap_path.exists():
                return {
                    "success": False,
                    "error": f"PCAP文件不存在: {pcap_file}",
                    "result": None
                }
            
            if pcap_path.suffix.lower() not in ['.pcap', '.cap']:
                return {
                    "success": False,
                    "error": f"不支持的文件格式: {pcap_path.suffix}，仅支持 .pcap 和 .cap 文件",
                    "result": None
                }
            
            # 解析PCAP文件
            print(f"正在解析PCAP文件: {pcap_file}...")
            try:
                packets = rdpcap(str(pcap_path))
            except Exception as e:
                return {
                    "success": False,
                    "error": f"PCAP文件解析失败: {str(e)}\n可能原因：文件损坏、格式不支持或文件过大",
                    "result": None
                }
            
            if len(packets) == 0:
                return {
                    "success": False,
                    "error": "PCAP文件中没有数据包",
                    "result": None
                }
            
            # 转换为DataFrame
            print(f"正在转换 {len(packets)} 个数据包为结构化数据...")
            try:
                df = self._packets_to_dataframe(packets)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"数据包转换失败: {str(e)}\n可能原因：数据包格式异常或内存不足",
                    "result": None
                }
            
            if df.empty:
                return {
                    "success": False,
                    "error": "转换后的DataFrame为空",
                    "result": None
                }
            
            # 应用基础过滤
            df_filtered = self._apply_filters(
                df, protocols, src_ip, dst_ip, src_port, dst_port
            )
            
            # 执行查询
            if query:
                if query_type.lower() == "sql":
                    if not PANDASQL_AVAILABLE:
                        return {
                            "success": False,
                            "error": "SQL查询需要 pandasql 库。请运行: pip install pandasql",
                            "result": None
                        }
                    df_result = self._execute_sql_query(df_filtered, query)
                else:  # pandas query
                    df_result = self._execute_pandas_query(df_filtered, query)
            else:
                df_result = df_filtered
            
            # 应用限制
            if limit and limit > 0:
                df_result = df_result.head(limit)
            
            # 统计信息
            stats = self._calculate_statistics(df, df_result)
            
            # 导出结果
            export_info = None
            if export_format:
                export_info = self._export_results(
                    df_result, export_format, export_path, pcap_path.stem
                )
            
            # 准备返回结果
            # 处理样本数据：确保所有值都可以序列化为JSON
            sample_data = []
            if len(df_result) > 0:
                sample_df = df_result.head(10).copy()
                # 将 datetime 列转换为字符串
                for col in sample_df.columns:
                    if pd.api.types.is_datetime64_any_dtype(sample_df[col]):
                        sample_df[col] = sample_df[col].astype(str)
                # 将大整数转换为字符串以避免JSON序列化问题
                for col in sample_df.select_dtypes(include=['int64']).columns:
                    if len(sample_df[col].dropna()) > 0:
                        max_val = sample_df[col].abs().max()
                        if max_val > 2**53 - 1:  # JavaScript Number.MAX_SAFE_INTEGER
                            sample_df[col] = sample_df[col].astype(str)
                # 转换为字典，使用 default_handler 处理 NaN 值
                try:
                    sample_data = sample_df.to_dict('records')
                    # 手动将 NaN 值替换为 None（用于 JSON 序列化）
                    for record in sample_data:
                        for key, value in record.items():
                            if pd.isna(value):
                                record[key] = None
                except Exception:
                    # 如果转换失败，使用更安全的方法
                    sample_data = []
                    for idx in range(min(10, len(sample_df))):
                        record = {}
                        for col in sample_df.columns:
                            val = sample_df.iloc[idx][col]
                            if pd.isna(val):
                                record[col] = None
                            else:
                                record[col] = val
                        sample_data.append(record)
            
            result = {
                "total_packets": len(df),
                "filtered_packets": len(df_filtered),
                "query_result_count": len(df_result),
                "statistics": stats,
                "sample_data": sample_data,
                "columns": list(df_result.columns) if len(df_result) > 0 else []
            }
            
            if export_info:
                result["export_info"] = export_info
            
            return {
                "success": True,
                "result": result,
                "error": None
            }
            
        except Exception as e:
            import traceback
            return {
                "success": False,
                "error": f"PCAP分析失败: {str(e)}\n{traceback.format_exc()}",
                "result": None
            }
    
    def _packets_to_dataframe(self, packets) -> pd.DataFrame:
        """
        将数据包列表转换为DataFrame
        
        Args:
            packets: scapy数据包列表
            
        Returns:
            DataFrame对象
        """
        rows = []
        
        for i, packet in enumerate(packets):
            row = {
                "packet_id": i + 1,
                "timestamp": float(packet.time),
                "time_str": datetime.fromtimestamp(packet.time).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                "length": len(packet),
                "protocol": self._get_protocol(packet),
                "src_ip": None,
                "dst_ip": None,
                "src_port": None,
                "dst_port": None,
                "src_mac": None,
                "dst_mac": None,
                "flags": None,
                "payload_length": 0,
                "has_payload": False
            }
            
            # 提取以太网层信息
            if Ether in packet:
                row["src_mac"] = packet[Ether].src
                row["dst_mac"] = packet[Ether].dst
            
            # 提取IP层信息
            if IP in packet:
                row["src_ip"] = packet[IP].src
                row["dst_ip"] = packet[IP].dst
                row["ttl"] = packet[IP].ttl
                row["ip_version"] = packet[IP].version
            
            # 提取TCP信息
            if TCP in packet:
                row["src_port"] = int(packet[TCP].sport) if packet[TCP].sport else None
                row["dst_port"] = int(packet[TCP].dport) if packet[TCP].dport else None
                row["flags"] = int(packet[TCP].flags) if packet[TCP].flags else None
                # seq 和 ack 可能是大整数，保持为整数类型
                row["seq"] = int(packet[TCP].seq) if hasattr(packet[TCP], 'seq') else None
                row["ack"] = int(packet[TCP].ack) if hasattr(packet[TCP], 'ack') else None
                # TCP窗口大小
                row["window"] = int(packet[TCP].window) if hasattr(packet[TCP], 'window') else None
                if Raw in packet:
                    row["payload_length"] = len(packet[Raw].load)
                    row["has_payload"] = True
            
            # 提取UDP信息
            elif UDP in packet:
                row["src_port"] = int(packet[UDP].sport) if packet[UDP].sport else None
                row["dst_port"] = int(packet[UDP].dport) if packet[UDP].dport else None
                if Raw in packet:
                    row["payload_length"] = len(packet[Raw].load)
                    row["has_payload"] = True
            
            # 提取ICMP信息
            elif ICMP in packet:
                row["icmp_type"] = int(packet[ICMP].type) if hasattr(packet[ICMP], 'type') else None
                row["icmp_code"] = int(packet[ICMP].code) if hasattr(packet[ICMP], 'code') else None
            
            # 提取ARP信息
            elif ARP in packet:
                row["arp_op"] = int(packet[ARP].op) if hasattr(packet[ARP], 'op') else None
                row["src_ip"] = packet[ARP].psrc if hasattr(packet[ARP], 'psrc') else None
                row["dst_ip"] = packet[ARP].pdst if hasattr(packet[ARP], 'pdst') else None
            
            # 提取DNS信息
            if DNS in packet:
                try:
                    if packet[DNS].qd:
                        row["dns_qname"] = packet[DNS].qd.qname.decode('utf-8', errors='ignore') if hasattr(packet[DNS].qd, 'qname') else None
                        row["dns_qtype"] = int(packet[DNS].qd.qtype) if hasattr(packet[DNS].qd, 'qtype') else None
                    else:
                        row["dns_qname"] = None
                        row["dns_qtype"] = None
                except (AttributeError, UnicodeDecodeError):
                    row["dns_qname"] = None
                    row["dns_qtype"] = None
            
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        # 转换时间戳列为datetime
        if 'timestamp' in df.columns:
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
        
        return df
    
    def _get_protocol(self, packet) -> str:
        """获取数据包的主要协议"""
        if TCP in packet:
            return "TCP"
        elif UDP in packet:
            return "UDP"
        elif ICMP in packet:
            return "ICMP"
        elif ARP in packet:
            return "ARP"
        elif DNS in packet:
            return "DNS"
        elif IP in packet:
            return "IP"
        else:
            return "Unknown"
    
    def _apply_filters(
        self,
        df: pd.DataFrame,
        protocols: Optional[List[str]] = None,
        src_ip: Optional[str] = None,
        dst_ip: Optional[str] = None,
        src_port: Optional[int] = None,
        dst_port: Optional[int] = None
    ) -> pd.DataFrame:
        """应用基础过滤条件"""
        df_filtered = df.copy()
        
        if protocols and 'protocol' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['protocol'].isin(protocols)]
        
        if src_ip and 'src_ip' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['src_ip'] == src_ip]
        
        if dst_ip and 'dst_ip' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['dst_ip'] == dst_ip]
        
        if src_port is not None and 'src_port' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['src_port'] == src_port]
        
        if dst_port is not None and 'dst_port' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['dst_port'] == dst_port]
        
        return df_filtered
    
    def _execute_pandas_query(self, df: pd.DataFrame, query: str) -> pd.DataFrame:
        """
        执行Pandas查询
        
        Args:
            df: DataFrame
            query: pandas query语法，如 "src_ip == '192.168.1.1' and protocol == 'TCP'"
            
        Returns:
            查询结果DataFrame
        """
        try:
            return df.query(query)
        except Exception as e:
            raise ValueError(f"Pandas查询语法错误: {str(e)}\n查询语句: {query}")
    
    def _execute_sql_query(self, df: pd.DataFrame, query: str) -> pd.DataFrame:
        """
        执行SQL查询
        
        Args:
            df: DataFrame
            query: SQL查询语句，如 "SELECT * FROM df WHERE src_ip = '192.168.1.1' AND protocol = 'TCP'"
            
        Returns:
            查询结果DataFrame
        """
        # 首先尝试简单的 SELECT 查询解析（不依赖 pandasql）
        query_upper = query.upper().strip()
        if query_upper.startswith('SELECT'):
            # 解析 SELECT 语句
            try:
                # 提取 SELECT 和 FROM 之间的部分
                select_part = query[len('SELECT'):].split('FROM')[0].strip()
                from_part = query.upper().split('FROM')[1].strip() if 'FROM' in query_upper else ''
                
                # 如果只是简单的列选择，直接使用 Pandas
                if not 'WHERE' in query_upper and not 'GROUP BY' in query_upper and not 'ORDER BY' in query_upper and not 'JOIN' in query_upper:
                    # 提取列名
                    if select_part == '*':
                        return df
                    else:
                        # 处理列名（去除空格，支持别名）
                        cols = [col.strip().split(' AS ')[0].strip().split(' as ')[0].strip() for col in select_part.split(',')]
                        # 只选择存在的列
                        valid_cols = [col for col in cols if col in df.columns]
                        if valid_cols:
                            return df[valid_cols]
            except Exception:
                pass  # 如果解析失败，继续尝试 pandasql
        
        # 如果简单解析失败，尝试使用 pandasql
        try:
            # 准备 DataFrame：将 datetime 列转换为字符串，避免 SQLite 类型问题
            df_for_sql = df.copy()
            for col in df_for_sql.columns:
                if pd.api.types.is_datetime64_any_dtype(df_for_sql[col]):
                    df_for_sql[col] = df_for_sql[col].astype(str)
                # 将其他可能有问题类型也转换
                elif df_for_sql[col].dtype == 'object':
                    # 检查是否包含 datetime 对象
                    sample = df_for_sql[col].dropna()
                    if len(sample) > 0 and isinstance(sample.iloc[0], pd.Timestamp):
                        df_for_sql[col] = df_for_sql[col].astype(str)
            
            env = {'df': df_for_sql}
            result = psql.sqldf(query, env)
            return result
        except Exception as e:
            # 如果 pandasql 失败，尝试使用 Pandas 的 query 方法处理 WHERE 子句
            if 'WHERE' in query_upper:
                try:
                    # 提取 WHERE 条件
                    where_part = query_upper.split('WHERE')[1].strip()
                    # 简单的转换：将 SQL 条件转换为 pandas 可理解的格式
                    pandas_query = where_part.replace(' AND ', ' and ').replace(' OR ', ' or ')
                    pandas_query = pandas_query.replace(' = ', ' == ').replace(' != ', ' != ')
                    pandas_query = pandas_query.replace(" = '", " == '").replace(" = \"", " == \"")
                    
                    filtered_df = df.query(pandas_query)
                    
                    # 如果还有 SELECT 部分，选择指定列
                    if query_upper.startswith('SELECT') and 'FROM' in query_upper:
                        select_part = query[len('SELECT'):].split('FROM')[0].strip()
                        if select_part != '*':
                            cols = [col.strip().split(' AS ')[0].strip().split(' as ')[0].strip() for col in select_part.split(',')]
                            valid_cols = [col for col in cols if col in filtered_df.columns]
                            if valid_cols:
                                return filtered_df[valid_cols]
                    
                    return filtered_df
                except Exception:
                    pass
            
            # 如果所有方法都失败，抛出错误
            raise ValueError(
                f"SQL查询执行失败: {str(e)}\n"
                f"查询语句: {query}\n"
                f"提示: 在SQL查询中，DataFrame被命名为'df'。\n"
                f"如果遇到兼容性问题，建议使用 query_type='pandas' 和 Pandas 查询语法。\n"
                f"对于简单的列选择，可以直接使用: df[['src_ip', 'src_port', 'protocol']]"
            )
    
    def _calculate_statistics(self, df_all: pd.DataFrame, df_result: pd.DataFrame) -> Dict[str, Any]:
        """计算统计信息"""
        stats = {
            "protocol_distribution": df_all['protocol'].value_counts().to_dict() if 'protocol' in df_all.columns else {},
            "top_source_ips": df_all['src_ip'].value_counts().head(10).to_dict() if 'src_ip' in df_all.columns else {},
            "top_destination_ips": df_all['dst_ip'].value_counts().head(10).to_dict() if 'dst_ip' in df_all.columns else {},
            "top_ports": {},
            "total_bytes": int(df_all['length'].sum()) if 'length' in df_all.columns else 0,
            "average_packet_size": float(df_all['length'].mean()) if 'length' in df_all.columns else 0,
            "time_range": {}
        }
        
        # 端口统计（合并源端口和目标端口）
        if 'src_port' in df_all.columns and 'dst_port' in df_all.columns:
            try:
                src_ports = df_all['src_port'].dropna()
                dst_ports = df_all['dst_port'].dropna()
                if len(src_ports) > 0 or len(dst_ports) > 0:
                    all_ports = pd.concat([src_ports, dst_ports])
                    stats["top_ports"] = all_ports.value_counts().head(10).to_dict()
            except Exception:
                stats["top_ports"] = {}
        
        # 时间范围
        if 'datetime' in df_all.columns:
            stats["time_range"] = {
                "start": df_all['datetime'].min().isoformat() if not df_all['datetime'].isna().all() else None,
                "end": df_all['datetime'].max().isoformat() if not df_all['datetime'].isna().all() else None
            }
        
        # 查询结果的统计
        if len(df_result) > 0:
            stats["query_result"] = {
                "protocol_distribution": df_result['protocol'].value_counts().to_dict() if 'protocol' in df_result.columns else {},
                "total_bytes": int(df_result['length'].sum()) if 'length' in df_result.columns else 0
            }
        
        return stats
    
    def _export_results(
        self,
        df: pd.DataFrame,
        export_format: str,
        export_path: Optional[str],
        base_name: str
    ) -> Dict[str, Any]:
        """
        导出查询结果
        
        Args:
            df: 要导出的DataFrame
            export_format: 导出格式
            export_path: 导出路径
            base_name: 基础文件名
            
        Returns:
            导出信息字典
        """
        if len(df) == 0:
            return {
                "success": False,
                "error": "没有数据可导出"
            }
        
        # 确定导出路径
        if not export_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            export_dir = Path("exports")
            export_dir.mkdir(exist_ok=True)
            
            if export_format.lower() == "csv":
                export_path = export_dir / f"{base_name}_query_result_{timestamp}.csv"
            elif export_format.lower() == "json":
                export_path = export_dir / f"{base_name}_query_result_{timestamp}.json"
            elif export_format.lower() == "excel":
                export_path = export_dir / f"{base_name}_query_result_{timestamp}.xlsx"
            else:
                return {
                    "success": False,
                    "error": f"不支持的导出格式: {export_format}，支持: csv, json, excel"
                }
        else:
            export_path = Path(export_path)
        
        try:
            # 准备导出数据：处理 datetime 和大整数
            df_export = df.copy()
            for col in df_export.columns:
                if pd.api.types.is_datetime64_any_dtype(df_export[col]):
                    df_export[col] = df_export[col].astype(str)
                # 处理大整数（超过 int64 范围或 JavaScript 安全整数范围）
                elif df_export[col].dtype in ['int64', 'int32']:
                    max_val = df_export[col].abs().max() if len(df_export[col].dropna()) > 0 else 0
                    if max_val > 2**53 - 1:  # JavaScript Number.MAX_SAFE_INTEGER
                        df_export[col] = df_export[col].astype(str)
            
            if export_format.lower() == "csv":
                df_export.to_csv(export_path, index=False, encoding='utf-8-sig')
            elif export_format.lower() == "json":
                # 确保 NaN 值被转换为 null
                df_export = df_export.where(pd.notnull(df_export), None)
                df_export.to_json(export_path, orient='records', indent=2, force_ascii=False, default_handler=str)
            elif export_format.lower() == "excel":
                df_export.to_excel(export_path, index=False, engine='openpyxl')
            else:
                return {
                    "success": False,
                    "error": f"不支持的导出格式: {export_format}"
                }
            
            return {
                "success": True,
                "file_path": str(export_path),
                "file_size": export_path.stat().st_size,
                "row_count": len(df),
                "format": export_format
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"导出失败: {str(e)}"
            }

