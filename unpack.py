#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import sys
from pathlib import Path

def log(message, level="INFO"):
    """打印日志信息"""
    print(f"[{level}] {message}")

def is_compressed_file(file_path):
    """检查文件是否为压缩文件"""
    compressed_extensions = ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2']
    return file_path.suffix.lower() in compressed_extensions

def safe_path_name(name):
    """处理可能包含非法字符的文件名"""
    # 替换Windows文件名中的非法字符
    illegal_chars = '<>:"/\\|?*'
    for char in illegal_chars:
        name = name.replace(char, '_')
    return name

def extract_with_7zip(archive_path, output_dir):
    """使用7zip解压文件"""
    try:
        # 使用7zip命令行工具解压,支持UTF-8编码
        cmd = ['7z', 'x', str(archive_path), f'-o{str(output_dir)}', '-y', '-r', '-aoa']
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode != 0:
            log(f"7zip解压失败: {result.stderr}", "ERROR")
            return False
        return True
    except Exception as e:
        log(f"调用7zip时出错: {e}", "ERROR")
        return False

def extract_with_winrar(archive_path, output_dir):
    """使用WinRAR解压文件"""
    try:
        # 使用WinRAR命令行工具解压
        cmd = ['winrar', 'x', '-y', '-ibck', str(archive_path), str(output_dir)]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode != 0:
            log(f"WinRAR解压失败: {result.stderr}", "ERROR")
            return False
        return True
    except Exception as e:
        log(f"调用WinRAR时出错: {e}", "ERROR")
        return False

def extract_archive(archive_path, output_dir):
    """解压压缩文件到指定目录"""
    log(f"开始解压: {archive_path} -> {output_dir}")
    
    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 尝试使用7zip解压
    if extract_with_7zip(archive_path, output_dir):
        log(f"成功使用7zip解压: {archive_path}")
        return True
    
    # 如果7zip失败,尝试使用WinRAR
    if extract_with_winrar(archive_path, output_dir):
        log(f"成功使用WinRAR解压: {archive_path}")
        return True
    
    log(f"无法解压文件: {archive_path}", "ERROR")
    return False

def copy_item(src_path, dst_path):
    """复制文件或文件夹到目标位置"""
    try:
        if src_path.is_dir():
            # 复制文件夹
            shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
            log(f"复制文件夹: {src_path} -> {dst_path}")
        else:
            # 复制文件
            shutil.copy2(src_path, dst_path)
            log(f"复制文件: {src_path} -> {dst_path}")
        return True
    except Exception as e:
        log(f"复制失败: {src_path} -> {dst_path}, 错误: {e}", "ERROR")
        return False

def process_c_to_d(c_dir, d_dir):
    """处理从C到D的复制和解压操作"""
    log(f"开始处理C文件夹: {c_dir}")
    
    # 第一步: 解压C文件夹中的所有压缩包到D文件夹
    for item in c_dir.iterdir():
        if is_compressed_file(item):
            # 创建以压缩包名字命名的文件夹
            folder_name = safe_path_name(item.stem)
            output_dir = d_dir / folder_name
            
            if not extract_archive(item, output_dir):
                log(f"跳过解压失败的压缩包: {item}", "WARNING")
    
    # 第二步: 复制C中除了压缩包以外的文件夹和文件到D文件夹
    for item in c_dir.iterdir():
        if not is_compressed_file(item):
            dst_path = d_dir / safe_path_name(item.name)
            if not copy_item(item, dst_path):
                log(f"跳过复制失败的项: {item}", "WARNING")

def find_all_compressed_files(directory):
    """递归查找目录中的所有压缩文件"""
    compressed_files = []
    try:
        for item in directory.iterdir():
            if item.is_dir():
                # 递归查找子目录
                compressed_files.extend(find_all_compressed_files(item))
            elif is_compressed_file(item):
                compressed_files.append(item)
    except PermissionError as e:
        log(f"无法访问目录 {directory}: {e}", "ERROR")
    except Exception as e:
        log(f"遍历目录 {directory} 时出错: {e}", "ERROR")
    
    return compressed_files

def process_d_folder(d_dir):
    """处理D文件夹中的压缩包,包括嵌套的压缩包"""
    log(f"开始处理D文件夹: {d_dir}")
    
    # 使用循环确保所有层级的压缩包都被处理
    processed_count = 0
    max_iterations = 100  # 防止无限循环
    
    for iteration in range(max_iterations):
        log(f"第 {iteration + 1} 轮扫描压缩包...")
        
        # 查找所有压缩文件
        compressed_files = find_all_compressed_files(d_dir)
        
        if not compressed_files:
            log(f"第 {iteration + 1} 轮扫描未找到压缩包,处理完成")
            break
        
        log(f"第 {iteration + 1} 轮扫描找到 {len(compressed_files)} 个压缩包")
        
        # 处理找到的所有压缩文件
        for archive_path in compressed_files:
            # 创建以压缩包名字命名的文件夹
            folder_name = safe_path_name(archive_path.stem)
            output_dir = archive_path.parent / folder_name
            
            log(f"处理压缩包 {archive_path} -> {output_dir}")
            
            if extract_archive(archive_path, output_dir):
                # 解压成功后删除原压缩包
                try:
                    archive_path.unlink()
                    log(f"已删除压缩包: {archive_path}")
                    processed_count += 1
                except Exception as e:
                    log(f"删除压缩包失败: {archive_path}, 错误: {e}", "ERROR")
            else:
                log(f"跳过处理失败的压缩包: {archive_path}", "WARNING")
        
        log(f"第 {iteration + 1} 轮处理完成,处理了 {len(compressed_files)} 个压缩包")
    
    if iteration == max_iterations - 1:
        log(f"达到最大迭代次数 {max_iterations},可能仍有压缩包未处理", "WARNING")
    
    log(f"总共处理了 {processed_count} 个压缩包")

def main():
    """主函数"""
    # 设置控制台编码为UTF-8
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    
    # 定义C和D文件夹路径
    c_dir = Path("C")
    d_dir = Path("D")
    
    # 检查文件夹是否存在
    if not c_dir.exists() or not c_dir.is_dir():
        log("C文件夹不存在或不是有效目录", "ERROR")
        return
    
    if not d_dir.exists() or not d_dir.is_dir():
        log("D文件夹不存在或不是有效目录", "ERROR")
        return
    
    log("开始处理任务...")
    
    # 第一步和第二步: 处理C到D的复制和解压
    process_c_to_d(c_dir, d_dir)
    
    # 第三步: 处理D文件夹中的压缩包,包括嵌套的压缩包
    process_d_folder(d_dir)
    
    log("所有任务完成!")

if __name__ == "__main__":
    main()