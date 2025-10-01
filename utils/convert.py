from datetime import datetime, timedelta


def get_yyyyMMddHHmmss_with_offset(days=0, hours=0, minutes=0):
    """
    返回偏移后的时间，格式: yyyyMMddHHmmss
    days: 偏移天数，可正可负
    hours: 偏移小时
    minutes: 偏移分钟
    """
    target_time = datetime.now() + timedelta(days=days, hours=hours, minutes=minutes)
    return target_time.strftime("%Y%m%d%H%M%S")
