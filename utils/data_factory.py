from faker import Faker

fake = Faker("zh_CN")


def _random_id():
    """生成一个随机 ID，用于关联同一组测试数据"""
    return fake.random_int(100, 9999)


def random_user():
    """生成随机用户字典（含 phone/nickname/password）"""
    uid = _random_id()
    return {
        "username": f"test_{fake.user_name()}_{uid}",
        "password": fake.password(length=8, special_chars=False),
        "realname": fake.name(),
        "email": f"test_user_{uid}@test.com",
        "phone": f"1{fake.random_int(30, 99)}{uid:04d}{fake.random_int(1000, 9999)}",
    }


def random_string(length: int = 10):
    """生成指定长度的随机字符串"""
    return fake.pystr(min_chars=length, max_chars=length)


def random_phone():
    """生成随机手机号：固定 11 位纯数字，符合国内接口校验规则"""
    return f"1{fake.random_int(30, 99)}{fake.random_int(10000000, 99999999)}"


def random_email():
    """生成随机邮箱"""
    return fake.email()
