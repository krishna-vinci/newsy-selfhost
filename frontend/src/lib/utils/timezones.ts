export type TimezoneOption = {
	value: string;
	label: string;
	country?: string | null;
	region?: string | null;
	city?: string | null;
};

export async function fetchTimezoneOptions(): Promise<{
	defaultTimezone: string;
	timezones: TimezoneOption[];
}> {
	const response = await fetch('/api/timezones');
	if (!response.ok) {
		throw new Error('Failed to load timezone options');
	}

	const payload = await response.json();
	return {
		defaultTimezone: payload.default ?? 'Asia/Kolkata',
		timezones: Array.isArray(payload.timezones) ? payload.timezones : []
	};
}

export function guessBrowserTimezone(fallback = 'Asia/Kolkata'): string {
	try {
		const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
		return tz || fallback;
	} catch {
		return fallback;
	}
}
