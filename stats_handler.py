"""Provide wrapper functions for psutil module to request various system info"""

import psutil


def get_cpu_stats():
    """Gives a mean cpu load"""
    cpu_load = psutil.cpu_percent(percpu=False)
    return cpu_load


def get_mem_stats():
    """Gives a MEM usage stats"""
    mem_data = psutil.virtual_memory()
    # Convert reported values to Mb
    mem_stats = {
        "total": mem_data.total / 1024,
        "used": mem_data.used / 1024,
        "dimension": "Mb",
    }
    return mem_stats


def get_space_stats():
    """Gives a disk usage stats"""
    space_data = psutil.disk_usage("/")
    # Convert reported values to Mb
    space_stats = {
        "total": space_data.total / 1024,
        "used": space_data.used / 1024,
        "dimension": "Mb",
    }
    return space_stats
