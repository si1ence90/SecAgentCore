"""
PCAP分析工具测试脚本
测试从1.cap文件中提取源IP、源端口和协议
"""

import sys
from pathlib import Path
from tools.pcap_analysis import PCAPAnalysisTool

def main():
    print("=" * 60)
    print("PCAP分析工具测试")
    print("=" * 60)
    
    # 检查文件是否存在
    pcap_file = "1.cap"
    if not Path(pcap_file).exists():
        print(f"[ERROR] 文件 {pcap_file} 不存在")
        print(f"当前目录: {Path.cwd()}")
        return 1
    
    print(f"[OK] 找到文件: {pcap_file}")
    print(f"文件大小: {Path(pcap_file).stat().st_size / 1024:.2f} KB")
    print()
    
    # 创建工具实例
    try:
        tool = PCAPAnalysisTool()
        print("[OK] 工具初始化成功")
    except Exception as e:
        print(f"[ERROR] 工具初始化失败: {e}")
        return 1
    
    print()
    print("=" * 60)
    print("开始分析PCAP文件...")
    print("=" * 60)
    
    # 执行分析 - 使用SQL查询提取源IP、源端口和协议
    # 先获取所有数据，然后过滤出有端口的数据包
    try:
        print("方法1: 提取所有数据包的源IP、源端口和协议...")
        result = tool.execute(
            pcap_file=pcap_file,
            query="SELECT src_ip, src_port, protocol FROM df",
            query_type="sql",
            limit=50  # 限制返回50条记录用于测试
        )
        
        if not result.get("success"):
            print(f"[ERROR] 分析失败: {result.get('error')}")
            return 1
        
        data = result.get("result", {})
        
        print()
        print("=" * 60)
        print("分析结果")
        print("=" * 60)
        print(f"总数据包数: {data.get('total_packets', 0)}")
        print(f"过滤后数据包数: {data.get('filtered_packets', 0)}")
        print(f"查询结果数: {data.get('query_result_count', 0)}")
        print()
        
        # 显示样本数据
        sample_data = data.get("sample_data", [])
        if sample_data:
            print("=" * 60)
            print("提取的数据（前50条，包含所有协议）:")
            print("=" * 60)
            print(f"{'序号':<6} {'源IP':<20} {'源端口':<10} {'协议':<10}")
            print("-" * 60)
            
            # 显示所有数据
            for idx, record in enumerate(sample_data, 1):
                src_ip = record.get('src_ip', 'N/A')
                src_port = record.get('src_port', 'N/A')
                protocol = record.get('protocol', 'N/A')
                print(f"{idx:<6} {str(src_ip):<20} {str(src_port):<10} {str(protocol):<10}")
            
            # 过滤出有端口的数据包（TCP/UDP）
            tcp_udp_data = [r for r in sample_data if r.get('src_port') is not None and r.get('protocol') in ['TCP', 'UDP']]
            if tcp_udp_data:
                print()
                print("=" * 60)
                print("TCP/UDP数据包（有端口信息）:")
                print("=" * 60)
                print(f"{'序号':<6} {'源IP':<20} {'源端口':<10} {'协议':<10}")
                print("-" * 60)
                for idx, record in enumerate(tcp_udp_data[:20], 1):
                    src_ip = record.get('src_ip', 'N/A')
                    src_port = record.get('src_port', 'N/A')
                    protocol = record.get('protocol', 'N/A')
                    print(f"{idx:<6} {str(src_ip):<20} {str(src_port):<10} {str(protocol):<10}")
        else:
            print("[WARNING] 没有提取到数据")
        
        # 显示统计信息
        stats = data.get("statistics", {})
        if stats:
            print()
            print("=" * 60)
            print("统计信息")
            print("=" * 60)
            
            protocol_dist = stats.get("protocol_distribution", {})
            if protocol_dist:
                print("\n协议分布:")
                for protocol, count in protocol_dist.items():
                    print(f"  {protocol}: {count}")
            
            top_src_ips = stats.get("top_source_ips", {})
            if top_src_ips:
                print("\nTop 10 源IP:")
                for ip, count in list(top_src_ips.items())[:10]:
                    print(f"  {ip}: {count} 个数据包")
        
        print()
        print("=" * 60)
        print("[OK] 测试完成")
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        print(f"[ERROR] 执行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

