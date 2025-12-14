import asyncio
import aiohttp
import re
from bs4 import BeautifulSoup

# 配置参数
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1


def keep_only_chinese(text):
    """
    使用正则表达式筛选并只保留中文字符。
    """
    if not isinstance(text, str):
        return ""
    pattern = re.compile(r'[\u4e00-\u9fa5]')
    chinese_chars = pattern.findall(text)
    return ''.join(chinese_chars)


async def make_request_with_retries(url, headers, retries=MAX_RETRIES, delay=RETRY_DELAY_SECONDS, timeout=15):
    """
    带有重试机制的异步请求函数。
    """
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                print(f"[调试] 尝试请求URL: {url}, 尝试次数: {attempt+1}/{retries}")
                async with session.get(url, headers=headers, timeout=timeout, ssl=False) as response:
                    print(f"[调试] 响应状态码: {response.status}, URL: {url}")
                    response.raise_for_status()
                    # 读取内容并手动处理编码
                    content = await response.read()
                    try:
                        text = content.decode('gb18030')
                    except UnicodeDecodeError:
                        text = content.decode('utf-8', errors='ignore')
                    print(f"[调试] 获取到HTML内容长度: {len(text)} 字符, 前500字符: {text[:500]}...")
                    return text
        except aiohttp.ClientError as e:
            print(f"[调试] 请求失败: {e}, URL: {url}")
            if attempt < retries - 1:
                await asyncio.sleep(delay)
    return None


async def fetch_oupei_data(match_id):
    """
    获取欧赔数据。
    """
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    url = f'https://odds.500.com/fenxi/ouzhi-{match_id}.shtml'
    print(f"[调试] 开始获取欧赔数据，match_id: {match_id}")
    res_text = await make_request_with_retries(url, headers)
    if not res_text:
        print(f"[调试] 获取欧赔数据失败，res_text为空，URL: {url}")
        return None
    if "百家欧赔" not in res_text:
        print(f"[调试] HTML内容中未找到'百家欧赔'，URL: {url}")
        return None

    try:
        soup = BeautifulSoup(res_text, 'lxml')
        data_table = soup.find('table', id='datatb')
        if not data_table:
            print(f"[调试] 未找到ID为'datatb'的表格，URL: {url}")
            return None

        extracted_data = {}
        company_rows = data_table.find_all('tr', id=re.compile(r'^\d+$'))
        print(f"[调试] 找到{len(company_rows)}行公司数据")

        for row in company_rows:
            company_td = row.find('td', class_='tb_plgs')
            if not company_td or not company_td.has_attr('title'):
                continue
            # 直接使用网页中提取的公司名称，不再进行硬编码映射
            clean_company_name = company_td['title']
            odds_table = row.find('table', class_='pl_table_data')
            if odds_table:
                odds_rows = odds_table.find_all('tr')
                if len(odds_rows) == 2:
                    initial_tds = odds_rows[0].find_all('td')
                    instant_tds = odds_rows[1].find_all('td')
                    extracted_data[clean_company_name] = {
                        'initial': [d.get_text(strip=True) for d in initial_tds],
                        'instant': [d.get_text(strip=True) for d in instant_tds]
                    }
        print(f"[调试] 成功提取欧赔数据，公司数量: {len(extracted_data)}")
        return extracted_data
    except Exception as e:
        print(f"[调试] 解析欧赔数据失败: {e}, URL: {url}")
        return None


