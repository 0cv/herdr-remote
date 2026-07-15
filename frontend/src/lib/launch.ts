export function launchNamePart(value: unknown, fallback: string): string {
  const normalized = String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  return normalized.replace(/[^a-z0-9._-]+/g, '-').replace(/^[^a-z0-9]+|[._-]+$/g, '') || fallback;
}

export function suggestedLaunchName(cwd: string, profileId: string): string {
  const parts = String(cwd || '').replace(/[\\/]+$/, '').split(/[\\/]/).filter(Boolean);
  const directory = launchNamePart(parts.pop(), 'project');
  const agent = launchNamePart(profileId, 'agent');
  const suffix = `-${agent}`;
  return `${directory.slice(0, Math.max(1, 48 - suffix.length))}${suffix}`;
}
