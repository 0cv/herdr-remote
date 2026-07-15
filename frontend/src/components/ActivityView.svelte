<script lang="ts">
  import { onMount } from 'svelte';
  import { activityMatchesSearch, activityTone } from '$lib/activity';
  import { relayStore } from '$lib/store';

  const activities = relayStore.activities;
  let search = $state('');
  const visible = $derived($activities.filter((activity) => activityMatchesSearch(activity, search.trim())));

  onMount(() => relayStore.requestActivities());
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
      <article class="activity-item">
        <div class="activity-title">
          <span class={`status-dot status-${activityTone(activity.status)}`}></span>
          <strong>{activity.summary || activity.kind || 'Activity'}</strong>
          <time datetime={new Date(Number(activity.timestamp)).toISOString()}>{new Date(Number(activity.timestamp)).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}</time>
        </div>
        <p>{[activity.relay_label, activity.project, activity.agent, activity.status].filter(Boolean).join(' · ')}</p>
      </article>
    {/each}
  </div>
</main>