async def fetch_yapan_data(match_id):
    """
    获取亚盘数据。
    """
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    url = f'https://odds.500.com/fenxi/yazhi-{match_id}.shtml'
    print(f"[调试] 开始获取亚盘数据，match_id: {match_id}")
    res_text = await make_request_with_retries(url, headers)
    if not res_text:
        print(f"[调试] 获取亚盘数据失败，res_text为空，URL: {url}")
        return None
    if "亚盘对比" not in res_text:
        print(f"[调试] HTML内容中未找到'亚盘对比'，URL: {url}")
        return None

    try:
        soup = BeautifulSoup(res_text, 'lxml')
        data_table = soup.find('table', id='datatb')
        if not data_table:
            print(f"[调试] 未找到ID为'datatb'的表格，URL: {url}")
            return None

        extracted_data = {}
        company_rows = data_table.find_all('tr', id=re.compile(r'^\d+$'))
        print(f"[调试] 找到{len(company_rows)}行公司数据")

        for row in company_rows:
            try:
                all_tds = row.find_all('td', recursive=False)
                if len(all_tds) < 6: continue
                company_link = all_tds[1].find('a')
                if not company_link or not company_link.has_attr('title'): continue
                # 直接使用网页中提取的公司名称，不再进行硬编码映射
                clean_company_name = company_link['title']
                instant_table = all_tds[2].find('table')
                initial_table = all_tds[4].find('table')

                if instant_table and initial_table:
                    instant_data = [d.get_text(strip=True) for d in instant_table.find_all('td')[:3]]
                    initial_data = [d.get_text(strip=True) for d in initial_table.find_all('td')[:3]]
                    if len(instant_data) == 3 and len(initial_data) == 3:
                        extracted_data[clean_company_name] = {
                            'initial': initial_data,
                            'instant': instant_data
                        }
            except (AttributeError, IndexError) as e:
                print(f"[调试] 解析亚盘行数据失败: {e}")
                continue
        print(f"[调试] 成功提取亚盘数据，公司数量: {len(extracted_data)}")
        return extracted_data
    except Exception as e:
        print(f"[调试] 解析亚盘数据失败: {e}, URL: {url}")
        return None


async def fetch_daxiao_data(match_id):
    """
    获取大小球数据。
    """
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    url = f'https://odds.500.com/fenxi/daxiao-{match_id}.shtml'
    print(f"[调试] 开始获取大小球数据，match_id: {match_id}")
    res_text = await make_request_with_retries(url, headers)
    if not res_text:
        print(f"[调试] 获取大小球数据失败，res_text为空，URL: {url}")
        return None
    if "大小指数" not in res_text:
        print(f"[调试] HTML内容中未找到'大小指数'，URL: {url}")
        return None

    try:
        soup = BeautifulSoup(res_text, 'lxml')
        data_table = soup.find('table', id='datatb')
        if not data_table:
            print(f"[调试] 未找到ID为'datatb'的表格，URL: {url}")
            return None

        extracted_data = {}
        company_rows = data_table.find_all('tr', id=re.compile(r'^\d+$'))
        print(f"[调试] 找到{len(company_rows)}行公司数据")

        for row in company_rows:
            try:
                all_tds = row.find_all('td', recursive=False)
                if len(all_tds) < 6: continue
                company_link = all_tds[1].find('a')
                if not company_link or not company_link.has_attr('title'): continue
                # 直接使用网页中提取的公司名称，不再进行硬编码映射
                clean_company_name = company_link['title']
                instant_table = all_tds[2].find('table')
                initial_table = all_tds[4].find('table')

                if instant_table and initial_table:
                    instant_data = [d.get_text(strip=True) for d in instant_table.find_all('td')[:3]]
                    initial_data = [d.get_text(strip=True) for d in initial_table.find_all('td')[:3]]
                    if len(instant_data) == 3 and len(initial_data) == 3:
                        extracted_data[clean_company_name] = {
                            'initial': initial_data,
                            'instant': instant_data
                        }
            except (AttributeError, IndexError) as e:
                print(f"[调试] 解析大小球行数据失败: {e}")
                continue
        print(f"[调试] 成功提取大小球数据，公司数量: {len(extracted_data)}")
        return extracted_data
    except Exception as e:
        print(f"[调试] 解析大小球数据失败: {e}, URL: {url}")
        return None


async def fetch_all_odds_data(match_id):
    """
    为单个ID获取所有赔率数据。
    """
    # 并行获取所有赔率数据
    oupei_task = fetch_oupei_data(match_id)
    yapan_task = fetch_yapan_data(match_id)
    daxiao_task = fetch_daxiao_data(match_id)
    
    # 等待所有任务完成
    oupei_data, yapan_data, daxiao_data = await asyncio.gather(oupei_task, yapan_task, daxiao_task)

    return {
        'oupei': oupei_data,
        'yapan': yapan_data,
        'daxiao': daxiao_data
    }
