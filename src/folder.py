#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import logging
from collections import defaultdict

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("folder_processing.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger()

def scan_folder_contents(folder_path):
    """
    递归扫描文件夹内容,返回{相对路径: 文件大小}字典
    只处理第一层文件夹,但会递归遍历其内部所有文件和子文件夹
    """
    folder_contents = {}
    
    # 遍历文件夹中的所有条目
    for root, dirs, files in os.walk(folder_path):
        # 计算相对于原始文件夹的路径
        rel_root = os.path.relpath(root, folder_path)
        
        # 处理文件
        for file in files:
            try:
                file_path = os.path.join(root, file)
                rel_path = os.path.join(rel_root, file) if rel_root != '.' else file
                
                # 获取文件大小
                file_size = os.path.getsize(file_path)
                folder_contents[rel_path] = file_size
            except (OSError, PermissionError) as e:
                logger.error(f"无法访问文件 {file_path}: {str(e)}")
                continue
        
        # 处理目录（作为大小为0的特殊条目）
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            rel_path = os.path.join(rel_root, dir_name) if rel_root != '.' else dir_name
            
            # 添加目录标记（以斜杠结尾）
            folder_contents[rel_path + '/'] = 0
    
    return folder_contents

def scan_folders(parent_folder):
    """
    扫描父文件夹中的所有第一层文件夹
    返回{文件夹路径: 内容字典}的字典
    """
    folders = {}
    
    # 确保父文件夹存在
    if not os.path.exists(parent_folder):
        logger.error(f"父文件夹不存在: {parent_folder}")
        return folders
    
    # 遍历父文件夹中的所有条目
    for entry in os.listdir(parent_folder):
        full_path = os.path.join(parent_folder, entry)
        
        # 只处理文件夹
        if os.path.isdir(full_path):
            logger.info(f"扫描文件夹: {full_path}")
            contents = scan_folder_contents(full_path)
            
            if contents:
                folders[full_path] = {
                    'contents': contents,
                    'total_size': sum(contents.values()),
                    'file_count': len(contents)
                }
    
    return folders

def are_folders_identical(folder1, folder2):
    """比较两个文件夹内容是否完全相同"""
    if folder1['file_count'] != folder2['file_count']:
        return False
    if folder1['total_size'] != folder2['total_size']:
        return False
    return folder1['contents'] == folder2['contents']

def is_folder_contained(folder_small, folder_large):
    """判断small的内容是否完全包含在large中"""
    if folder_small['file_count'] > folder_large['file_count']:
        return False
    
    for file, size in folder_small['contents'].items():
        if file not in folder_large['contents'] or folder_large['contents'][file] != size:
            return False
    return True

def safe_delete_folder(folder_path, log_file, reason):
    """安全删除文件夹并记录"""
    try:
        if os.path.exists(folder_path):
            # 使用shutil.rmtree递归删除文件夹
            import shutil
            shutil.rmtree(folder_path)
            log_file.write(f"删除: {folder_path} ({reason})\n")
            logger.info(f"已删除: {folder_path} ({reason})")
            return True
        return False
    except Exception as e:
        logger.error(f"删除文件夹失败: {folder_path} - {str(e)}")
        log_file.write(f"删除失败: {folder_path} - {str(e)}\n")
        return False

def process_folders(folder_a, folder_c):
    """
    主处理函数：比较A和C文件夹中的文件夹
    """
    # 扫描文件夹
    logger.info("开始扫描文件夹A中的第一层文件夹...")
    folders_a = scan_folders(folder_a)
    logger.info(f"文件夹A中找到 {len(folders_a)} 个第一层文件夹")
    
    logger.info("开始扫描文件夹C中的第一层文件夹...")
    folders_c = scan_folders(folder_c)
    logger.info(f"文件夹C中找到 {len(folders_c)} 个第一层文件夹")
    
    # 创建日志文件
    with open("folder_processing_report.txt", "w", encoding="utf-8") as log_file:
        log_file.write("文件夹处理报告\n\n")
        
        # 1. 处理C中重复的文件夹
        logger.info("检查C中重复的文件夹...")
        
        # 找出所有内容相同的文件夹组
        content_groups = defaultdict(list)
        for path, data in folders_c.items():
            # 使用内容的字符串表示作为键
            content_key = json.dumps(data['contents'], sort_keys=True)
            content_groups[content_key].append(path)
        
        # 处理每个组
        to_delete = []
        for content_key, paths in content_groups.items():
            if len(paths) > 1:
                # 保留一个文件夹（选择第一个）
                keep_path = paths[0]
                delete_paths = paths[1:]
                
                # 记录删除信息
                log_file.write(f"发现 {len(paths)} 个相同内容的文件夹:\n")
                log_file.write(f"  保留: {os.path.basename(keep_path)}\n")
                for path in delete_paths:
                    log_file.write(f"  删除: {os.path.basename(path)}\n")
                log_file.write("\n")
                
                # 添加到删除列表
                to_delete.extend(delete_paths)
        
        # 执行删除
        for path in to_delete:
            safe_delete_folder(path, log_file, "C中重复文件夹")
            del folders_c[path]
        
        # 2. 处理C中与A重复的文件夹
        logger.info("检查C中与A重复的文件夹...")
        to_delete = []
        
        for c_path, c_data in list(folders_c.items()):
            for a_path, a_data in folders_a.items():
                if are_folders_identical(a_data, c_data):
                    if c_path not in to_delete:
                        to_delete.append(c_path)
                        log_file.write(f"删除: C {os.path.basename(c_path)} "
                                     f"保留: A {os.path.basename(a_path)} (与A重复)\n")
                    break
        
        # 执行删除
        for path in to_delete:
            safe_delete_folder(path, log_file, "与A中文件夹重复")
            del folders_c[path]
        
        # 3. 处理包含关系的文件夹（只检测C被A包含的情况）
        logger.info("检查C中的文件夹是否被A中的文件夹包含...")
        to_delete = []
        processed_pairs = set()
        
        # 遍历C中的每个文件夹
        for c_path, c_data in list(folders_c.items()):
            # 遍历A中的每个文件夹
            for a_path, a_data in folders_a.items():
                # 跳过已处理的组合
                pair_key = tuple(sorted((c_path, a_path)))
                if pair_key in processed_pairs:
                    continue
                processed_pairs.add(pair_key)
                
                # 跳过大小差异过大的文件夹
                size_ratio = abs(c_data['total_size'] - a_data['total_size']) / max(c_data['total_size'], a_data['total_size'])
                if size_ratio > 0.15:
                    continue
                
                # 检查C中的文件夹是否被A中的文件夹包含
                if is_folder_contained(c_data, a_data) and c_data['file_count'] < a_data['file_count']:
                    if c_path not in to_delete and os.path.exists(c_path):
                        to_delete.append(c_path)
                        log_file.write(f"删除: C {os.path.basename(c_path)} "
                                     f"保留: A {os.path.basename(a_path)} (C被A包含)\n")
                        break
        
        # 执行删除
        for path in to_delete:
            safe_delete_folder(path, log_file, "被A中文件夹包含")
            del folders_c[path]
    
    logger.info("文件夹处理完成!")
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
    
    success = process_folders(FOLDER_A, FOLDER_C)
    
    if not success:
        logger.error("处理过程中遇到错误")
        sys.exit(1)
    else:
        logger.info("操作成功完成")
        sys.exit(0)