#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import time
from pathlib import Path
import logging

# 设置日志
def setup_logging():
    """配置日志系统"""
    logger = logging.getLogger("ScriptRunner")
    logger.setLevel(logging.INFO)
    
    # 防止重复添加处理器
    if logger.handlers:
        return logger
    
    # 文件处理器
    file_handler = logging.FileHandler("script_runner.log", encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # 格式化
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

def run_script(script_name):
    """运行指定的Python脚本"""
    script_path = Path(script_name)
    
    if not script_path.exists():
        logger.error(f"脚本不存在: {script_name}")
        return False
    
    logger.info(f"开始执行脚本: {script_name}")
    start_time = time.time()
    
    try:
        # 使用当前Python解释器运行脚本
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=3600  # 设置1小时超时
        )
        
        elapsed_time = time.time() - start_time
        
        # 记录脚本输出
        if result.stdout:
            logger.info(f"{script_name} 输出:\n{result.stdout}")
        
        # 记录错误输出
        if result.stderr:
            logger.error(f"{script_name} 错误输出:\n{result.stderr}")
        
        # 检查返回码
        if result.returncode == 0:
            logger.info(f"脚本执行成功: {script_name}, 耗时: {elapsed_time:.2f}秒")
            return True
        else:
            logger.error(f"脚本执行失败: {script_name}, 返回码: {result.returncode}, 耗时: {elapsed_time:.2f}秒")
            return False
            
    except subprocess.TimeoutExpired:
        elapsed_time = time.time() - start_time
        logger.error(f"脚本执行超时: {script_name}, 耗时: {elapsed_time:.2f}秒")
        return False
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"执行脚本时发生异常: {script_name}, 错误: {e}, 耗时: {elapsed_time:.2f}秒")
        return False

def main():
    """主函数"""
    # 设置控制台编码为UTF-8
    if sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass
    
    logger.info("开始执行脚本序列")
    total_start_time = time.time()
    
    # 定义要执行的脚本列表（按顺序）
    scripts_to_run = [
        "Compressed_package.py",
        "folder.py", 
        "Files.py",
        "unpack.py",
        "Plagiarism_check.py"
    ]
    
    # 检查所有脚本是否存在
    missing_scripts = []
    for script in scripts_to_run:
        if not Path(script).exists():
            missing_scripts.append(script)
    
    if missing_scripts:
        logger.error(f"以下脚本不存在: {', '.join(missing_scripts)}")
        logger.error("请确保所有脚本都在当前目录下")
        return
    
    # 依次执行脚本
    success_count = 0
    failed_count = 0
    
    for script in scripts_to_run:
        if run_script(script):
            success_count += 1
        else:
            failed_count += 1
            # 询问用户是否继续执行后续脚本
            user_input = input(f"脚本 {script} 执行失败,是否继续执行后续脚本? (y/n): ")
            if user_input.lower() != 'y':
                logger.info("用户选择停止执行后续脚本")
                break
    
    total_elapsed_time = time.time() - total_start_time
    logger.info(f"所有脚本执行完成! 成功: {success_count}, 失败: {failed_count}, 总耗时: {total_elapsed_time:.2f}秒")
    
    if failed_count > 0:
        logger.warning("部分脚本执行失败,请检查日志以获取详细信息")

if __name__ == "__main__":
    main()