import { io } from 'socket.io-client';
import { createTypsioClient } from 'typsio-client';
import type { RPCMethods, ServerToClientEvents } from './generated/api-types';

const socket = io('http://localhost:8000');
const client = createTypsioClient<ServerToClientEvents, RPCMethods>(socket);

export const api = client.remote;
export const on = client.on;
export const socketInstance = client.socket;
