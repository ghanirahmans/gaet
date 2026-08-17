import { GaetClient } from './client.js';

export * from './types.js';
export * from './client.js';

/**
 * Default singleton instance of GaetClient pointing to http://127.0.0.1:6161.
 */
export const gaet = new GaetClient();

export default GaetClient;
