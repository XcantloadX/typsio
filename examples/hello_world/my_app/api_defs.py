from pydantic import BaseModel, Field
from typsio import RPCRegistry
import datetime

# 1. 定义数据模型
class User(BaseModel):
    id: int
    name: str

class Message(BaseModel):
    text: str = Field(..., max_length=256)
    user: User

# 2. 创建 RPC 注册表
rpc_registry = RPCRegistry()

# 3. 注册 RPC 函数
@rpc_registry.register
async def get_user(user_id: int) -> User | None:
    if user_id == 1:
        return User(id=1, name="Alice")
    return None

@rpc_registry.register
def send_message(message: Message) -> bool:
    print(f"Received message from {message.user.name}: {message.text}")
    # 在真实应用中，这里会触发一个事件
    return True

# 4. 定义服务器到客户端的事件
class Notification(BaseModel):
    message: str
    timestamp: datetime.datetime

SERVER_EVENTS = {
    "newNotification": Notification
}
