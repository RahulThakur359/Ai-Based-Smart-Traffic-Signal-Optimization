/**
 * ITSC Traffic Signal Synchronization Helper (v3.0)
 * Connects directly to backend adaptive signal optimizer API.
 */

class SignalAPIClient {
    constructor() {
        this.roads = ['road1', 'road2', 'road3', 'road4'];
    }

    async syncStatus() {
        try {
            const res = await fetch('/api/signal/status');
            if (res.ok) {
                const data = await res.json();
                return data;
            }
        } catch (err) {
            console.debug("[SignalAPI] Sync skipped:", err);
        }
        return null;
    }
}

window.SignalAPIClient = SignalAPIClient;
