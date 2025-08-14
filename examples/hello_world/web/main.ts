import { api, on, socketInstance } from './api';

document.querySelector<HTMLDivElement>('#app')!.innerHTML = `
  <div>
    <h1>Typsio Demo</h1>
    <div id="logs"></div>
  </div>
`
const logs = document.querySelector<HTMLDivElement>('#logs')!;
const log = (msg: string) => {
  logs.innerHTML += `<p>${new Date().toLocaleTimeString()}: ${msg}</p>`;
};

socketInstance.on('connect', async () => {
  log('✅ Connected to server!');
  
  // Test RPC call 1
  try {
    const user = await api.get_user(1);
    log(`RPC get_user(1) success: ${JSON.stringify(user)}`);

    // Test RPC call 2
    if(user) {
      const success = await api.send_message({ text: 'Hello Typsio!', user });
      log(`RPC send_message success: ${success}`);
    }
  } catch (e) {
    log(`RPC Error: ${(e as Error).message}`);
  }
});

// Test event listener
on('newNotification', (payload) => {
  log(`EVENT newNotification received: ${payload.message} at ${payload.timestamp}`);
});
