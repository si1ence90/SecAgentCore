"""
PCAP分析工具简单测试 - 提取源IP、源端口和协议
"""

from tools.pcap_analysis import PCAPAnalysisTool

# 创建工具
tool = PCAPAnalysisTool()

# 执行分析 - 使用Pandas查询语法过滤有端口的数据包
print("Analyzing 1.cap file...")
result = tool.execute(
    pcap_file="1.cap",
    query="src_port.notna()",
    query_type="pandas",
    limit=30
)

if result.get("success"):
    data = result.get("result", {})
    print(f"\nTotal packets: {data.get('total_packets', 0)}")
    print(f"Query results: {data.get('query_result_count', 0)}")
    
    # 只显示需要的列（源IP、源端口、协议）
    print("\nExtracted data (TCP/UDP packets with ports):")
    print("-" * 70)
    print(f"{'No.':<6} {'Source IP':<20} {'Source Port':<12} {'Protocol':<10}")
    print("-" * 70)
    
    sample_data = data.get("sample_data", [])
    for idx, record in enumerate(sample_data, 1):
        src_ip = record.get('src_ip', 'N/A')
        src_port = record.get('src_port', 'N/A')
        protocol = record.get('protocol', 'N/A')
        # 只显示有端口的数据包
        if src_port != 'N/A' and src_port is not None:
            print(f"{idx:<6} {str(src_ip):<20} {str(src_port):<12} {str(protocol):<10}")
    
    # 统计信息
    stats = data.get("statistics", {})
    if stats:
        print("\nProtocol Distribution:")
        for proto, count in stats.get("protocol_distribution", {}).items():
            print(f"  {proto}: {count}")
else:
    print(f"Error: {result.get('error')}")

