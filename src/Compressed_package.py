#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import sys
import json
from collections import defaultdict
import shutil
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("archive_processing.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger()

# 检查7z是否可用
def check_7z_available():
    # 尝试常见的7-Zip安装路径
    possible_paths = [
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
        # 添加其他可能的路径
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # 检查系统PATH
    try:
        result = subprocess.run(
            ['7z', '--help'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0:
            return "7z"  # 返回命令名称
    except FileNotFoundError:
        pass
    
    return None

# 使用7z列出压缩文件内容
def list_archive_contents(archive_path):
    """使用7z列出压缩文件内容,返回{文件名: 文件大小}字典,包含文件夹"""
    seven_zip_path = check_7z_available()
    if seven_zip_path is None:
        logger.error("未找到7z程序")
        return None
    
    try:
        cmd = [seven_zip_path, 'l', '-ba', '-slt', archive_path] if seven_zip_path != "7z" else ['7z', 'l', '-ba', '-slt', archive_path]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if result.returncode != 0:
            logger.error(f"读取压缩文件失败: {archive_path}\n错误: {result.stderr}")
            return None
        
        # 解析7z输出
        contents = {}
        current_file = {}
        lines = result.stdout.splitlines()
        
        for line in lines:
            if line.strip() == '':
                if current_file.get('Path'):
                    # 处理目录和文件
                    if current_file.get('Folder', '') == '+':
                        # 目录,大小为0
                        contents[current_file['Path']] = 0
                    else:
                        # 文件,记录实际大小
                        contents[current_file['Path']] = int(current_file.get('Size', 0))
                current_file = {}
            elif '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                current_file[key] = value
        
        return contents
    except Exception as e:
        logger.exception(f"处理压缩文件异常: {archive_path}")
        return None

# 扫描文件夹中的压缩文件
def scan_archives(folder_path):
    """扫描文件夹中的压缩文件,返回{压缩文件路径: 内容字典}"""
    archives = {}
    for entry in os.listdir(folder_path):
        full_path = os.path.join(folder_path, entry)
        if os.path.isfile(full_path):
            ext = os.path.splitext(entry)[1].lower()
            if ext in ['.zip', '.rar']:
                logger.info(f"扫描压缩文件: {full_path}")
                contents = list_archive_contents(full_path)
                if contents is not None:
                    archives[full_path] = {
                        'contents': contents,
                        'total_size': sum(contents.values()),
                        'file_count': len(contents)
                    }
    return archives

# 判断两个压缩文件内容是否相同
def are_archives_identical(archive1, archive2):
    """比较两个压缩文件内容是否完全相同"""
    if archive1['file_count'] != archive2['file_count']:
        return False
    if archive1['total_size'] != archive2['total_size']:
        return False
    return archive1['contents'] == archive2['contents']

# 判断一个压缩文件是否包含另一个
def is_archive_contained(archive_small, archive_large):
    """判断small的内容是否完全包含在large中"""
    if archive_small['file_count'] > archive_large['file_count']:
        return False
    
    for file, size in archive_small['contents'].items():
        if file not in archive_large['contents'] or archive_large['contents'][file] != size:
            return False
    return True

# 删除文件并记录
def safe_delete_file(file_path, log_file, reason):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            log_file.write(f"删除: {file_path} ({reason})\n")
            logger.info(f"已删除: {file_path} ({reason})")
            return True
        return False
    except Exception as e:
        logger.error(f"删除文件失败: {file_path} - {str(e)}")
        log_file.write(f"删除失败: {file_path} - {str(e)}\n")
        return False

# 主处理函数
def process_archives(folder_a, folder_c):
    # 检查7z可用性
    if check_7z_available() is None:
        logger.error("未找到7z程序,请安装7-Zip并添加到系统PATH")
        return False
    
    # 扫描压缩文件
    logger.info("开始扫描文件夹A...")
    archives_a = scan_archives(folder_a)
    logger.info(f"文件夹A中找到 {len(archives_a)} 个压缩文件")
    
    logger.info("开始扫描文件夹C...")
    archives_c = scan_archives(folder_c)
    logger.info(f"文件夹C中找到 {len(archives_c)} 个压缩文件")
    
    # 创建日志文件
    with open("archive_processing_report.txt", "w", encoding="utf-8") as log_file:
        log_file.write("压缩文件处理报告\n\n")
        
        # 2.1 处理C中重复的压缩文件
        logger.info("检查C中重复的压缩文件...")
        
        # 找出所有内容相同的压缩包组
        content_groups = defaultdict(list)
        for path, data in archives_c.items():
            # 使用内容的字符串表示作为键
            content_key = json.dumps(data['contents'], sort_keys=True)
            content_groups[content_key].append(path)
        
        # 处理每个组
        to_delete = []
        for content_key, paths in content_groups.items():
            if len(paths) > 1:
                # 保留一个压缩包（选择第一个）
                keep_path = paths[0]
                delete_paths = paths[1:]
                
                # 记录删除信息
                log_file.write(f"发现 {len(paths)} 个相同内容的压缩包:\n")
                log_file.write(f"  保留: {os.path.basename(keep_path)}\n")
                for path in delete_paths:
                    log_file.write(f"  删除: {os.path.basename(path)}\n")
                log_file.write("\n")
                
                # 添加到删除列表
                to_delete.extend(delete_paths)
        
        # 执行删除
        for path in to_delete:
            safe_delete_file(path, log_file, "C中重复文件")
            del archives_c[path]
        
        # 2.2 处理C中与A重复的压缩文件
        logger.info("检查C中与A重复的压缩文件...")
        to_delete = []
        
        for c_path, c_data in list(archives_c.items()):
            for a_path, a_data in archives_a.items():
                if are_archives_identical(a_data, c_data):
                    if c_path not in to_delete:
                        to_delete.append(c_path)
                        log_file.write(f"删除: C {os.path.basename(c_path)} "
                                     f"保留: A {os.path.basename(a_path)} (与A重复)\n")
                    break
        
        # 执行删除
        for path in to_delete:
            safe_delete_file(path, log_file, "与A中文件重复")
            del archives_c[path]
        
        # 2.3 处理包含关系的压缩文件（只检测C被A包含的情况）
        logger.info("检查C中的压缩包是否被A中的压缩包包含...")
        to_delete = []
        processed_pairs = set()
        
        # 遍历C中的每个压缩包
        for c_path, c_data in list(archives_c.items()):
            # 遍历A中的每个压缩包
            for a_path, a_data in archives_a.items():
                # 跳过已处理的组合
                pair_key = tuple(sorted((c_path, a_path)))
                if pair_key in processed_pairs:
                    continue
                processed_pairs.add(pair_key)
                
                # 跳过大小差异过大的文件
                size_ratio = abs(c_data['total_size'] - a_data['total_size']) / max(c_data['total_size'], a_data['total_size'])
                if size_ratio > 0.15:
                    continue
                
                # 检查C中的压缩包是否被A中的压缩包包含
                if is_archive_contained(c_data, a_data) and c_data['file_count'] < a_data['file_count']:
                    if c_path not in to_delete and os.path.exists(c_path):
                        to_delete.append(c_path)
                        log_file.write(f"删除: C {os.path.basename(c_path)} "
                                     f"保留: A {os.path.basename(a_path)} (C被A包含)\n")
                        break
        
        # 执行删除
        for path in to_delete:
            safe_delete_file(path, log_file, "被A中压缩包包含")
            del archives_c[path]
    
    logger.info("处理完成!")
    return True

if __name__ == "__main__":
    # 设置实际的文件夹路径 - 用户需要修改这些路径
    FOLDER_A = r"A"  # 替换为实际的A文件夹路径
    FOLDER_C = r"C"     # 替换为实际的C文件夹路径
    
    # 检查文件夹是否存在
    if not os.path.exists(FOLDER_A):
        logger.error(f"文件夹 {FOLDER_A} 不存在！")
        sys.exit(1)
    
    if not os.path.exists(FOLDER_C):
        logger.error(f"文件夹 {FOLDER_C} 不存在！")
        sys.exit(1)
    
    # 运行主处理
    logger.info(f"开始处理文件夹 A: {FOLDER_A}")
    logger.info(f"开始处理文件夹 C: {FOLDER_C}")
    
    success = process_archives(FOLDER_A, FOLDER_C)
    
    if not success:
        logger.error("处理过程中遇到错误")
        sys.exit(1)
    else:
        logger.info("操作成功完成")
        sys.exit(0)