import { io } from 'socket.io-client';
import { createTypsioClient, DefaultServerEvents } from 'typsio-client';
import type { RPCMethods } from './generated/api-types';

// NOTE: Actuall server path is '/socket.io' instead of '/'. Socket.io will append 'socket.io' to the url.
// If you want to use a different path, you can specify { path: '...' } in second argument.
const socket = io('/');
const client = createTypsioClient<DefaultServerEvents, RPCMethods>(socket);

export const api = client.remote;
export const on = client.on;
export const socketInstance = client.socket;
