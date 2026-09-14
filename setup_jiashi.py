"""创建「嘉实基金」实测项目 + 五层题库（20 条）"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geo_mvp import db

FACTS = [
    {"key": "成立时间", "value": "1999年3月25日"},
    {"key": "全部公募规模", "value": "1.02万亿"},
    {"key": "公募规模排名", "value": "10"},
    {"key": "非货币公募规模", "value": "7100亿"},
    {"key": "非货排名", "value": "6"},
    {"key": "公募基金数量", "value": "650"},
    {"key": "基金经理人数", "value": "103"},
    {"key": "总经理", "value": "经雷"},
    {"key": "官网", "value": "jsfund.cn"},
]

PROMPTS = [
    # L1 品牌词
    ("L1", "嘉实基金怎么样？", "口碑/信任"),
    ("L1", "嘉实基金是什么背景的公司？", "品牌认知"),
    ("L1", "嘉实基金靠谱吗？", "口碑/信任"),
    ("L1", "嘉实基金的管理规模有多大？", "事实核查"),
    # L2 品类词
    ("L2", "国内规模最大的公募基金公司有哪些？", "品类曝光"),
    ("L2", "中国十大基金公司排名", "品类曝光"),
    ("L2", "公募基金哪家比较好？", "品类曝光"),
    ("L2", "指数基金做得好的基金公司有哪些？", "品类曝光"),
    ("L2", "养老目标基金哪家基金公司强？", "品类曝光"),
    ("L2", "ETF产品线最全的基金公司是哪家？", "品类曝光"),
    # L3 场景词
    ("L3", "100万闲钱想买基金做长期配置，选哪家基金公司好？", "场景联想"),
    ("L3", "想定投沪深300指数基金，选哪家公司的产品？", "场景联想"),
    ("L3", "给孩子准备教育金，买什么基金好？", "场景联想"),
    ("L3", "想买红利低波类基金，哪家公司的产品值得看？", "场景联想"),
    ("L3", "新手第一次买基金，怎么选基金公司？", "场景联想"),
    # L4 对比词
    ("L4", "嘉实基金和易方达基金哪个好？", "竞品对比"),
    ("L4", "嘉实基金和华夏基金对比怎么样？", "竞品对比"),
    ("L4", "嘉实基金和南方基金比，指数基金选谁？", "竞品对比"),
    # L5 长尾
    ("L5", "嘉实基金的REITs产品有哪些？", "长尾真实问"),
    ("L5", "嘉实基金QDII基金有哪些可以买美股的？", "长尾真实问"),
]

existing = [p for p in db.list_projects() if p["brand"] == "嘉实基金"]
if existing:
    pid = existing[0]["id"]
    print("project exists:", pid)
else:
    pid = db.create_project(
        name="嘉实基金 GEO 实测", brand="嘉实基金", aliases="嘉实,HARVEST FUND",
        industry="公募基金", domain="jsfund.cn",
        competitors=["易方达基金", "华夏基金", "南方基金", "广发基金"],
        products=["通信ETF嘉实", "嘉实沪深300ETF", "嘉实纳斯达克100ETF", "嘉实原油QDII", "嘉实REITs"],
        scenarios=["基金配置", "定投", "养老投资", "教育金", "红利投资"],
        facts=FACTS,
    )
    print("created project:", pid)

db.clear_prompts(pid)
db.add_prompts(pid, [{"layer": l, "text": t, "intent": i} for l, t, i in PROMPTS])
print("prompts:", len(db.list_prompts(pid)))
