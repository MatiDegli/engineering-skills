import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

import { createApp } from './server.ts';
import { openStore } from './store.ts';

const apiKey = process.env.BOOKING_API_KEY;
if (apiKey === undefined || apiKey.length < 16) {
  console.error('BOOKING_API_KEY must be set to a secret of at least 16 characters');
  process.exit(1);
}
const port = Number(process.env.PORT ?? 8080);
const databasePath = process.env.DATABASE_PATH ?? './data/booking.db';

mkdirSync(dirname(databasePath), { recursive: true });
const store = openStore(databasePath);
const server = createApp({ store, apiKey });
server.listen(port, () => {
  console.log(JSON.stringify({ message: 'listening', port }));
});

function shutdown(): void {
  server.close(() => {
    store.close();
    process.exit(0);
  });
}
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
