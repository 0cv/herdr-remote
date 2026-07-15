import { render, screen, waitFor, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SettingsView from '$components/SettingsView.svelte';
import { PUSH_ENABLED_KEY, STATUS_LINE_KEY } from '$lib/config';
import { relayStore } from '$lib/store';

class MockWebSocket {
  static OPEN = 1;
  static instances: MockWebSocket[] = [];
  readyState = 0;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;

  constructor(readonly url: string) {
    MockWebSocket.instances.push(this);
  }

  send() {}
  close() { this.readyState = 3; }
  open() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.();
  }
  server(message: unknown) {
    this.onmessage?.({ data: JSON.stringify(message) });
  }
}

describe('settings relay status', () => {
  const serviceWorkerDescriptor = Object.getOwnPropertyDescriptor(navigator, 'serviceWorker');

  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.stubGlobal('Notification', { permission: 'granted', requestPermission: vi.fn().mockResolvedValue('granted') });
    vi.stubGlobal('PushManager', class {});
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: {} });
    relayStore.destroy();
    relayStore.relayConfigs.set([]);
    relayStore.addRelay({ label: 'Fedora', url: 'wss://fedora.example', token: 'secret' });
  });

  afterEach(() => {
    relayStore.destroy();
    relayStore.relayConfigs.set([]);
    vi.unstubAllGlobals();
    if (serviceWorkerDescriptor) Object.defineProperty(navigator, 'serviceWorker', serviceWorkerDescriptor);
    else Reflect.deleteProperty(navigator, 'serviceWorker');
  });

  it('updates connection and push state without remounting settings', async () => {
    render(SettingsView);
    const socket = MockWebSocket.instances[0];
    expect(screen.getByRole('img', { name: 'Fedora relay connecting' })).toBeInTheDocument();
    expect(screen.getByText('Push: waiting for relay…')).toBeInTheDocument();

    socket.open();
    relayStore.setPushStatus('fedora-wss-fedora-example', 'sent');
    await waitFor(() => expect(screen.getByRole('img', { name: 'Fedora relay connected' })).toBeInTheDocument());
    expect(screen.getByText('Push: syncing…')).toBeInTheDocument();

    socket.server({ type: 'push_subscribed', ok: true });
    await waitFor(() => expect(screen.getByText('Push: synced')).toBeInTheDocument());
  });

  it('applies interface size from the accessible settings group', async () => {
    const user = userEvent.setup();
    render(SettingsView);
    const sizes = within(screen.getByRole('group', { name: 'Interface Size' }));

    await user.click(sizes.getByRole('button', { name: 'Large' }));
    expect(document.documentElement.dataset.interfaceSize).toBe('large');
    expect(localStorage.getItem('herdr_terminal_font_size')).toBe('large');

    await user.click(sizes.getByRole('button', { name: 'Compact' }));
    expect(document.documentElement.dataset.interfaceSize).toBe('compact');

    const statusLine = screen.getByRole('switch', { name: 'Show Agent Status Line' }) as HTMLInputElement;
    const nextStatusLine = !statusLine.checked;
    await user.click(statusLine);
    expect(statusLine.checked).toBe(nextStatusLine);
    expect(localStorage.getItem(STATUS_LINE_KEY)).toBe(String(nextStatusLine));
  });

  it('enables the finished-agent switch immediately after push is enabled', async () => {
    const user = userEvent.setup();
    localStorage.setItem(PUSH_ENABLED_KEY, 'false');
    render(SettingsView);
    const socket = MockWebSocket.instances[0];
    socket.open();
    await waitFor(() => expect(screen.getByRole('img', { name: 'Fedora relay connected' })).toBeInTheDocument());
    socket.server({ type: 'push_config', protocol: 2, version: 'abc1234', vapid_public_key: 'test-key' });
    const finished = screen.getByRole('switch', { name: 'Notify When Agents Finish' });

    expect(finished).toHaveAttribute('type', 'checkbox');
    expect(finished).toBeDisabled();
    await user.click(await screen.findByRole('button', { name: 'Enable Push Notifications' }));

    await waitFor(() => expect(finished).toBeEnabled());
  });
});
