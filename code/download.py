import os
from sec_edgar_downloader import Downloader


def download_ma_filings(company_ticker, download_dir="./sec_data"):
    """
    根据股票代码批量下载与并购（M&A）相关的 SEC 备案文件
    包含：8-K (重大事件), S-4 (股票发行登记/合并), 14A (代理委托书/投票)
    """
    # 1. 初始化下载器 (严格遵守 SEC 要求，必须填写公司名/个人名和邮箱)
    # 示例: "YourName your-email@domain.com"
    user_agent = "MyResearchProject student@university.edu"

    dl = Downloader(company_ticker, user_agent, download_dir)

    # 2. 定义并购相关的核心表单类型
    filing_types = ["8-K", "S-4", "DEFM14A"]  # DEFM14A 是正式的并购投票代理委托书

    print(f"开始下载公司 {company_ticker} 的 M&A 相关文件...")

    for filing in filing_types:
        try:
            print(f"正在下载 {filing} 文件...")
            # download(表单类型, 限制下载最新的N份)
            # 如果想下载历史所有的，可以去掉 limit 参数，或者设置一个很大的数
            dl.get(filing, company_ticker, limit=5)
            print(f"✓ {filing} 下载完成")
        except Exception as e:
            print(f"✗ 下载 {filing} 时发生错误: {e}")

    print(f"\n所有下载任务结束！文件保存在: {os.path.abspath(download_dir)}")


if __name__ == "__main__":
    # 示例：下载 微软 (MSFT) 或 苹果 (AAPL) 的文件
    # 你可以替换成任何美国上市公司的 Ticker (股票代码) 或 CIK (中央索引代码)
    TARGET_COMPANY = "MSFT"

    download_ma_filings(TARGET_COMPANY)
