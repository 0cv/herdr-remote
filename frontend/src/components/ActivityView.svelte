<script lang="ts">
  import { onMount } from 'svelte';
  import { activityMatchesSearch, activityTone } from '$lib/activity';
  import { navigate } from '$lib/router';
  import { relayStore } from '$lib/store';
  import type { Activity } from '$lib/types';

  const activities = relayStore.activities;
  let search = $state('');
  const visible = $derived($activities.filter((activity) => activityMatchesSearch(activity, search.trim())));

  onMount(() => relayStore.requestActivities());

  function open(activity: Activity) {
    navigate({ view: 'activity_detail', key: activity.activity_key });
  }
</script>

<main class="page activity-page" aria-labelledby="activity-title">
  <h2 id="activity-title">Activity</h2>
  <label class="sr-only" for="activity-search">Search activity</label>
  <input id="activity-search" class="activity-search" bind:value={search} type="search" placeholder="Search activity…" />
  <div class="activity-list" aria-live="polite">
    {#if !$activities.length}
      <div class="empty-state">No activity yet.</div>
    {:else if !visible.length}
      <div class="empty-state">No matching activity.</div>
    {/if}
    {#each visible as activity (activity.activity_key)}
      <button type="button" class="activity-item" onclick={() => open(activity)}>
        <span class="activity-title">
          <span class={`status-dot status-${activityTone(activity.status)}`}></span>
          <strong>{activity.summary || activity.kind || 'Activity'}</strong>
          <time datetime={new Date(Number(activity.timestamp)).toISOString()}>{new Date(Number(activity.timestamp)).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}</time>
          <span class="activity-chevron" aria-hidden="true">›</span>
        </span>
        <span class="activity-meta">{[activity.relay_label, activity.project, activity.session, activity.agent, activity.status].filter(Boolean).join(' · ')}</span>
      </button>
    {/each}
  </div>
</main>
