import streamlit as st
import plotly.express as px
import json
import openai
# 新增导入
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
# 初始化配置
st.set_page_config(page_title="AI Chart Generator", layout="wide")

# 侧边栏配置
with st.sidebar:
    st.header("配置")
    proxy_url = st.text_input("代理地址 (可选)", 
                            value="http://127.0.0.1:7890",
                            help="格式：http://ip:port")
    base_url = "https://api.deepseek.com/"
    #blockchair_key = st.text_input("Blockchair API Key", type="password", 
    #                             help="从blockchair.com获取免费API密钥")
     # 示例部分保持不变 ...
    if 'api_key' not in st.session_state:
        st.session_state.api_key = ''
    
    api_key = st.text_input(
        "DeepSeek API密钥",
        type="password",
        value=st.session_state.api_key,
        help="密钥不会存储，刷新页面后需要重新输入"
    )
    
    # 添加安全警告
    st.markdown("""
    <div style="color: #ff4b4b; font-size: 0.8em; margin-top: -10px;">
    注意：请勿在公共设备保存密钥
    </div>
    """, unsafe_allow_html=True)

# 在代码中使用前添加验证
if not api_key.startswith('sk-'):
    st.error("无效的API密钥格式")
    st.stop()
# 修改后的比特币数据获取函数
def fetch_bitcoin_data(metric, days=30):
    # 初始化日期范围（UTC时区）
    end_date = datetime.now(pytz.utc)
    start_date = end_date - timedelta(days=days)
    
    # 确保日期范围不超过Bitaps限制（2年）
    if days > 730:
        st.error("Bitaps API最多支持查询2年历史数据")
        return pd.DataFrame()

    all_blocks = []
    
    # 按天循环请求
    current_date = start_date
    while current_date <= end_date:
        try:
            # 转换日期格式为API要求的路径参数
            day_str = current_date.strftime('%Y%m%d')
            url = f"https://api.bitaps.com/btc/v1/blockchain/blocks/day/{day_str}"
            
            # 分页参数
            params = {
                "limit": 100,
                "offset": 0
            }
            
            # 处理分页
            while True:
                response = requests.get(
                    url,
                    params=params,
                    proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
                    verify=False,
                    timeout=15
                )
                response.raise_for_status()
                
                data = response.json().get('data', {})
                
                if 'blocks' in data:
                    all_blocks.extend(data['blocks'])
                    
                    # 更新分页参数
                    if data.get('pagination', {}).get('next'):
                        params['offset'] += params['limit']
                    else:
                        break
                else:
                    break
                    
        except Exception as e:
            st.error(f"获取{day_str}数据失败: {str(e)}")
        
        # 移动到下一天
        current_date += timedelta(days=1)
    
    # ... 后续数据处理保持不变 ...

    # 处理空数据情况
    if not all_blocks:
        st.warning("所选日期范围内无可用区块数据")
        return pd.DataFrame(columns=['date', 'transaction_count', 'size'])

    # 按文档结构处理区块数据
    processed_data = []
    for block in all_blocks:
        try:
            # 转换时间戳为日期（UTC时区）
            block_date = datetime.utcfromtimestamp(block['time']).date()
            
            processed_data.append({
                'date': block_date,
                'transaction_count': block['tx_count'],
                'size': block['size'] / (1024 * 1024)  # 转换为MB
            })
            
        except KeyError as e:
            st.warning(f"区块数据缺少必要字段: {str(e)}")
            continue

    # 按日期聚合数据
    df = pd.DataFrame(processed_data)
    df = df.groupby('date').agg({
        'transaction_count': 'sum',
        'size': 'sum'
    }).reset_index()
    
    df.sort_values('date', inplace=True)
    return df
    
# 主界面
st.title("📊 智能图表生成器")
user_input = st.chat_input("用自然语言描述您需要的图表...")

if user_input:
    with st.status("生成图表中..."):
        # 初始化OpenAI客户端
        client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        # 构造请求
        # 修改AI提示词中的数据结构说明
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{
                "role": "user",
                "content": f"""
                用户需求：{user_input}
                
                如果涉及比特币真实历史数据，返回：
                {{
                    "data_type": "bitcoin",
                    "chart_type": "line|bar",
                    "metric": "transactions|block_size",
                    "days": 30,
                    "layout": {{...}}
                }}
                
                2. 其他情况返回json数据格式
                返回格式示例：
                {{
                    "chart_type": "line|bar|pie|scatter|3d",
                    "data": {{
                        "x": [...],
                        "y": [...],
                        "labels": [...],
                        "values": [...]
                    }},
                    "layout": {{
                        "title": "图表标题",
                        "xaxis_title": "X轴标签",
                        "yaxis_title": "Y轴标签"
                    }}
                }}
                """
            }],
            response_format={"type": "json_object"}
        )            
        # 字号阶梯参考
        SMALL = 12
        MEDIUM = 14
        LARGE = 16

        # 颜色配置示例
        hoverlabel=dict(
            font_size=MEDIUM,
            font_color="#2c3e50",
            bgcolor="#ecf0f1",
            bordercolor="#bdc3c7"
        )            # 解析响应
        chart_data = json.loads(response.choices[0].message.content)
        # 后续图表生成代码保持不变 ...
        # 修正后的图表生成逻辑
        if chart_data.get("data_type") == "bitcoin":
            df = fetch_bitcoin_data(chart_data["metric"], chart_data.get("days", 30))
            fig = None  # 确保变量初始化
            if df is not None:
                # 统一使用折线图展示比特币数据
                fig = px.line(df, x='date', y=chart_data["metric"], 
                            title=chart_data["layout"]["title"])
                fig.update_layout(
                    xaxis_title="日期",
                    yaxis_title="交易数量" if chart_data["metric"]=="transactions" else "区块大小 (MB)",
                    hovermode="x unified"
                )
        else:
            # 确保所有分支都初始化fig变量
            fig = None
            chart_type = chart_data["chart_type"]
            
            if chart_type == "line":
                fig = px.line(chart_data["data"], x='x', y='y', 
                            title=chart_data["layout"]["title"])
            elif chart_type == "bar":
                fig = px.bar(chart_data["data"], x='x', y='y',
                            title=chart_data["layout"]["title"])
            elif chart_type == "pie":
                fig = px.pie(chart_data["data"], names='labels', values='values',
                        title=chart_data["layout"]["title"])
            elif chart_type == "3d":
                fig = px.scatter_3d(chart_data["data"], x='x', y='y', z='z',
                                title=chart_data["layout"]["title"])
            else:
                st.error("不支持的图表类型")

        # 统一处理图表显示前确保fig存在
        if fig is not None:
            fig.update_layout(
                xaxis_title=chart_data["layout"].get("xaxis_title", ""),
                yaxis_title=chart_data["layout"].get("yaxis_title", ""),
                hoverlabel=hoverlabel
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("图表生成失败：无法创建图形对象")