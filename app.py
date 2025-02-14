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
    api_key = st.text_input("DeepSeek API密钥", type="password")
    base_url = "https://api.deepseek.com/"
    #blockchair_key = st.text_input("Blockchair API Key", type="password", 
    #                             help="从blockchair.com获取免费API密钥")
     # 示例部分保持不变 ...
# 修改后的比特币数据获取函数
def fetch_bitcoin_data(metric, days=30):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # 确保日期范围不超过Bitaps限制（2年）
    if days > 730:
        st.error("Bitaps API最多支持查询2年历史数据")
        return None
    
    # 添加时区处理
    tz = pytz.timezone('UTC')
    start_date = tz.localize(start_date)
    end_date = tz.localize(end_date)
    
    url = "https://api.bitaps.com/btc/v1/blockchain/block/date"
    params = {
        "date_from": start_date.strftime('%Y-%m-%d'),
        "date_to": end_date.strftime('%Y-%m-%d')
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        # 处理空数据情况
        if not response.json().get('data'):
            st.warning("所选日期范围内无可用数据")
            return pd.DataFrame(columns=['date', 'transaction_count', 'size'])
            
        # ... 原有数据处理代码 ...
        
    except requests.exceptions.HTTPError as e:
        error_msg = response.json().get('message', '未知错误')
        st.error(f"API请求失败 ({e.response.status_code}): {error_msg}")
        return None
    
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