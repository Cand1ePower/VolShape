import datetime
from typing import Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import WeeklySummary

class WeeklyReportGenerator:
    """
    高保真健身周报 HTML 生成服务 (Retention Tool)。
    自动提取 PostgreSQL weekly_summaries 归档，渲染成适合移动端 WebView 加载的高阶精美交互周报卡片。
    """
    
    @staticmethod
    async def get_latest_report_html(user_id: str, db: AsyncSession) -> Optional[str]:
        """
        获取用户最近一周的周报 HTML 数据。
        """
        stmt = select(WeeklySummary).where(
            WeeklySummary.user_id == user_id
        ).order_by(desc(WeeklySummary.week_start)).limit(1)
        
        result = await db.execute(stmt)
        summary = result.scalars().first()
        
        if not summary:
            return None
            
        # 提取快照数据
        snapshot = summary.metrics_snapshot or {}
        weight = snapshot.get("weight", "N/A")
        body_fat = snapshot.get("body_fat", "N/A")
        
        # 组装高阶留存 HTML，融入丰富的设计美学 (Curated Harmonious Palette & sleek styling)
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: -apple-system, system-ui, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    background-color: #000000;
                    color: #FFFFFF;
                    margin: 0;
                    padding: 16px;
                }}
                .card {{
                    background: linear-gradient(135deg, #1C1C1E 0%, #2C2C2E 100%);
                    border-radius: 20px;
                    border: 1px solid #3A3A3C;
                    padding: 24px;
                    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
                }}
                h1 {{
                    font-size: 24px;
                    margin: 0 0 8px 0;
                    background: linear-gradient(90deg, #007AFF, #34C759);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                }}
                .subtitle {{
                    font-size: 13px;
                    color: #AEAEB2;
                    margin-bottom: 24px;
                }}
                .metric-row {{
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 20px;
                    gap: 12px;
                }}
                .metric-box {{
                    flex: 1;
                    background: rgba(255, 255, 255, 0.05);
                    border-radius: 12px;
                    padding: 16px;
                    text-align: center;
                }}
                .metric-label {{
                    font-size: 11px;
                    color: #8E8E93;
                    margin-bottom: 4px;
                }}
                .metric-value {{
                    font-size: 20px;
                    font-weight: bold;
                }}
                .summary-box {{
                    background: rgba(52, 199, 89, 0.1);
                    border-left: 4px solid #34C759;
                    border-radius: 8px;
                    padding: 16px;
                    font-size: 14px;
                    line-height: 1.6;
                    margin-top: 20px;
                }}
                .footer {{
                    text-align: center;
                    font-size: 11px;
                    color: #8E8E93;
                    margin-top: 24px;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>VolShape 个人体征周报</h1>
                <div class="subtitle">周报周期起始: {summary.week_start.isoformat()}</div>
                
                <div class="metric-row">
                    <div class="metric-box">
                        <div class="metric-label">体重记录</div>
                        <div class="metric-value">{weight} kg</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-label">体脂均值</div>
                        <div class="metric-value">{body_fat} %</div>
                    </div>
                </div>
                
                <div class="summary-box">
                    <strong>💡 AI 教练科学建议:</strong><br>
                    {summary.summary_text.replace('\n', '<br>')}
                </div>
                
                <div class="footer">
                    📊 本数据基于您的可穿戴设备与主动打卡流水统计，已由 VolShape 康复学 AI 模块双向校准。
                </div>
            </div>
        </body>
        </html>
        """
        return html_content.strip()
