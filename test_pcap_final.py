"""
PCAP分析工具最终测试 - 提取源IP、源端口和协议
使用最简单的SQL查询确保兼容性
"""

from tools.pcap_analysis import PCAPAnalysisTool

# 创建工具
tool = PCAPAnalysisTool()

# 执行分析 - 使用简单SQL查询（不带WHERE子句）
print("=" * 70)
print("PCAP Analysis Tool Test - Extract Source IP, Port, and Protocol")
print("=" * 70)
print("\nAnalyzing 1.cap file...\n")

result = tool.execute(
    pcap_file="1.cap",
    query="SELECT src_ip, src_port, protocol FROM df",
    query_type="sql",
    limit=50
)

if result.get("success"):
    data = result.get("result", {})
    print(f"Total packets: {data.get('total_packets', 0)}")
    print(f"Query results: {data.get('query_result_count', 0)}")
    
    print("\n" + "=" * 70)
    print("Extracted Data (Source IP, Source Port, Protocol):")
    print("=" * 70)
    print(f"{'No.':<6} {'Source IP':<20} {'Source Port':<12} {'Protocol':<10}")
    print("-" * 70)
    
    sample_data = data.get("sample_data", [])
    # 显示所有数据，包括有端口和没有端口的
    for idx, record in enumerate(sample_data, 1):
        src_ip = record.get('src_ip', 'N/A')
        src_port = record.get('src_port', 'N/A')
        protocol = record.get('protocol', 'N/A')
        print(f"{idx:<6} {str(src_ip):<20} {str(src_port):<12} {str(protocol):<10}")
    
    # 统计信息
    stats = data.get("statistics", {})
    if stats:
        print("\n" + "=" * 70)
        print("Protocol Distribution:")
        print("=" * 70)
        for proto, count in stats.get("protocol_distribution", {}).items():
            print(f"  {proto}: {count} packets")
        
        top_ips = stats.get("top_source_ips", {})
        if top_ips:
            print("\nTop 5 Source IPs:")
            for ip, count in list(top_ips.items())[:5]:
                print(f"  {ip}: {count} packets")
    
    print("\n" + "=" * 70)
    print("[SUCCESS] Test completed successfully!")
    print("=" * 70)
else:
    print(f"\n[ERROR] Analysis failed: {result.get('error')}")

