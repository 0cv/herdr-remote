<script lang="ts">
  import { onMount } from 'svelte';
  import AppSwitch from '$components/ui/AppSwitch.svelte';
  import Button from '$components/ui/Button.svelte';
  import Card from '$components/ui/Card.svelte';
  import {
    INTERFACE_SIZES,
    TERMINAL_HISTORY_OPTIONS,
    THEMES,
    type InterfaceSize,
    type TerminalHistoryLines,
    type Theme,
  } from '$lib/config';
  import {
    interfaceSize,
    setInterfaceSize,
    setShowAgentStatusLine,
    setTerminalHistoryLines,
    setTheme,
    showAgentStatusLine,
    terminalHistoryLines,
    theme,
  } from '$lib/preferences';
  import { relayVersionMeta } from '$lib/protocol';
  import {
    finishedNotificationsEnabled,
    notificationsSupported,
    pushPreferences,
    pushSupported,
    refreshPushPreferences,
    removeRelayPushSubscription,
    setFinishedNotifications,
    toggleNotifications,
  } from '$lib/push';
  import {
    deviceVerificationEnabled,
    deviceVerificationSupported,
    securityState,
    setDeviceVerificationRequired,
  } from '$lib/security';
  import { relayStore } from '$lib/store';
  import type { RelayConnectionView } from '$lib/types';

  const relays = relayStore.relayConfigs;
  const connections = relayStore.connections;
  const agents = relayStore.agents;
  const notificationBusy = relayStore.notificationBusy;

  onMount(refreshPushPreferences);

  let relayLabel = $state('');
  let relayUrl = $state('');
  let relayToken = $state('');
  let finished = $state(finishedNotificationsEnabled());
  let deviceLock = $state(deviceVerificationEnabled());

  const relayRows = $derived($relays.map((relay) => ({
    relay,
    connection: $connections.get(relay.id),
  })));
  const connectedCount = $derived([...$connections.values()].filter((connection) => connection.status === 'connected').length);
  const notification = $derived.by(() => notificationMeta(
    [...$connections.values()],
    $notificationBusy,
    $pushPreferences,
  ));

  function addRelay(event: SubmitEvent) {
    event.preventDefault();
    relayStore.addRelay({ label: relayLabel, url: relayUrl, token: relayToken });
    relayLabel = '';
    relayUrl = '';
    relayToken = '';
  }

  async function removeRelay(id: string) {
    await removeRelayPushSubscription(id);
    relayStore.removeRelay(id);
  }

  async function changeFinished(value: boolean) {
    finished = value;
    await setFinishedNotifications(value);
  }

  async function changeDeviceLock(value: boolean) {
    const changed = await setDeviceVerificationRequired(value);
    deviceLock = value && changed;
  }

  function notificationMeta(all: RelayConnectionView[], busy: boolean, preferences: { notificationsEnabled: boolean; optedIn: boolean }) {
    if (!notificationsSupported()) return { label: 'Notifications Unavailable', hint: 'This browser does not support page notifications.', disabled: true };
    if (Notification.permission === 'denied') return { label: 'Notifications Blocked', hint: 'Enable notifications in this browser site settings.', disabled: true };
    if (!preferences.notificationsEnabled) return { label: 'Enable Notifications', hint: pushSupported() ? 'Required before closed-app push notifications can work.' : 'Required before background tabs can notify.', disabled: false };
    if (!pushSupported()) return { label: 'Notifications Enabled', hint: 'Background tabs can notify while this browser keeps the page alive.', disabled: true };
    const connected = all.filter((connection) => connection.status === 'connected');
    const synced = connected.filter((connection) => connection.pushStatus === 'subscribed').length;
    const syncing = connected.some((connection) => ['syncing', 'sent'].includes(connection.pushStatus));
    if (busy || syncing) return { label: 'Syncing Push…', hint: 'Updating this browser subscription on connected relays.', disabled: true };
    if (!connected.length) return { label: 'Sync Push Subscription', hint: 'Connect a relay before syncing push notifications.', disabled: true };
    if (!preferences.optedIn) return { label: 'Enable Push Notifications', hint: 'Push is stopped for this browser; site permission remains allowed.', disabled: false };
    if (synced === connected.length) return { label: 'Stop Push Notifications', hint: `Push subscription synced with ${synced} relay${synced === 1 ? '' : 's'}.`, disabled: false };
    if (connected.some((connection) => connection.pushStatus === 'key-mismatch')) return { label: 'Sync Push Subscription', hint: 'A relay changed its push key. Sync again to refresh this device.', disabled: false };
    if (connected.some((connection) => connection.pushStatus === 'failed')) return { label: 'Sync Push Subscription', hint: 'Push subscription sync failed. Reconnect and try again.', disabled: false };
    return { label: 'Sync Push Subscription', hint: synced ? `Push synced with ${synced}/${connected.length} connected relays.` : 'Push can wake this app when an agent blocks.', disabled: false };
  }

  function pushStatusLabel(connection?: RelayConnectionView): string {
    if (!connection) return 'not connected';
    if (!pushSupported()) return 'unavailable';
    if (connection.pushStatus === 'subscribed') return 'synced';
    if (['syncing', 'sent'].includes(connection.pushStatus)) return 'syncing…';
    if (connection.pushStatus === 'browser-subscribed') return 'browser subscription found';
    if (connection.pushStatus === 'missing-config') return 'relay push unavailable';
    if (connection.pushStatus === 'key-mismatch') return 'key changed';
    if (connection.pushStatus === 'failed') return 'sync failed';
    if (connection.status === 'connecting') return 'waiting for relay…';
    if (connection.status === 'connected' && $pushPreferences.optedIn) return 'checking…';
    return 'not synced';
  }
