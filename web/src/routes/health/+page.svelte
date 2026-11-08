<script lang="ts">
	import { onMount } from 'svelte';

	type HealthResponse = {
		status: 'healthy' | 'unhealthy';
		timestamp: number;
		uptime_seconds: number;
		metrics: {
			cpu_usage_percent: number;
			memory_usage_percent: number;
			memory_available_gb: number;
		};
		checks: Record<string, string>;
	};

	type SearchAiHealthResponse = {
		status: 'healthy' | 'unhealthy';
		checked_at: number;
		providers: Record<string, string>;
	};

	function isRecord(value: unknown): value is Record<string, unknown> {
		return typeof value === 'object' && value !== null && !Array.isArray(value);
	}

	function isHealthResponse(value: unknown): value is HealthResponse {
		if (!isRecord(value) || !isRecord(value.metrics) || !isRecord(value.checks)) return false;

		return (
			(value.status === 'healthy' || value.status === 'unhealthy') &&
			typeof value.timestamp === 'number' &&
			Number.isFinite(value.timestamp) &&
			typeof value.uptime_seconds === 'number' &&
			Number.isFinite(value.uptime_seconds) &&
			typeof value.metrics.cpu_usage_percent === 'number' &&
			Number.isFinite(value.metrics.cpu_usage_percent) &&
			typeof value.metrics.memory_usage_percent === 'number' &&
			Number.isFinite(value.metrics.memory_usage_percent) &&
			typeof value.metrics.memory_available_gb === 'number' &&
			Number.isFinite(value.metrics.memory_available_gb) &&
			typeof value.checks.database === 'string' &&
			typeof value.checks.api_gemini === 'string' &&
			Object.values(value.checks).every((check) => typeof check === 'string')
		);
	}

	function isSearchAiHealthResponse(value: unknown): value is SearchAiHealthResponse {
		return (
			isRecord(value) &&
			(value.status === 'healthy' || value.status === 'unhealthy') &&
			typeof value.checked_at === 'number' &&
			Number.isFinite(value.checked_at) &&
			isRecord(value.providers) &&
			Object.values(value.providers).every((provider) => typeof provider === 'string')
		);
	}

	let healthData = $state<HealthResponse | null>(null);
	let searchAiData = $state<SearchAiHealthResponse | null>(null);
	let isLoading = $state(true);
	let isRefreshing = $state(false);
	let errorMessage = $state<string | null>(null);
	let searchAiError = $state<string | null>(null);
	let requestController: AbortController | undefined;

	let overallStatus = $derived.by(() => {
		if (!healthData || !searchAiData) return 'unavailable';
		const providerStatuses = [
			...Object.values(healthData.checks),
			...Object.values(searchAiData.providers)
		];
		return healthData.status === 'healthy' &&
			searchAiData.status === 'healthy' &&
			providerStatuses.every((provider) => provider === 'healthy' || provider === 'not_configured')
			? 'healthy'
			: 'unhealthy';
	});

	let humanReadableUptime = $derived.by(() => {
		const uptime = healthData?.uptime_seconds ?? 0;
		const days = Math.floor(uptime / 86_400);
		const hours = Math.floor((uptime % 86_400) / 3_600);
		const minutes = Math.floor((uptime % 3_600) / 60);
		const seconds = uptime % 60;

		const parts: string[] = [];
		if (days > 0) parts.push(`${days}d`);
		if (hours > 0) parts.push(`${hours}h`);
		if (minutes > 0) parts.push(`${minutes}m`);
		parts.push(`${seconds}s`);
		return parts.join(' ');
	});

	function progressWidth(value: number): string {
		return `${Math.min(100, Math.max(0, value))}%`;
	}

	async function fetchDiagnostics() {
		if (isRefreshing) return;
		isRefreshing = true;
		requestController = new AbortController();

		const fetchApiHealth = async () => {
			try {
				const response = await fetch('/api/health', {
					cache: 'no-store',
					headers: { Accept: 'application/json' },
					signal: requestController?.signal
				});
				const payload: unknown = await response.json();
				if (response.status !== 200 && response.status !== 503) {
					healthData = null;
					errorMessage = `The API health endpoint returned an unexpected response (${response.status}).`;
					return;
				}
				if (!isHealthResponse(payload)) {
					healthData = null;
					errorMessage =
						'The API is returning an outdated health-check response. Restart the API locally or redeploy the API service, then refresh this page.';
					return;
				}

				healthData = payload;
				errorMessage = null;
			} catch (error) {
				if (error instanceof DOMException && error.name === 'AbortError') return;
				errorMessage = 'Could not reach the API health endpoint. Check the API connection and retry.';
			}
		};

		const fetchSearchAiHealth = async () => {
			try {
				const response = await fetch('/health/search-ai', {
					cache: 'no-store',
					headers: { Accept: 'application/json' },
					signal: requestController?.signal
				});
				const payload: unknown = await response.json();
				if (
					(response.status !== 200 && response.status !== 503) ||
					!isSearchAiHealthResponse(payload)
				) {
					const detail =
						isRecord(payload) && typeof payload.error === 'string'
							? payload.error
							: `Unexpected response (${response.status}).`;
					searchAiError = detail;
					searchAiData = null;
					return;
				}

				searchAiData = payload;
				searchAiError = null;
			} catch (error) {
				if (error instanceof DOMException && error.name === 'AbortError') return;
				searchAiError = 'Could not reach the search AI health endpoint.';
				searchAiData = null;
			}
		};

		try {
			await Promise.all([fetchApiHealth(), fetchSearchAiHealth()]);
		} finally {
			isLoading = false;
			isRefreshing = false;
			requestController = undefined;
		}
	}

	onMount(() => {
		void fetchDiagnostics();
		const interval = setInterval(() => void fetchDiagnostics(), 10_000);
		return () => {
			clearInterval(interval);
			requestController?.abort();
		};
	});
