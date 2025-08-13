// packages/ts_typsio/src/index.ts
import { io, Socket } from 'socket.io-client';

// 默认类型，将被用户生成的类型覆盖
export interface DefaultRPCMethods { [key: string]: (...args: any[]) => Promise<any>; }
export interface DefaultServerEvents { [key: string]: (...args: any[]) => void; }

export interface TypsioClientOptions {
  timeout?: number;
  rpcEventName?: string;
}

interface PendingCall {
  resolve: (value: any) => void;
  reject: (reason?: any) => void;
  timeoutTimer: NodeJS.Timeout;
}

/**
 * 创建一个类型安全的 Typsio 客户端。
 * @param socket 一个已存在的 socket.io-client 实例。
 * @param options Typsio 客户端的配置选项。
 * @returns 一个包含 remote (用于 RPC 调用) 和事件监听器 (on, off) 的客户端实例。
 */
export function createTypsioClient<
  ServerEvents extends DefaultServerEvents = DefaultServerEvents,
  ClientRPC extends DefaultRPCMethods = DefaultRPCMethods
>(socket: Socket, options: TypsioClientOptions = {}) {
  const {
    timeout = 10000,
    rpcEventName = 'rpc_call',
  } = options;
  const responseEventName = `${rpcEventName}_response`;

  let callCounter = 0;
  const pendingCalls = new Map<string, PendingCall>();

  socket.on(responseEventName, (data: { call_id: string; result?: any; error?: string }) => {
    const pending = pendingCalls.get(data.call_id);
    if (!pending) return;

    clearTimeout(pending.timeoutTimer);
    if (data.error) {
      pending.reject(new Error(data.error));
    } else {
      pending.resolve(data.result);
    }
    pendingCalls.delete(data.call_id);
  });
  
  socket.on('disconnect', () => {
    pendingCalls.forEach((call, id) => {
      clearTimeout(call.timeoutTimer);
      call.reject(new Error('Socket disconnected. RPC call aborted.'));
      pendingCalls.delete(id);
    });
  });

  const remote = new Proxy({}, {
    get: (target, prop) => {
      if (typeof prop !== 'string') return undefined;
      return (...args: any[]) => {
        return new Promise((resolve, reject) => {
          if (!socket.connected) {
            return reject(new Error("Socket is not connected."));
          }
          const callId = `${socket.id}-${callCounter++}`;

          const timeoutTimer = setTimeout(() => {
            pendingCalls.delete(callId);
            reject(new Error(`RPC call '${prop}' timed out after ${timeout}ms`));
          }, timeout);

          pendingCalls.set(callId, { resolve, reject, timeoutTimer });

          socket.emit(rpcEventName as any, {
            call_id: callId,
            function_name: prop,
            args,
          });
        });
      };
    },
  }) as ClientRPC;

  return {
    remote,
    on<E extends keyof ServerEvents>(event: E, listener: ServerEvents[E]): void {
      socket.on(event as string, listener);
    },
    off<E extends keyof ServerEvents>(event: E, listener?: ServerEvents[E]): void {
      socket.off(event as string, listener);
    },
    socket,
  };
}