</script>

<main class="page settings-page" aria-labelledby="settings-title">
  <h2 id="settings-title">Settings</h2>

  <Card>
    <h3>Relays</h3>
    <form class="form-stack" onsubmit={addRelay}>
      <label for="relay-label">Relay Name</label>
      <input id="relay-label" bind:value={relayLabel} placeholder="Fedora" />
      <label for="relay-url">Relay URL</label>
      <input id="relay-url" bind:value={relayUrl} type="url" required placeholder="wss://relay-fedora.example.com" />
      <label for="relay-token">Token</label>
      <input id="relay-token" bind:value={relayToken} type="password" placeholder="HERDR_RELAY_TOKEN" />
      <div class="form-actions">
        <Button type="submit">Add Relay</Button>
        <Button variant="secondary" onclick={() => relayStore.connectAll()}>Reconnect All</Button>
      </div>
    </form>
    <div class="relay-list">
      {#if !$relays.length}<p class="hint">No relays configured.</p>{/if}
      {#each relayRows as { relay, connection } (relay.id)}
        {@const connectionStatus = connection?.status || 'disconnected'}
        {@const version = relayVersionMeta(connection)}
        <article class="relay-row">
          <span
            class={`status-dot status-${connectionStatus === 'connected' ? 'success' : connectionStatus === 'connecting' ? 'warning' : 'danger'}`}
            role="img"
            aria-label={`${relay.label} relay ${connectionStatus}`}
          ></span>
          <div class="relay-info">
            <strong>{relay.label}</strong>
            <span>{relay.url}</span>
            <small>Push: {pushStatusLabel(connection)}</small>
            {#if version}<small class:warning={version.tone === 'warning'} title={version.title}>{version.label}</small>{/if}
          </div>
          <Button variant="danger" size="sm" aria-label={`Remove ${relay.label}`} onclick={() => removeRelay(relay.id)}>Remove</Button>
        </article>
      {/each}
    </div>
    <p class="hint">Use one relay URL per computer. Relay tokens remain in this browser’s local storage.</p>
  </Card>

  <Card>
    <h3>Appearance</h3>
    <fieldset class="choice-grid">
      <legend>Theme</legend>
      {#each THEMES as item (item)}
        <button class:active={$theme === item} type="button" aria-pressed={$theme === item} onclick={() => setTheme(item as Theme)}>{item}</button>
      {/each}
    </fieldset>
    <fieldset class="choice-grid compact-grid">
      <legend>Interface Size</legend>
      {#each INTERFACE_SIZES as item (item)}
        <button class:active={$interfaceSize === item} type="button" aria-pressed={$interfaceSize === item} onclick={() => setInterfaceSize(item as InterfaceSize)}>{item.charAt(0).toUpperCase() + item.slice(1)}</button>
      {/each}
    </fieldset>
    <fieldset class="choice-grid history-grid">
      <legend>Terminal History</legend>
      {#each TERMINAL_HISTORY_OPTIONS as item (item)}
        <button
          class:active={$terminalHistoryLines === item}
          type="button"
          aria-pressed={$terminalHistoryLines === item}
          onclick={() => setTerminalHistoryLines(item as TerminalHistoryLines)}
        >{item}</button>
      {/each}
    </fieldset>
    <p class="hint">Lines requested per terminal. 5,000–10,000 lines can use substantially more network data and rendering work.</p>
    <AppSwitch checked={$showAgentStatusLine} label="Show Agent Status Line" onchange={setShowAgentStatusLine} />
  </Card>

  <Card>
    <h3>Notifications</h3>
    <Button disabled={notification.disabled} onclick={() => toggleNotifications()}>{notification.label}</Button>
    <AppSwitch
      checked={finished}
      disabled={!pushSupported() || !$pushPreferences.optedIn || !connectedCount || $notificationBusy}
      label="Notify When Agents Finish"
      descriptionId="finished-notification-hint"
      onchange={changeFinished}
    />
    <p class="hint" id="finished-notification-hint">Optional. Blocked-agent notifications remain enabled whenever push is active.</p>
    <p class="hint" role="status">{notification.hint}</p>
  </Card>

  <Card>
    <h3>Security</h3>
    <AppSwitch checked={deviceLock} disabled={$securityState.busy} label="Require Fingerprint / Device Unlock" onchange={changeDeviceLock} />
    <p class="hint">{deviceVerificationSupported() ? $securityState.hint : 'Device verification needs HTTPS and a browser with WebAuthn support.'}</p>
  </Card>

  <Card>
    <h3>Status</h3>
    <p><span class={`status-dot status-${connectedCount ? 'success' : 'danger'}`}></span> {connectedCount}/{$relays.length} relays connected · {$agents.length} agents</p>
  </Card>
</main>