</script>

<main class="container">
	<header class="dashboard-header">
		<div>
			<h1>Root-Cause Diagnostics</h1>
			<p>API readiness and runtime metrics</p>
		</div>
		<div class="header-actions">
			<span
				class="badge"
				class:pass={overallStatus === 'healthy'}
				class:fail={overallStatus === 'unhealthy' || overallStatus === 'unavailable'}
				aria-live="polite"
			>
				{isLoading ? 'CHECKING' : overallStatus.toUpperCase()}
			</span>
			<button class="refresh-button" onclick={fetchDiagnostics} disabled={isRefreshing}>
				{isRefreshing ? 'Refreshing…' : 'Refresh'}
			</button>
		</div>
	</header>

	{#if isLoading}
		<div class="card status-card" role="status">Checking API, database, and AI provider health…</div>
	{:else if !healthData}
		<div class="card status-card error-state" role="alert">
			<h2>Health data unavailable</h2>
			<p>{errorMessage ?? 'The API did not return health information.'}</p>
			<button class="refresh-button" onclick={fetchDiagnostics} disabled={isRefreshing}>
				Retry
			</button>
		</div>
	{:else}
		{#if errorMessage}
			<div class="card status-card error-state" role="alert">
				<p>{errorMessage} Showing the last successful health check.</p>
			</div>
		{/if}
		{#if searchAiError}
			<div class="card status-card error-state" role="alert">
				<p>{searchAiError} Search-provider status is unavailable.</p>
			</div>
		{/if}

		<section class="grid-vitals" aria-label="System metrics">
			<div class="card metric-card">
				<h2>System memory</h2>
				<div
					class="progress-bar-container"
					role="progressbar"
					aria-label="System memory usage"
					aria-valuemin="0"
					aria-valuemax="100"
					aria-valuenow={healthData.metrics.memory_usage_percent}
				>
					<div
						class="progress-bar"
						style:width={progressWidth(healthData.metrics.memory_usage_percent)}
					></div>
				</div>
				<p class="metric-label">
					<strong>{healthData.metrics.memory_usage_percent}% used</strong>
					({healthData.metrics.memory_available_gb} GB available)
				</p>
			</div>

			<div class="card metric-card">
				<h2>CPU usage</h2>
				<div
					class="progress-bar-container"
					role="progressbar"
					aria-label="CPU usage"
					aria-valuemin="0"
					aria-valuemax="100"
					aria-valuenow={healthData.metrics.cpu_usage_percent}
				>
					<div
						class="progress-bar cpu"
						style:width={progressWidth(healthData.metrics.cpu_usage_percent)}
					></div>
				</div>
				<p class="metric-label">
					<strong>{healthData.metrics.cpu_usage_percent}% utilization</strong>
				</p>
			</div>

			<div class="card metric-card">
				<h2>API uptime</h2>
				<p class="uptime-clock">{humanReadableUptime}</p>
				<p class="metric-label">Time since the API process started</p>
			</div>
		</section>

		<section class="dependency-section" aria-labelledby="dependency-heading">
			<h2 id="dependency-heading">Database and AI provider checks</h2>
			<div class="dependency-list">
				{#each Object.entries(healthData.checks) as [serviceName, serviceStatus] (serviceName)}
					<div class="dependency-row card">
						<span class="service-name">{serviceName.replaceAll('_', ' ')}</span>
						<span
							class="service-status"
							class:healthy={serviceStatus === 'healthy' || serviceStatus === 'not_configured'}
							class:unhealthy={serviceStatus === 'unhealthy' || serviceStatus === 'unreachable'}
							class:unknown={serviceStatus !== 'healthy' &&
								serviceStatus !== 'not_configured' &&
								serviceStatus !== 'unhealthy' &&
								serviceStatus !== 'unreachable'}
						>
							{serviceStatus.replaceAll('_', ' ').toUpperCase()}
						</span>
					</div>
				{/each}
				{#each Object.entries(searchAiData?.providers ?? { search_service: 'unavailable' }) as [providerName, providerStatus] (`search_${providerName}`)}
					<div class="dependency-row card">
						<span class="service-name">Search {providerName}</span>
						<span
							class="service-status"
							class:healthy={providerStatus === 'healthy' || providerStatus === 'not_configured'}
							class:unhealthy={providerStatus === 'unhealthy' || providerStatus === 'unavailable'}
							class:unknown={providerStatus !== 'healthy' &&
								providerStatus !== 'not_configured' &&
								providerStatus !== 'unhealthy' &&
								providerStatus !== 'unavailable'}
						>
							{providerStatus.replaceAll('_', ' ').toUpperCase()}
						</span>
					</div>
				{/each}
			</div>
			{#if searchAiData}
				<p class="checked-at">
					Search AI providers last tested {new Date(searchAiData.checked_at * 1000).toLocaleString()}.
					Generation probes are cached for five minutes.
				</p>
			{/if}
		</section>
	{/if}
</main>

<style>
	.container {
		max-width: 1100px;
		margin: 2rem auto;
		padding: 0 1.5rem;
		color: #f8fafc;
		font-family: system-ui, -apple-system, sans-serif;
	}
	.dashboard-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
		border-bottom: 1px solid #334155;
		padding-bottom: 1rem;
		margin-bottom: 2rem;
	}
	.dashboard-header h1,
	.metric-card h2 {
		margin: 0;
	}
	.dashboard-header p {
		margin: 0.4rem 0 0;
		color: #94a3b8;
	}
	.header-actions {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}
	.card {
		background-color: #1e293b;
		border: 1px solid #334155;
		border-radius: 0.75rem;
		padding: 1.5rem;
	}
	.grid-vitals {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
		gap: 1.5rem;
		margin-bottom: 3rem;
	}
	.metric-card h2,
	.dependency-section h2 {
		margin-bottom: 1rem;
		color: #cbd5e1;
		font-size: 1rem;
	}
	.progress-bar-container {
		background-color: #334155;
		border-radius: 9999px;
		height: 10px;
		overflow: hidden;
		margin-bottom: 0.75rem;
	}
	.progress-bar {
		background-color: #10b981;
		height: 100%;
		border-radius: 9999px;
		transition: width 0.4s ease;
	}
	.progress-bar.cpu {
		background-color: #3b82f6;
	}
	.metric-label {
		margin: 0;
		font-size: 0.9rem;
		color: #cbd5e1;
	}
	.uptime-clock {
		font-size: 1.75rem;
		font-weight: 700;
		color: #f59e0b;
		margin: 0 0 0.5rem;
	}
	.badge {
		padding: 0.5rem 1rem;
		border-radius: 9999px;
		font-weight: 700;
		font-size: 0.85rem;
	}
	.badge.pass {
		background-color: #065f46;
		color: #34d399;
	}
	.badge.fail,
	.error-state {
		background-color: #7f1d1d;
		color: #fecaca;
	}
	.status-card {
		margin-bottom: 1.5rem;
	}
	.status-card h2,
	.status-card p {
		margin-top: 0;
	}
	.status-card p:last-child {
		margin-bottom: 0;
	}
	.dependency-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.dependency-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
		padding: 1rem 1.5rem;
	}
	.service-name {
		font-weight: 600;
		text-transform: capitalize;
	}
	.service-status {
		font-weight: 700;
	}
	.service-status.healthy {
		color: #34d399;
	}
	.service-status.unhealthy {
		color: #f87171;
	}
	.service-status.unknown {
		color: #fbbf24;
	}
	.checked-at {
		margin-top: 1rem;
		color: #94a3b8;
		font-size: 0.85rem;
	}
	.refresh-button {
		border: 0;
		border-radius: 0.375rem;
		padding: 0.55rem 0.9rem;
		background-color: #2563eb;
		color: white;
		font: inherit;
		cursor: pointer;
	}
	.refresh-button:disabled {
		cursor: wait;
		opacity: 0.65;
	}
	@media (max-width: 600px) {
		.container {
			margin: 1rem auto;
			padding: 0 1rem;
		}
		.dashboard-header {
			align-items: flex-start;
			flex-direction: column;
		}
	}
</style>
